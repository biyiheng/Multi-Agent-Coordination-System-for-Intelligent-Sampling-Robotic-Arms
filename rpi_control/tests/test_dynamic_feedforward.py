"""
动力学前馈模块数值稳定性与单元测试 (S3).

覆盖:
1. 重力补偿单位正确性 (物理量级校验, 修复 1e-6 单位 bug)。
2. 摩擦模型零速/大速度下的有界性。
3. 极端工况 (NaN/Inf 输入) 不会永久污染低通滤波。
4. 参数缺失时的健壮性 (link_params 短于关节数不崩溃)。
"""

import math
import unittest

import numpy as np

from rpi_control.motion.dynamic_feedforward import (
    DynamicFeedforwardController, DynamicParams, FrictionParams,
    LinkDynamicParams, default_dynamic_params)
from rpi_control.motion.kinematics import NUM_JOINTS


class TestGravityUnit(unittest.TestCase):
    """重力补偿必须为物理量级 (N·mm), 而非 ~1e-4 的近零值."""

    def setUp(self):
        self.params = default_dynamic_params()
        self.ctrl = DynamicFeedforwardController(params=self.params)

    def test_gravity_magnitude_physical(self):
        """肩关节 (水平展开) 重力项应达数百~数千 N·mm 量级."""
        q = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        G = self.ctrl.compute_gravity(q)
        # 至少最远端有意义的连杆应有明显重力项
        self.assertTrue(np.any(np.abs(G) > 50.0),
                        f"Gravity should be physically significant, got {G}")
        # 结果必须有限
        self.assertTrue(np.all(np.isfinite(G)))

    def test_gravity_symmetry(self):
        """重力项对关节角应连续(非跳变): 微小扰动不应产生巨大差异."""
        q = np.array([0.1, 0.2, 0.3, 0.0, 0.0, 0.0])
        G1 = self.ctrl.compute_gravity(q)
        G2 = self.ctrl.compute_gravity(q + 1e-4)
        self.assertTrue(np.max(np.abs(G1 - G2)) < 100.0)


class TestFrictionStability(unittest.TestCase):
    def test_zero_speed_bounded(self):
        """零速附近摩擦必须平滑有界, 无 sign() 跳变导致抖振."""
        ctrl = DynamicFeedforwardController(params=default_dynamic_params())
        vals = [ctrl.compute_friction(np.array([v, 0, 0, 0, 0, 0]))[0]
                for v in np.linspace(-0.2, 0.2, 21)]
        # 单调且平滑
        self.assertTrue(np.all(np.abs(np.diff(vals)) < 30.0),
                        f"Friction should be smooth near zero, jumps={np.diff(vals)}")

    def test_high_speed_bounded(self):
        """极大速度下摩擦仍应有限(粘滞项线性增长但无发散)."""
        ctrl = DynamicFeedforwardController(params=default_dynamic_params())
        F = ctrl.compute_friction(np.array([1e6, -1e6, 0, 0, 0, 0]))
        self.assertTrue(np.all(np.isfinite(F)))
        # tanh 有界, 库仑+stribeck 分量 < 幅值之和
        self.assertTrue(abs(F[0]) < 1e9)


class TestExtremeConditionFilter(unittest.TestCase):
    def test_nan_does_not_poison_filter(self):
        """单次 NaN 输入后, 下一次正常输入不应输出 NaN (滤波不中毒)."""
        ctrl = DynamicFeedforwardController(params=default_dynamic_params())
        q = np.array([0.1, 0.2, 0.3, 0.0, 0.0, 0.0])
        qd = np.zeros(NUM_JOINTS)
        # 正常
        ctrl.compute_smoothed(q, qd)
        # NaN 输入 -> 返回零且复位滤波
        q_nan = q.copy()
        q_nan[0] = float("nan")
        out_nan = ctrl.compute_smoothed(q_nan, qd)
        self.assertTrue(np.all(np.isfinite(out_nan)))
        # 恢复正常输入, 输出必须仍然有限 (未被污染)
        out_ok = ctrl.compute_smoothed(q, qd)
        self.assertTrue(np.all(np.isfinite(out_ok)))

    def test_inf_input_finite_output(self):
        ctrl = DynamicFeedforwardController(params=default_dynamic_params())
        q = np.array([float("inf"), 0.2, 0.3, 0.0, 0.0, 0.0])
        qd = np.zeros(NUM_JOINTS)
        out = ctrl.compute_smoothed(q, qd)
        self.assertTrue(np.all(np.isfinite(out)))


class TestPartialParamsRobust(unittest.TestCase):
    def test_short_link_params_no_crash(self):
        """link_params 少于关节数时不应 IndexError."""
        params = DynamicParams(link_params=[LinkDynamicParams(mass_kg=0.5)])
        ctrl = DynamicFeedforwardController(params=params)
        q = np.array([0.1, 0.2, 0.3, 0.0, 0.0, 0.0])
        G = ctrl.compute_gravity(q)  # 不应崩溃
        self.assertEqual(G.shape, (NUM_JOINTS,))
        self.assertTrue(np.all(np.isfinite(G)))


class TestIdentification(unittest.TestCase):
    def test_friction_identification(self):
        """稳态回归应恢复库仑+粘滞系数."""
        ctrl = DynamicFeedforwardController(params=default_dynamic_params())
        samples = [(v, 20.0 * math.copysign(1, v) + 2.0 * v)
                   for v in (-2, -1, -0.5, 0.5, 1, 2)]
        p = ctrl.identify_friction_from_steady(samples)
        self.assertAlmostEqual(p.coulomb_nmm, 20.0, delta=0.5)
        self.assertAlmostEqual(p.viscous_nmm_per_rads, 2.0, delta=0.5)


if __name__ == "__main__":
    unittest.main()
