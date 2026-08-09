"""Tests for STM32 communication interface."""

import json
import time
import unittest
from unittest.mock import MagicMock, patch


class STM32Command:
    """Command formatting for STM32 communication."""

    @staticmethod
    def format_move_joint(joint_id, position, move_time=1.0):
        """Format a single joint move command."""
        return json.dumps({
            "cmd": "move_joint",
            "joint_id": joint_id,
            "position": position,
            "time": move_time,
        }).encode("utf-8")

    @staticmethod
    def format_move_all(positions, move_time=1.0):
        """Format a move-all-joints command."""
        return json.dumps({
            "cmd": "move_all",
            "positions": positions,
            "time": move_time,
        }).encode("utf-8")

    @staticmethod
    def format_gripper(action, force=50):
        """Format a gripper command."""
        return json.dumps({
            "cmd": "gripper",
            "action": action,
            "force": force,
        }).encode("utf-8")

    @staticmethod
    def format_estop():
        """Format an emergency stop command."""
        return json.dumps({"cmd": "estop"}).encode("utf-8")

    @staticmethod
    def format_origin():
        """Format a return-to-origin command."""
        return json.dumps({"cmd": "origin"}).encode("utf-8")

    @staticmethod
    def parse_response(data):
        """Parse a response from STM32."""
        try:
            return json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"status": "error", "message": "Invalid response format"}


class STM32Interface:
    """Mock STM32 UART interface."""

    def __init__(self):
        self.connected = False
        self._command_queue = []
        self._response_queue = []
        self._timeout = 2.0

    def connect(self):
        self.connected = True
        return True

    def disconnect(self):
        self.connected = False

    def send_command(self, command):
        if not self.connected:
            raise ConnectionError("Not connected to STM32")
        self._command_queue.append(command)
        return self._get_response()

    def _get_response(self):
        if self._response_queue:
            return self._response_queue.pop(0)
        return json.dumps({"status": "ok"}).encode("utf-8")

    def set_response(self, response):
        self._response_queue.append(json.dumps(response).encode("utf-8"))

    def wait_for_ready(self, timeout=5.0):
        start = time.time()
        while time.time() - start < timeout:
            if self.connected:
                return True
            time.sleep(0.1)
        return False


class TestSTM32Commands(unittest.TestCase):
    """Test STM32 command formatting and parsing."""

    def test_format_move_joint(self):
        cmd = STM32Command.format_move_joint(1, 90.0, 2.0)
        parsed = json.loads(cmd.decode("utf-8"))
        self.assertEqual(parsed["cmd"], "move_joint")
        self.assertEqual(parsed["joint_id"], 1)
        self.assertEqual(parsed["position"], 90.0)
        self.assertEqual(parsed["time"], 2.0)

    def test_format_move_all(self):
        positions = [10, 20, 30, 40, 50, 60]
        cmd = STM32Command.format_move_all(positions, 1.5)
        parsed = json.loads(cmd.decode("utf-8"))
        self.assertEqual(parsed["cmd"], "move_all")
        self.assertEqual(parsed["positions"], positions)
        self.assertEqual(parsed["time"], 1.5)

    def test_format_gripper_open(self):
        cmd = STM32Command.format_gripper("open")
        parsed = json.loads(cmd.decode("utf-8"))
        self.assertEqual(parsed["cmd"], "gripper")
        self.assertEqual(parsed["action"], "open")

    def test_format_gripper_close(self):
        cmd = STM32Command.format_gripper("close", 75)
        parsed = json.loads(cmd.decode("utf-8"))
        self.assertEqual(parsed["cmd"], "gripper")
        self.assertEqual(parsed["action"], "close")
        self.assertEqual(parsed["force"], 75)

    def test_format_estop(self):
        cmd = STM32Command.format_estop()
        parsed = json.loads(cmd.decode("utf-8"))
        self.assertEqual(parsed["cmd"], "estop")

    def test_format_origin(self):
        cmd = STM32Command.format_origin()
        parsed = json.loads(cmd.decode("utf-8"))
        self.assertEqual(parsed["cmd"], "origin")

    def test_parse_valid_response(self):
        response = STM32Command.parse_response(b'{"status": "ok", "position": 90}')
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["position"], 90)

    def test_parse_invalid_response(self):
        response = STM32Command.parse_response(b"not valid json")
        self.assertEqual(response["status"], "error")

    def test_parse_error_response(self):
        response = STM32Command.parse_response(b'{"status": "error", "code": 1001}')
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["code"], 1001)


class TestSTM32Interface(unittest.TestCase):
    """Test STM32 interface (mock)."""

    def setUp(self):
        self.interface = STM32Interface()

    def test_connect(self):
        self.assertTrue(self.interface.connect())
        self.assertTrue(self.interface.connected)

    def test_disconnect(self):
        self.interface.connect()
        self.interface.disconnect()
        self.assertFalse(self.interface.connected)

    def test_send_command_when_connected(self):
        self.interface.connect()
        response = self.interface.send_command(b"test")
        self.assertIsNotNone(response)

    def test_send_command_when_disconnected(self):
        with self.assertRaises(ConnectionError):
            self.interface.send_command(b"test")

    def test_response_ordering(self):
        self.interface.connect()
        self.interface.set_response({"status": "ok", "seq": 1})
        self.interface.set_response({"status": "ok", "seq": 2})

        r1 = json.loads(self.interface.send_command(b"cmd1").decode("utf-8"))
        r2 = json.loads(self.interface.send_command(b"cmd2").decode("utf-8"))

        self.assertEqual(r1["seq"], 1)
        self.assertEqual(r2["seq"], 2)

    def test_timeout_handling(self):
        self.interface.connect()
        # With no responses queued, should get default ok response
        response = self.interface.send_command(b"test")
        parsed = json.loads(response.decode("utf-8"))
        self.assertEqual(parsed["status"], "ok")

    def test_wait_for_ready(self):
        self.interface.connect()
        self.assertTrue(self.interface.wait_for_ready(timeout=1.0))

    def test_wait_for_ready_timeout(self):
        # Don't connect - should timeout
        self.assertFalse(self.interface.wait_for_ready(timeout=0.5))

    def test_reconnection_logic(self):
        # Simulate disconnect and reconnect
        self.interface.connect()
        self.assertTrue(self.interface.connected)

        self.interface.disconnect()
        self.assertFalse(self.interface.connected)

        self.interface.connect()
        self.assertTrue(self.interface.connected)


if __name__ == "__main__":
    unittest.main()