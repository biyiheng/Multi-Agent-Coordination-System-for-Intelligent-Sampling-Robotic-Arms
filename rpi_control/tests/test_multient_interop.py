"""Multi-end interop tests: auth / device registry / WiFi API / hub routing.

验证多端互通服务器:
1. 鉴权流: 注册 -> 登录 -> me -> 登出
2. 设备中心: App / 硬件 注册与查询
3. WiFi API: 状态 / 扫描 / 连接 / 热点 (模拟模式)
4. WebSocket 中枢: App 与硬件端 hello 绑定 -> 命令路由 -> 遥测广播
"""

import sys
from pathlib import Path

import pytest

# Ensure the project root is on sys.path so that `rpi_control` package
# can be imported from the test runner's working directory.
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from fastapi.testclient import TestClient

from rpi_control.database.repository import db_manager
from rpi_control.web.server import app

from rpi_control.hardware import esp32_wifi


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Isolated DB + HTTP client with lifespan."""
    # 隔离数据库
    db_path = tmp_path / "interop.db"
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_manager.engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    db_manager.SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=db_manager.engine
    )
    db_manager.init_db()

    # 强制 WiFi 模拟模式 (无真实 ESP32)
    monkeypatch.setattr(esp32_wifi, "HAS_PYSERIAL", False)

    with TestClient(app) as c:
        yield c


def _register_and_login(client, username="alice", password="secret123"):
    """Register a user and return the bearer token."""
    r = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password, "role": "user"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "access_token" in data
    return data["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# 1. 鉴权流
# ===========================================================================


class TestAuthFlow:
    def test_register_login_me_logout(self, client):
        token = _register_and_login(client)

        # me
        r = client.get("/api/v1/auth/me", headers=_auth_headers(token))
        assert r.status_code == 200
        me = r.json()
        assert me["username"] == "alice"
        assert me["role"] == "user"
        assert me["enabled"] is True

        # login
        r = client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "secret123", "scope": "app"},
        )
        assert r.status_code == 200
        token2 = r.json()["access_token"]

        # logout (revokes tokens)
        r = client.post("/api/v1/auth/logout", headers=_auth_headers(token2))
        assert r.status_code == 200

        # revoked token should now be rejected
        r = client.get("/api/v1/auth/me", headers=_auth_headers(token2))
        assert r.status_code == 401

    def test_duplicate_registration_conflict(self, client):
        _register_and_login(client, username="bob")
        r = client.post(
            "/api/v1/auth/register",
            json={"username": "bob", "password": "secret123"},
        )
        assert r.status_code == 409

    def test_wrong_password_rejected(self, client):
        _register_and_login(client, username="carol")
        r = client.post(
            "/api/v1/auth/login",
            json={"username": "carol", "password": "wrongpass", "scope": "app"},
        )
        assert r.status_code == 401

    def test_protected_endpoint_requires_token(self, client):
        r = client.get("/api/v1/devices")
        assert r.status_code == 401


# ===========================================================================
# 2. 设备中心 (App / 硬件注册与查询)
# ===========================================================================


class TestDeviceRegistry:
    def test_register_and_list_devices(self, client):
        token = _register_and_login(client)

        # App 端注册
        r = client.post(
            "/api/v1/devices/register",
            json={
                "device_id": "app-alice",
                "name": "App-Alice",
                "device_type": "app",
                "client_type": "app",
                "extra": {"platform": "android", "app_version": "1.0.0"},
            },
            headers=_auth_headers(token),
        )
        assert r.status_code == 200
        dev = r.json()
        assert dev["id"] == "app-alice"
        assert dev["status"] == "online"
        assert dev["extra"]["platform"] == "android"

        # 硬件端注册
        r = client.post(
            "/api/v1/devices/register",
            json={
                "device_id": "esp32-01",
                "name": "ESP32 WiFi",
                "device_type": "esp32",
                "client_type": "hardware",
                "mac": "24:6f:28:00:00:01",
            },
            headers=_auth_headers(token),
        )
        assert r.status_code == 200

        # 列表 (按 client_type 过滤)
        r = client.get("/api/v1/devices?client_type=app", headers=_auth_headers(token))
        assert r.status_code == 200
        apps = r.json()
        assert len(apps) == 1
        assert apps[0]["id"] == "app-alice"

        # 单个设备
        r = client.get("/api/v1/devices/esp32-01", headers=_auth_headers(token))
        assert r.status_code == 200
        assert r.json()["mac"] == "24:6f:28:00:00:01"

        # 心跳更新 (保持 online 并刷新 last_seen)
        r = client.post(
            "/api/v1/devices/register",
            json={"device_id": "esp32-01", "online": True},
            headers=_auth_headers(token),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "online"

        # 标记离线
        r = client.post(
            "/api/v1/devices/esp32-01/offline", headers=_auth_headers(token)
        )
        assert r.status_code == 200
        r = client.get("/api/v1/devices/esp32-01", headers=_auth_headers(token))
        assert r.json()["status"] == "offline"


# ===========================================================================
# 3. WiFi API (模拟模式)
# ===========================================================================


class TestWifiApi:
    def test_wifi_status_and_scan(self, client):
        token = _register_and_login(client)
        h = _auth_headers(token)

        r = client.get("/api/v1/wifi/status", headers=h)
        assert r.status_code == 200
        status = r.json()
        assert "esp32_present" in status
        assert "mode" in status

        r = client.get("/api/v1/wifi/scan", headers=h)
        assert r.status_code == 200
        results = r.json()
        assert isinstance(results, list)
        assert any("ssid" in ap for ap in results)

    def test_wifi_connect_and_hotspot(self, client):
        token = _register_and_login(client)
        h = _auth_headers(token)

        r = client.post(
            "/api/v1/wifi/connect",
            json={"ssid": "HomeWiFi", "password": "12345678"},
            headers=h,
        )
        assert r.status_code == 200
        result = r.json()
        assert result["status"] == "ok" or result["status"] == "error"

        r = client.post(
            "/api/v1/wifi/hotspot",
            json={"ssid": "SmartArm-Ap", "password": "", "channel": 6},
            headers=h,
        )
        assert r.status_code == 200


# ===========================================================================
# 4. WebSocket 多端互通中枢
# ===========================================================================


class TestHubRouting:
    def _recv_until(self, ws, expected_type, timeout_ms=5000):
        """Receive JSON messages until the expected type arrives."""
        import time

        start = time.monotonic()
        while time.monotonic() - start < timeout_ms / 1000.0:
            msg = ws.receive_json()
            if msg.get("type") == expected_type:
                return msg
        raise AssertionError(f"no {expected_type} received within {timeout_ms}ms")

    def test_command_routing_between_app_and_hardware(self, client):
        with client.websocket_connect("/ws/hub") as app_ws:
            # App 端 hello
            app_ws.send_json({
                "type": "hello",
                "device_id": "app-alice",
                "client_type": "app",
                "device_type": "app",
                "role": "controller",
                "name": "App-Alice",
            })
            welcome = self._recv_until(app_ws, "welcome")
            assert welcome["device_id"] == "app-alice"
            # 绑定后的广播
            self._recv_until(app_ws, "device_status")

            with client.websocket_connect("/ws/hub") as hw_ws:
                # 硬件端 hello
                hw_ws.send_json({
                    "type": "hello",
                    "device_id": "esp32-01",
                    "client_type": "hardware",
                    "device_type": "esp32",
                    "role": "observer",
                })
                self._recv_until(hw_ws, "welcome")
                # 硬件上线广播: 硬件端与 App 端都应收到
                self._recv_until(hw_ws, "device_status")
                self._recv_until(app_ws, "device_status")

                # App -> 硬件 命令路由
                app_ws.send_json({
                    "type": "command",
                    "target": "esp32-01",
                    "action": "wifi.scan",
                    "payload": {},
                    "seq": 1001,
                })

                # 硬件端收到命令
                cmd = self._recv_until(hw_ws, "command")
                assert cmd["action"] == "wifi.scan"
                assert cmd["from"] == "app-alice"

                # App 端收到确认
                ack = self._recv_until(app_ws, "command_ack")
                assert ack["seq"] == 1001
                assert ack["status"] == "ok"
                assert "esp32-01" in ack["targets"]

                # 硬件 -> App 遥测广播
                hw_ws.send_json({
                    "type": "telemetry",
                    "data": {"temperature": 31.5, "voltage": 12.1},
                })
                tele = self._recv_until(app_ws, "telemetry")
                assert tele["from"] == "esp32-01"
                assert tele["data"]["temperature"] == 31.5

    def test_hub_offline_on_disconnect(self, client):
        token = _register_and_login(client)
        with client.websocket_connect("/ws/hub") as ws:
            ws.send_json({
                "type": "hello",
                "device_id": "app-bob",
                "client_type": "app",
            })
            self._recv_until(ws, "welcome")
            self._recv_until(ws, "device_status")

            # 断连后设备应标记离线
        r = client.get("/api/v1/devices/app-bob", headers=_auth_headers(token))
        assert r.json()["status"] == "offline"


# ===========================================================================
# 5. ESP32 AT 超时回归测试
# ===========================================================================


class TestESP32Timeout:
    """回归测试: _read_until 必须在超时后返回, 而不是无限循环 (修复 time.monotonic 死循环)。"""

    def test_read_until_timeout_bounded(self):
        import asyncio
        import time

        esp = esp32_wifi.ESP32Interface()

        # 模拟一个永远不返回数据的串口, 强制走超时路径
        class FakeSerial:
            is_open = True
            in_waiting = 0

            def read(self, n):
                return b""

        esp._serial = FakeSerial()
        esp._connected = True

        async def run():
            start = time.monotonic()
            final, lines = await esp._read_until(("OK",), timeout=0.5)
            elapsed = time.monotonic() - start
            return final, lines, elapsed

        final, lines, elapsed = asyncio.run(run())
        assert final == ""
        assert lines == []
        # 修复前该调用会无限循环; 修复后应在 ~0.6s 内返回
        assert elapsed < 2.0

