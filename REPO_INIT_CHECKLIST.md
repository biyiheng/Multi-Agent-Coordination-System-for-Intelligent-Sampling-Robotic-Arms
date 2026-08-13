# 仓库初始化检查清单（推送前确认）

> 用途：在手动执行 `git push` 前，逐项确认仓库状态、关键文件、CI 配置与忽略规则均已就绪。
> 状态：截至本清单生成时，**本地已 `git init` 并完成初始提交 `6ea6380`，但未推送**。
> 用户决定：暂不自动提交/推送，由本人手动执行。

---

## 1. Git 仓库基础状态

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 已 `git init` | ✅ | `.git/` 存在于项目根 |
| 默认分支 | `master` | `git branch --show-current` = master |
| 身份 user.name | ✅ | `biyiheng` |
| 身份 user.email | ✅ | `3511148501@qq.com` |
| 初始提交 | ✅ `6ea6380` | 214 个文件，含 CI 工作流与核心代码 |
| 远程 origin | ⬜ 未配置 | 需手动 `git remote add origin ...` |

## 2. 关键文件就绪

| 文件/目录 | 状态 | 说明 |
|-----------|------|------|
| `.github/workflows/ci.yml` | ✅ 已跟踪 | GitHub Actions 工作流 |
| `hardware_debug_cs/HardwareDebug/{Program.cs,HardwareDebug.csproj}` | ✅ 已跟踪 | C# 板卡/链路/单测 |
| `hardware_debug_cs/CI_RUN_INSTRUCTIONS.md` | ✅ 已跟踪 | CI 运行说明 |
| `rpi_control/`（agents/vision/motion/grasp/tests/...） | ✅ 已跟踪 | RPi 主代码 |
| `openmv_firmware/` | ✅ 已跟踪 | OpenMV 固件 |
| `rpi_control/reports/*.md`（审查/模拟/优化报告） | ✅ 已跟踪 | 文档 |

## 3. 待手动 `git add` 的源文件（当前未跟踪）

| 项 | 说明 |
|----|------|
| `mini_program/` | 小程序源码 |
| `stm32_firmware/` | STM32 固件源码 |
| `reports/` | 根目录报告 |
| `start_system.py` | 系统启动脚本 |
| `ik_fix_plan.md`、`介绍内容.md`、`详细内容.md`、`项目文档/`、`项目计划.docx` | 文档 |

> 若要一并推送，先执行：`git add mini_program stm32_firmware reports start_system.py 项目文档 介绍内容.md 详细内容.md 项目计划.docx ik_fix_plan.md`（按需取舍）。

## 4. .gitignore 忽略规则确认（已更新并待提交）

| 规则 | 覆盖 | 影响 |
|------|------|------|
| `bin/ obj/ *.user` | .NET 构建产物 | 避免提交二进制 |
| `__pycache__/ *.py[cod] .venv/ venv/` | Python | 避免提交缓存/虚拟环境 |
| `.trae/ .vscode/ .idea/` | IDE | 避免提交本地配置 |
| `logs/ *.log` | 日志 | 避免提交调试日志 |
| `data/ models/ canshu/` | **约 7.2GB 大数据** | **必须忽略** |
| `debug_*.py flash_*.py scan_*.py _*.py test_*.py` 等 | 一次性调试/烧录脚本 | 避免提交临时脚本 |
| `e2e_merged_log.json *.exe *.dll` | 生成物/二进制 | 避免提交 |

当前忽略计数：**133 项**（`git status --ignored | grep ^!!`）。

> ⚠️ `.gitignore` 更新**尚未提交**。推送前请先提交：
> ```powershell
> git add .gitignore
> git commit -m "完善 .gitignore: 忽略调试/日志/IDE/大数据"
> ```

## 5. CI 配置确认（workflow_dispatch）

[ci.yml](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/.github/workflows/ci.yml#L10) 第 10 行 `workflow_dispatch:` **已声明**，支持手动运行：
- 推送后：Actions → **CSharp Hardware CI** → **Run workflow** → 选 `master` → Run。
- 两个 job：`build-and-test`（构建+单测+冒烟）与 `e2e-report`（依赖前者，跑合并报告并上传产物）。
- 单测失败（`test` 退出码非 0）会**使流水线失败**并阻断合并。

## 6. 手动推送命令（推送前最后执行）

```powershell
# 1) 提交 .gitignore 更新（必须）
git add .gitignore
git commit -m "完善 .gitignore: 忽略调试/日志/IDE/大数据"

# 2) （可选）提交待入库源文件
git add mini_program stm32_firmware reports start_system.py
git commit -m "补充源文件: 小程序/STM32固件/报告/启动脚本"

# 3) 关联并推送
git remote add origin https://github.com/biyiheng/zidongaixiangmu.git
git push -u origin master
```

---

# 附录：手动触发（workflow_dispatch）预期流水线日志

> 以下为 **build-and-test** job 的预期输出（已按等价命令实测，数据真实）。
> `e2e-report` job 依赖前者，在 build-and-test 通过后执行。

```
✓ CSharp Hardware CI                     # 手动触发 (workflow_dispatch), branch=master

Job: build-and-test  (windows-latest)
  ✓ Set up job
  ✓ actions/checkout@v4                    # 检出 6ea6380 (master)
  ✓ Setup .NET 8 (.NET SDK 8.0.x)
  ✓ dotnet restore
       正在确定要还原的项目…
       所有项目均是最新的，无法还原。
  ✓ dotnet build -c Release
       Build succeeded.
       0 个警告
       0 个错误
       已用时间 00:00:01.95
  ✓ dotnet run -c Release --no-build -- test   # 单元测试
       == C# 单元测试: 坐标变换与工作空间 ==
       [PASS] 主点处像素映射到相机系原点 ...
       [PASS] FOV 内像素映射为正前方 (60,30,300) ...
       [PASS] 手眼变换 robot=R·cam+t ...
       [PASS] 完整链路 像素->相机->机器人 ...
       [PASS] 工作空间对齐: 目标在区间内 ...
       [PASS] 边界最小值(含) 在工作空间内 ...
       [PASS] 边界最大值(含) 在工作空间内 ...
       [PASS] x 略低于下界被拒绝 ...
       [PASS] y 略高于上界被拒绝 ...
       [PASS] 名义原点(0,0,0) 不在对齐工作空间内 ...
       [PASS] 空数组返回 false 不抛异常 ...
       == 测试结果: 通过 11, 失败 0 ==        # exit 0
  ✓ dotnet run -c Release --no-build -- chain  # 冒烟: 多硬件链路
       chain_end ... status=completed (exit 0)
  ✓ dotnet run -c Release --no-build -- board  # 冒烟: 板卡调试
       debug_end ... status=completed (exit 0)
  ✓ Post actions/upload-artifact
Result: ✅ SUCCESS (build-and-test)

Job: e2e-report  (ubuntu-latest)   # needs: build-and-test
  ✓ Setup .NET 8 / Setup Python 3.11
  ✓ dotnet build -c Release HardwareDebug.csproj
  ✓ python _merge_e2e_report.py
       [1] C# 链路: 16 事件
       [2] C# 板卡调试: 17 事件
       [2.1] C# 单测: 11 通过 / 0 失败
       [3] RPi 坐标链路: ...s
       [4] RPi 抓取仿真: ...s
       报告已生成: rpi_control/reports/e2e_performance_report.md
  ✓ Upload artifact (e2e-report)
Result: ✅ SUCCESS (e2e-report)

结论: 两条 job 均预计通过 (绿色) → 可合并。
```

> 模拟依据：本地等价命令 `dotnet build/test/chain/board` 与 `_merge_e2e_report.py` 均已实测通过（exit 0），故手动触发流水线预期全部步骤通过。
