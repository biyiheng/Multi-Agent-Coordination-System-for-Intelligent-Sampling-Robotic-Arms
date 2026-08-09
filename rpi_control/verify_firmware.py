#!/usr/bin/env python3
"""
STM32 固件验证脚本 - 验证 STM32 控制板固件版本和通信协议

用法:
    python verify_firmware.py [PORT] [--baud BAUD] [--output REPORT.json]

示例:
    python verify_firmware.py COM4 --baud 115200 --output report.json
    python verify_firmware.py /dev/serial0 --baud 38400
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import serial
    import serial.tools.list_ports
    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False
    print("❌ pyserial 未安装。请运行: pip install pyserial")
    sys.exit(1)


# =============================================================================
# 伺服协议测试用例
# =============================================================================

# 13 个伺服协议测试用例
SERVO_TEST_CASES = [
    # (test_name, command_bytes, expected_response_pattern, timeout_s)
    ("单舵机移动", b"#000P1500T1000!", ["OK", "ECHO_ACK"], 0.5),
    ("多舵机移动", b"{#000P1500T1000!#001P1500T1000!#002P1500T1000!}", ["OK", "ECHO_ACK"], 0.5),
    ("停止所有舵机", b"$DST!", ["OK", "ECHO_ACK"], 0.5),
    ("停止单舵机", b"$DST:0!", ["OK", "ECHO_ACK"], 0.5),
    ("软件复位", b"$RST!", ["OK", "ECHO_ACK"], 1.0),
    ("动作组播放", b"$DGT:0-0,1!", ["OK", "ECHO_ACK"], 0.5),
    ("系统信息查询", b"#SYS:INFO!", ["FW:", "OK", "ECHO_ACK"], 0.5),
    ("舵机状态查询", b"#ARM:STATUS!", ["POS:", "OK", "ECHO_ACK"], 0.5),
    ("传感器读取", b"#SENSOR:TEMP!", ["OK", "ECHO_ACK"], 0.5),
    ("紧急停止", b"#ARM:ESTOP!", ["OK", "ECHO_ACK"], 0.5),
    ("回原位", b"#ARM:ORIGIN!", ["OK", "ECHO_ACK"], 0.5),
    ("舵机极限位置", b"#000P0500T1000!", ["OK", "ECHO_ACK"], 0.5),
    ("舵机最大位置", b"#000P2500T1000!", ["OK", "ECHO_ACK"], 0.5),
]


def list_available_ports() -> List[Dict[str, Any]]:
    """列出所有可用串口"""
    ports = serial.tools.list_ports.comports()
    result = []
    for port in ports:
        info = {
            "device": port.device,
            "description": port.description,
            "hwid": port.hwid,
        }
        if port.vid is not None:
            info["vid"] = f"0x{port.vid:04X}"
            info["pid"] = f"0x{port.pid:04X}"
        result.append(info)
    return result


def probe_firmware(port: str, baudrate: int = 115200, timeout: float = 0.5) -> Dict[str, Any]:
    """探测 STM32 固件信息"""
    result: Dict[str, Any] = {
        "port": port,
        "baudrate": baudrate,
        "connected": False,
        "firmware_type": "unknown",
        "firmware_version": "unknown",
        "protocol": "unknown",
        "tests": [],
    }

    try:
        ser = serial.Serial(port, baudrate, timeout=timeout, write_timeout=timeout)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        result["connected"] = True

        # 等待自发数据
        time.sleep(0.3)
        if ser.in_waiting > 0:
            data = ser.read(min(ser.in_waiting, 256))
            result["spontaneous_data"] = data.decode("ascii", errors="replace")

        # 探测协议类型
        # 测试 YH-K32 协议
        ser.write(b"#SYS:INFO!")
        ser.flush()
        time.sleep(0.2)
        response = b""
        if ser.in_waiting > 0:
            response = ser.read(min(ser.in_waiting, 256))
        response_str = response.decode("ascii", errors="replace")

        if "FW:" in response_str or "YHK32" in response_str.upper():
            result["protocol"] = "YH-K32 (custom)"
            result["firmware_type"] = "YH-K32 compatible"
            # Try to extract version
            if "FW:" in response_str:
                fw_start = response_str.index("FW:") + 3
                fw_end = response_str.find("!", fw_start) if "!" in response_str[fw_start:] else len(response_str)
                result["firmware_version"] = response_str[fw_start:fw_end].strip()
        elif "OK" in response_str or "ECHO_ACK" in response_str:
            result["protocol"] = "Custom ASCII"
            result["firmware_type"] = "Custom firmware"
        elif len(response) > 0:
            result["protocol"] = "Unknown (raw response)"
            result["firmware_type"] = "Unknown"
        else:
            # Try YH-K32 factory protocol
            ser.write(b"#000P1500T1!")
            ser.flush()
            time.sleep(0.2)
            if ser.in_waiting > 0:
                response2 = ser.read(min(ser.in_waiting, 256))
                if response2:
                    result["protocol"] = "YH-K32 (factory)"
                    result["firmware_type"] = "YH-K32 factory"

        ser.close()

    except serial.SerialException as e:
        result["error"] = f"串口打开失败: {e}"
    except Exception as e:
        result["error"] = f"探测失败: {e}"

    return result


def run_servo_tests(port: str, baudrate: int = 115200) -> List[Dict[str, Any]]:
    """运行所有伺服协议测试"""
    results = []

    try:
        ser = serial.Serial(port, baudrate, timeout=0.5, write_timeout=0.5)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        for test_name, cmd, expected_patterns, timeout_s in SERVO_TEST_CASES:
            test_result = {
                "name": test_name,
                "command": cmd.decode("ascii", errors="replace"),
                "passed": False,
                "response": "",
                "duration_ms": 0,
            }

            try:
                ser.reset_input_buffer()
                start = time.time()
                ser.write(cmd)
                ser.flush()
                time.sleep(0.05)

                response = b""
                deadline = time.time() + timeout_s
                while time.time() < deadline:
                    if ser.in_waiting > 0:
                        byte = ser.read(1)
                        if byte == b"!":
                            if response:
                                break
                        else:
                            response += byte
                    else:
                        time.sleep(0.001)

                test_result["duration_ms"] = round((time.time() - start) * 1000, 1)
                response_str = response.decode("ascii", errors="replace")
                test_result["response"] = response_str

                # 检查是否符合预期
                for pattern in expected_patterns:
                    if pattern in response_str:
                        test_result["passed"] = True
                        break

                # 如果无响应但有回声确认，也算通过
                if not test_result["passed"] and cmd.decode("ascii", errors="replace").rstrip("!") in response_str:
                    test_result["passed"] = True
                    test_result["response"] += " (echo acknowledged)"

            except Exception as e:
                test_result["error"] = str(e)

            results.append(test_result)

        ser.close()

    except serial.SerialException as e:
        results.append({
            "name": "连接失败",
            "passed": False,
            "error": f"串口打开失败: {e}",
        })

    return results


def main() -> int:
    """主入口"""
    parser = argparse.ArgumentParser(
        description="STM32 固件验证脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python verify_firmware.py COM4 --baud 38400 --output report.json
  python verify_firmware.py /dev/serial0 --baud 115200
        """,
    )
    parser.add_argument("port", nargs="?", default=None, help="串口端口 (如 COM4, /dev/serial0)")
    parser.add_argument("--baud", type=int, default=115200, help="波特率 (默认: 115200)")
    parser.add_argument("--output", "-o", type=str, default=None, help="输出 JSON 报告文件路径")
    parser.add_argument("--list-ports", "-l", action="store_true", help="列出所有可用串口")
    args = parser.parse_args()

    # 列出可用串口
    if args.list_ports:
        ports = list_available_ports()
        print("=" * 60)
        print("可用串口列表:")
        print("=" * 60)
        if not ports:
            print("  ❌ 未检测到任何串口设备!")
            print("  请确认:")
            print("  1. STM32 已通过 USB 转串口连接")
            print("  2. 驱动程序已安装 (CH340/CP2102/ST-Link VCP)")
        else:
            for p in ports:
                vid_pid = f" ({p.get('vid', '')}:{p.get('pid', '')})" if "vid" in p else ""
                print(f"  {p['device']} - {p['description']}{vid_pid}")
        return 0 if ports else 1

    # 自动检测端口
    if args.port is None:
        ports = list_available_ports()
        if not ports:
            print("❌ 未检测到任何串口设备!")
            return 1
        if len(ports) == 1:
            args.port = ports[0]["device"]
            print(f"自动选择端口: {args.port}")
        else:
            print("检测到多个串口设备:")
            for i, p in enumerate(ports):
                print(f"  [{i}] {p['device']} - {p['description']}")
            print("\n请指定端口: python verify_firmware.py <端口名>")
            return 1

    print("=" * 60)
    print("STM32 固件验证")
    print("=" * 60)
    print(f"端口: {args.port}")
    print(f"波特率: {args.baud}")
    print()

    # 探测固件
    print("[1/2] 探测固件信息...")
    fw_info = probe_firmware(args.port, args.baud)
    if fw_info.get("connected"):
        print(f"  ✅ 连接成功")
        print(f"  📋 协议类型: {fw_info.get('protocol', 'unknown')}")
        print(f"  📋 固件类型: {fw_info.get('firmware_type', 'unknown')}")
        if fw_info.get("firmware_version") and fw_info["firmware_version"] != "unknown":
            print(f"  📋 固件版本: {fw_info['firmware_version']}")
    else:
        print(f"  ❌ 连接失败: {fw_info.get('error', '未知错误')}")
        return 1

    # 运行伺服测试
    print(f"\n[2/2] 运行伺服协议测试 ({len(SERVO_TEST_CASES)} 项)...")
    test_results = run_servo_tests(args.port, args.baud)
    passed = sum(1 for t in test_results if t.get("passed"))
    failed = len(test_results) - passed

    for t in test_results:
        status = "✅" if t.get("passed") else "❌"
        duration = f" ({t.get('duration_ms', 0)}ms)" if t.get("duration_ms") else ""
        print(f"  {status} {t['name']}{duration}")
        if t.get("error"):
            print(f"      错误: {t['error']}")

    # 汇总
    print(f"\n{'=' * 60}")
    print(f"测试结果: {passed}/{len(test_results)} 通过, {failed} 失败")
    print(f"{'=' * 60}")

    # 构建完整报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "port": args.port,
        "baudrate": args.baud,
        "firmware_info": fw_info,
        "servo_tests": {
            "total": len(test_results),
            "passed": passed,
            "failed": failed,
            "details": test_results,
        },
        "overall_pass": passed == len(test_results),
    }

    # 保存报告
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n报告已保存到: {output_path}")

    return 0 if passed == len(test_results) else 1


if __name__ == "__main__":
    sys.exit(main())