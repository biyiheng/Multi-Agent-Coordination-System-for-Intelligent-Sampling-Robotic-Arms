# 贡献指南 (Contributing Guide)

欢迎为本项目贡献代码、文档与建议。请遵循以下约定，以确保协作顺畅。

---

## 开发流程

1. **Fork 本仓库**，并克隆到本地。
2. 创建功能分支：`git checkout -b feat/xxx`（或 `fix/xxx`）。
3. 进行修改，并**为新增功能编写测试**。
4. 在提交前运行测试套件确保无回归。
5. 提交 Pull Request，描述改动内容与验证结果。

## 提交信息规范

- 使用语义化提交：`feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:`。
- 示例：`feat: 增加急停优先级日志埋点`、`fix: 修复 CAN 坏帧处理越界`。

## 代码规范

- **Python**：遵循 PEP 8；类型注解用于公共接口；文档字符串说明意图与单位。
- **固件 (C)**：使用 `-std=gnu99`，外设操作封装于 `SRC/*/y_*.c`，头文件在 `SRC/*/y_*.h`。
- **日志**：统一使用 `rpi_control/utils/logger.py`，不直接 `print`。
- **错误处理**：在系统边界（用户输入 / 外部 API / 硬件通信）做校验；内部代码信任框架保证。
- **安全约束**：所有 Agent 必须经 `BaseAgent.run()`，不得未经授权擅自决策；新增决策必须符合事实逻辑与常识。

## 测试要求

```bash
cd rpi_control
python -m pytest tests/ -q        # 全部测试
python -m pytest tests/stress_test_extreme.py -q   # 极端工况压力测试
```

- 新增/修改功能需补充对应测试。
- 提交 PR 前确保本地全部测试通过。

## 文档

- 涉及行为、接口或架构变更时，请同步更新 `项目文档/` 下对应文档，或在 PR 中说明原因。

## 分支与发布

- 主分支：`master`。
- 功能开发基于 `feat/*`，修复基于 `fix/*`，文档基于 `docs/*`。

## 提问与讨论

- 使用 [Issues](https://github.com/biyiheng/Multi-Agent-Coordination-System-for-Intelligent-Sampling-Robotic-Arms/issues) 提出 bug 与需求。
- 重大设计变更建议先通过 Issue 讨论，再实现。
