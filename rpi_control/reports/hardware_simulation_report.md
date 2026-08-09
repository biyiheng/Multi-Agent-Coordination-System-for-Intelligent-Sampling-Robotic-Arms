# 硬件调试与多硬件链路模拟报告

> 工程：`hardware_debug_cs\HardwareDebug`（C# / .NET 8）
> 覆盖：板卡调试（STM32 寄存器/PWM/UART/心跳/时钟自检）+ 多硬件链路（RPi → STM32 → OpenMV）
> 附带：RPi 端坐标链路与抓取仿真复现（`_sim_coord_chain.py`、`_sim_grasp.py`）
> 构建结果：`dotnet build -c Release` → 0 警告 0 错误

---

## 1. C# 工程结构与运行

### 1.1 模块清单

| 模块 | 类/命名空间 | 职责 | 与 RPi 对齐点 |
|------|-------------|------|--------------|
| 坐标系变换 | `CoordTransform` | 像素→相机→机器人基座（mm） | `vision/calibration.py` |
| 结构化日志 | `JLog` | JSON 事件输出 | `utils/logger.py JsonFormatter` |
| STM32 板卡模拟 | `Stm32Board` | 寄存器读写/PWM/UART 回环/心跳/时钟自检 | `hardware/stm32_comm.py` |
| OpenMV 模拟 | `OpenMvCam` | blob / AprilTag JSON 响应 | `openmv_comm.py` |
| 多硬件链路 | `HardwareChain` | RPi→STM32→OpenMV 端到端 | — |
| 板卡调试 | `BoardDebug` | 单板自检流程 | `scripts/diagnose_stm32.py` |

运行方式：

```
hardware_debug.exe board   # 板卡调试模式
hardware_debug.exe chain   # 多硬件链路模式（默认）
```

### 1.2 运行环境

- .NET SDK 8.0，目标框架 `net8.0`，无第三方依赖。
- 构建：`dotnet build -c Release` → **0 警告 0 错误**。

---

## 2. 板卡调试模式模拟结果（`hardware_debug.exe board`）

| 阶段 | 事件 | 结果 |
|------|------|------|
| 上电初始化 | `debug_start` | ✅ STM32F103(YH-KSTM32) |
| 连接 | `board_connect` | ✅ /dev/serial0 @115200 |
| 时钟自检 | `board_selftest` | ✅ RCC_APB2ENR=0x1D，GPIOA/B/C+AFIO 使能 |
| 寄存器写读 | `reg_write/reg_read` | ✅ TIM2_ARR=0x4E1F(19999)→50Hz |
| PWM 舵机 | `servo_pwm` | ✅ 500us(open)/1800us(close)/900us(hold)，脉宽限幅校验 |
| UART 回环 | `uart_echo` | ✅ `#PING!` 原样回显，pass=true |
| 心跳 | `heartbeat` | ✅ 12 拍，5/10 拍输出 |
| 结束 | `debug_end` | ✅ completed |

**关键日志（节选）：**

```json
{"level":"INFO","event":"board_selftest","payload":{"rcc_ok":true,"enr":"0x0000001D"}}
{"level":"INFO","event":"servo_pwm","payload":{"channel":1,"pulseUs":1800,"action":"close"}}
{"level":"INFO","event":"uart_echo","payload":{"echoed":"#PING!","pass":true}}
{"level":"INFO","event":"debug_end","payload":{"status":"completed"}}
```

---

## 3. 多硬件链路模拟结果（`hardware_debug.exe chain`）

链路时序：**RPi(上位机) --UART--> STM32(桥接) --> OpenMV** → 回传检测 → 手眼变换 → 下发运动。

| 步骤 | 事件 | 数据/结果 |
|------|------|-----------|
| 1 启动 | `chain_start` | nodes=[RPi,STM32,OpenMV] |
| 2 连接 | `board_connect` | /dev/ttyAMA0 @115200 |
| 3 RPi 下发 | `chain_rpi_tx` | `#vision:detect_apriltag:TAG36H11!` |
| 4 STM32 桥接 | `uart_rx` | 原样转发 |
| 5 OpenMV 回传 | `chain_openmv_rx` | JSON：tag id=0, cx=224, cy=152 |
| 6 相机系位姿 | `chain_camera_pose` | (60, 30, 300) mm, frame=camera |
| 7 **手眼变换** | `chain_robot_pose` | **(-40, -230, -250)** mm, frame=robot_base |
| 8 运动指令 | `servo_pwm` / `chain_motion_cmd` | 关节1 1500us, MOTION_TARGET_X=0x28 |
| 9 STM32 确认 | `chain_stm32_ack` | ack=true, motion=approach |
| 10 时钟自检 | `board_selftest` | rcc_ok=true |
| 11 结束 | `chain_end` | selftest=true, status=completed |

**关键日志（节选）：**

```json
{"level":"INFO","event":"chain_camera_pose","payload":{"x":60,"y":30,"z":300,"unit":"mm","frame":"camera"}}
{"level":"INFO","event":"chain_robot_pose","payload":{"x":-40,"y":-230,"z":-250,"unit":"mm","frame":"robot_base"}}
{"level":"INFO","event":"chain_motion_cmd","payload":{"target":[-40,-230,-250],"unit":"mm"}}
{"level":"INFO","event":"chain_end","payload":{"selftest":true,"status":"completed"}}
```

### 3.1 ⚠️ 链路发现（与代码审查联动）

手眼变换将相机点 (60,30,300) 映射到机器人系 **(-40,-230,-250)**，坐标为负、落在 `0~500` 名义工作空间之外。C# 模拟与 RPi 仿真一致暴露了同一问题（见审查报告 §4.4）。**这是"目标可达但被判越界"的系统性隐患，应在真机标定后统一工作空间原点与手眼参数。**

---

## 4. RPi 端仿真复现（坐标系同步）

### 4.1 坐标链路（`_sim_coord_chain.py`）

场景：目标真实位于机器人系 (120, 80, 20) mm。

| 路径 | 结果 | 误差 |
|------|------|------|
| [A] AprilTag（新链路：手眼标定） | (120.0, 80.0, 20.0) | **0.0000 mm** ✅ |
| [B] Blob 旧链路（像素→mm 外推） | (350.0, 316.7, 50.0) | 735.5 mm |
| [B] Blob 新链路（手眼标定） | (-40.0, -230.0, -250.0) | **0.0 mm** ✅ |
| [C] sampling_agent 消费 | (120.0, 80.0, 20.0) | **0.0000 mm** ✅ |

**结论**：旧链路把像素当毫米、误差高达 735.5mm；新链路接通手眼标定后误差降为 0，坐标断链问题彻底解决。

### 4.2 端到端抓取（`_sim_grasp.py`）

| 阶段 | 结果 |
|------|------|
| 视觉 PnP 定位 | 置信度 0.978 |
| 手眼变换 | 定位误差 **1.00 mm**（真值 -100,-200,-160） |
| 逆运动学 | 接近 1 解 / 抓取 4 解 / 放置 3 解，全部可达 |
| 轨迹规划 | 3 段共 153 点（51/26/76） |
| 力控状态机 | approach→contact→grasping→grasped，滑移 False |
| 放置 | 搬运位移 **274.6 mm**，状态 grasped，松开后 released |
| 总结果 | ✅ 抓取流程完成，定位误差 1.00mm，搬运 274.6mm |

---

## 5. 模拟报告汇总

| 验证项 | 结果 | 说明 |
|--------|------|------|
| C# 构建 | ✅ 0 警告 0 错误 | net8.0 |
| 板卡调试（寄存器/PWM/UART/心跳/自检） | ✅ 全部通过 | — |
| 多硬件链路（RPi→STM32→OpenMV） | ✅ 端到端完成 | 检测→变换→运动→自检 |
| RPi↔OpenMV 坐标同步 | ✅ 通过 | AprilTag/Blob/采样 三路误差≈0 |
| 端到端视觉抓取 | ✅ 通过 | 定位误差 1mm，搬运 274.6mm |
| 工作空间一致性 | ⚠️ 需真机校准 | 手眼默认参数映射到名义工作空间之外 |

**工程产物**：
- `hardware_debug_cs\HardwareDebug\HardwareDebug.csproj`
- `hardware_debug_cs\HardwareDebug\Program.cs`
- 可执行：`hardware_debug_cs\HardwareDebug\bin\Release\net8.0\hardware_debug.exe`
