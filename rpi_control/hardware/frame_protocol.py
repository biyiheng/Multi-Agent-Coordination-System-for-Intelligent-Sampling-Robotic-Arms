"""
Unified Frame-Based Communication Protocol (v1.2).

对应《改进计划.md》§5 通信协议设计，实现统一的、基于帧的通信协议，
供 STM32 / OpenMV / ESP32 等底层通信层复用：

    帧格式:
    | 帧头 (2B) | 目标地址 (1B) | 源地址 (1B) | 命令字 (1B) |
    | 数据长度 (1B) | 数据 (N B) | CRC16校验 (2B) | 帧尾 (2B) |

设计要点:
- 帧头/帧尾固定魔数, 便于字节流同步;
- 数据长度上限 255, 单帧载荷受控;
- CRC16 (CCITT, poly=0x1021) 覆盖 目标地址~数据 字段, 篡改/坏帧被丢弃;
- 命令字与地址集中定义, 保持协议可扩展 (v1.2 引入, 与既有 #CMD! 协议共存)。

v1.2 新增: 帧协议模块 + CRC16 校验 + 编解码器 + 坏帧过滤。
"""

import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 帧常量
# ---------------------------------------------------------------------------

FRAME_HEADER = b"\xaa\x55"  # 帧头 (2B)
FRAME_TERMINATOR = b"\x0d\x0a"  # 帧尾 (2B)
MAX_PAYLOAD_LENGTH = 255  # 数据长度字段为 1B, 上限 255
MIN_FRAME_LENGTH = 2 + 1 + 1 + 1 + 1 + 0 + 2 + 2  # 帧头+地址+地址+命令+长度+数据(0)+CRC+帧尾

# CRC16-CCITT (ITU-T, poly 0x1021, init 0xFFFF)
CRC16_POLY = 0x1021
CRC16_INIT = 0xFFFF


def crc16(data: bytes) -> int:
    """计算 CRC16-CCITT 校验值.

    Args:
        data: 待校验字节串 (目标地址 ~ 数据字段).

    Returns:
        16 位 CRC 校验值 (big-endian 发送).
    """
    crc = CRC16_INIT
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ CRC16_POLY) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


# ---------------------------------------------------------------------------
# 地址与命令定义
# ---------------------------------------------------------------------------

# 设备地址
ADDR_HOST = 0x00  # 树莓派 / 上位机
ADDR_STM32 = 0x01  # STM32 微控制器
ADDR_OPENMV = 0x02  # OpenMV 视觉模组
ADDR_ESP32 = 0x03  # ESP32 WiFi 模块
ADDR_BROADCAST = 0xFF  # 广播

ADDRESS_NAMES: Dict[int, str] = {
    ADDR_HOST: "host",
    ADDR_STM32: "stm32",
    ADDR_OPENMV: "openmv",
    ADDR_ESP32: "esp32",
    ADDR_BROADCAST: "broadcast",
}

# 命令字
CMD_MOVE_JOINT = 0x01  # 设置单个关节目标角度
CMD_MOVE_ALL = 0x02  # 设置全部关节目标
CMD_MOVE_LINEAR = 0x03  # 末端笛卡尔线性运动 (上位机计算 IK)
CMD_GET_STATUS = 0x04  # 请求状态上报
CMD_EMERGENCY_STOP = 0x05  # 紧急停止 (最高优先级)
CMD_STOP = 0x06  # 软停止
CMD_ORIGIN = 0x07  # 回原位
CMD_SENSOR_READ = 0x08  # 传感器读取
CMD_AG_PLAY = 0x09  # 动作组播放
CMD_CONFIG_SET = 0x0A  # 配置写入
CMD_ACK = 0x80  # 确认
CMD_ERROR = 0x81  # 错误响应

COMMAND_NAMES: Dict[int, str] = {
    CMD_MOVE_JOINT: "move_joint",
    CMD_MOVE_ALL: "move_all",
    CMD_MOVE_LINEAR: "move_linear",
    CMD_GET_STATUS: "get_status",
    CMD_EMERGENCY_STOP: "emergency_stop",
    CMD_STOP: "stop",
    CMD_ORIGIN: "origin",
    CMD_SENSOR_READ: "sensor_read",
    CMD_AG_PLAY: "action_group_play",
    CMD_CONFIG_SET: "config_set",
    CMD_ACK: "ack",
    CMD_ERROR: "error",
}


# ---------------------------------------------------------------------------
# 帧数据模型
# ---------------------------------------------------------------------------


@dataclass
class Frame:
    """一帧统一协议数据.

    Attributes:
        target: 目标地址.
        source: 源地址.
        command: 命令字.
        payload: 载荷字节串 (0 ~ 255 B).
        crc: 校验值 (解码后填充; 编码时自动计算).
        valid: 解码时 CRC 是否通过.
    """
    target: int
    source: int
    command: int
    payload: bytes = b""
    crc: int = 0
    valid: bool = True

    # ------------------------------------------------------------------
    # 编码
    # ------------------------------------------------------------------

    def encode(self) -> bytes:
        """将帧编码为字节串 (含 CRC16 与帧尾)."""
        if len(self.payload) > MAX_PAYLOAD_LENGTH:
            raise ValueError(
                f"payload too long: {len(self.payload)} > {MAX_PAYLOAD_LENGTH}"
            )
        head = struct.pack(
            ">BBBB", self.target, self.source, self.command, len(self.payload)
        )
        self.crc = crc16(head + self.payload)
        crc_bytes = struct.pack(">H", self.crc)
        return FRAME_HEADER + head + self.payload + crc_bytes + FRAME_TERMINATOR

    # ------------------------------------------------------------------
    # 便捷访问
    # ------------------------------------------------------------------

    def payload_str(self, encoding: str = "ascii", errors: str = "replace") -> str:
        """将载荷解码为字符串 (如 "0,1500,1000")."""
        return self.payload.decode(encoding, errors=errors)

    def payload_ints(self) -> List[int]:
        """将载荷按逗号分隔解析为整数列表."""
        text = self.payload_str()
        if not text.strip():
            return []
        return [int(part) for part in text.split(",") if part.strip()]

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典 (便于日志/序列化)."""
        return {
            "target": self.target,
            "target_name": ADDRESS_NAMES.get(self.target, "unknown"),
            "source": self.source,
            "source_name": ADDRESS_NAMES.get(self.source, "unknown"),
            "command": self.command,
            "command_name": COMMAND_NAMES.get(self.command, "unknown"),
            "payload": self.payload_str(),
            "crc": self.crc,
            "valid": self.valid,
        }

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return (
            f"Frame(target={ADDRESS_NAMES.get(self.target, self.target)}, "
            f"source={ADDRESS_NAMES.get(self.source, self.source)}, "
            f"cmd={COMMAND_NAMES.get(self.command, hex(self.command))}, "
            f"payload={self.payload_str()!r}, valid={self.valid})"
        )


# ---------------------------------------------------------------------------
# 编解码器
# ---------------------------------------------------------------------------


def encode_frame(
    target: int,
    source: int,
    command: int,
    payload: bytes = b"",
) -> bytes:
    """编码一帧协议数据.

    Args:
        target: 目标地址.
        source: 源地址.
        command: 命令字.
        payload: 载荷字节串 (可选).

    Returns:
        完整帧字节串 (帧头 + 帧体 + CRC16 + 帧尾).
    """
    return Frame(target=target, source=source, command=command, payload=payload).encode()


def decode_frame(data: bytes) -> Optional[Frame]:
    """从字节串解码一帧.

    若数据不足一帧 / 帧头帧尾不匹配 / CRC 校验失败, 返回 None (坏帧丢弃).

    Args:
        data: 收到的字节串 (应恰好为一帧).

    Returns:
        解码后的 Frame (CRC 校验失败时 valid=False 且返回 None 以丢弃).
    """
    if data is None or len(data) < MIN_FRAME_LENGTH:
        return None
    if not data.startswith(FRAME_HEADER):
        return None
    if not data.endswith(FRAME_TERMINATOR):
        return None

    body = data[2:-2]  # 去掉帧头帧尾
    if len(body) < 6:  # 至少 目标+源+命令+长度+CRC(2B)
        return None
    # 固定头: 目标(1) 源(1) 命令(1) 长度(1); 载荷在中间; CRC16 在帧体末尾
    target, source, command, length = struct.unpack(">BBBB", body[:4])
    payload = body[4:-2]
    crc_recv = struct.unpack(">H", body[-2:])[0]
    if len(payload) != length or length > MAX_PAYLOAD_LENGTH:
        return None  # 长度字段与实际载荷不符 -> 坏帧

    crc_calc = crc16(body[:4] + payload)
    if crc_calc != crc_recv:
        return None  # CRC 校验失败 -> 坏帧丢弃

    return Frame(
        target=target,
        source=source,
        command=command,
        payload=payload,
        crc=crc_recv,
        valid=True,
    )


def extract_frames(buffer: bytearray) -> Tuple[List[Frame], bytearray]:
    """从字节流缓冲区提取完整帧 (用于流式串口读取).

    循环扫描 FRAME_HEADER, 尝试解析; 成功则取走该帧, 失败则丢弃
    当前头并继续, 最后返回剩余未完整数据。

    Args:
        buffer: 累积的接收缓冲区.

    Returns:
        (帧列表, 剩余未完整缓冲区).
    """
    frames: List[Frame] = []
    remaining = buffer
    while True:
        idx = remaining.find(FRAME_HEADER)
        if idx < 0:
            remaining = bytearray()
            break
        if idx > 0:
            # 丢弃帧头前的杂散字节
            remaining = remaining[idx:]
        # 尝试从当前位置解析一帧
        frame = _try_parse_one(remaining)
        if frame is None:
            # 未能解析: 若长度不足则保留等待更多数据, 否则丢弃头部一字节
            if len(remaining) < MIN_FRAME_LENGTH + 2:
                break
            remaining = remaining[1:]
            continue
        frames.append(frame)
        consumed = len(frame.encode())
        remaining = remaining[consumed:]
        if not remaining:
            break
    return frames, bytearray(remaining)


def _try_parse_one(buf: bytearray) -> Optional[Frame]:
    """尝试从缓冲区起始处解析一帧 (仅在缓冲区以帧头开头时使用)."""
    if len(buf) < MIN_FRAME_LENGTH:
        return None
    # 按最小帧长度快速裁剪, 若长度字段可见则按长度精确裁剪
    length = buf[5]  # 帧头2B + 目标1B + 源1B + 命令1B = 索引5
    total = MIN_FRAME_LENGTH + length
    if len(buf) < total:
        return None
    candidate = bytes(buf[:total])
    return decode_frame(candidate)


# ---------------------------------------------------------------------------
# 便捷命令构造
# ---------------------------------------------------------------------------


def make_move_joint_frame(
    target: int, servo_id: int, pwm: int, move_time: int, source: int = ADDR_HOST
) -> bytes:
    """构造单关节运动帧: 载荷 "servo_id,pwm,move_time"."""
    payload = f"{servo_id},{pwm},{move_time}".encode("ascii")
    return encode_frame(target, source, CMD_MOVE_JOINT, payload)


def make_move_all_frame(
    target: int, positions: List[int], move_time: int, source: int = ADDR_HOST
) -> bytes:
    """构造全关节运动帧: 载荷 "p0,...,p5,move_time"."""
    payload = (",".join(str(p) for p in positions) + f",{move_time}").encode("ascii")
    return encode_frame(target, source, CMD_MOVE_ALL, payload)


def make_get_status_frame(target: int, source: int = ADDR_HOST) -> bytes:
    """构造状态查询帧."""
    return encode_frame(target, source, CMD_GET_STATUS)


def make_estop_frame(target: int, source: int = ADDR_HOST) -> bytes:
    """构造紧急停止帧."""
    return encode_frame(target, source, CMD_EMERGENCY_STOP)


def make_ack_frame(
    target: int, source: int, ack_payload: bytes = b"", command: int = CMD_ACK
) -> bytes:
    """构造确认帧."""
    return encode_frame(target, source, command, ack_payload)
