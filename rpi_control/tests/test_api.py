"""Integration tests for REST API endpoints."""

import json
import sys
import uuid
from pathlib import Path

import pytest

# Ensure the project root is on sys.path so that `rpi_control` package
# can be imported from the test runner's working directory.
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from fastapi.testclient import TestClient

from rpi_control.web.server import app

client = TestClient(app)


def _auth_headers() -> dict:
    """Register a fresh user and return bearer auth headers for mutation tests."""
    username = f"testapi_{uuid.uuid4().hex[:12]}"
    r = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "secret123", "role": "user"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestHealthEndpoints:
    """Tests for health and status endpoints."""

    def test_root_endpoint(self):
        """Test the root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["status"] == "running"

    def test_health_check(self):
        """Test the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_api_docs_available(self):
        """Test that OpenAPI docs are available."""
        response = client.get("/docs")
        assert response.status_code == 200

        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data


class TestArmEndpoints:
    """Tests for arm control API endpoints."""

    def test_get_arm_status(self):
        """Test getting arm status."""
        response = client.get("/api/v1/arm/status")
        assert response.status_code == 200
        data = response.json()
        assert "joint_positions" in data or "is_moving" in data

    def test_get_joint_positions(self):
        """Test getting joint positions."""
        response = client.get("/api/v1/arm/position")
        assert response.status_code == 200

    def test_get_end_effector_pose(self):
        """Test getting end-effector pose."""
        response = client.get("/api/v1/arm/pose")
        assert response.status_code == 200

    def test_emergency_stop(self):
        """Test emergency stop endpoint."""
        response = client.post("/api/v1/arm/estop", headers=_auth_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_return_to_origin(self):
        """Test return to origin endpoint."""
        response = client.post("/api/v1/arm/origin", headers=_auth_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_stop_arm(self):
        """Test soft stop endpoint."""
        response = client.post("/api/v1/arm/stop", headers=_auth_headers())
        assert response.status_code == 200

    def test_move_single_joint(self):
        """Test moving a single joint."""
        response = client.post(
            "/api/v1/arm/move/joint",
            json={"joint_id": 1, "position": 90.0, "time": 1.0},
            headers=_auth_headers(),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_move_single_joint_invalid(self):
        """Test moving a single joint with invalid ID."""
        response = client.post(
            "/api/v1/arm/move/joint",
            json={"joint_id": 10, "position": 90.0, "time": 1.0},
            headers=_auth_headers(),
        )
        assert response.status_code == 400

    def test_move_all_joints(self):
        """Test moving all joints."""
        response = client.post(
            "/api/v1/arm/move/all",
            json={"positions": [1500, 1500, 1500, 1500, 1500, 1000], "time": 1.0},
            headers=_auth_headers(),
        )
        assert response.status_code == 200

    def test_move_all_joints_invalid_count(self):
        """Test moving all joints with wrong number of positions."""
        response = client.post(
            "/api/v1/arm/move/all",
            json={"positions": [1500, 1500], "time": 1.0},
            headers=_auth_headers(),
        )
        assert response.status_code == 400

    def test_open_gripper(self):
        """Test opening the gripper."""
        response = client.post("/api/v1/arm/gripper/open", headers=_auth_headers())
        assert response.status_code == 200

    def test_close_gripper(self):
        """Test closing the gripper."""
        response = client.post(
            "/api/v1/arm/gripper/close", json={"force": 50.0}, headers=_auth_headers()
        )
        assert response.status_code == 200

    def test_get_workspace(self):
        """Test getting workspace boundaries."""
        response = client.get("/api/v1/arm/workspace")
        assert response.status_code == 200
        data = response.json()
        assert "points" in data


class TestTaskEndpoints:
    """Tests for task management API endpoints."""

    def test_create_task(self):
        """Test creating a new task."""
        response = client.post(
            "/api/v1/task/create",
            json={
                "name": "Test Task",
                "strategy": "grid",
                "priority": 5,
                "bounds": {"x_min": 0, "x_max": 100, "y_min": 0, "y_max": 100, "z": 10},
                "parameters": {"spacing": 20},
            },
            headers=_auth_headers(),
        )
        assert response.status_code in [200, 201]

    def test_list_tasks(self):
        """Test listing all tasks."""
        response = client.get("/api/v1/task/list", headers=_auth_headers())
        assert response.status_code == 200

    def test_get_task_not_found(self):
        """Test getting a non-existent task."""
        response = client.get("/api/v1/task/nonexistent-id", headers=_auth_headers())
        assert response.status_code == 404


class TestVisionEndpoints:
    """Tests for vision API endpoints."""

    def test_get_vision_status(self):
        """Test getting vision system status."""
        response = client.get("/api/v1/vision/status")
        assert response.status_code == 200

    def test_detect_color(self):
        """Test color detection endpoint."""
        response = client.post(
            "/api/v1/vision/detect/color",
            json={"color": "red", "threshold": {}},
            headers=_auth_headers(),
        )
        assert response.status_code in [200, 404, 501]


class TestMonitorEndpoints:
    """Tests for monitoring API endpoints."""

    def test_get_system_status(self):
        """Test getting system status."""
        response = client.get("/api/v1/monitor/status")
        assert response.status_code == 200

    def test_get_safety_status(self):
        """Test getting safety status."""
        response = client.get("/api/v1/monitor/safety")
        assert response.status_code == 200


class TestErrorHandling:
    """Tests for API error handling."""

    def test_invalid_json(self):
        """Test sending invalid JSON."""
        h = _auth_headers()
        h["Content-Type"] = "application/json"
        response = client.post(
            "/api/v1/arm/move/joint",
            content=b"not valid json",
            headers=h,
        )
        assert response.status_code in [400, 422]

    def test_missing_required_fields(self):
        """Test sending request with missing required fields."""
        response = client.post("/api/v1/arm/move/joint", json={}, headers=_auth_headers())
        assert response.status_code in [400, 422]

    def test_nonexistent_endpoint(self):
        """Test accessing a nonexistent endpoint."""
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])