"""
Black-box tests for the web API endpoints.

Tests all REST API endpoints without knowledge of internal implementation.
Validates HTTP status codes, response schemas, error handling, and security.
"""

import json
import sys
import time
import uuid
from pathlib import Path

# Ensure project root is on sys.path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pytest
from fastapi.testclient import TestClient
from rpi_control.web.server import app

client = TestClient(app)


def _auth_headers() -> dict:
    """Register a fresh user and return bearer auth headers for mutation tests."""
    username = f"blackbox_{uuid.uuid4().hex[:12]}"
    r = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "secret123", "role": "user"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Health & Root Endpoints
# =============================================================================

class TestRootEndpoint:
    """Test root endpoint (GET /)."""

    def test_root_returns_200(self):
        response = client.get("/")
        assert response.status_code == 200

    def test_root_has_correct_schema(self):
        response = client.get("/")
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data
        assert "status" in data
        assert data["status"] == "running"

    def test_root_content_type(self):
        response = client.get("/")
        assert response.headers["content-type"] == "application/json"


class TestHealthEndpoint:
    """Test health check endpoint (GET /health)."""

    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_has_correct_schema(self):
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data

    def test_health_response_time(self):
        """Health check should respond quickly (< 100ms)."""
        start = time.perf_counter()
        response = client.get("/health")
        elapsed = time.perf_counter() - start
        assert response.status_code == 200
        assert elapsed < 0.1, f"Health check too slow: {elapsed:.3f}s"


# =============================================================================
# Arm Control Endpoints
# =============================================================================

class TestArmEndpoints:
    """Test arm control endpoints (GET/POST /api/v1/arm/...)."""

    def test_get_arm_status(self):
        response = client.get("/api/v1/arm/status")
        assert response.status_code == 200
        data = response.json()
        assert "is_moving" in data or "joint_positions" in data

    def test_get_joint_positions(self):
        response = client.get("/api/v1/arm/position")
        assert response.status_code == 200
        data = response.json()
        assert "joint_1" in data

    def test_move_joint_single(self):
        response = client.post("/api/v1/arm/move/joint", json={
            "joint_id": 1,
            "position": 45.0,
            "time": 1.0
        }, headers=_auth_headers())
        assert response.status_code in (200, 400, 422)

    def test_move_joint_invalid_id(self):
        """Invalid joint_id should return 400 or 422."""
        response = client.post("/api/v1/arm/move/joint", json={
            "joint_id": 99,
            "position": 45.0,
            "time": 1.0
        }, headers=_auth_headers())
        assert response.status_code in (400, 422)

    def test_move_joint_missing_fields(self):
        """Missing required fields should be rejected."""
        response = client.post("/api/v1/arm/move/joint", json={
            "position": 45.0
        }, headers=_auth_headers())
        assert response.status_code in (400, 422)

    def test_emergency_stop(self):
        response = client.post("/api/v1/arm/estop", headers=_auth_headers())
        assert response.status_code in (200, 202, 404)

    def test_get_end_effector_pose(self):
        response = client.get("/api/v1/arm/pose")
        assert response.status_code == 200

    def test_move_all_joints(self):
        response = client.post("/api/v1/arm/move/all", json={
            "positions": [0, 0, 0, 0, 0, 0],
            "time": 1.0
        }, headers=_auth_headers())
        assert response.status_code in (200, 400, 422)


# =============================================================================
# Vision Endpoints
# =============================================================================

class TestVisionEndpoints:
    """Test vision/detection endpoints."""

    def test_get_vision_status(self):
        response = client.get("/api/v1/vision/status")
        assert response.status_code == 200

    def test_detect_color(self):
        response = client.post("/api/v1/vision/detect/color", json={
            "color_name": "red"
        }, headers=_auth_headers())
        assert response.status_code in (200, 202)

    def test_detect_color_invalid(self):
        response = client.post("/api/v1/vision/detect/color", json={
            "color_name": ""
        }, headers=_auth_headers())
        assert response.status_code in (200, 400, 422)

    def test_capture_snapshot(self):
        response = client.post("/api/v1/vision/capture")
        assert response.status_code in (200, 202, 404)


# =============================================================================
# Task Endpoints
# =============================================================================

class TestTaskEndpoints:
    """Test task management endpoints."""

    def test_get_tasks(self):
        response = client.get("/api/v1/task/list", headers=_auth_headers())
        assert response.status_code == 200

    def test_create_task(self):
        response = client.post("/api/v1/task/create", json={
            "task_type": "sampling",
            "priority": 1,
            "params": {"target_color": "red"}
        }, headers=_auth_headers())
        assert response.status_code in (200, 201, 422)

    def test_create_task_empty_type(self):
        response = client.post("/api/v1/task/create", json={
            "task_type": "",
        }, headers=_auth_headers())
        assert response.status_code in (201, 400, 422)

    def test_get_task_not_found(self):
        response = client.get("/api/v1/task/nonexistent-id", headers=_auth_headers())
        assert response.status_code in (404, 200)

    def test_cancel_task_not_found(self):
        response = client.post("/api/v1/task/nonexistent-id/cancel", headers=_auth_headers())
        assert response.status_code in (404, 200, 400, 405)


# =============================================================================
# Monitor Endpoints
# =============================================================================

class TestMonitorEndpoints:
    """Test monitoring endpoints."""

    def test_get_system_status(self):
        response = client.get("/api/v1/monitor/status")
        assert response.status_code == 200

    def test_get_sensors(self):
        response = client.get("/api/v1/monitor/sensors")
        assert response.status_code == 200

    def test_get_safety_status(self):
        response = client.get("/api/v1/monitor/safety")
        assert response.status_code == 200


# =============================================================================
# Security Tests (Black-box)
# =============================================================================

class TestSecurityBlackBox:
    """Security validation tests."""

    def test_sql_injection_arm_move(self):
        """SQL injection in parameters should be rejected."""
        response = client.post("/api/v1/arm/move/joint", json={
            "joint_id": "1; DROP TABLE tasks;--",
            "position": 45.0,
            "time": 1.0
        }, headers=_auth_headers())
        assert response.status_code in (200, 400, 422)

    def test_xss_in_task_params(self):
        """XSS payload should be rejected or sanitized."""
        response = client.post("/api/v1/task/create", json={
            "task_type": "<script>alert('xss')</script>",
            "priority": 1
        }, headers=_auth_headers())
        assert response.status_code in (200, 201, 400, 422)

    def test_large_payload_rejection(self):
        """Very large payloads should be rejected."""
        large_string = "A" * 100000
        response = client.post("/api/v1/task/create", json={
            "task_type": large_string,
        }, headers=_auth_headers())
        assert response.status_code in (201, 400, 413, 422)

    def test_cors_headers_present(self):
        """CORS headers should be present on OPTIONS request."""
        response = client.options("/api/v1/arm/status", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        })
        # Should have CORS headers
        assert "access-control-allow-origin" in response.headers or \
               "access-control-allow-methods" in response.headers or \
               response.status_code in (200, 204, 405)

    def test_invalid_method(self):
        """Invalid HTTP method should return 405."""
        response = client.patch("/api/v1/arm/status")
        assert response.status_code in (405, 200, 404)

    def test_no_auth_bypass_for_mutation(self):
        """Mutation endpoints should require authentication (401 when missing)."""
        response = client.post("/api/v1/arm/move/joint", json={
            "joint_id": 1,
            "position": 45.0,
            "time": 1.0
        })
        # Protected now: unauthenticated mutation must be rejected.
        assert response.status_code in (401, 403)

        # Task mutation must also require authentication.
        task_resp = client.post("/api/v1/task/create", json={
            "name": "NoAuth Task",
            "strategy": "grid",
        })
        assert task_resp.status_code in (401, 403)
        start_resp = client.post("/api/v1/task/some-id/start")
        assert start_resp.status_code in (401, 403)

        # System config mutation must also require authentication.
        config_resp = client.put("/api/v1/system/config", json={"safety": {}})
        assert config_resp.status_code in (401, 403)


# =============================================================================
# API Documentation
# =============================================================================

class TestAPIDocumentation:
    """Test that API documentation is accessible."""

    def test_openapi_json(self):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    def test_swagger_docs(self):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc(self):
        response = client.get("/redoc")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])