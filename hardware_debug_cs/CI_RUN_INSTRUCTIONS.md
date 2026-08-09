# C# 侧 GitHub Actions 式 CI 运行说明

> 位置：`.github/workflows/ci.yml`
> 目的：对 `hardware_debug_cs` 的 C# 工程进行自动化**构建 + 单测 + 冒烟测试 + 端到端合并报告**验证，防止坐标/工作空间/链路回归。

---

## 1. CI 覆盖内容

| Job | 运行环境 | 步骤 | 失败条件 |
|-----|----------|------|----------|
| `build-and-test` | `windows-latest` | restore → build(Release) → `test`(单测) → `chain`(冒烟) → `board`(冒烟) | 任一 `dotnet` 命令非 0 退出 |
| `e2e-report` | `ubuntu-latest` | 装 .NET8 + Python → 构建 C# → 跑 `_merge_e2e_report.py` → 上传报告产物 | Python 脚本返回非 0 |

**关键点**：C# 单测模式（`CoordinateTests.Run`）在出现失败时返回非 0，从而让 CI 步骤失败并阻断合并——无需额外测试框架（自测运行器，零第三方依赖）。

---

## 2. 触发方式

- **Push**：`main`/`master` 分支，且改动涉及 `hardware_debug_cs/**` 或 `**/*.cs` / `**/*.csproj`。
- **Pull Request**：目标为 `main`/`master`，同上路径过滤。
- **手动**：GitHub → Actions → **CSharp Hardware CI** → Run workflow（`workflow_dispatch`）。

---

## 3. 本地复现（等价于 CI）

在 PowerShell 中（C# 工程目录）：

```powershell
# 构建
dotnet build -c Release

# 单测（等价于 CI 的 test 步骤；返回 0=通过）
.\bin\Release\net8.0\hardware_debug.exe test

# 冒烟测试
.\bin\Release\net8.0\hardware_debug.exe chain
.\bin\Release\net8.0\hardware_debug.exe board

# 端到端合并报告（等价于 e2e-report job，需 Python + numpy）
python _merge_e2e_report.py
```

---

## 4. 单测用例清单（`hardware_debug.exe test`）

1. 主点处像素映射到相机系原点 `(0,0,300)`
2. FOV 内像素映射为正前方 `(60,30,300)`
3. 手眼变换 `robot=R·cam+t = (-40,-230,-250)`
4. 完整链路 像素→相机→机器人 = `(-40,-230,-250)`
5. 工作空间对齐：目标 `(-40,-230,-250)` 在区间内
6. 工作空间边界最小值(含) / 最大值(含) 在区间内
7. 边界越界：x 略低 / y 略高 被拒绝
8. 名义原点 `(0,0,0)` 不在对齐工作空间内（原隐患回归保护）
9. 空数组返回 false 不抛异常

---

## 5. 产物（Artifacts）

`e2e-report` 任务上传：
- `rpi_control/reports/e2e_performance_report.md` —— 最终端到端对比报告（含 C# 单测、链路、板卡、坐标同步、抓取全量验证）
- `e2e_merged_log.json` —— 合并后的结构化日志/指标

可在 GitHub Actions 运行页 → **Artifacts** 下载查看。

---

## 6. 本地运行（act，无需推 GitHub）

用 [nektos/act](https://github.com/nektos/act) 可在本地模拟 GitHub Actions：

```powershell
# 默认跑全部 job（需 Docker）
act -j build-and-test

# 仅跑端到端报告 job
act -j e2e-report
```

注意：`windows-latest` job 需 `act` 配置对应的 runner 镜像；若环境受限，可仅本地执行 §3 的等价命令。
