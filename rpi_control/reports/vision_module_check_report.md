# 视觉模块检查报告：空间坐标定位 / 坐标系同步 / 运动算法

> **文档版本**: v1.0
> **生成日期**: 2026-08-09
> **检查方式**: 静态代码审查 + 实际执行仿真验证（numpy 2.5.1 / Python 3.14）
> **涉及模块**: `rpi_control/vision/*`、`rpi_control/hardware/openmv_comm.py`、`rpi_control/agents/vision_agent.py`、`rpi_control/agents/sampling_agent.py`、`openmv_firmware/*`

---

## 一、结论速览

| # | 检查项 | 结果 | 关键依据（含实测数值） |
|---|--------|------|------------------------|
| 1 | 空间坐标定位链路（像素→相机→机器人） | ✅ **正确** | 往返误差 **0.0000 mm** |
| 2 | ICP 点云精配准 | ✅ **正确** | 配准 RMS **0.0011 mm** |
| 3 | 传送带运动补偿 | ✅ **正确** | 编码器0.5m + 延迟0.1m = **600mm** 偏移符合期望 |
| 4 | PnP 6D 位姿估计 | ❌ **有Bug** | 位置误差 **约 3×10⁷ mm（3万米）** |
| 5 | 卡尔曼滤波跟踪 | ⚠️ **不合理** | 误差仅收敛到测量噪声水平（约 **10–26 mm**），未达 ±0.5mm |
| 6 | 坐标系同步（RPi↔OpenMV） | ⚠️ **未接通** | 手眼标定/位姿估计**未接入实际运动链路**；单位 mm/m 混用 |
| 7 | 视觉→运动衔接 | ❌ **断链** | 实际采样链路使用**粗略像素→mm 近似**，绕过标定 |

---

## 二、空间坐标定位分析（重点）

### 2.1 坐标变换链路（已验证正确）

代码链路：[calibration.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/vision/calibration.py)

```
像素(u,v) + 深度Z --pixel_to_camera--> 相机坐标(Xc,Yc,Zc)
                                     --camera_to_robot(手眼T)--> 机器人基座坐标
```

仿真验证：构造手眼变换 `R_cam→robot` 与内参 K，取一个已知机器人坐标点
`(300, 250, 120)mm` 反算相机坐标 → 投影成像素 → 再经 `pixel_to_camera` + `camera_to_robot`
正向还原。**完整链路往返误差 = 0.0000 mm**，数学上完全自洽。

- [pixel_to_camera](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/vision/calibration.py#L279-L307)：针孔模型，`x=(u-cx)*Z/fx`，正确。
- [camera_to_robot](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/vision/calibration.py#L309-L326)：`T @ [x,y,z,1]`，齐次变换正确。
- [get_transform_matrix](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/vision/calibration.py#L266-L277)：由 R、t 组装 4×4，正确。
- 手眼标定 `hand_eye_calibration`（AX=XB，[calibration.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/vision/calibration.py#L201-L264)）使用 OpenCV `calibrateHandEye`，算法正确。

**结论**：坐标变换的“数学内核”没有问题，具备亚毫米精度潜力。

### 2.2 PnP 6D 位姿估计（发现问题）

代码：[pose_estimator.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/vision/pose_estimator.py#L215-L355)

仿真：注册立方体模型（8 角点，单位 m），真值位姿 `t=[0.1,0.2,0.5]`，
投影生成图像点并加 0~2px 噪声，调用 `estimate_pose_pnp`。

**实测结果（连模块自带 `__main__` 自测同样失败）**：

```
噪声0.0px -> 位置误差 19722318 mm
噪声0.5px -> 位置误差 23967398 mm
模块自测   -> 位置误差 30439334 mm (约3万米)
```

**根因**（[DLT 初始化 `_solve_pnp_dlt`](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/vision/pose_estimator.py#L274-L305)）：

DLT 直接用**像素坐标** u,v 构建方程组并解出投影矩阵 `P`，此时 `P = K·[R|t]`
（含内参 K）。但代码随后直接取 `R = P[:,:3]`、`t = P[:,3]`，把 `K·R` 当成了 `R`，
旋转与平移被内参污染 → 位姿完全错误。

**修复方向**：DLT 前先用内参把像素点归一化为相机坐标系下的点（`x=(u-cx)/fx`），
或对 `P` 做 `K⁻¹P` 分解；并核对 LM 的雅可比/旋转增量更新（当前 `_optimize_reprojection`
的简化梯度下降存在明显误差）。

### 2.3 ICP 精配准（验证正确）

代码：[refine_pose_icp](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/vision/pose_estimator.py#L361-L446)

仿真：源点云 = 立方体 8 点，经真值旋转+平移生成目标点云并叠加 0.001mm 噪声，
ICP 精配准后 **RMS = 0.0011 mm**。SVD 求解最优变换、3σ 离群点剔除、行列式校正均正确。

**结论**：ICP 实现健壮，可作为 PnP 之后的精配准环节。

---

## 三、树莓派 与 OpenMV 坐标系同步性（重点）

### 3.1 通信链路与坐标流

```
OpenMV:  detect_apriltag 输出相机系位姿 (x,y,z 单位 mm)   [apriltag_detection.py]
   │ UART (#vision:...! 协议)
   ▼
RPi:    OpenMVInterface.request_vision → 解析 JSON        [openmv_comm.py]
   ▼
        VisionAgent.estimate_object_pose → 提取 position   [vision_agent.py]
   ▼
        coordinate_transform_to_robot(手眼T)???
   ▼
        sampling_agent.handle_vision_result → 生成采样点    [sampling_agent.py]
```

### 3.2 发现的问题

#### 问题 A：手眼标定结果【未接入实际链路】

- `vision_agent.calibration` 字段在 [vision_agent.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/agents/vision_agent.py#L58) 初始化为 `None`，**全工程搜索无任何赋值**；
- `coordinate_transform_to_robot`（[vision_agent.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/agents/vision_agent.py#L513-L542)）**只定义、从未被调用**；
- `CameraCalibration` 在运行时代码中**无实例化**（仅在 `scripts/camera_calibrate.py` 校准脚本中使用）。

→ 意味着 OpenMV 得到的**相机系坐标没有经手眼变换转成机器人基座系**就往下传。

#### 问题 B：实际运动链路使用“粗略近似”而非标定

`sampling_agent.handle_vision_result`（[sampling_agent.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/agents/sampling_agent.py#L438-L473)）中：

```python
x_mm = (cx / 320.0) * (workspace_x_range)   # 像素线性映射到工作空间
y_mm = (cy / 240.0) * (workspace_y_range)
```

这是把像素坐标**直接线性外推**成工作空间坐标，**绕过了全部标定/手眼变换**，
与 2.1 中正确的手眼链路完全脱节。

#### 问题 C：单位不统一（mm vs m）

- OpenMV：`tag.x_translation()` 单位 **mm**（[apriltag_detection.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/openmv_firmware/vision/apriltag_detection.py#L105-L107)）；
- `VisionAgent.estimate_object_pose` 直接取 tag 的 x/y/z 当作 **mm**；
- 而 [pose_estimator.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/vision/pose_estimator.py) 的 PnP/ICP/Kalman/传送带补偿全部以 **米(m)** 为单位（模型点 0.05m、位移 m/s）。

同一项目中 **mm 与 m 混用且无显式换算边界**，一旦两套逻辑被接起来会直接产生 1000 倍误差。

### 3.3 正确性结论

- 协议帧（`#vision:type:data!`）与编解码：OpenMV 端 [uart_protocol.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/openmv_firmware/comm/uart_protocol.py) 与 RPi 端 [openmv_comm.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/hardware/openmv_comm.py) 两侧一致，**协议本身同步无错**；
- 但**坐标系同步（手眼变换）没有实际打通**，属于“代码有、链路没接”的断点。

---

## 四、运动算法合理性（重点）

### 4.1 传送带运动补偿（合理 ✅）

代码：[compensate_conveyor_motion](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/vision/pose_estimator.py#L467-L497)

- 位移 = 编码器增量/每米编码数 + 速度×延迟，方向沿 X 轴。
- 仿真：`(15000-10000)/10000 + 0.5*0.2 = 0.6 m`，输出补偿 x 偏移 **600mm**，**与期望完全一致**。

**注意**：假设传送带沿 X 轴，若实际布局非 X 轴需配置化。

### 4.2 卡尔曼滤波跟踪（⚠️ 不合理）

代码：[kalman_update](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/vision/pose_estimator.py#L503-L570)

仿真（匀速运动、测量噪声 σ=10mm、帧间隔 dt=0.033s）：

```
滤波误差：首帧19.9mm → 稳定在约 9–26mm（≈测量噪声水平）
```

- 滤波器**没有把误差压低到测量噪声以下**（预期应显著平滑降噪）；
- 当 dt 趋近 0（快速循环）时，速度状态无法更新，目标运动时误差**漂移增大**（曾出现 113mm）；
- 未达文档声称的 ±0.5mm 精度目标。

**根因**：过程噪声 `Q = 0.01*dt` 与测量噪声 `R=0.001` 的量级/匹配不合理，且 dt 由时间戳差计算，
在高速循环下接近 0。需要重新整定噪声矩阵并保证稳定帧率。

### 4.3 视觉→运动的衔接断链（❌）

- 运动侧实际消费视觉坐标的是 `sampling_agent`（粗略像素映射），而
  `PoseEstimator`/`SensorFusion`（6D 位姿 + 卡尔曼 + 力觉融合 + 故障检测）**完全独立、未被运动链路调用**；
- 两套视觉逻辑并存的“双轨”结构导致：复杂的位姿/滤波算法形同虚设，实际运动用的是不精确近似。

---

## 五、问题清单与修复优先级

| 优先级 | 问题 | 位置 | 建议 |
|--------|------|------|------|
| 🔴 高 | PnP 位姿解算出错（DLT 未去内参） | pose_estimator.py `_solve_pnp_dlt` | DLT 前用 K⁻¹ 归一化像素点；核对 LM 雅可比 |
| 🔴 高 | 手眼标定未接入实际链路 | vision_agent.py / 无调用点 | 在 agent 初始化中加载 `CameraCalibration`，并在 `estimate_object_pose` 后调用 `coordinate_transform_to_robot` |
| 🔴 高 | 运动链路用粗略像素→mm，绕过标定 | sampling_agent.py `handle_vision_result` | 改为消费手眼变换后的机器人坐标 |
| 🟡 中 | mm / m 单位混用 | 全项目 | 统一为 mm，或在模块边界显式换算 |
| 🟡 中 | 卡尔曼滤波不收敛、整定不合理 | pose_estimator.py `kalman_update` | 重设 Q/R、保证稳定 dt、加收敛自检 |
| 🟢 低 | 传送带方向硬编码 X 轴 | pose_estimator.py `compensate_conveyor_motion` | 方向参数化 |

---

## 六、总体结论

1. **坐标变换数学内核正确**（像素→相机→机器人往返 0 误差），但**未在实际运动链路中被使用**。
2. **PnP 存在确定性 Bug**，当前输出完全不可用（误差 3 万米），需修复后才能支撑“空间坐标定位”。
3. **坐标系同步（RPi↔OpenMV）协议层 OK，但手眼标定/位姿估计层“有实现、未接通”**，属于集成断点而非算法错误。
4. **运动算法**：传送带补偿与 ICP 合理可用；卡尔曼滤波整定不合理、未达精度目标。
5. 建议按“修 PnP → 打通手眼标定链路 → 统一单位 → 重调卡尔曼”的顺序推进，使视觉模块真正服务运动控制。
