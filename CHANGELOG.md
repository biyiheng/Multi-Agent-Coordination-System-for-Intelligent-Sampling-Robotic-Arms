# 更新日志 (CHANGELOG)

本文件记录智能采样机械臂多智能体协同系统各版本的更新内容。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)规范。

---

## [v1.2.0] - 2026-08-19

### 新增

- **统一帧格式通信协议**（对应《改进计划.md》§5 通信协议设计）
  - 新增 `rpi_control/hardware/frame_protocol.py`：实现 `帧头(2B) | 目标地址(1B) | 源地址(1B) | 命令字(1B) | 数据长度(1B) | 数据(N B) | CRC16(2B) | 帧尾(2B)` 的标准帧协议
  - 内置 CRC16 校验、帧编解码、畸形帧/篡改帧丢弃，供 STM32 / OpenMV / ESP32 通信层复用
- **遥测推送频率升级至 20 Hz**（对应《改进计划.md》§4.1 状态上报任务 20Hz）
  - `TelemetryStream` 默认推送率 10Hz → 20Hz，支持配置覆盖
- **实时安全监控增强**（对应《改进计划.md》§4.1 安全监控任务 1kHz）
  - 新增温度过载（TEMP_OVERLOAD）与电流过载（CURRENT_OVERLOAD）检测事件
  - 传感器采集链路（100Hz 量级）与安全状态机联动
- **视觉感知与采样 Agent 增强**
  - VisionAgent 多帧融合滤波（EMA）增强检测稳定性
  - SamplingAgent 分层采样（等距 + 边界增强）提升覆盖均匀性
- **模型重训练 Round 12**
  - 补充公开数据源（合法爬取）与合成数据增强，重建训练数据集
  - 重训练 motion_ik / safety / quality / collision 四个模型并校验精度
- **帧协议正式回归测试**
  - 新增 `rpi_control/tests/test_frame_protocol.py`（19 项）：CRC16 / 编解码 / 篡改丢弃 / 流式解析 / STM32 帧模式仿真接入
- **v1.2 增强特性正式回归测试**
  - 新增 `rpi_control/tests/test_v12_enhancements.py`（14 项）：传感器温度/电流过载监控、Vision EMA 多帧滤波、Sampling 分层采样边界增强

### 变更

- 系统版本号统一升级为 `1.2.0`（settings.yaml / server.py / main.py / README 等）
- 通信层适配统一帧协议（STM32 / OpenMV 命令封装）
- 文档全量同步 v1.2（01–19 文档版本提升，新增 20-更新报告、21-测试报告）

### 修复

- 依据 v1.2 全量回归测试结果修复若干缺陷（详见 21-测试报告v1.2.md）
- 修正部分文档中版本号 / 计数与实现不一致的问题

### 安全

- 模型重训练保持碰撞模型召回率门控（≥0.85），确保安全关键能力不退化

---

## [v1.1.0] - 2026-08-15

### 新增

- 后台控制模块全面接入 SQLite 数据库（机械臂 / 视觉 / 系统配置状态持久化）
- 全模块 CRUD 补齐：用户 / 设备 / WiFi / 样本 / 系统配置 / 闭环工程 6 模型
- 闭环工程数据持久化：`SampleRepository` 与 6 个闭环工程仓储 + `/api/v1/samples`、`/api/v1/loop/*`
- App（Android/iOS）界面美化：Material 3 主题、`SectionHeader` / `StatusCard`、夜间模式、控制页重构
- App 配置持久化：服务端地址 `shared_preferences` 保存

### 变更

- 双端 App 工程化落地：本地安装 Flutter SDK，`flutter analyze` 0 error、UI 冒烟 6/6
- 全量测试 **412 passed / 11 skipped / 0 failed**

### 文档

- 新增 18-更新报告v1.1.md、19-测试报告v1.1.md
- 01/02/03/04/05/06/08/12 全量同步 v1.1

---

## [v1.0.0] - 2026-08-14

### 新增

- 初始交付：多智能体协同架构（Orchestrator + 5 Agent + 12 状态状态机）
- 运动学 / 轨迹规划 / 碰撞检测 / 工作空间 / 力控 / 柔顺抓取
- 循环工程（Loop Engineering）七大组件
- Web 远程控制（FastAPI + WebSocket 遥测）+ 微信小程序 + ESP32 WiFi
- Docker 容器化 + CI（GitHub Actions）
- 压力测试与安全分析

---

## 版本对照

| 版本 | 项目版本 | 文档基线 | 发布日期 |
|------|---------|---------|---------|
| v1.0.0 | 1.0 | 01–17 | 2026-08-14 |
| v1.1.0 | 1.1 | 01–19 | 2026-08-15 |
| v1.2.0 | 1.2 | 01–21 | 2026-08-19 |
