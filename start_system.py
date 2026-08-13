#!/usr/bin/env python3
"""
系统启动脚本: 启动智能采样机械臂系统。

集成修复后的视觉位姿估计 (pose_estimator) 与力控抓取 (force_control) 到主控制流程。

用法:
    python start_system.py                # 完整启动 (初始化 + Web 服务 + 主循环)
    python start_system.py --demo         # 初始化后立即执行一次视觉引导抓取并退出
    python start_system.py --sim          # 强制仿真模式 (默认)
    python start_system.py --real         # 强制真实硬件模式 (需已连接 STM32/机械臂)
    python start_system.py --grasp        # 与 --demo 相同

示例:
    # 无硬件, 验证完整抓取流程
    python start_system.py --demo --sim

    # 真实机械臂 + Web 服务
    python start_system.py --real
"""

import argparse
import asyncio
import os
import sys

from rpi_control import main as app


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="start_system",
        description="智能采样机械臂系统启动脚本",
    )
    p.add_argument("--demo", "--grasp", action="store_true", dest="demo",
                   help="初始化后执行一次视觉引导抓取并退出")
    p.add_argument("--sim", action="store_true", help="强制仿真模式")
    p.add_argument("--real", action="store_true", help="强制真实硬件模式")
    return p


async def _demo(args) -> int:
    """初始化系统并执行一次完整抓取循环. 返回退出码."""
    ok = await app.initialize_system()
    if not ok:
        print("[start_system] 系统初始化失败")
        return 1
    if app.state.pipeline is None:
        print("[start_system] 抓取流水线未初始化 (grasp.enabled=false?)")
        await app.shutdown_system()
        return 1

    print("=" * 60)
    print("  视觉引导抓取演示 (Grasp Demo)")
    print("=" * 60)
    result = await app._run_grasp()
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))

    await app.shutdown_system()
    return 0 if result.get("status") == "ok" else 1


def _server(args) -> int:
    """完整启动: 初始化 + Web 服务 + 主循环 (同步, app.main 内部已用 asyncio.run)."""
    return app.main()


def main() -> int:
    args = _build_parser().parse_args()

    if args.sim and args.real:
        print("--sim 与 --real 不能同时指定")
        return 2

    # 通过环境变量覆盖运行模式 (在 initialize_system 构建流水线前生效)
    if args.real:
        os.environ["GRASP_MODE"] = "real"
    elif args.sim:
        os.environ["GRASP_MODE"] = "simulation"

    if args.demo:
        return asyncio.run(_demo(args))
    return _server(args)


if __name__ == "__main__":
    sys.exit(main())
