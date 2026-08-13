# 安全策略 (Security Policy)

本项目用于工业采样机械臂控制，涉及实时运动控制与硬件交互，安全性至关重要。请阅读以下安全说明。

---

## 支持的版本

| 版本 | 支持状态 |
|------|----------|
| 最新 master | ✅ 支持 |
| 已发布 tag | ✅ 支持 |
| 更早版本 | ❌ 不维护 |

建议始终运行最新版本并定期同步 `master`。

---

## 报告漏洞

请**不要**在公开 Issue 中披露安全漏洞。请通过以下方式私密上报：

- 联系维护者：**biyiheng**（仓库 Owner）
- 在 [GitHub Security Advisory](https://github.com/biyiheng/Multi-Agent-Coordination-System-for-Intelligent-Sampling-Robotic-Arms/security/advisories) 中创建私密咨询

请在上报中包含：
1. 漏洞类型与影响范围
2. 触发条件与复现步骤
3. 受影响的模块/文件
4. 建议的修复方案（如有）

我们会在确认后尽快响应并发布修复。

---

## 安全设计要点

本项目内置了以下安全机制（详见 [03-安全性文档.md](项目文档/03-安全性文档.md) 与 [10-工业级升级规划.md](项目文档/10-工业级升级规划.md)）：

- **急停优先级**：三级响应 `OK → DANGER → ESTOP`，危险条件（心跳丢失 / 关节越限 / 碰撞 / 双网丢失）可靠升级为实际急停。
- **实时安全状态机**：通信超时 / 越限 / 越界 → `PROTECTIVE_STOP`；硬件故障 → `FAULT`。
- **CAN 通信安全**：CRC32 校验与重传，坏帧丢弃。
- **约束护栏**：所有 Agent 经 `BaseAgent.run()`，禁止未经授权擅自决策。
- **数值鲁棒性**：动力学前馈对 NaN/Inf 输入返回零并复位滤波，防止异常传播。

---

## 依赖与凭据安全

- 请勿将任何 **token / 密钥 / 密码** 提交到仓库（包括 `.env`、配置文件、日志）。
- 克隆后请基于 `.env.example` 创建本地 `.env`，不要提交真实凭据。
- 使用 GitHub fine-grained PAT 时，推送完成后请及时撤销。
