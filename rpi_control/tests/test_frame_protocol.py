"""Tests for the unified frame-based communication protocol (v1.2).

对应《改进计划.md》§5 通信协议设计, 验证:
- 帧编解码往返 (encode -> decode)
- CRC16 篡改帧丢弃
- 流式字节缓冲解析 (extract_frames, 杂散字节容错)
- 便捷命令构造 (move_joint / move_all / estop)
- STM32 帧模式接入 (仿真模式, 无硬件)
"""
import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pytest

from rpi_control.hardware.frame_protocol import (
    ADDR_STM32,
    ADDR_HOST,
    CMD_MOVE_ALL,
    CMD_MOVE_JOINT,
    CMD_EMERGENCY_STOP,
    CMD_GET_STATUS,
    MAX_PAYLOAD_LENGTH,
    Frame,
    crc16,
    decode_frame,
    encode_frame,
    extract_frames,
    make_estop_frame,
    make_get_status_frame,
    make_move_all_frame,
    make_move_joint_frame,
)
from rpi_control.hardware.stm32_comm import STM32Interface


# =============================================================================
# CRC16 校验
# =============================================================================

class TestCRC16:
    def test_crc16_deterministic(self):
        assert crc16(b"") == crc16(b"")
        assert crc16(b"abc") == crc16(b"abc")

    def test_crc16_differs_by_input(self):
        assert crc16(b"abc") != crc16(b"abd")

    def test_crc16_range(self):
        for i in range(100):
            v = crc16(bytes([i % 256, (i * 7) % 256]))
            assert 0 <= v <= 0xFFFF


# =============================================================================
# 编解码
# =============================================================================

class TestFrameEncodeDecode:
    def test_roundtrip_move_joint(self):
        raw = make_move_joint_frame(ADDR_STM32, 0, 1500, 1000)
        f = decode_frame(raw)
        assert f is not None and f.valid
        assert f.target == ADDR_STM32
        assert f.source == ADDR_HOST
        assert f.command == CMD_MOVE_JOINT
        assert f.payload_ints() == [0, 1500, 1000]

    def test_roundtrip_move_all(self):
        raw = make_move_all_frame(ADDR_STM32, [1500] * 6, 500)
        f = decode_frame(raw)
        assert f is not None and f.valid
        assert f.command == CMD_MOVE_ALL
        assert f.payload_ints() == [1500] * 6 + [500]

    def test_roundtrip_get_status(self):
        raw = make_get_status_frame(ADDR_STM32)
        f = decode_frame(raw)
        assert f is not None and f.valid
        assert f.command == CMD_GET_STATUS
        assert f.payload == b""

    def test_roundtrip_estop(self):
        raw = make_estop_frame(ADDR_STM32)
        f = decode_frame(raw)
        assert f is not None and f.valid
        assert f.command == CMD_EMERGENCY_STOP

    def test_payload_too_long_rejected(self):
        with pytest.raises(ValueError):
            encode_frame(ADDR_STM32, ADDR_HOST, CMD_MOVE_JOINT, b"x" * (MAX_PAYLOAD_LENGTH + 1))

    def test_too_short_data_returns_none(self):
        assert decode_frame(b"\xaa\x55") is None
        assert decode_frame(b"") is None

    def test_wrong_header_returns_none(self):
        raw = make_move_joint_frame(ADDR_STM32, 0, 1500, 1000)
        bad = b"\xbb\x55" + raw[2:]
        assert decode_frame(bad) is None

    def test_wrong_terminator_returns_none(self):
        raw = bytearray(make_move_joint_frame(ADDR_STM32, 0, 1500, 1000))
        raw[-1] = 0x00  # 破坏帧尾
        assert decode_frame(bytes(raw)) is None


# =============================================================================
# CRC 篡改检测
# =============================================================================

class TestTamperDetection:
    def test_tampered_payload_dropped(self):
        raw = bytearray(make_move_joint_frame(ADDR_STM32, 0, 1500, 1000))
        raw[7] ^= 0xFF  # 翻转载荷字节
        assert decode_frame(bytes(raw)) is None

    def test_tampered_crc_dropped(self):
        raw = bytearray(make_move_joint_frame(ADDR_STM32, 0, 1500, 1000))
        raw[-4] ^= 0xFF  # 翻转 CRC 高字节
        assert decode_frame(bytes(raw)) is None

    def test_length_mismatch_dropped(self):
        raw = bytearray(make_move_joint_frame(ADDR_STM32, 0, 1500, 1000))
        raw[4] = 0x7F  # 伪造长度字段 (与实际载荷不符)
        assert decode_frame(bytes(raw)) is None


# =============================================================================
# 流式字节缓冲解析
# =============================================================================

class TestExtractFrames:
    def test_two_frames_from_stream(self):
        buf = bytearray()
        buf.extend(make_move_joint_frame(ADDR_STM32, 0, 1500, 1000))
        buf.extend(make_estop_frame(ADDR_STM32))
        frames, rem = extract_frames(buf)
        assert len(frames) == 2
        assert frames[0].command == CMD_MOVE_JOINT
        assert frames[1].command == CMD_EMERGENCY_STOP
        assert len(rem) == 0

    def test_stray_bytes_before_frame(self):
        buf = bytearray(b"\x00junk\xaa\x55")  # 杂散字节 + 帧头部分
        buf.extend(make_estop_frame(ADDR_STM32))
        frames, _ = extract_frames(buf)
        assert len(frames) == 1
        assert frames[0].command == CMD_EMERGENCY_STOP

    def test_partial_frame_kept_for_next_read(self):
        buf = bytearray(make_estop_frame(ADDR_STM32)[:-3])  # 未完整帧
        frames, rem = extract_frames(buf)
        assert len(frames) == 0
        assert len(rem) > 0  # 剩余数据保留等待更多


# =============================================================================
# STM32 帧模式接入 (仿真)
# =============================================================================

class TestSTM32FrameMode:
    def test_frame_mode_toggle(self):
        s = STM32Interface(port="COM99")  # 无硬件 -> 仿真模式
        assert s.frame_mode is False
        s.set_frame_mode(True)
        assert s.frame_mode is True

    @pytest.mark.asyncio
    async def test_send_frame_commands_simulation(self):
        s = STM32Interface(port="COM99")
        s.set_frame_mode(True)
        await s.send_frame_command(ADDR_STM32, CMD_MOVE_JOINT, b"0,1500,1000")
        await s.frame_move_joint(0, 1500, 1000)
        await s.frame_move_all([1500] * 6, 500)
        await s.frame_emergency_stop()
        # 仿真模式不抛异常即视为通过
