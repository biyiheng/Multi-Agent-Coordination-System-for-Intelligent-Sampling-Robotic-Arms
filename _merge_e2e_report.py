"""
端到端性能对比报告生成器.

合并两条链路的日志/输出:
  1. C# 硬件链路仿真 (hardware_debug.exe chain) -> 结构化 JSON 事件
  2. C# 板卡调试 (hardware_debug.exe board)     -> 结构化 JSON 事件
  2.1 C# 单元测试 (hardware_debug.exe test)     -> [PASS]/[FAIL] 文本
  3. RPi 坐标链路仿真 (_sim_coord_chain.py)       -> 文本指标
  4. RPi 端到端抓取仿真 (_sim_grasp.py)           -> 文本指标

输出:
  - rpi_control/reports/e2e_performance_report.md  (最终端到端对比报告)
  - e2e_merged_log.json                            (合并后的结构化日志/指标)

用法:  python _merge_e2e_report.py
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CS_EXE = ROOT / "hardware_debug_cs" / "HardwareDebug" / "bin" / "Release" / "net8.0" / "hardware_debug.exe"
RPI_REPORTS = ROOT / "rpi_control" / "reports"
REPORT_MD = RPI_REPORTS / "e2e_performance_report.md"
MERGED_JSON = ROOT / "e2e_merged_log.json"


def run(cmd: list, cwd: Path) -> tuple[str, float]:
    """执行命令, 返回 (合并输出, 耗时秒)."""
    t0 = time.perf_counter()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd))
        out = (r.stdout or "") + (r.stderr or "")
    except FileNotFoundError:
        out = f"ERROR: 命令未找到: {cmd}"
    dt = time.perf_counter() - t0
    return out, dt


def parse_csharp_logs(text: str) -> list[dict]:
    """从 C# 输出中逐行解析 JSON 日志事件."""
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def parse_coord_chain(text: str) -> dict:
    """解析 _sim_coord_chain.py 关键指标."""
    m: dict = {}
    for line in text.splitlines():
        if "AprilTag 路径" in line:
            m["path_a"] = True
        if "误差" in line and "mm" in line and "PASS" in line:
            m["apriltag_err_mm"] = float(re_first(r"([\d.]+)\s*mm", line))
        if "旧链路(像素->mm)" in line:
            m["old_err_mm"] = float(re_first(r"误差=([\d.]+)\s*mm", line))
        if "新链路(手眼标定)" in line and "误差=" in line:
            m["new_err_mm"] = float(re_first(r"误差=([\d.]+)\s*mm", line))
        if "误差降低" in line:
            m["improvement_x"] = re_first(r"误差降低\s*([\d.]+|\S+)x", line)
        if "采样点误差" in line:
            m["sampling_err_mm"] = float(re_first(r"([\d.]+)\s*mm", line))
        if line.startswith("汇总"):
            m["summary"] = line
    return m


def parse_grasp_sim(text: str) -> dict:
    """解析 _sim_grasp.py 关键指标."""
    m: dict = {}
    for line in text.splitlines():
        if "定位误差:" in line:
            m["localization_err_mm"] = float(re_first(r"([\d.]+)\s*mm", line))
        if "搬运位移:" in line:
            m["travel_mm"] = float(re_first(r"([\d.]+)\s*mm", line))
        if "PnP 置信度" in line or "置信度:" in line:
            m["pnp_confidence"] = re_first(r"([\d.]+)", line)
        if "抓取流程完成" in line:
            m["grasp_ok"] = True
    return m


def re_first(pat: str, s: str) -> str | None:
    import re
    m = re.search(pat, s)
    return m.group(1) if m else None


def csharp_event_summary(events: list[dict], keys: list[str]) -> list[dict]:
    """按事件名过滤并整理 C# 事件."""
    return [e for e in events if e.get("event") in keys]


def parse_csharp_tests(text: str) -> dict:
    """解析 C# 单测输出 ([PASS]/[FAIL] 行 + 汇总行)."""
    cases: list[dict] = []
    summary = {"passed": 0, "failed": 0}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[PASS]") or line.startswith("[FAIL]"):
            ok = line.startswith("[PASS]")
            name = line.split("] ", 1)[1] if "] " in line else line
            cases.append({"ok": ok, "name": name})
        m = re.search(r"通过 (\d+), 失败 (\d+)", line)
        if m:
            summary = {"passed": int(m.group(1)), "failed": int(m.group(2))}
    return {"cases": cases, "summary": summary,
            "ok": summary["failed"] == 0}


def main() -> int:
    print("=" * 72)
    print("端到端性能对比报告生成器")
    print("=" * 72)

    merged: dict = {"source": "end_to_end", "phases": []}

    # ---- 1. C# 多硬件链路 ----
    cs_out, cs_t = run([str(CS_EXE), "chain"], ROOT)
    cs_events = parse_csharp_logs(cs_out)
    merged["phases"].append({
        "name": "C# multi-hardware chain",
        "duration_s": round(cs_t, 3),
        "events": cs_events,
    })
    print(f"[1] C# 链路: {len(cs_events)} 事件, {cs_t:.3f}s")

    # ---- 2. C# 板卡调试 ----
    dbg_out, dbg_t = run([str(CS_EXE), "board"], ROOT)
    dbg_events = parse_csharp_logs(dbg_out)
    merged["phases"].append({
        "name": "C# board debug",
        "duration_s": round(dbg_t, 3),
        "events": dbg_events,
    })
    print(f"[2] C# 板卡调试: {len(dbg_events)} 事件, {dbg_t:.3f}s")

    # ---- 2.1 C# 单元测试 (坐标变换 + 工作空间) ----
    cs_test_out, cs_test_t = run([str(CS_EXE), "test"], ROOT)
    cs_tests = parse_csharp_tests(cs_test_out)
    merged["phases"].append({
        "name": "C# unit tests",
        "duration_s": round(cs_test_t, 3),
        "metrics": cs_tests,
    })
    print(f"[2.1] C# 单测: {cs_tests['summary']['passed']} 通过 / "
          f"{cs_tests['summary']['failed']} 失败, {cs_test_t:.3f}s")

    # ---- 3. RPi 坐标链路 ----
    py_chain_out, py_chain_t = run([sys.executable, "_sim_coord_chain.py"], ROOT)
    coord = parse_coord_chain(py_chain_out)
    merged["phases"].append({
        "name": "RPi coord chain",
        "duration_s": round(py_chain_t, 3),
        "metrics": coord,
    })
    print(f"[3] RPi 坐标链路: {py_chain_t:.3f}s")

    # ---- 4. RPi 端到端抓取 ----
    py_grasp_out, py_grasp_t = run([sys.executable, "_sim_grasp.py"], ROOT)
    grasp = parse_grasp_sim(py_grasp_out)
    merged["phases"].append({
        "name": "RPi end-to-end grasp",
        "duration_s": round(py_grasp_t, 3),
        "metrics": grasp,
    })
    print(f"[4] RPi 抓取仿真: {py_grasp_t:.3f}s")

    # 提取 C# 关键事件用于报告
    ws_check = csharp_event_summary(cs_events, ["chain_workspace_check"])
    robot_pose = csharp_event_summary(cs_events, ["chain_robot_pose"])
    camera_pose = csharp_event_summary(cs_events, ["chain_camera_pose"])
    board_self = csharp_event_summary(dbg_events, ["board_selftest"])
    uart_echo = csharp_event_summary(dbg_events, ["uart_echo"])

    # ---- 生成 Markdown ----
    rows: list[str] = []
    def line(s: str = ""):
        rows.append(s)
    def md_row(*cells):
        rows.append("| " + " | ".join(str(c) for c in cells) + " |")

    line("# 端到端性能对比报告（RPi + C# 双链路）")
    line()
    line(f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    line("> 链路：C# 硬件链路 / 板卡调试  +  RPi 坐标链路 / 端到端抓取")
    line()

    line("## 1. 运行耗时")
    md_row("阶段", "耗时(s)")
    md_row("------", "--------")
    for ph in merged["phases"]:
        md_row(ph["name"], ph["duration_s"])
    line()

    line("## 2. C# 多硬件链路（RPi→STM32→OpenMV）")
    if camera_pose:
        p = camera_pose[0]["payload"]
        md_row("相机系位姿", f"({p['x']}, {p['y']}, {p['z']}) mm")
    if robot_pose:
        p = robot_pose[0]["payload"]
        md_row("机器人系位姿", f"({p['x']}, {p['y']}, {p['z']}) mm")
    if ws_check:
        p = ws_check[0]["payload"]
        md_row("工作空间校验", f"bounds=`{p['bounds']}` target={p['target']} inside=`{p['inside']}`")
    line()

    line("## 3. C# 板卡调试")
    if board_self:
        md_row("时钟自检", f"rcc_ok=`{board_self[0]['payload']['rcc_ok']}`")
    if uart_echo:
        md_row("UART 回环", f"pass=`{uart_echo[0]['payload']['pass']}`")
    line()

    line("## 3.1 C# 单元测试（坐标变换 + 工作空间）")
    s = cs_tests["summary"]
    md_row("结果", f"{s['passed']} 通过 / {s['failed']} 失败 → {'✅' if cs_tests['ok'] else '❌'}")
    for c in cs_tests["cases"]:
        md_row(("✅" if c["ok"] else "❌") + " " + c["name"], "")
    line()

    line("## 4. RPi 坐标链路（坐标系同步）")
    if "apriltag_err_mm" in coord:
        md_row("AprilTag 定位误差", f"{coord['apriltag_err_mm']} mm")
    if "old_err_mm" in coord and "new_err_mm" in coord:
        md_row("Blob 旧链路误差(像素->mm)", f"{coord['old_err_mm']} mm")
        md_row("Blob 新链路误差(手眼标定)", f"{coord['new_err_mm']} mm")
    if "improvement_x" in coord:
        md_row("误差改善", f"{coord['improvement_x']}x")
    if "sampling_err_mm" in coord:
        md_row("采样点消费误差", f"{coord['sampling_err_mm']} mm")
    if "summary" in coord:
        md_row("汇总", coord["summary"])
    line()

    line("## 5. RPi 端到端抓取")
    if "localization_err_mm" in grasp:
        md_row("视觉定位误差", f"{grasp['localization_err_mm']} mm")
    if "travel_mm" in grasp:
        md_row("搬运位移", f"{grasp['travel_mm']} mm")
    if "pnp_confidence" in grasp:
        md_row("PnP 置信度", grasp["pnp_confidence"])
    if "grasp_ok" in grasp:
        md_row("抓取结果", "✅ 流程完成")
    line()

    line("## 6. 汇总")
    md_row("验证项", "结果")
    md_row("--------", "------")
    ws_ok = ws_check and ws_check[0]["payload"].get("inside") is True
    md_row("C# 构建/运行", "✅" if cs_events else "❌")
    md_row("C# 工作空间对齐", "✅ 目标在工作空间内" if ws_ok else "❌ 越界")
    md_row("C# 单元测试", f"✅ {cs_tests['summary']['passed']} 通过" if cs_tests["ok"] else "❌ 有失败")
    coord_ok = coord.get("apriltag_err_mm", 9e9) < 0.01
    md_row("RPi 坐标同步", "✅ 误差≈0" if coord_ok else "❌")
    grasp_ok = bool(grasp.get("grasp_ok"))
    md_row("端到端抓取", "✅ 成功" if grasp_ok else "❌")
    line()

    md_text = "\n".join(rows)
    REPORT_MD.write_text(md_text, encoding="utf-8")
    MERGED_JSON.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n报告已生成: {REPORT_MD}")
    print(f"合并日志已生成: {MERGED_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
