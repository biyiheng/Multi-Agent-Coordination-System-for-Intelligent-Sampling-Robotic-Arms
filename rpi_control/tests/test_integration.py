"""Integration tests for the sampling robotic arm system."""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure the project root is on sys.path so that `rpi_control` package
# can be imported from the test runner's working directory.
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from fastapi.testclient import TestClient

from rpi_control.web.server import app
from rpi_control.web.models.task import TaskCreate, TaskStatus, Bounds
from rpi_control.web.models.status import ArmStatus, SensorData, SafetyStatus


class TestAPIEndpoints(unittest.TestCase):
    """Test REST API endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_root_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Intelligent Sampling Robotic Arm API")

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")

    def test_docs_available(self):
        response = self.client.get("/docs")
        self.assertEqual(response.status_code, 200)

    def test_openapi_json(self):
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("openapi", response.json())


class TestArmEndpoints(unittest.TestCase):
    """Test arm control API endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_get_arm_status(self):
        response = self.client.get("/api/v1/arm/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("joint_positions", data)
        self.assertIn("ee_pose", data)

    def test_get_position(self):
        response = self.client.get("/api/v1/arm/position")
        self.assertEqual(response.status_code, 200)

    def test_get_pose(self):
        response = self.client.get("/api/v1/arm/pose")
        self.assertEqual(response.status_code, 200)

    def test_move_joint(self):
        response = self.client.post("/api/v1/arm/move/joint", json={
            "joint_id": 1, "position": 45.0, "time": 1.0
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_move_joint_invalid(self):
        response = self.client.post("/api/v1/arm/move/joint", json={
            "joint_id": 7, "position": 45.0
        })
        self.assertEqual(response.status_code, 400)

    def test_move_cartesian(self):
        response = self.client.post("/api/v1/arm/move/cartesian", json={
            "x": 200, "y": 100, "z": 50, "roll": 0, "pitch": 0, "yaw": 0
        })
        self.assertEqual(response.status_code, 200)

    def test_move_all(self):
        response = self.client.post("/api/v1/arm/move/all", json={
            "positions": [10, 20, 30, 40, 50, 60], "time": 1.0
        })
        self.assertEqual(response.status_code, 200)

    def test_move_all_invalid(self):
        response = self.client.post("/api/v1/arm/move/all", json={
            "positions": [10, 20, 30], "time": 1.0
        })
        self.assertEqual(response.status_code, 400)

    def test_stop(self):
        response = self.client.post("/api/v1/arm/stop")
        self.assertEqual(response.status_code, 200)

    def test_estop(self):
        response = self.client.post("/api/v1/arm/estop")
        self.assertEqual(response.status_code, 200)

    def test_origin(self):
        response = self.client.post("/api/v1/arm/origin")
        self.assertEqual(response.status_code, 200)

    def test_gripper_open(self):
        response = self.client.post("/api/v1/arm/gripper/open")
        self.assertEqual(response.status_code, 200)

    def test_gripper_close(self):
        response = self.client.post("/api/v1/arm/gripper/close", json={"force": 60})
        self.assertEqual(response.status_code, 200)

    def test_workspace(self):
        response = self.client.get("/api/v1/arm/workspace")
        self.assertEqual(response.status_code, 200)
        self.assertIn("points", response.json())


class TestVisionEndpoints(unittest.TestCase):
    """Test vision API endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_get_vision_status(self):
        response = self.client.get("/api/v1/vision/status")
        self.assertEqual(response.status_code, 200)

    def test_detect_color(self):
        response = self.client.post("/api/v1/vision/detect/color", json={
            "color_name": "red"
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("detections", response.json())

    def test_detect_unknown_color(self):
        response = self.client.post("/api/v1/vision/detect/color", json={
            "color_name": "purple"
        })
        self.assertEqual(response.status_code, 400)

    def test_detect_apriltag(self):
        response = self.client.post("/api/v1/vision/detect/apriltag", json={})
        self.assertEqual(response.status_code, 200)
        self.assertIn("tags", response.json())

    def test_classify(self):
        response = self.client.post("/api/v1/vision/classify", json={})
        self.assertEqual(response.status_code, 200)
        self.assertIn("top_prediction", response.json())

    def test_inspect(self):
        response = self.client.post("/api/v1/vision/inspect", json={})
        self.assertEqual(response.status_code, 200)
        self.assertIn("inspection", response.json())

    def test_set_threshold(self):
        response = self.client.post("/api/v1/vision/threshold", json={
            "color": "red",
            "threshold": {"h_min": 0, "h_max": 15, "s_min": 100, "s_max": 255, "v_min": 100, "v_max": 255}
        })
        self.assertEqual(response.status_code, 200)


class TestTaskEndpoints(unittest.TestCase):
    """Test task management API endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_create_task(self):
        response = self.client.post("/api/v1/task/create", json={
            "name": "Test Task",
            "strategy": "grid",
            "bounds": {"x_min": 0, "x_max": 100, "y_min": 0, "y_max": 100, "z": 10},
            "parameters": {"step": 50},
            "priority": 5,
        })
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["name"], "Test Task")
        self.assertIn("id", data)

    def test_list_tasks(self):
        response = self.client.get("/api/v1/task/list")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_get_task(self):
        # Create first
        create_resp = self.client.post("/api/v1/task/create", json={
            "name": "Get Test",
            "strategy": "random",
            "bounds": {"x_min": 0, "x_max": 50, "y_min": 0, "y_max": 50, "z": 5},
            "parameters": {"count": 10},
            "priority": 3,
        })
        task_id = create_resp.json()["id"]

        response = self.client.get(f"/api/v1/task/{task_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Get Test")

    def test_task_not_found(self):
        response = self.client.get("/api/v1/task/nonexistent-id")
        self.assertEqual(response.status_code, 404)

    def test_task_lifecycle(self):
        # Create
        create_resp = self.client.post("/api/v1/task/create", json={
            "name": "Lifecycle Task",
            "strategy": "grid",
            "bounds": {"x_min": 0, "x_max": 100, "y_min": 0, "y_max": 100, "z": 10},
            "parameters": {"step": 50},
            "priority": 1,
        })
        task_id = create_resp.json()["id"]

        # Start
        start_resp = self.client.post(f"/api/v1/task/{task_id}/start")
        self.assertEqual(start_resp.status_code, 200)

        # Pause
        pause_resp = self.client.post(f"/api/v1/task/{task_id}/pause")
        self.assertEqual(pause_resp.status_code, 200)

        # Resume
        resume_resp = self.client.post(f"/api/v1/task/{task_id}/resume")
        self.assertEqual(resume_resp.status_code, 200)

        # Progress
        progress_resp = self.client.get(f"/api/v1/task/{task_id}/progress")
        self.assertEqual(progress_resp.status_code, 200)

        # Cancel
        cancel_resp = self.client.post(f"/api/v1/task/{task_id}/cancel")
        self.assertEqual(cancel_resp.status_code, 200)

        # Delete
        delete_resp = self.client.delete(f"/api/v1/task/{task_id}")
        self.assertEqual(delete_resp.status_code, 200)


class TestMonitorEndpoints(unittest.TestCase):
    """Test monitoring API endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_get_system_status(self):
        response = self.client.get("/api/v1/monitor/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("arm", data)
        self.assertIn("sensors", data)
        self.assertIn("safety", data)

    def test_get_sensors(self):
        response = self.client.get("/api/v1/monitor/sensors")
        self.assertEqual(response.status_code, 200)

    def test_get_safety(self):
        response = self.client.get("/api/v1/monitor/safety")
        self.assertEqual(response.status_code, 200)

    def test_get_logs(self):
        response = self.client.get("/api/v1/monitor/logs?limit=10")
        self.assertEqual(response.status_code, 200)
        self.assertIn("logs", response.json())

    def test_get_statistics(self):
        response = self.client.get("/api/v1/monitor/statistics")
        self.assertEqual(response.status_code, 200)

    def test_health(self):
        response = self.client.get("/api/v1/monitor/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")


class TestIntegration(unittest.TestCase):
    """End-to-end integration tests."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_sampling_workflow(self):
        """Test end-to-end sampling workflow."""
        # 1. Create task
        create_resp = self.client.post("/api/v1/task/create", json={
            "name": "Integration Test Task",
            "strategy": "grid",
            "bounds": {"x_min": 0, "x_max": 100, "y_min": 0, "y_max": 100, "z": 10},
            "parameters": {"step": 50},
            "priority": 5,
        })
        self.assertEqual(create_resp.status_code, 201)
        task_id = create_resp.json()["id"]

        # 2. Check arm status
        arm_resp = self.client.get("/api/v1/arm/status")
        self.assertEqual(arm_resp.status_code, 200)

        # 3. Check vision
        vision_resp = self.client.get("/api/v1/vision/status")
        self.assertEqual(vision_resp.status_code, 200)

        # 4. Start task
        start_resp = self.client.post(f"/api/v1/task/{task_id}/start")
        self.assertEqual(start_resp.status_code, 200)

        # 5. Cancel task
        cancel_resp = self.client.post(f"/api/v1/task/{task_id}/cancel")
        self.assertEqual(cancel_resp.status_code, 200)

        # 6. Delete task
        delete_resp = self.client.delete(f"/api/v1/task/{task_id}")
        self.assertEqual(delete_resp.status_code, 200)

    def test_vision_motion_pipeline(self):
        """Test vision + motion pipeline."""
        # Detect color
        detect_resp = self.client.post("/api/v1/vision/detect/color", json={
            "color_name": "red"
        })
        self.assertEqual(detect_resp.status_code, 200)
        detections = detect_resp.json()["detections"]
        self.assertTrue(len(detections) > 0)

        # Move to detected position
        if detections:
            d = detections[0]
            move_resp = self.client.post("/api/v1/arm/move/cartesian", json={
                "x": d["x"], "y": d["y"], "z": 50,
                "roll": 0, "pitch": 0, "yaw": 0,
            })
            self.assertEqual(move_resp.status_code, 200)

    def test_safety_integration(self):
        """Test safety system integration."""
        # Check initial safety status
        safety_resp = self.client.get("/api/v1/monitor/safety")
        self.assertEqual(safety_resp.status_code, 200)
        self.assertEqual(safety_resp.json()["level"], "normal")

        # Trigger estop
        self.client.post("/api/v1/arm/estop")

        # Verify safety status reflects estop
        arm_resp = self.client.get("/api/v1/arm/status")
        self.assertTrue(arm_resp.json()["safety_status"]["emergency_stop"])


if __name__ == "__main__":
    unittest.main()