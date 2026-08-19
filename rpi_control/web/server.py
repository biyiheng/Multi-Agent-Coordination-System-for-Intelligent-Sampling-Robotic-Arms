"""FastAPI server for the intelligent sampling robotic arm system."""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure the project root is on sys.path so that `rpi_control` package
# can be imported regardless of the working directory (works in Docker,
# direct execution, and test runners).
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from rpi_control.database.repository import db_manager
from rpi_control.web.routes import (
    arm_routes, vision_routes, task_routes, monitor_routes,
    auth_routes, device_routes, wifi_routes, system, loop_routes,
    sample_routes,
)
from rpi_control.web.websocket.handler import ws_manager, telemetry_stream
from rpi_control.web.websocket.hub import device_hub, handle_hub_connection

# Configure logging
log_dir = Path("./logs")
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(log_dir / "rpi_control.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown handlers."""
    # Startup
    logger.info("=" * 60)
    logger.info("Starting Intelligent Sampling Robotic Arm Server")
    logger.info("=" * 60)

    # Initialize database
    db_manager.init_db()
    logger.info("Database initialized")

    # Start telemetry streaming (v1.2: 频率可从 settings.yaml protocol.telemetry_push_rate 配置)
    try:
        from rpi_control.utils.config_loader import load_config
        _cfg = load_config()
        _push_rate = float(_cfg.get("protocol.telemetry_push_rate", 20))
        telemetry_stream.set_push_rate(_push_rate)
    except Exception:  # noqa: BLE001
        pass
    await telemetry_stream.start_streaming()
    logger.info("Telemetry streaming started")

    # Ensure data directory exists
    data_dir = Path("./data")
    data_dir.mkdir(parents=True, exist_ok=True)

    # Ensure snapshots directory exists
    snapshots_dir = Path("./data/snapshots")
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Server startup complete")

    yield

    # Shutdown
    logger.info("Shutting down server...")
    await telemetry_stream.stop_streaming()
    logger.info("Server shutdown complete")


app = FastAPI(
    title="Intelligent Sampling Robotic Arm API",
    description="REST API for controlling and monitoring an intelligent sampling robotic arm system",
    version="1.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS middleware - restrict origins via config, default to localhost in production
# In production, configure allowed origins via settings.yaml: web.cors_origins
_cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# Include route modules
app.include_router(arm_routes.router)
app.include_router(vision_routes.router)
app.include_router(task_routes.router)
app.include_router(monitor_routes.router)
app.include_router(auth_routes.router)
app.include_router(device_routes.router)
app.include_router(wifi_routes.router)
app.include_router(system.router)
app.include_router(loop_routes.router)
app.include_router(sample_routes.router)

# Static file serving for camera snapshots
snapshots_dir = Path("./data/snapshots")
snapshots_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/snapshots", StaticFiles(directory=str(snapshots_dir)), name="snapshots")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Intelligent Sampling Robotic Arm API",
        "version": "1.2.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    import time
    return {
        "status": "healthy",
        "version": "1.2.0",
        "uptime": "running",
        "timestamp": time.time(),
    }


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    """WebSocket endpoint for real-time telemetry data."""
    client_id = await ws_manager.connect(websocket)
    try:
        # Send initial status
        await ws_manager.send_to_client(client_id, {
            "type": "connected",
            "client_id": client_id,
            "message": "Connected to telemetry stream",
        })

        # Listen for client messages
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await ws_manager.send_to_client(client_id, {"type": "pong"})
    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
    finally:
        await ws_manager.disconnect(websocket)


@app.websocket("/ws/hub")
async def websocket_hub(websocket: WebSocket):
    """WebSocket endpoint for the multi-end device hub (App/小程序/Web/硬件).

    客户端先发送 hello 绑定 device_id + client_type, 之后可通过
    command / telemetry / ping 消息与其它端数据互通。
    """
    await handle_hub_connection(websocket)


@app.get("/api/v1/hub/devices")
async def hub_devices():
    """List devices currently connected to the multi-end hub."""
    return {"status": "ok", "count": device_hub.client_count,
            "devices": device_hub.get_devices()}


def main():
    """Entry point for running the server."""
    import uvicorn
    # reload=True is for development only; use reload=False in production
    _reload = os.getenv("ENV", "production") == "development"
    uvicorn.run(
        "rpi_control.web.server:app",
        host="0.0.0.0",
        port=8000,
        reload=_reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()