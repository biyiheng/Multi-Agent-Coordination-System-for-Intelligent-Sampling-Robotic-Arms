"""
ESP32 WiFi module (AT command) driver for the intelligent sampling robotic arm.

工业级升级 / WiFi 模块: 通过 UART 以 ESP-AT 指令控制外接 ESP32 模块,
实现设备联网 (STA)、热点 (AP/SoftAP) 与配网 (Provisioning)。

    Command:  AT+<CMD>...
    Response: OK / ERROR / +<data> / WIFI CONNECTED ...

设计要点:
1. 遵循 pyserial 可选导入模式: 无 pyserial / 无 ESP32 时进入模拟模式,
   保证单元测试与开发环境可运行 (与 STM32Interface 一致)。
2. 所有 AT 命令经 asyncio.Lock 串行化, 避免半双工 AT 帧交错。
3. 响应解析容忍 \r\n / "WIFI GOT IP" / "WIFI CONNECTED" 等异步回显。
4. 提供配置持久化接口供上层 WifiService 存储最近配网状态。

参考: Espressif AT Command Set (ESP32-WROOM-32 / ESP-AT).
"""

import asyncio
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from ..utils.logger import get_logger
from ..utils.error_handler import (
    HardwareError,
    CommunicationError,
    error_notifier,
)

logger = get_logger(__name__)

# Conditional import for platforms without pyserial (e.g., during tests)
try:
    import serial
    import serial.tools.list_ports

    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False
    logger.warning("pyserial not available; ESP32 WiFi communication will be simulated")

DEFAULT_BAUDRATE = 115200
DEFAULT_TIMEOUT = 1.0
RESPONSE_TIMEOUT = 5.0
LINE_TERMINATOR = b"\r\n"
AT_CMD_PREFIX = b"AT"

# AT response markers
OK_MARKER = "OK"
ERROR_MARKER = "ERROR"
WIFI_CONNECTED = "WIFI CONNECTED"
WIFI_GOT_IP = "WIFI GOT IP"
WIFI_DISCONNECTED = "WIFI DISCONNECT"

# CWMODE values
MODE_STA = 1
MODE_AP = 2
MODE_APSTA = 3


def detect_esp32_port() -> str:
    """Auto-detect the serial port of the ESP32 (USB-TTL / onboard).

    Tries common VID/PID chips (CP210x, CH340, Silicon Labs), then falls back
    to platform defaults.
    """
    if HAS_PYSERIAL:
        try:
            for port in serial.tools.list_ports.comports():
                name = (port.description or "").lower() + " " + (port.manufacturer or "").lower()
                if any(k in name for k in ("cp210", "ch340", "ch341", "silicon labs", "esp32")):
                    return port.device
        except Exception:
            pass
    import platform
    if platform.system() == "Windows":
        return "COM5"
    return "/dev/ttyUSB0"


class ESP32Interface:
    """Async, thread-safe interface for an external ESP32 WiFi module over UART.

    Communicates using the Espressif AT command set. When pyserial is
    unavailable (e.g. dev/test environment), runs in simulation mode.
    """

    def __init__(
        self,
        port: Optional[str] = None,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = DEFAULT_TIMEOUT,
        response_timeout: float = RESPONSE_TIMEOUT,
    ) -> None:
        self._port = port if port is not None else detect_esp32_port()
        self._baudrate = baudrate
        self._timeout = timeout
        self._response_timeout = response_timeout

        self._serial: Optional[serial.Serial] = None
        self._lock: asyncio.Lock = asyncio.Lock()
        self._connected = False
        self._running = False

    # ------------------------------------------------------------------
    # Connection Management
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Open the serial connection and verify the AT stack responds."""
        if not HAS_PYSERIAL:
            logger.warning("ESP32: running in simulation mode (pyserial not available)")
            self._connected = True
            self._running = True
            return True

        async with self._lock:
            try:
                self._serial = serial.Serial(
                    port=self._port,
                    baudrate=self._baudrate,
                    timeout=self._timeout,
                    write_timeout=self._timeout,
                )
                self._serial.reset_input_buffer()
                self._connected = True
                self._running = True
                logger.info(f"ESP32 connected on {self._port} at {self._baudrate} baud")
            except serial.SerialException as e:
                raise HardwareError(
                    f"Failed to open ESP32 serial port '{self._port}': {e}",
                    code="ESP32_CONNECT_FAILED",
                ) from e

        # Verify AT stack responds (outside lock to avoid re-entrancy)
        try:
            await self.at_check()
        except CommunicationError as e:
            logger.warning(f"ESP32 AT stack not responding: {e}")
        return True

    async def disconnect(self) -> None:
        """Close the serial connection."""
        self._running = False
        async with self._lock:
            if self._serial and self._serial.is_open:
                self._serial.close()
                logger.info("ESP32 disconnected")
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Low-level AT I/O
    # ------------------------------------------------------------------

    async def _read_line(self, timeout: float) -> str:
        """Read a single CRLF-terminated line from the ESP32.

        Returns:
            The decoded line (without terminator), or "" on timeout.
        """
        if not HAS_PYSERIAL:
            await asyncio.sleep(0.05)
            return ""

        buffer = bytearray()
        start = time.monotonic()
        while True:
            if time.monotonic() - start > timeout:
                return buffer.decode("utf-8", errors="replace").strip()
            if self._serial.in_waiting > 0:
                byte = self._serial.read(1)
                if byte == b"\n":
                    return buffer.decode("utf-8", errors="replace").strip()
                if byte not in (b"\r", b"\0"):
                    buffer += byte
            else:
                await asyncio.sleep(0.001)

    async def _read_until(self, markers: Tuple[str, ...],
                          timeout: Optional[float] = None) -> Tuple[str, List[str]]:
        """Read lines until one of the markers appears or timeout.

        Returns:
            (final_line, all_lines)
        """
        effective = timeout or self._response_timeout
        lines: List[str] = []
        deadline = _now() + effective
        while True:
            line = await self._read_line(timeout=0.2)
            if line:
                lines.append(line)
                for m in markers:
                    if m in line.upper():
                        return line, lines
            if _now() > deadline:
                break
        return "", lines

    async def at_command(self, cmd: str, *,
                         markers: Tuple[str, ...] = ("OK",),
                         timeout: Optional[float] = None) -> Tuple[str, List[str]]:
        """Send an AT command and wait for a response marker.

        Args:
            cmd: Command payload WITHOUT the "AT" prefix (e.g. "CWMODE=1").
            markers: Response markers to stop reading on (default ("OK",)).
            timeout: Overall response timeout in seconds.

        Returns:
            (final_marker_or_last_line, all_lines)

        Raises:
            CommunicationError: If ERROR or timeout occurs.
        """
        payload = (AT_CMD_PREFIX + cmd.encode("ascii") + b"\r\n")

        if not HAS_PYSERIAL:
            # Simulation: synthesize plausible responses
            return self._simulate(cmd, markers)

        async with self._lock:
            try:
                self._serial.write(payload)
                self._serial.flush()
                logger.debug(f"ESP32 TX: AT{cmd}")
            except (serial.SerialException, AttributeError) as e:
                self._connected = False
                raise CommunicationError(
                    f"ESP32 write failed for 'AT{cmd}': {e}", code="ESP32_WRITE_FAILED"
                ) from e

            final, lines = await self._read_until(markers + ("ERROR",), timeout=timeout)
            if ERROR_MARKER in final.upper() or ERROR_MARKER in " ".join(lines).upper():
                raise CommunicationError(
                    f"ESP32 rejected 'AT{cmd}': {' | '.join(lines[-3:])}",
                    code="ESP32_CMD_REJECTED",
                )
            if not final and not lines:
                raise CommunicationError(
                    f"ESP32 no response to 'AT{cmd}'", code="ESP32_TIMEOUT"
                )
            return final, lines

    # ------------------------------------------------------------------
    # Simulation (dev/test without hardware)
    # ------------------------------------------------------------------

    def _simulate(self, cmd: str, markers: Tuple[str, ...]) -> Tuple[str, List[str]]:
        """Return plausible simulated AT responses for unit/dev environments."""
        logger.debug(f"ESP32 SIM TX: AT{cmd}")
        # 去掉前导 '+' (AT+CWxxx -> CWxxx), 便于统一匹配
        upper = cmd.upper().lstrip("+")
        if upper.startswith("CWMODE"):
            return OK_MARKER, [OK_MARKER]
        if upper.startswith("CWJAP"):
            return WIFI_CONNECTED, [WIFI_CONNECTED, WIFI_GOT_IP]
        if upper.startswith("CWSAP"):
            return OK_MARKER, [OK_MARKER]
        if upper.startswith("CIFSR"):
            return "+CIFSR:STAIP,\"192.168.1.100\"", [
                "+CIFSR:STAIP,\"192.168.1.100\"",
                "+CIFSR:STAMAC,\"24:6f:28:00:00:01\"",
                OK_MARKER,
            ]
        if upper.startswith("CWLAP"):
            return "+CWLAP:(3,\"HomeWiFi\",-45,\"aa:bb:cc:dd:ee:ff\",6)", [
                "+CWLAP:(3,\"HomeWiFi\",-45,\"aa:bb:cc:dd:ee:ff\",6)",
                "+CWLAP:(4,\"GuestNet\",-72,\"11:22:33:44:55:66\",1)",
                OK_MARKER,
            ]
        if upper.startswith("CIPSTAMAC"):
            return "+CIPSTAMAC:\"24:6f:28:00:00:01\"", ["+CIPSTAMAC:\"24:6f:28:00:00:01\"", OK_MARKER]
        if upper.startswith("CWJAP?"):
            return "+CWJAP:\"HomeWiFi\"", ["+CWJAP:\"HomeWiFi\"", OK_MARKER]
        if upper.startswith("CIPSTATUS"):
            return "+CIPSTATUS:5", ["+CIPSTATUS:5", OK_MARKER]
        if upper == "RST":
            return OK_MARKER, [OK_MARKER]
        if upper == "":
            return OK_MARKER, [OK_MARKER]
        return OK_MARKER, [OK_MARKER]

    # ------------------------------------------------------------------
    # High-level WiFi operations
    # ------------------------------------------------------------------

    async def at_check(self) -> bool:
        """Verify the AT stack is alive (sends bare 'AT')."""
        await self.at_command("", markers=("OK",), timeout=2.0)
        return True

    async def reset(self) -> None:
        """Soft reset the ESP32 (AT+RST)."""
        logger.info("ESP32: issuing soft reset (AT+RST)")
        await self.at_command("+RST", markers=("OK",), timeout=8.0)
        await asyncio.sleep(0.2)

    async def set_mode(self, mode: int) -> None:
        """Set WiFi mode: 1=STA, 2=AP, 3=APSTA."""
        if mode not in (MODE_STA, MODE_AP, MODE_APSTA):
            raise ValueError(f"mode must be 1/2/3, got {mode}")
        await self.at_command(f"+CWMODE={mode}", markers=("OK",))

    async def join_ap(self, ssid: str, password: str,
                      timeout: Optional[float] = None) -> bool:
        """Connect the ESP32 to an existing AP (STA mode)."""
        eff = timeout or self._response_timeout
        logger.info(f"ESP32: connecting to AP '{ssid}'")
        await self.set_mode(MODE_STA)
        cmd = f'+CWJAP="{_esc(ssid)}","{_esc(password)}"'
        final, lines = await self.at_command(
            cmd, markers=(WIFI_CONNECTED, WIFI_GOT_IP, "OK"), timeout=eff
        )
        ok = any(m in " ".join(lines).upper() for m in (WIFI_CONNECTED, WIFI_GOT_IP))
        if not ok:
            raise CommunicationError(
                f"ESP32 failed to join AP '{ssid}'", code="ESP32_JOIN_FAILED"
            )
        return True

    async def create_ap(self, ssid: str, password: str = "",
                        channel: int = 6) -> bool:
        """Create a soft-AP (AP mode) on the ESP32."""
        logger.info(f"ESP32: starting soft-AP '{ssid}' (ch {channel})")
        await self.set_mode(MODE_AP)
        cmd = f'+CWSAP="{_esc(ssid)}","{_esc(password)}",{int(channel)},3'
        await self.at_command(cmd, markers=("OK",))
        return True

    async def get_ip(self) -> Optional[str]:
        """Return the STA IP address (AT+CIFSR), or None."""
        final, lines = await self.at_command("+CIFSR", markers=("OK",))
        for line in lines:
            m = re.search(r'\+CIFSR:STAIP,"([0-9.]+)"', line)
            if m:
                return m.group(1)
        return None

    async def get_mac(self) -> Optional[str]:
        """Return the ESP32 MAC address (AT+CIPSTAMAC?)."""
        try:
            final, lines = await self.at_command("+CIPSTAMAC?", markers=("OK",))
            for line in lines:
                m = re.search(r'"([0-9A-Fa-f:]{17})"', line)
                if m:
                    return m.group(1)
        except CommunicationError:
            return None
        return None

    async def scan(self) -> List[Dict[str, Any]]:
        """Scan nearby APs (AT+CWLAP)."""
        _, lines = await self.at_command("+CWLAP", markers=("OK",), timeout=12.0)
        results: List[Dict[str, Any]] = []
        for line in lines:
            m = re.search(r'\+CWLAP:\((\d),"([^"]*)",(-?\d+),"([0-9A-Fa-f:]{17})",(\d+)\)', line)
            if m:
                results.append({
                    "auth": m.group(1),
                    "ssid": m.group(2),
                    "rssi": int(m.group(3)),
                    "bssid": m.group(4),
                    "channel": int(m.group(5)),
                })
        return results

    async def get_status(self) -> Dict[str, Any]:
        """Aggregate the ESP32 status."""
        status: Dict[str, Any] = {
            "esp32_present": self._connected,
            "mode": "unknown",
            "connected": False,
            "ssid": None,
            "ip": None,
            "mac": None,
        }
        try:
            mode = 1
            if not HAS_PYSERIAL:
                mode = 1
            else:
                _, ml = await self.at_command("+CWMODE?", markers=("OK",))
                for line in ml:
                    m = re.search(r"\+CWMODE:(\d)", line)
                    if m:
                        mode = int(m.group(1))
                        break
            status["mode"] = {1: "sta", 2: "ap", 3: "apsta"}.get(mode, "unknown")
            if mode in (MODE_STA, MODE_APSTA):
                status["ip"] = await self.get_ip()
                try:
                    _, jl = await self.at_command("+CWJAP?", markers=("OK",))
                    for line in jl:
                        m = re.search(r'\+CWJAP:"([^"]*)"', line)
                        if m:
                            status["ssid"] = m.group(1)
                            status["connected"] = True
                except CommunicationError:
                    pass
            status["mac"] = await self.get_mac()
        except CommunicationError as e:
            logger.warning(f"ESP32 status partial: {e}")
        return status

    async def __aenter__(self) -> "ESP32Interface":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()


def _esc(value: str) -> str:
    """Escape AT string (double quotes inside the string)."""
    return value.replace('"', '\\"')


def _now() -> float:
    return time.monotonic()
