#!/usr/bin/env python3
"""
STM32硬件诊断脚本 - 探测STM32当前固件类型和通信能力
"""

import serial
import serial.tools.list_ports
import time
import sys

def list_ports():
    """列出所有可用串口"""
    ports = serial.tools.list_ports.comports()
    print("=" * 60)
    print("可用串口列表:")
    for port in ports:
        print(f"  {port.device} - {port.description} (VID:{port.vid:04X} PID:{port.pid:04X})" if port.vid else f"  {port.device} - {port.description}")
    return ports

def probe_port(port_name, baudrate=115200):
    """探测指定串口，尝试不同方式与STM32通信"""
    print(f"\n{'=' * 60}")
    print(f"探测端口: {port_name} @ {baudrate} baud")
    print("=" * 60)
    
    try:
        ser = serial.Serial(port_name, baudrate, timeout=0.5, write_timeout=0.5)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        print(f"✓ 端口打开成功")
        
        # 测试1: 等待是否有数据自发输出
        print(f"\n[测试1] 等待自发数据 (2秒)...")
        time.sleep(0.5)
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            print(f"  收到自发数据 ({len(data)} bytes): {data[:100]}")
        else:
            print(f"  无自发数据")
        
        # 测试2: 发送 SYS:INFO 命令
        print(f"\n[测试2] 发送 #SYS:INFO!")
        ser.reset_input_buffer()
        ser.write(b"#SYS:INFO!")
        ser.flush()
        time.sleep(0.3)
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            print(f"  收到响应 ({len(data)} bytes): {data}")
        else:
            print(f"  无响应")
        
        # 测试3: 发送简单字符测试回声
        print(f"\n[测试3] 回声测试 - 发送 'AT\r\n'")
        ser.reset_input_buffer()
        ser.write(b"AT\r\n")
        ser.flush()
        time.sleep(0.3)
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            print(f"  收到响应 ({len(data)} bytes): {data}")
        else:
            print(f"  无响应")
        
        # 测试4: 尝试不同波特率
        for test_baud in [9600, 38400, 57600, 115200, 230400, 921600]:
            if test_baud == baudrate:
                continue
            print(f"\n[测试4] 尝试波特率 {test_baud}...")
            try:
                ser.close()
                ser = serial.Serial(port_name, test_baud, timeout=0.3)
                ser.reset_input_buffer()
                time.sleep(0.2)
                if ser.in_waiting > 0:
                    data = ser.read(min(ser.in_waiting, 100))
                    print(f"  收到数据 ({len(data)} bytes): {data}")
                    # 恢复原始波特率
                    ser.close()
                    ser = serial.Serial(port_name, baudrate, timeout=0.5)
                    break
                else:
                    print(f"  无数据")
            except Exception as e:
                print(f"  错误: {e}")
        
        # 恢复原始波特率
        try:
            ser.close()
            ser = serial.Serial(port_name, baudrate, timeout=0.5)
        except:
            pass
        
        # 测试5: 发送 STM32 常见 AT 命令
        print(f"\n[测试5] 发送 STM32 常见命令...")
        test_cmds = [
            b"#SYS:RESET!",
            b"#ARM:STATUS!",
            b"#SENSOR:ALL!",
            b"AT\r\n",
            b"AT+UART?\r\n",
        ]
        for cmd in test_cmds:
            ser.reset_input_buffer()
            ser.write(cmd)
            ser.flush()
            time.sleep(0.2)
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                print(f"  命令 {cmd}: 响应 ({len(data)} bytes): {data[:100]}")
            else:
                print(f"  命令 {cmd}: 无响应")
        
        ser.close()
        print(f"\n✓ 诊断完成")
        
    except serial.SerialException as e:
        print(f"✗ 无法打开端口: {e}")
    except Exception as e:
        print(f"✗ 错误: {e}")

if __name__ == "__main__":
    ports = list_ports()
    
    if not ports:
        print("\n✗ 未检测到任何串口设备!")
        print("  请确认:")
        print("  1. STM32已通过USB转串口连接")
        print("  2. 驱动程序已安装 (CH340/CP2102/ST-Link VCP)")
        sys.exit(1)
    
    # 优先探测 COM4
    target = "COM4"
    if target in [p.device for p in ports]:
        probe_port(target)
    else:
        # 探测所有端口
        for port in ports:
            probe_port(port.device)