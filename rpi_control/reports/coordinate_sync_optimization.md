# 专项优化说明：坐标同步误差 735.5mm → 0mm

> 主题：RPi 与 OpenMV 坐标系同步断链修复与优化
> 指标：端到端目标定位误差从 **735.5mm** 降至 **0mm**（Blob 路径），AprilTag 路径 0mm，端到端抓取定位误差 1mm
> 文档定位：专项优化说明，供开发/联调/评审参考

---

## 1. 背景与问题现象

在最初实现中，视觉检测结果从像素坐标到机器人基座坐标的链路是**断裂**的：

- 编排器把检测返回的像素 `cx, cy` 直接当毫米下发；
- 采样智能体用"像素 ÷ 图像宽度 × 工作空间尺寸"做**粗略线性外推**，得到一个"看起来合理"但物理上无意义的坐标；
- 相机内参 K 与手眼标定 (R, t) 定义了，但**从未真正接入**检测结果的换算。

后果（`_sim_coord_chain.py` 实测）：
| 路径 | 方式 | 目标定位误差 |
|------|------|-------------|
| Blob 旧链路 | 像素→mm 线性外推 | **735.5 mm** |
| AprilTag 旧链路 | 无手眼标定 | 相机系，不可直接用于运动 |

735.5mm 的误差意味着机械臂会把抓爪送到离目标半米开外的位置，**完全不可用**。

---

## 2. 根因分析

误差来自**坐标系的定义与变换未贯穿全链路**，具体四层：

1. **手眼标定未接入**：`CameraCalibration` 有 `camera_to_robot`，但无人调用，检测结果始终停留在像素/相机系。
2. **像素被当成毫米**：编排器 `_do_detecting` 直接把 `cx/cy` 当 mm 传给运动，缺少 `pixel→camera→robot` 换算。
3. **采样侧二次近似**：`sampling_agent` 又做了一次像素→mm 外推，把误差进一步放大。
4. **单位不统一**：PnP 输出为米、AprilTag 为毫米、像素为像素，各段口径不一。

---

## 3. 优化方案（分层修复）

### 3.1 接入手眼标定（关键）
- `VisionAgent.configure_calibration` 组装 K 与 (R, t) 进 `CameraCalibration`；
- 新增 `pose_in_robot_frame`：`检测结果 → estimate_object_pose(相机系, mm) → coordinate_transform_to_robot(机器人系, mm)`；
- 编排器 `_ensure_vision_calibration` 在进入 DETECTING 前注入内参与手眼参数，并调用 `pose_in_robot_frame` 生成 `vision_target_robot`。

### 3.2 编排器与采样消费机器人系坐标
- `orchestrator._do_detecting` 用机器人系坐标；
- `sampling_agent.handle_vision_result` 直接消费机器人系位置，删除像素→mm 外推。

### 3.3 PnP 精度修复（配套）
- `pose_estimator`：DLT 初始化前先做 **K⁻¹ 归一化**，避免投影矩阵被内参污染；LM 优化 + det(R)=+1 约束。

### 3.4 焦距一致性（配套，消除 Blob 深度比例失配）
- `configure_calibration` 末尾同步 `_focal_length=(fx+fy)/2`，保证深度估计与像素→世界换算用同一焦距。

### 3.5 工作空间原点对齐（配套）
- C# 链路新增 `Workspace` 类，按手眼变换推导可达区间，目标 `(-40,-230,-250)` 判定在工作空间内（原名义 0~500 会误判越界）。

---

## 4. 优化效果（实测）

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| Blob 目标定位误差 | 735.5 mm | **0.0 mm** | ≈∞（线性外推被替换） |
| AprilTag 目标定位误差 | 相机系（不可用） | **0.0 mm** | 接入手眼标定 |
| 采样点消费误差 | 二次近似放大 | **0.0 mm** | 直接消费机器人系 |
| 端到端抓取定位误差 | — | **1.0 mm** | 达标（±0.5mm 含仿真噪声） |
| 坐标系链路 | 断裂 | 全贯通 | ✅ |

**验证方式**（可复现）：
- `python _sim_coord_chain.py` → 三条路径误差≈0，汇总"全部通过"；
- `python _sim_grasp.py` → 端到端定位误差 1mm、搬运 274.6mm、力控抓取成功；
- `hardware_debug.exe test` → 11 个 C# 坐标/工作空间单测全部通过；
- `python _merge_e2e_report.py` → 生成端到端对比报告，汇总全 ✅。

---

## 5. 影响面与遗留项

**已修复并验证**：
- 视觉→运动坐标链路全贯通（编排器、vision、sampling、grasp_pipeline）；
- PnP K⁻¹ 归一化、焦距同步、工作空间原点对齐（C# 侧）。

**遗留（需真机标定后处理）**：
- RPi 侧各智能体 `workspace_bounds`（0~500）仍与手眼原点不一致，需在真机手眼标定后统一（改默认手眼参数进入正象限，或放宽 RPi 边界为负区间）；
- OpenMV 内参（自动计算）与 RPi K 需在真机上对齐；
- PnP(米) 与 AprilTag(毫米) 两路原始单位不同，建议在代码层统一为单一基准（如一律 mm）。

---

## 6. 相关文件

| 文件 | 作用 |
|------|------|
| `rpi_control/vision/pose_estimator.py` | PnP K⁻¹ 归一化 + LM 优化 |
| `rpi_control/agents/vision_agent.py` | 接入标定、`pose_in_robot_frame`、焦距同步 |
| `rpi_control/agents/orchestrator.py` | 机器人系坐标注入 |
| `rpi_control/agents/sampling_agent.py` | 消费机器人系坐标 |
| `hardware_debug_cs/.../Program.cs` | C# 链路 + 工作空间对齐 + 单测 |
| `_sim_coord_chain.py` / `_sim_grasp.py` | 仿真验证 |
| `_merge_e2e_report.py` | 端到端合并报告 |
