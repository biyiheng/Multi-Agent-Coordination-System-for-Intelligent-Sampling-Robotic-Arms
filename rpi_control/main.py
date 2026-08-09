#!/usr/bin/env python3
"""
Main entry point for the intelligent sampling robotic arm system.

Initializes all subsystems (STM32 communication, OpenMV vision, servo
controller, motion planning), starts the web server, and runs the
main async event loop with graceful shutdown handling.
"""

import asyncio
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np

from rpi_control.utils.logger import setup_logger, get_logger
from rpi_control.utils.config_loader import ConfigLoader, load_config
from rpi_control.utils.error_handler import (
    HardwareError,
    CommunicationError,
    SafetyError,
    SystemError,
    error_notifier,
)

from rpi_control.hardware.stm32_comm import STM32Interface
from rpi_control.hardware.openmv_comm import OpenMVInterface
from rpi_control.hardware.servo_controller import ServoController

from rpi_control.motion.collision import ObstacleManager
from rpi_control.grasp.grasp_pipeline import GraspPipeline, ScriptedForceSource
from rpi_control.grasp.motion_driver import SimulationMotionDriver, RealArmMotionDriver

# Setup logging early
logger = get_logger("main")


# ---------------------------------------------------------------------------
# System State
# ---------------------------------------------------------------------------


class SystemState:
    """Central system state container."""

    def __init__(self) -> None:
        self.running: bool = False
        self.initialized: bool = False
        self.stm32: Optional[STM32Interface] = None
        self.openmv: Optional[OpenMVInterface] = None
        self.servo: Optional[ServoController] = None
        self.config: Optional[ConfigLoader] = None
        self.obstacle_manager: Optional[ObstacleManager] = None
        self.pipeline: Optional[GraspPipeline] = None
        self.shutdown_event: asyncio.Event = asyncio.Event()


# Global system state
state = SystemState()


# ---------------------------------------------------------------------------
# Grasp Pipeline
# ---------------------------------------------------------------------------


def _grasp_config() -> dict:
    """读取 grasp 配置节 (空字典兜底)."""
    return state.config.config.get("grasp", {}) if state.config else {}


def _build_pipeline() -> Optional[GraspPipeline]:
    """根据配置构建抓取流水线 (仿真或真实硬件驱动).

    Returns:
        GraspPipeline 实例, 或 None (grasp 未启用).
    """
    g = _grasp_config()
    if not g.get("enabled", True):
        logger.info("Grasp pipeline disabled by config")
        return None

    camera_matrix = np.array(g.get("camera_matrix"), dtype=np.float64)
    hand_eye_R = np.array(g.get("hand_eye_rotation"), dtype=np.float64)
    hand_eye_t = np.array(g.get("hand_eye_translation"), dtype=np.float64)

    # 运行模式: 环境变量 GRASP_MODE 可覆盖配置 (供启动脚本 --real/--sim 使用)
    mode = os.environ.get("GRASP_MODE") or g.get("mode", "simulation")
    if mode == "real" and state.servo is not None:
        driver = RealArmMotionDriver(state.servo)
        logger.info("Grasp pipeline using REAL hardware driver")
    else:
        driver = SimulationMotionDriver()
        logger.info("Grasp pipeline using SIMULATION driver")

    pipeline = GraspPipeline(
        driver=driver,
        camera_matrix=camera_matrix,
        hand_eye_rotation=hand_eye_R,
        hand_eye_translation=hand_eye_t,
        config=g,
    )
    pipeline.initialize_gripper(
        max_force_n=g.get("gripper", {}).get("max_force_n", 30.0),
        min_force_n=g.get("gripper", {}).get("min_force_n", 1.0),
    )

    # 注册物体 3D 模型 (立方体, 米)
    size_m = g.get("object_size_mm", 60.0) / 1000.0
    model = np.array([
        [0, 0, 0], [size_m, 0, 0], [size_m, size_m, 0], [0, size_m, 0],
        [0, 0, size_m], [size_m, 0, size_m], [size_m, size_m, size_m],
        [0, size_m, size_m],
    ])
    pipeline.register_object(g.get("object_name", "obj"), model)

    # 若配置了标定文件则加载 (覆盖默认手眼参数)
    cal_file = g.get("calibration_file", "")
    if cal_file:
        pipeline.load_calibration(cal_file)
    return pipeline


def _synthesize_image_points() -> Optional[np.ndarray]:
    """仿真模式: 依据配置的物体位姿生成带噪声的 2D 投影点 (Nx2)."""
    if state.pipeline is None:
        return None
    g = _grasp_config()
    obj_pos = np.array(g.get("object_pose_mm"), dtype=np.float64)
    size_m = g.get("object_size_mm", 60.0) / 1000.0

    # 物体在相机系 (反算手眼变换), mm -> 视觉管线统一用米
    T_inv = np.linalg.inv(state.pipeline.cal.get_transform_matrix())
    cam_origin_mm = (T_inv @ np.array(
        [obj_pos[0], obj_pos[1], obj_pos[2], 1.0]))[:3]
    cam_origin = cam_origin_mm / 1000.0

    model = state.pipeline.estimator.object_model_points[
        g.get("object_name", "obj")]
    half = np.array([size_m, size_m, size_m]) / 2.0
    obj_cam = model + (cam_origin - half)

    K = state.pipeline.camera_matrix
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
    uv = np.stack([obj_cam[:, 0] * fx / obj_cam[:, 2] + cx,
                   obj_cam[:, 1] * fy / obj_cam[:, 2] + cy], axis=1)
    uv += np.random.randn(8, 2) * 0.5  # 0.5px 投影噪声
    return uv


async def _get_image_points_from_openmv() -> Optional[np.ndarray]:
    """真实模式: 从 OpenMV 检测结果提取 2D 角点, 用于 PnP.

    当前版本尝试从 AprilTag 检测响应中提取角点。若设备返回格式与此不符,
    在此处接入对应的视觉适配器即可。
    """
    if state.openmv is None or not state.openmv.is_connected():
        logger.error("OpenMV 未连接, 无法获取检测点")
        return None
    resp = await state.openmv.detect_apriltag()
    corners = resp.get("corners") or resp.get("points")
    if not corners:
        logger.error("OpenMV 响应中未找到角点: %s", resp)
        return None
    return np.asarray(corners, dtype=np.float64).reshape(-1, 2)


async def _run_grasp() -> dict:
    """执行一次视觉引导抓取, 返回结果 (供 Web/脚本调用)."""
    if state.pipeline is None:
        return {"status": "error", "message": "Grasp pipeline not available"}
    g = _grasp_config()
    object_name = g.get("object_name", "obj")

    if g.get("mode", "simulation") == "simulation":
        image_points = _synthesize_image_points()
        if image_points is None:
            return {"status": "error", "message": "Failed to synthesize image points"}
    else:
        image_points = await _get_image_points_from_openmv()
        if image_points is None:
            return {"status": "error", "message": "No detection points from OpenMV"}

    result = await state.pipeline.run_cycle(image_points, object_name)
    return {"status": "ok" if result.get("success") else "failed", "result": result}


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


async def initialize_system() -> bool:
    """
    Initialize all system components.

    Loads configuration, connects to hardware, and initializes
    controllers and motion planning subsystems.

    Returns:
        True if initialization succeeded.
    """
    logger.info("=" * 60)
    logger.info("Initializing Intelligent Sampling Robotic Arm System")

    # Load configuration
    try:
        state.config = load_config()
        logger.info("Configuration loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return False

    # Configure logging from config
    log_level = state.config.get("system.log_level", "INFO")
    setup_logger(name="rpi_control", level=log_level)
    logger.info(f"Log level set to {log_level}")

    system_name = state.config.get("system.name", "Unknown")
    system_version = state.config.get("system.version", "0.0.0")
    logger.info(f"System: {system_name} v{system_version}")

    # Initialize obstacle manager
    state.obstacle_manager = ObstacleManager()
    logger.info("Obstacle manager initialized")

    # Initialize STM32 interface
    stm32_config = state.config.config.get("hardware", {}).get("stm32", {})
    stm32_port = stm32_config.get("port", "/dev/ttyAMA0")
    stm32_baudrate = stm32_config.get("baudrate", 115200)
    stm32_timeout = stm32_config.get("timeout", 0.5)

    state.stm32 = STM32Interface(
        port=stm32_port,
        baudrate=stm32_baudrate,
        timeout=stm32_timeout,
    )

    try:
        await state.stm32.connect()
        logger.info("STM32 interface connected")
        await state.stm32.start_heartbeat()
    except HardwareError as e:
        logger.error(f"Failed to connect to STM32: {e}")
        logger.warning("Continuing without STM32 (simulation mode)")
        # Allow simulation mode by directly setting internal state
        state.stm32._connected = True
        state.stm32._running = True

    # Initialize OpenMV interface
    openmv_config = state.config.config.get("hardware", {}).get("openmv", {})
    openmv_port = openmv_config.get("port", "/dev/ttyUSB0")
    openmv_baudrate = openmv_config.get("baudrate", 115200)
    openmv_timeout = openmv_config.get("timeout", 1.0)

    state.openmv = OpenMVInterface(
        port=openmv_port,
        baudrate=openmv_baudrate,
        timeout=openmv_timeout,
        stm32_interface=state.stm32,  # Use STM32 passthrough for OpenMV UART2 bridge
    )

    try:
        await state.openmv.connect()
        logger.info("OpenMV interface connected")
    except CommunicationError as e:
        logger.error(f"Failed to connect to OpenMV: {e}")
        logger.warning("Continuing without OpenMV (simulation mode)")
        state.openmv._connected = True

    # Initialize servo controller
    arm_config = state.config.config.get("gripper", {})
    state.servo = ServoController(
        stm32_interface=state.stm32,
        open_pwm=arm_config.get("open_pwm", 500),
        close_pwm=arm_config.get("close_pwm", 1800),
        grip_force=arm_config.get("grip_force", 1500),
        adaptive_enabled=arm_config.get("adaptive_enabled", True),
    )
    logger.info("Servo controller initialized")

    # Initialize grasp pipeline (vision + motion + force control)
    state.pipeline = _build_pipeline()
    if state.pipeline is not None:
        logger.info("Grasp pipeline initialized")
    else:
        logger.warning("Grasp pipeline not initialized")

    state.initialized = True
    logger.info("System initialization complete")
    logger.info("=" * 60)
    return True


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------


async def shutdown_system() -> None:
    """Gracefully shut down all system components."""
    logger.info("=" * 60)
    logger.info("Shutting down system...")

    # Stop heartbeat first
    if state.stm32:
        await state.stm32.stop_heartbeat()

    # Stop servo movement
    if state.servo:
        try:
            await state.servo.stop()
        except Exception as e:
            logger.error(f"Error stopping servos: {e}")

    # Disconnect hardware
    if state.stm32:
        try:
            await state.stm32.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting STM32: {e}")

    if state.openmv:
        try:
            await state.openmv.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting OpenMV: {e}")

    # Report error summary
    error_summary = error_notifier.get_error_summary()
    if error_summary:
        logger.info(f"Error summary during session: {error_summary}")

    state.running = False
    logger.info("System shutdown complete")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Signal Handlers
# ---------------------------------------------------------------------------


def _signal_handler(signum: int, frame: object) -> None:
    """
    Handle OS signals for graceful shutdown.

    Args:
        signum: Signal number.
        frame: Current stack frame (unused).
    """
    sig_name = signal.Signals(signum).name
    logger.info(f"Received signal {sig_name} ({signum}). Initiating shutdown...")
    state.shutdown_event.set()


def _register_signal_handlers() -> None:
    """Register signal handlers for SIGINT and SIGTERM."""
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    logger.debug("Signal handlers registered (SIGINT, SIGTERM)")


# ---------------------------------------------------------------------------
# Web Server
# ---------------------------------------------------------------------------


async def _start_web_server() -> None:
    """Start the web server if configured."""
    web_config = state.config.config.get("web", {})
    host = web_config.get("host", "0.0.0.0")
    port = web_config.get("port", 8000)

    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        import uvicorn

        app = FastAPI(
            title="Intelligent Sampling Robotic Arm",
            version=state.config.get("system.version", "2.0.0"),
        )

        # CORS middleware
        cors_origins = web_config.get("cors_origins", ["*"])
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @app.get("/api/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "ok" if state.initialized else "initializing",
                "stm32_connected": (
                    state.stm32.is_connected if state.stm32 else False
                ),
                "openmv_connected": (
                    state.openmv.is_connected if state.openmv else False
                ),
                "version": state.config.get("system.version", "2.0.0"),
            }

        @app.get("/api/status")
        async def system_status():
            """System status endpoint."""
            return {
                "initialized": state.initialized,
                "running": state.running,
                "stm32_connected": (
                    state.stm32.is_connected if state.stm32 else False
                ),
                "openmv_connected": (
                    state.openmv.is_connected if state.openmv else False
                ),
                "servo_positions": (
                    state.servo.current_positions if state.servo else []
                ),
                "errors": error_notifier.get_error_summary(),
            }

        @app.post("/api/emergency_stop")
        async def emergency_stop():
            """Emergency stop endpoint."""
            if state.servo:
                await state.servo.emergency_stop()
                return {"status": "emergency_stop_triggered"}
            return {"status": "error", "message": "Servo controller not available"}

        @app.post("/api/home")
        async def home_all():
            """Return to home position."""
            if state.servo:
                await state.servo.home_all()
                return {"status": "homing"}
            return {"status": "error", "message": "Servo controller not available"}

        @app.post("/api/grasp")
        async def trigger_grasp():
            """Trigger a single vision-guided grasp cycle."""
            return await _run_grasp()

        @app.get("/api/pipeline/status")
        async def pipeline_status():
            """Grasp pipeline status."""
            if state.pipeline is None:
                return {"available": False}
            return {
                "available": True,
                "driver": state.pipeline.driver.name,
                "mode": _grasp_config().get("mode", "simulation"),
                "gripper_ready": state.pipeline._gripper_ready,
                "object_models": list(state.pipeline.estimator.object_model_points.keys()),
            }

        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)

        logger.info(f"Web server starting on http://{host}:{port}")
        await server.serve()

    except ImportError:
        logger.warning("FastAPI/uvicorn not installed; web server not available")
    except Exception as e:
        logger.error(f"Failed to start web server: {e}")
        error_notifier.report(e)


# ---------------------------------------------------------------------------
# Cloud Sync
# ---------------------------------------------------------------------------


async def _cloud_sync_loop() -> None:
    """Background task for cloud synchronization."""
    cloud_config = state.config.config.get("cloud", {})
    if not cloud_config.get("enabled", False):
        logger.info("Cloud sync disabled")
        return

    sync_interval = cloud_config.get("sync_interval", 60)
    api_url = cloud_config.get("api_url", "")

    logger.info(f"Cloud sync enabled: interval={sync_interval}s, url={api_url}")

    while state.running:
        try:
            # Placeholder for actual cloud sync logic
            logger.debug(f"Cloud sync tick (interval={sync_interval}s)")
            await asyncio.sleep(sync_interval)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Cloud sync error: {e}")
            error_notifier.report(e)
            await asyncio.sleep(sync_interval)


# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------


async def _main_loop() -> None:
    """Main async event loop for the robotic arm system."""

    state.running = True
    logger.info("System running. Press Ctrl+C to stop.")

    # Start web server in background
    web_task = asyncio.create_task(_start_web_server())

    # Start cloud sync in background
    cloud_task = asyncio.create_task(_cloud_sync_loop())

    # Main loop - wait for shutdown signal
    try:
        await state.shutdown_event.wait()
    except asyncio.CancelledError:
        pass

    # Cancel background tasks
    for task in [web_task, cloud_task]:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


def main() -> int:
    """
    Main entry point for the robotic arm system.

    Returns:
        Exit code: 0 for success, 1 for failure.
    """
    # Register signal handlers
    _register_signal_handlers()

    try:
        # Run the async main
        asyncio.run(_async_main())
        return 0
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        return 1


async def _async_main() -> None:
    """Async entry point for the robotic arm system."""

    # Initialize system
    init_ok = await initialize_system()
    if not init_ok:
        logger.critical("System initialization failed")
        return

    # Run main loop
    try:
        await _main_loop()
    finally:
        await shutdown_system()


if __name__ == "__main__":
    sys.exit(main())