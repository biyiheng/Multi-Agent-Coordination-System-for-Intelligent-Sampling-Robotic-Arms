<div align="center">

# 🤖 智能采样机械臂多智能体协同系统

**Multi-Agent Coordination System for Intelligent Sampling Robotic Arms**

一套面向工业自动化场景的六自由度采样机械臂综合控制平台 —— 融合多智能体编排、机器视觉、运动规划、力控抓取、实时安全防护与工业级固件。

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)
![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%2FJetson%2FLinux-important?style=flat-square)
![CI](https://img.shields.io/badge/CI-GitHub%20Actions-brightgreen?style=flat-square)

</div>

---

## 📌 项目简介

本项目是一套运行于 **Raspberry Pi / Jetson / Linux** 的智能采样机械臂综合控制系统，通过 **STM32 微控制器** 驱动六路舵机，并集成 **OpenMV / Jetson 视觉模组** 实现目标检测与位姿估计。系统采用异步事件驱动架构，支持 Docker 容器化部署与 systemd 服务管理，具备从采样规划、运动控制、力控抓取、质量评估到安全防护与云同步的完整能力链路。

- **核心价值**：多智能体协同决策 + 工业级实时安全约束 + 循环工程持续优化
- **运行平台**：Raspberry Pi OS (64-bit) / Jetson / Linux / Windows（仿真模式）
- **许可证**：MIT

---

## 🏗️ 系统架构

系统由 **`Orchestrator`（编排器）** 统一调度五大专业智能体，形成感知 → 决策 → 执行 → 评估 → 防护的闭环：

| 智能体 | 职责 |
|--------|------|
| **Sampling Agent** | 采样任务规划与执行策略生成 |
| **Vision Agent** | 图像采集、目标检测与位姿估计 |
| **Motion Agent** | 运动规划、轨迹生成与逆运动学求解（ML 热启动加速） |
| **Quality Agent** | 抓取质量评估与任务完成度判定 |
| **Safety Agent** | 实时安全监控、碰撞预警与紧急停止（ESTOP） |

状态机覆盖 `IDLE → PLANNING → APPROACHING → DETECTING → GRASPING → LIFTING → INSPECTING → PLACING → EVALUATING → DONE` 等 12 种状态，并包含 `RECOVERY`（故障恢复）与 `ABORT`（紧急中止）两条异常处理路径。

```
┌────────────────────────────────────────────────────────────┐
│                     Orchestrator (编排器)                    │
│   Sampling ── Vision ── Motion ── Quality ── Safety         │
└───────┬──────────────┬──────────────┬──────────┬───────────┘
        ▼              ▼              ▼          ▼
   Web/API        OpenMV/Jetson    STM32 舵机    实时安全
   (FastAPI)      视觉模组         运动/力控      ESTOP/看门狗
```

---

## ✨ 核心特性

### 1. 多智能体协同编排
LangGraph 启发的状态机设计，由 `Orchestrator` 统一调度，各 Agent 均经 `BaseAgent.run()` 执行，内置**约束护栏**（不可擅自决策 / 符合事实逻辑）。

### 2. 工业级实时安全约束（工业级升级）
- **急停优先级**：三级响应 `OK → DANGER → ESTOP`，DANGER 态（心跳丢失 / 关节越限 / 碰撞 / 双网丢失）**可靠升级为实际急停**，并输出具体触发原因日志
- **坏帧处理**：CAN 通信层带 CRC32 校验与重传，篡改 / 非法帧被丢弃
- **实时安全状态机**：通信超时、关节越限、工作区越界 → `PROTECTIVE_STOP`；硬件故障 → `FAULT`
- **压力测试**：自动化极端工况脚本（急停触发 / CAN 丢包 / 数值鲁棒性 / 双网丢失），部署前一键验证

### 3. 动力学前馈控制（工业级升级 S3）
重力补偿 + 摩擦模型（库仑/粘滞/Stribeck）+ 可选惯量项，叠加在纯运动学轨迹之上，提升低速与变速精度；内置 NaN/Inf 极端工况防护与输出滤波。

### 4. 力位混合控制与柔顺抓取
基于 Hogan 阻抗控制与 Siciliano 力控框架：导纳控制 / 阻抗控制 / 力位混合控制 / 自适应夹持力、滑移检测 / 自动 TCP 标定。

### 5. 运动学与轨迹规划
正/逆运动学（Pieper + 多解排序）、数值雅可比 + SVD 阻尼伪逆、五次多项式 / S 曲线 / 梯形轨迹、蒙特卡洛工作空间分析。

### 6. 循环工程（Loop Engineering）持续优化
Profiler / Evaluator（七维）/ Context Manager / Skill Extractor / Knowledge Inheritor / Meta-Optimizer 自动化闭环优化。

### 7. 视觉与抓取
OpenMV / Jetson 视觉节点、Apriltag 检测、颜色与目标分类、质量检测、手眼标定、抓取管线。

### 8. Web 远程控制 + 小程序
FastAPI RESTful API + WebSocket 实时遥测 + Swagger UI（`/docs`）+ 微信小程序远程控制面板。

### 9. 多端互通（App / 小程序 / Web / 硬件）
多端互通服务器统一鉴权与设备中心，App（Android/iOS）、微信小程序、Web 与硬件端（RPi / ESP32 / STM32 / OpenMV）通过 **WebSocket 多端互通中枢 `/ws/hub`** 数据互通：
- **账号体系**：注册 / 登录 / Token（PBKDF2 密码哈希 + SHA-256 令牌哈希）/ 角色权限（admin/user/viewer）
- **设备中心**：各端注册 / 心跳 / 在线状态持久化到数据库
- **命令路由**：定向（device_id）/ 分组（hardware）/ 广播三种路由，遥测实时推送
- **WiFi / ESP32 配网**：STA 连接 / AP 热点 / 扫描 / 复位 / 状态持久化

### 10. Android/iOS 双端 App（Flutter）
`mobile_app/` 提供双端远程控制 App：登录注册、6 关节滑杆 / 笛卡尔 / 夹爪 / 回零 / 急停控制、实时监控（传感器 + 多端设备在线状态）、WiFi 配网、服务端地址设置。

### 11. ESP32 WiFi 模块
外接 ESP32 AT 模块（`rpi_control/hardware/esp32_wifi.py`）实现 STA/AP/扫描/复位，无硬件时自动回退**模拟模式**；另附独立配网固件 `esp32_firmware/`（SoftAP 配网 + NVS 持久化 + GPIO0 长按重置）。

---

## 🧠 运动学算法

运动学模块（`rpi_control/motion/kinematics.py`）负责六自由度机械臂的位姿建模与求解，是运动规划、力控与安全检测的数学基础。

### 设计理念
- **统一参数化建模**：采用标准 DH 参数约定描述连杆几何关系，将机械臂建模为一系列齐次变换的链式组合，使位姿描述简洁、可扩展、与实物结构一致。
- **解析与数值结合**：兼顾**实时性**与**通用性**——既提供适合典型构型的解析求解路径，又保留数值求解作为兜底，提升对奇异与特殊位形的鲁棒性。
- **安全优先**：所有求解都受关节限位约束，并对不可达目标做显式判定，避免错误位形导致机械臂越限或碰撞。
- **数值稳定**：重视计算中的数值稳定性，避免因浮点误差、角度缠绕或接近奇异造成跳变。

### 实现方法
- **正运动学（FK）**：沿 DH 变换链递推各连杆坐标系位姿，得到末端在世界系下的位姿与各连杆质心位置。
- **逆运动学（IK）**：面向典型"球腕"构型采用解析解耦思路；对多解依据"最小关节位移"等准则排序，选出最优位形。
- **雅可比与奇异处理**：数值雅可比配合阻尼伪逆，在接近奇异时平滑降级而非突变。
- **数值 IK 兜底**：加入单步关节增量约束与角度归一化，防止振荡与误差累积。

### 核心技术
| 技术 | 作用 |
|------|------|
| DH 参数化建模 | 统一连杆几何描述 |
| 齐次变换链 | 正向位姿递推 |
| 解析解耦 + 多解排序 | 高效求逆解并选优 |
| 雅可比 + 阻尼伪逆 | 速度级求解与奇异处理 |
| 关节限位 / 可达性判定 | 安全约束与异常防护 |

> 具体 DH 参数、解算公式与工程调参细节见 `项目文档/02-技术文档.md`，此处仅作概念性介绍。

---

## 🧱 技术栈

| 层 | 技术 |
|----|------|
| 控制端 | Python 3.11+ / FastAPI / WebSocket / SQLAlchemy / SQLite |
| 部署 | Docker / docker-compose / systemd / `start_all.sh` |
| 边缘视觉 | OpenMV (MicroPython) / NVIDIA Jetson (可选) |
| 底层固件 | STM32F103C8T6（C / Makefile）+ STM32H7 驱动参考 |
| **双端 App** | **Flutter 3.0+（Android / iOS 远程控制）** |
| 小程序 | 微信小程序（WXML / WXSS / JS） |
| **WiFi 模块** | **ESP32 AT 指令 + 独立配网固件（C++ / Arduino 框架）** |
| 机器学习 | numpy / scipy / scikit-learn（4 个 ML 模型） |
| CI | GitHub Actions（C# 硬件调试 + 合并报告） |

---

## 📂 仓库结构

```
.
├── rpi_control/            # Raspberry Pi 主控制系统
│   ├── agents/             # 5 大智能体 + 编排器 + A2A 协议
│   ├── motion/             # 运动学 / 轨迹 / 碰撞 / 力控 / 动力学前馈
│   ├── safety/             # 实时安全状态机
│   ├── vision/             # 视觉处理 / 标定 / 位姿估计
│   ├── grasp/              # 抓取管线 / 运动驱动
│   ├── sampling/           # 采样规划 / 策略
│   ├── hardware/           # STM32 / 舵机 / OpenMV 通信抽象
│   ├── web/                # FastAPI + WebSocket + 服务层
│   ├── training/           # 模型训练管线 / 数据生成
│   ├── loop_engineering/   # 循环工程优化框架
│   ├── tests/              # 测试套件（含压力测试）
│   ├── scripts/            # 标定 / 诊断 / 部署脚本
│   ├── main.py             # 主入口
│   ├── Dockerfile          # 镜像构建
│   └── docker-compose.yml  # 容器编排
├── stm32_firmware/         # STM32F103 固件 + STM32H7 驱动参考
├── openmv_firmware/        # OpenMV 视觉固件 (MicroPython)
├── esp32_firmware/         # ESP32 WiFi 配网固件（SoftAP/STA/NVS）
├── mobile_app/             # Android/iOS 双端远程控制 App（Flutter）
├── mini_program/           # 微信小程序远程控制
├── hardware_debug_cs/      # C# 板卡/链路调试 + CI
├── 项目文档/               # 完整项目文档（01–17）
├── start_all.sh            # 一键启动（含 --check / --stress / --ros2 / --jetson）
└── README.md
```

---

## 🚀 快速开始

### 环境要求
- **Python 3.11+**，Raspberry Pi OS (64-bit) / Ubuntu 22.04+ / Windows（仿真模式）
- **硬件**：Raspberry Pi 4B/5、STM32F103、OpenMV Cam H7、6× 舵机（可选 Jetson）
- **可选**：Docker 24.0+

### 安装与测试
```bash
# 克隆并进入
git clone https://github.com/biyiheng/Multi-Agent-Coordination-System-for-Intelligent-Sampling-Robotic-Arms.git
cd Multi-Agent-Coordination-System-for-Intelligent-Sampling-Robotic-Arms

# 安装依赖
pip install -r rpi_control/requirements.txt

# 运行测试（无需硬件，仿真模式）
cd rpi_control && python -m pytest tests/ -q
```

### 一键启动（真实硬件 / Linux）
```bash
./start_all.sh --check     # 环境/模型/约束自检（不启动）
./start_all.sh --stress    # 压力测试 + 生成报告（部署前验证）
./start_all.sh             # 启动全部 5 个 Agent + 模型服务
./start_all.sh --stop      # 停止服务
# 工业级扩展
./start_all.sh --ros2      # 以 ROS2 节点方式启动 Agent（若检测到 ROS2）
./start_all.sh --jetson    # 额外启动 Jetson 视觉节点
```

### Docker 部署
```bash
docker compose -f rpi_control/docker-compose.yml up -d
```

### 双端 App（Android / iOS）
```bash
cd mobile_app
flutter pub get
flutter build apk --release     # Android: build/app/outputs/flutter-apk/app-release.apk
flutter build ios --release     # iOS（需 macOS）
```
> 默认连接 `192.168.1.100:8000`，可在 App「设置」页修改；登录后即可远程控制 / 实时监控 / WiFi 配网。

### ESP32 WiFi 模块
- **方案 A（推荐）**：ESP32 刷 Espressif AT 固件，接树莓派 UART，由服务端 WiFi API（`/api/v1/wifi/*`）控制（无硬件时自动模拟模式）。
- **方案 B**：烧录 `esp32_firmware/esp32_wifi_provisioning/` 独立配网固件 → 手机连 `SmartArm-XXXX` 热点 → 访问 `192.168.4.1` 配网。

---

## 📚 文档索引

`项目文档/` 下提供了完整文档（01–17）：

| 编号 | 文档 | 编号 | 文档 |
|------|------|------|------|
| 01 | 项目结构文档 | 10 | 工业级升级规划 |
| 02 | 技术文档 | 11 | 硬件采购清单 |
| 03 | 安全性文档 | 12 | 项目交付报告 |
| 04 | 部署文档 | 13 | 压力测试方案 |
| 05 | 需求清单 | 14 | 真实硬件部署操作手册 |
| 06 | API 接口文档 | 15 | 现场工程师部署与验证操作手册 |
| 07 | 部署操作手册 | 16 | 故障排查速查表 |
| 08 | 验证报告 | **17** | **部署操作指南（含 App / WiFi 模块）** |
| 09 | 部署执行清单 | | |

---

## 🧪 测试与质量

- 覆盖：运动学、轨迹规划、碰撞检测、工作空间、力控、动力学前馈、API、安全扫描、性能基准、**极端工况压力测试**、**多端互通（鉴权/设备中心/WiFi API/WebSocket 中枢）**
- 支持 `pytest`、`pytest-asyncio`、`pytest-cov`
- 硬件仿真模式：无需物理硬件即可运行完整测试套件（ESP32 WiFi 自动模拟）
- 压力测试报告：`reports/stress_test_results.json`（由 `--stress` 自动生成）
- 多端互通测试：`python -m pytest rpi_control/tests/test_multient_interop.py -q`（10 项全过）

---

## 🤝 贡献

欢迎提交 Issue 与 Pull Request，请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 🔒 安全

安全策略与漏洞上报方式见 [SECURITY.md](SECURITY.md)。

## 📄 许可证

[MIT](LICENSE) © 智能采样机械臂团队
