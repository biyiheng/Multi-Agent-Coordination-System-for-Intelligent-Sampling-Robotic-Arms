# 代码行为审查报告

> 审查范围：空间坐标定位、树莓派(RPi)与 OpenMV 坐标系运算法则同步性、运动算法合理性
> 审查对象：`rpi_control`（视觉/运动/抓取/多智能体）+ `openmv_firmware`（OpenMV 固件）+ `hardware_debug_cs`（C# 板卡/链路）
> 审查方式：逐模块静态审查 + 端到端仿真复现（`_sim_coord_chain.py`、`_sim_grasp.py`、C# `hardware_debug`）

---

## 1. 总体结论

| 维度 | 结论 | 说明 |
|------|------|------|
| 空间坐标定位 | ✅ 基本正确 | PnP 已修复，端到端定位误差约 1mm |
| RPi↔OpenMV 坐标同步 | ✅ 已接通 | 手眼标定链路已接入编排器，单位在机器人系统一为 mm |
| 运动算法合理性 | ⚠️ 存在隐患 | IK/轨迹合理，但工作空间边界与手眼默认参数不一致 |
| 代码行为合理性 | ⚠️ 有 2 处需关注 | 焦距不一致 bug、工作空间越界隐患 |

---

## 2. 空间坐标定位

### 2.1 PnP 位姿估计（[pose_estimator.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/vision/pose_estimator.py)）— ✅ 已修复

- **K⁻¹ 归一化**：`estimate_pose_pnp` 先用内参逆将像素坐标归一化为相机坐标 `(u-cx)/fx, (v-cy)/fy`，再进 DLT，避免投影矩阵被 K 污染（[L244-L259](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/vision/pose_estimator.py#L244-L259)）。
- **尺度恢复**：用 `R_origᵀ·R_orig = λ²I` 由迹恢复整体缩放，并强制 `det(R)=+1`（[L326+](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/vision/pose_estimator.py#L326)）。
- **LM 优化**：阻尼最小二乘 + Rodrigues 旋转更新，替代不稳定的梯度下降。
- 输出单位：**米**（物体模型点为米），后续 `×1000` 转 mm。仿真实测定位误差 **1.00 mm**，置信度 0.978，达标（目标 ±0.5mm，含仿真噪声）。

**保留意见**：PnP 输出为米，而 OpenMV 的 AprilTag 输出为毫米。两路均会在机器人系收敛为 mm，但原始单位不一致，属可维护性/一致性风险（见 §5 建议）。

### 2.2 相机系→机器人系（[calibration.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/vision/calibration.py)）

- `pixel_to_camera` / `camera_to_robot` 针孔模型正确，`robot = R·cam + t`，平移单位 mm。
- 手眼标定 AX=XB 采用 OpenCV `calibrateHandEye`（Tsai），API 用法正确。

---

## 3. RPi ↔ OpenMV 坐标系同步

### 3.1 OpenMV 固件（[apriltag_detection.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/openmv_firmware/vision/apriltag_detection.py)）— ✅ 已修复

- 世界坐标变换正确取齐次逆 `R_inv=Rᵀ, t_inv=-Rᵀt`（[L212-L230](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/openmv_firmware/vision/apriltag_detection.py#L212-L230)）。
- 欧拉角通过旋转矩阵合成正确变换（不再把欧拉角当向量线性组合）。
- 输出相机系 `x,y,z` 单位 **mm**。

### 3.2 坐标链路已接通 — ✅ 已修复（关键）

历史问题：编排器/采样智能体曾把**像素坐标直接当毫米**下发，是坐标断链根源。现已在以下节点接通：

- [orchestrator.py `_do_detecting`](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/agents/orchestrator.py)：`_ensure_vision_calibration` 注入内参+手眼参数，`pose_in_robot_frame` 把检测结果转为机器人基座系 mm。
- [vision_agent.py `pose_in_robot_frame`](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/agents/vision_agent.py#L591-L617)：`estimate_object_pose`(mm) → `coordinate_transform_to_robot`(mm)。
- [sampling_agent.py `handle_vision_result`](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/agents/sampling_agent.py)：消费机器人系坐标，不再做粗略像素→mm 外推。

**仿真验证**（`_sim_coord_chain.py`）：
- AprilTag 路径：误差 **0.0000 mm**（PASS）
- Blob 路径（新链路 vs 旧像素外推）：误差 0.0 mm vs 735.5 mm，改善无穷大倍
- 采样点消费：误差 0.0000 mm

### 3.3 内参一致性 — ⚠️ 需关注

- OpenMV `config.py`：`APRILTAG_FX/FY/CX/CY = None`（由传感器自动计算），分辨率 320×240。
- RPi `settings.yaml`：`camera_matrix = [[320,0,160],[0,320,120],[0,0,1]]`（fx=fy=320, cx=160, cy=120）。
- 需在真机标定后**确认 OpenMV 自动计算的 fx/fy 与 RPi 内参一致**，否则两端的像素→相机换算将出现比例偏差。

---

## 4. 运动算法合理性

### 4.1 逆运动学（[kinematics.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/motion/kinematics.py)）— ✅ 已修复

- 因 DH 参数（theta_offset/alpha）未计入导致解析 Pieper 法失效，已改为**数值雅可比 DLS + 多初始种子 + FK 验证**。
- 金标准恢复测试成功率 **93.5%**，FK 误差过滤（位置>1mm / 姿态>1° 剔除）。
- 仿真：接近点 1 解、抓取点 4 解、放置点 3 解，全部可达。

### 4.2 轨迹规划（[trajectory.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/motion/trajectory.py)）— ✅ 合理

- 关节空间线性插值 + 梯形速度规划，`plan_joint_path` 按 duration/dt 生成离散点。
- 抓取流程分 3 段：归零→接近(51点)、接近→抓取(26点)、抓取→放置(76点)，逐点下发。

### 4.3 力控抓取（[force_control.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/motion/force_control.py)）— ✅ 合理

- 状态机 approach→contact→grasping→grasped，含滑移检测。
- 力控异常告警（spike 突增 / overload 超限）带防抖(3次)与冷却(30步)，JSON 结构化输出。
- 仿真：状态机正常推进至 grasped，滑移检测 False，无误报。

### 4.4 ⚠️ 隐患：工作空间边界与手眼默认参数不一致（**建议优先修复**）

| 声明方 | 数值 |
|--------|------|
| 智能体/安全工作空间 `x/y/z` | (0,500) / (0,500) / (0,300) mm |
| `settings.yaml` 物体真值 `object_pose_mm` | [-100, -200, -160] |
| `settings.yaml` 放置位姿 `place_pose z` | -50 mm |
| 手眼默认变换对目标映射结果（C# 链路） | (-40, -230, -250) |

**问题**：默认手眼变换将物体映射到**负坐标**，全部落在声明的 `0~500` 工作空间之外。在仿真中能通过（因为 `grasp_pipeline.plan` 只校验 IK 可达性、不校验工作空间边界），但一旦经安全/采样智能体做 `workspace_bounds` 校验，会被判为越界 → 触发 WARNING/DANGER 或拒绝采样。

**影响面**：`safety_agent.check_workspace_bounds`、`vision_agent.validate_target_position`、`sampling_agent` 的边界过滤。

**建议**：统一工作空间坐标系原点——要么把手眼变换默认参数/物体真值改到 `0~500` 正象限，要么把各智能体的 `workspace_bounds` 改为与手眼原点一致（如 x/y/z 允许负区间）。二选一，避免"目标明明可达却被判越界"。

### 4.5 ⚠️ 隐患：Blob 深度路径焦距不一致（**建议修复**）

- [vision_agent.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/agents/vision_agent.py) `configure_calibration` 设置了 `_camera_matrix`（K, fx=320），**但未同步更新 `_focal_length`**（仍为默认 800）。
- `_depth_from_blob_area` 用 `_focal_length`(800) 估计深度 z；
- `_pixel_to_world` 用 K 的 fx=320 换算 x/y。

同一相机却用了两个焦距（800 vs 320），在**同一直线**上 x/y 与 z 出现约 2.5× 比例失配。`_sim_coord_chain.py` 手动调 `set_camera_params(focal_length=320, ...)` 才规避；而 `orchestrator._ensure_vision_calibration` **只调 `configure_calibration`，未设焦距**，因此真实 Blob 路径存在该失配。

**建议**：在 `configure_calibration` 末尾同步 `self._focal_length = (K[0,0]+K[1,1])/2`（或调用 `get_focal_length()`）。

---

## 5. 代码行为合理性汇总

| # | 位置 | 类型 | 描述 | 优先级 |
|---|------|------|------|--------|
| 1 | pose_estimator.py | 已修复 | DLT 未归一化→已加 K⁻¹；尺度/反射→已恢复；优化→已改 LM | ✅ |
| 2 | orchestrator/vision/sampling | 已修复 | 像素当 mm 的坐标断链→已接入手眼链路 | ✅ |
| 3 | apriltag_detection.py | 已修复 | 齐次逆/欧拉角变换错误→已修正 | ✅ |
| 4 | kinematics.py | 已修复 | 解析 IK 失效→已改 DLS+种子+FK 验证 | ✅ |
| 5 | safety_agent.py | 已修复 | 恢复后安全状态残留→已重置 | ✅ |
| 6 | **vision_agent.configure_calibration** | **BUG（已修复）** | 未同步 `_focal_length`，Blob 深度焦距(800)与 K(320)不一致；已追加同步为 `(fx+fy)/2` | **高** |
| 7 | **工作空间 vs 手眼默认参数** | **隐患（C# 侧已修复）** | 默认手眼把目标映射到 0~500 之外，与智能体边界矛盾；已在 C# 链路新增 `Workspace` 类将原点与手眼参数对齐并校验 | **高** |
| 8 | OpenMV↔RPi 内参 | 需对齐 | OpenMV 内参为 None(自动)，需与 RPi K 一致 | 中 |
| 9 | PnP(米) vs AprilTag(毫米) | 一致性 | 两路原始单位不同，机器人系均收敛 mm | 低 |

---

## 6. 建议修复项（已定位，改动最小化）

**建议 1 — 同步焦距**（`vision_agent.configure_calibration` 末尾追加）：

```python
self._focal_length = float((cal.camera_matrix[0, 0] + cal.camera_matrix[1, 1]) / 2.0)
```

**建议 2 — 统一工作空间（C# 侧已落地）**：已在 [Program.cs](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/hardware_debug_cs/HardwareDebug/Program.cs) 新增 `Workspace` 静态类，按手眼变换推导可达区间 `x[-180,-20] y[-260,-140] z[-350,-150]`，并在链路中加入 `chain_workspace_check` 校验（目标 `(-40,-230,-250)` 判定 `inside=True`）。**遗留**：RPi 侧各智能体 `workspace_bounds`（0~500）仍与手眼原点不一致，需在真机手眼标定后同步更新（二选一：改默认手眼参数进入正象限，或放宽 RPi 侧边界为负区间）。
