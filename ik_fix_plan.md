# IK 修复方案 — kinematics.py 逆运动学重构

## 1. 问题根因

`inverse_kinematics`（[kinematics.py](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/motion/kinematics.py#L236)）采用解析 Pieper 法，但内部 `_solve_position_ik` / `_solve_orientation_ik` 把机械臂当作**零偏置的标准平面二连杆**来解：

- DH 中 joint 1 带 `theta_offset = -90°`、joint 0 带 `alpha = 90°`（[kinematics.py L39-L46](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/motion/kinematics.py#L39-L46)）。
- 这使肩部坐标系被旋转：实测 `home`（全 0 关节角）末端位于 `(-95,-65,-145)`，即肩连杆在 θ1=0 时**竖直朝下**。
- 但解析公式假设肩连杆在 θ=0 时水平（`atan2(z',r)`），未计入 offset/扭转。

**验证结果**：IK 解与 FK 回环误差高达 100–280mm、姿态误差 ~2.83，属于系统性错误，而非个别点不可达。

## 2. 修复策略：改用数值 Jacobian IK（推荐）

不手推带偏置的解析解（易错、难维护），改用**基于 FK 的阻尼最小二乘（DLS）数值 IK**。因为 `forward_kinematics` 与 `jacobian()`（[kinematics.py L477](file:///c:/Users/毕以恒/Desktop/zidongaixiangmu/rpi_control/motion/kinematics.py#L477)）都基于真实 DH 链式计算，天然计入所有 offset/扭转，所以数值法**自动正确**。

### 核心算法

```
输入: 目标位姿 (x,y,z,roll,pitch,yaw), 初始关节 q0(=current_joints 或 home)
1. R_tgt = euler_to_R(roll,pitch,yaw)；p_tgt = (x,y,z)
2. 迭代 i = 0..N (N=100):
   a. T, _ = forward_kinematics(q)；p_cur=T[:3,3]；R_cur=T[:3,:3]
   b. 位置误差  e_p = p_tgt - p_cur                    (3)
      姿态误差  e_o = 0.5 * (R_cur.T @ R_tgt - R_tgt.T @ R_cur) 的对偶向量 (3)
      e = [e_p; e_o]                                  (6)
   c. 若 ||e|| < tol(0.5mm, 0.5°) → 收敛，返回 q
   d. J = jacobian(q)                                  (6x6，真实 DH)
   e. Δq = (JᵀJ + λ²I)⁻¹ Jᵀ e       # λ 自适应阻尼，防奇异
   f. q += Δq；夹紧到 joint_limits
   g. 若 e 增大则增大 λ，否则减小 λ
3. 收敛则再对目标 FK 回环校验，误差<1mm 才返回；
   否则尝试多组不同初始 q 扰动（肘部上/下、腕部翻转），取最优。
```

### 关键设计点

| 点 | 说明 |
|---|---|
| **姿态误差** | 用旋转矩阵对数映射（轴角）而非欧拉角差，避免万向节锁与不连续 |
| **奇异性** | DLS 用 `λ²I` 正则化，λ 自适应（e 增大→λ↑），保证数值稳定 |
| **多解** | 从不同初始姿态（`current_joints`、home、home+π 扰动）各跑一次，选出 FK 误差最小且不越限的解 |
| **回环验证** | 每个返回解都经 `forward_kinematics` 校验位置≤1mm、姿态≤1°，防止假解 |
| **接口不变** | `inverse_kinematics(target_pose, current_joints, ...)` 签名与返回类型（`List[List[float]]`）保持不变，下游无需改动 |
| **性能** | 6 关节数值 IK 通常 <30 次迭代即收敛，单次 <1ms，满足实时 |

## 3. 改动范围

- **新增** `_solve_numerical_ik(...)`（在 `inverse_kinematics` 内作为主求解器）。
- **保留** `forward_kinematics` / `jacobian` / `get_end_effector_pose` / DH 定义（均正确）。
- **保留或停用** 原 `_solve_position_ik` / `_solve_orientation_ik`（不再作为主路径；若确认无人直接调用可删除）。
- `inverse_kinematics` 改为：先用数值 IK 求多个候选 → FK 回环校验 → 按 `current_joints` 距离排序返回。

## 4. 验证方案（修复后必须通过）

1. **回环测试**：在可达工作空间内随机采样 N=200 个 (x,y,z,pitch=π/0)，对每个目标调用 `inverse_kinematics`，再用 `forward_kinematics` 校验，统计：
   - 位置误差均值/最大 < 1mm
   - 姿态误差均值/最大 < 1°
   - 成功率 > 95%
2. **联调回归**：重跑 `_sim_grasp.py`，确认"归零→接近→抓取→搬运→放置"整条链路走通。
3. **限位安全**：确认所有返回解都满足 `joint_limits`。

## 5. 备选方案（若你倾向解析法）

为 `_solve_position_ik` 手动补偿 DH 偏置（把 θ1 的 -90° offset、alpha 扭转换算进平面几何式），优点是无迭代、快；缺点是推导复杂、维护困难、且仍需完整回环验证。**默认不推荐**。

---

请审阅以上方案，确认后我将按第 2、3、4 节落地实现并跑通验证。
