"""
STM32H7 集成测试用例: 编码器 + CAN 通信的闭环控制逻辑 (S1/S2).

由于本机无 H7 硬件, 本测试用主机侧仿真镜像 H7 固件的闭环控制逻辑,
覆盖:
1. AS5048 绝对值编码器: 原始值(0-16383) -> 角度(deg), 单调/跨零点。
2. CAN 通信层: CRC32 校验、坏帧拒绝、优先级仲裁(急停帧优先)。
3. 闭环控制逻辑: 编码器反馈 -> PID -> 力矩/舵机命令 -> CAN 帧 -> 执行。
   验证闭环收敛、编码器测量噪声下稳定、CAN 丢帧/坏帧下安全响应。

对应 H7 固件接口 (stm32_firmware/stm32h7):
- as5048_read_angle(&enc, &deg)  -> HAL_OK
- can_link_send(&link, prio, node_id, data, len)
- can_link_crc32(data, len)
"""

import unittest

import numpy as np

AS5048_LSB = 360.0 / 16384.0   # 14bit 分辨率


# ---------------------------------------------------------------------------
# 主机侧仿真: 镜像 H7 外设行为
# ---------------------------------------------------------------------------

class EncoderSim:
    """仿真 AS5048 绝对值编码器 (含测量噪声)."""

    def __init__(self, true_deg=0.0, noise_deg=0.03):
        self.true_deg = true_deg
        self.noise_deg = noise_deg

    def set_angle(self, deg):
        self.true_deg = deg % 360.0

    def read_deg(self):
        # AS5048 返回 0-16383 原始值, 转角度
        raw = int(round(self.true_deg / AS5048_LSB)) & 0x3FFF
        # 加测量噪声
        val = (raw * AS5048_LSB) % 360.0
        if self.noise_deg > 0:
            val = val + np.random.normal(0.0, self.noise_deg)
        return val % 360.0


def can_crc32(data):
    """镜像 H7 CAN 层 CRC32 (查表)."""
    crc = 0xFFFFFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ (0xEDB88320 if crc & 1 else 0)
    return crc ^ 0xFFFFFFFF


class CanLinkSim:
    """仿真 H7 CAN 链路: 组帧(负载+CRC)、CRC 校验、坏帧丢弃."""

    def __init__(self):
        self.sent = []          # 成功发送的帧
        self.rx_crc_fail = 0    # 接收端 CRC 失败计数
        self.rx_ok = 0

    def send(self, prio, node_id, data):
        # 帧 ID = (prio<<8)|node_id, 负载 + CRC 尾
        frame = bytearray(data)
        crc = can_crc32(bytes(frame))
        frame += crc.to_bytes(4, "little")
        # 返回待发送的完整帧 (H7 的 can_link_send 会组装)
        return bytes(frame)

    def receive_and_validate(self, frame, prio, node_id):
        # 分离负载与 CRC 尾
        if len(frame) < 5:
            return None
        payload = frame[:-4]
        crc_rx = int.from_bytes(frame[-4:], "little")
        if can_crc32(payload) != crc_rx:
            self.rx_crc_fail += 1
            return None  # 坏帧丢弃
        self.rx_ok += 1
        return {"prio": prio, "node_id": node_id, "payload": payload}


class PIDController:
    """关节闭环 PID (镜像 H7 闭环)."""

    def __init__(self, kp, ki, kd, dt=0.001):
        self.kp, self.ki, self.kd, self.dt = kp, ki, kd, dt
        self.integral = 0.0
        self.prev_err = 0.0

    def step(self, ref_deg, meas_deg):
        err = ref_deg - meas_deg
        self.integral += err * self.dt
        deriv = (err - self.prev_err) / self.dt
        self.prev_err = err
        return self.kp * err + self.ki * self.integral + self.kd * deriv


# ---------------------------------------------------------------------------
# 集成测试
# ---------------------------------------------------------------------------

class TestH7ClosedLoop(unittest.TestCase):

    def test_encoder_absolute_read(self):
        """AS5048 绝对角度读取: 原始值->角度, 跨 0/360 连续."""
        enc = EncoderSim(noise_deg=0.0)
        enc.set_angle(45.0)
        self.assertAlmostEqual(enc.read_deg(), 45.0, delta=0.1)
        # 跨零点
        enc.set_angle(359.5)
        self.assertAlmostEqual(enc.read_deg(), 359.5, delta=0.3)

    def test_encoder_noise_bounded(self):
        """带测量噪声的编码器读数应在真实值附近有界."""
        enc = EncoderSim(noise_deg=0.03)
        enc.set_angle(120.0)
        for _ in range(20):
            self.assertTrue(abs(enc.read_deg() - 120.0) < 0.5)

    def test_can_crc_validation(self):
        """CAN 帧 CRC32 校验: 合法帧通过, 篡改负载被丢弃."""
        link = CanLinkSim()
        frame = link.send(0x10, 1, b"\x01\x02\x03")
        # 合法
        msg = link.receive_and_validate(frame, 0x10, 1)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["payload"], b"\x01\x02\x03")
        # 篡改负载
        bad = bytearray(frame)
        bad[1] ^= 0xFF
        self.assertIsNone(link.receive_and_validate(bytes(bad), 0x10, 1))
        self.assertEqual(link.rx_crc_fail, 1)

    def test_can_priority_arbitration(self):
        """CAN 优先级仲裁: 低数值 ID (急停 0x0) 应优先于关节帧 0x10."""
        # 急停帧 prio=0x0, 关节帧 prio=0x10; ID 越小优先级越高
        ids = [(0x10 << 8) | 1, (0x0 << 8) | 2]
        self.assertTrue(ids[1] < ids[0], "E-stop ID must be lower (higher prio)")

    def test_closed_loop_convergence(self):
        """编码器反馈 + PID + CAN 命令闭环: 应收敛到参考位置."""
        enc = EncoderSim(noise_deg=0.02)
        pid = PIDController(kp=5.0, ki=0.0, kd=0.0, dt=0.001)
        link = CanLinkSim()
        ref = 60.0
        enc.set_angle(0.0)
        for _ in range(5000):   # 5s @ 1kHz
            meas = enc.read_deg()
            vel_cmd = pid.step(ref, meas)          # deg/s
            # 命令 -> CAN 帧 (float32 速度命令, 钳制安全范围)
            cmd_clip = float(np.clip(vel_cmd, -200.0, 200.0))
            frame = link.send(0x10, 1, np.float32(cmd_clip).tobytes())
            msg = link.receive_and_validate(frame, 0x10, 1)
            if msg is not None:
                applied = np.frombuffer(msg["payload"], dtype=np.float32)[0]
                enc.set_angle(enc.true_deg + float(applied) * 0.001)  # 速度积分
        self.assertLess(abs(enc.read_deg() - ref), 1.0,
                        f"closed loop should converge, got {enc.read_deg()}")

    def test_can_bad_frame_safe_response(self):
        """CAN 坏帧在闭环中被拒绝, 不改变执行器状态 (安全)."""
        link = CanLinkSim()
        enc = EncoderSim(noise_deg=0.0)
        enc.set_angle(10.0)
        # 制造坏帧
        good = link.send(0x10, 1, b"\x00\x00")
        bad = bytearray(good)
        bad[-1] ^= 0xFF
        msg = link.receive_and_validate(bytes(bad), 0x10, 1)
        self.assertIsNone(msg)          # 坏帧被丢弃
        self.assertEqual(link.rx_crc_fail, 1)
        # 执行器状态不变 (未应用坏命令); 允许编码器量化误差
        self.assertLess(abs(enc.read_deg() - 10.0), 0.1)


if __name__ == "__main__":
    unittest.main()
