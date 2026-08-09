"""
Unit tests: 焦距同步逻辑 + 坐标定位边界情况.

覆盖审查报告修复点 (vision_agent.configure_calibration 同步 _focal_length)
及相机/机器人坐标系定位的边界用例:
- configure_calibration 焦距同步 (默认 320 / 自定义内参)
- Blob 深度估计与像素->世界换算使用同一内参焦距 (一致性边界)
- pixel_to_camera / camera_to_robot 往返与主点边界
- pose_in_robot_frame (AprilTag / Blob)
- 工作空间校验边界 (恰在边界 / 越界)
- PnP 输出单位(米) -> 机器人系(毫米) 归一
"""

import sys
from pathlib import Path

import numpy as np
import pytest

# 确保项目根目录在 sys.path (与 test_whitebox_core.py 一致)
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from rpi_control.agents.vision_agent import VisionAgent
from rpi_control.vision.calibration import CameraCalibration

# 与 settings.yaml grasp.camera_matrix 一致
K_DEFAULT = np.array([[320.0, 0, 160.0], [0, 320.0, 120.0], [0, 0, 1.0]])
R_DEFAULT = np.array([[1.0, 0, 0], [0, -1.0, 0], [0, 0, -1.0]])
T_DEFAULT = np.array([-100.0, -200.0, 50.0])


# =============================================================================
# 1. configure_calibration 焦距同步 (修复点)
# =============================================================================


def test_focal_length_synced_from_default_intrinsics():
    """默认内参 fx=fy=320 -> _focal_length 应同步为 320 (不再残留默认 800)."""
    va = VisionAgent()
    assert va._focal_length == 800.0  # 修复前默认值
    va.configure_calibration(K_DEFAULT, R_DEFAULT, T_DEFAULT)
    assert va._focal_length == pytest.approx(320.0)


def test_focal_length_synced_from_asymmetric_intrinsics():
    """非对称内参 fx=400, fy=300 -> _focal_length 应等于 (fx+fy)/2 = 350."""
    K_asy = np.array([[400.0, 0, 160.0], [0, 300.0, 120.0], [0, 0, 1.0]])
    va = VisionAgent()
    va.configure_calibration(K_asy, R_DEFAULT, T_DEFAULT)
    assert va._focal_length == pytest.approx(350.0)


def test_camera_matrix_also_synced():
    """configure_calibration 应同时设置 _camera_matrix 供 _pixel_to_world 使用."""
    va = VisionAgent()
    va.configure_calibration(K_DEFAULT, R_DEFAULT, T_DEFAULT)
    assert va._camera_matrix is not None
    assert va._camera_matrix[0, 0] == pytest.approx(320.0)
    assert va.calibration.is_hand_eye_calibrated()


# =============================================================================
# 2. 深度估计与像素->世界 焦距一致性 (修复点边界)
# =============================================================================


def test_blob_depth_and_pixel_world_use_same_focal():
    """修复后 Blob 路径: 深度估计用 f, 像素->世界用 K.fx, 两者必须一致,
    否则同一直线上 x/y 与 z 出现比例失配. 这里用面积推导的深度反算 x/y,
    验证与 camera_matrix.pixel_to_camera 结果一致."""
    va = VisionAgent()
    va.configure_calibration(K_DEFAULT, R_DEFAULT, T_DEFAULT)

    # 构造一个 blob: 直径 32px, 真实直径 30mm, 深度 z = 320*30/32 = 300mm
    blob_diameter_px = 32.0
    area = np.pi * (blob_diameter_px / 2.0) ** 2
    det = {"found": True, "detection": {"cx": 224.0, "cy": 152.0,
                                        "area": float(area), "confidence": 0.9}}
    pose = va.estimate_object_pose(det)
    z_est = pose["position"][2]
    assert z_est == pytest.approx(300.0, rel=0.05)

    # 关键: 深度来自面积(f=320), x/y 用 K.fx=320, 应互相自洽
    # 用 pose 的 x,y 反推与 pixel_to_camera(K) 一致
    cam = K_DEFAULT  # noqa: F841
    x_expect = (224.0 - 160.0) * z_est / 320.0  # = 60
    y_expect = (152.0 - 120.0) * z_est / 320.0  # = 30
    assert pose["position"][0] == pytest.approx(x_expect, rel=1e-6)
    assert pose["position"][1] == pytest.approx(y_expect, rel=1e-6)


def test_depth_formula_consistency_no_scale_mismatch():
    """若深度焦距与 K 不一致会放大误差, 修复后二者必须一致 (回归保护)."""
    va = VisionAgent()
    va.configure_calibration(K_DEFAULT, R_DEFAULT, T_DEFAULT)
    # 触发深度估计的内部焦距
    assert va._focal_length == va._camera_matrix[0, 0]
    assert va._focal_length == va._camera_matrix[1, 1]


# =============================================================================
# 3. 像素->相机->机器人 坐标定位边界
# =============================================================================


def test_pixel_to_camera_at_principal_point():
    """主点 (cx, cy) 处像素应映射到相机系 x=y=0, z=depth."""
    cal = CameraCalibration()
    cal.camera_matrix = K_DEFAULT
    x, y, z = cal.pixel_to_camera((160.0, 120.0), 300.0)
    assert x == pytest.approx(0.0, abs=1e-9)
    assert y == pytest.approx(0.0, abs=1e-9)
    assert z == pytest.approx(300.0)


def test_pixel_to_camera_positive_fov():
    """FOV 内像素 -> 相机前方正 z, x/y 符号符合针孔模型."""
    cal = CameraCalibration()
    cal.camera_matrix = K_DEFAULT
    x, y, z = cal.pixel_to_camera((224.0, 152.0), 300.0)
    assert z > 0
    assert x == pytest.approx(60.0, rel=1e-6)
    assert y == pytest.approx(30.0, rel=1e-6)


def test_camera_to_robot_roundtrip():
    """camera_to_robot 与手眼矩阵一致: robot = R·cam + t."""
    cal = CameraCalibration()
    cal.camera_matrix = K_DEFAULT
    cal.rotation_matrix = R_DEFAULT
    cal.translation_vector = T_DEFAULT.reshape(3, 1)
    cam = (60.0, 30.0, 300.0)
    robot = cal.camera_to_robot(cam)
    expected = R_DEFAULT @ np.array(cam) + T_DEFAULT
    assert robot == pytest.approx(tuple(expected), abs=1e-9)


def test_camera_to_robot_without_handeye_returns_none():
    """未配置手眼标定时 camera_to_robot 应返回 None (安全降级)."""
    cal = CameraCalibration()
    cal.camera_matrix = K_DEFAULT
    assert cal.camera_to_robot((1.0, 2.0, 3.0)) is None


# =============================================================================
# 4. pose_in_robot_frame (AprilTag / Blob)
# =============================================================================


def test_pose_in_robot_frame_apriltag():
    va = VisionAgent()
    va.configure_calibration(K_DEFAULT, R_DEFAULT, T_DEFAULT)
    det = {"found": True, "tags": [{"id": 0, "cx": 160, "cy": 120,
                                    "x": 60.0, "y": 30.0, "z": 300.0,
                                    "roll": 0, "pitch": 0, "yaw": 0,
                                    "confidence": 0.95}]}
    pose = va.pose_in_robot_frame(det)
    assert pose.get("frame") == "robot"
    expected = R_DEFAULT @ np.array([60.0, 30.0, 300.0]) + T_DEFAULT
    assert pose["position"] == pytest.approx(tuple(expected), abs=1e-9)


def test_pose_in_robot_frame_without_calibration_warns_and_returns_camera():
    """未接入手眼标定时, pose_in_robot_frame 应退回相机系位姿且 frame != robot."""
    va = VisionAgent()  # 不调用 configure_calibration
    det = {"found": True, "tags": [{"id": 0, "cx": 160, "cy": 120,
                                    "x": 60.0, "y": 30.0, "z": 300.0,
                                    "roll": 0, "pitch": 0, "yaw": 0,
                                    "confidence": 0.95}]}
    pose = va.pose_in_robot_frame(det)
    assert pose.get("frame") != "robot"
    assert pose["position"][0] == pytest.approx(60.0)


def test_pose_in_robot_frame_blob_roundtrip_matches_chain():
    """Blob 链路: pose 机器人系 == 手眼正向 (与 C# chain 一致)."""
    va = VisionAgent()
    va.configure_calibration(K_DEFAULT, R_DEFAULT, T_DEFAULT)
    z = 300.0
    det = {"found": True,
           "detection": {"cx": 224.0, "cy": 152.0, "area": 804.0, "confidence": 0.9}}
    pose = va.pose_in_robot_frame(det)
    # Blob 路径 x/y 由 K 换算, z 由面积估计(≈300) -> 机器人系应≈(-40,-230,-250)
    expected = R_DEFAULT @ np.array([60.0, 30.0, z]) + T_DEFAULT
    assert pose["position"] == pytest.approx(tuple(expected), abs=15.0)


# =============================================================================
# 5. 工作空间校验边界
# =============================================================================


def test_workspace_bounds_validate_boundary_inside():
    """恰在边界内的位置应通过校验."""
    va = VisionAgent()
    assert va.validate_target_position((0.0, 0.0, 0.0)) is True
    assert va.validate_target_position((500.0, 500.0, 300.0)) is True


def test_workspace_bounds_validate_just_outside():
    """恰在边界外的位置应被拒绝."""
    va = VisionAgent()
    assert va.validate_target_position((500.1, 0.0, 0.0)) is False
    assert va.validate_target_position((0.0, -0.1, 0.0)) is False
    assert va.validate_target_position((0.0, 0.0, 300.1)) is False


def test_workspace_bounds_validate_negative_outside():
    """默认工作空间 x/y/z ∈ [0, ·]: 负坐标应在名义边界内被拒绝,
    印证审查报告 §4.4 (需与手眼原点对齐后由真机标定更新边界)."""
    va = VisionAgent()
    assert va.validate_target_position((-40.0, -230.0, -250.0)) is False


# =============================================================================
# 6. 边界退化 / 异常输入
# =============================================================================


def test_pixel_to_world_without_camera_matrix_fallback():
    """未配置内参时 _pixel_to_world 走比例近似且不抛异常."""
    va = VisionAgent()  # 无内参
    x, y = va._pixel_to_world(160.0, 120.0, 300.0)
    # 图像中心处 -> 近似 (0,0)
    assert x == pytest.approx(0.0, abs=1e-6)
    assert y == pytest.approx(0.0, abs=1e-6)


def test_estimate_object_pose_empty_detection():
    """空 detection 应安全返回零位姿而不抛异常."""
    va = VisionAgent()
    pose = va.estimate_object_pose({"found": True, "detection": None})
    assert pose["position"] == (0.0, 0.0, 0.0)
    assert pose["source"] == "none"


def test_filter_outliers_single_point_unchanged():
    """不足 3 个点的异常过滤应原样返回."""
    va = VisionAgent()
    pts = [(1.0, 2.0, 3.0)]
    assert va.filter_outliers(pts) == pts


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
