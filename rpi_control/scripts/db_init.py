#!/usr/bin/env python3
"""
Database initialization script.

Creates all database tables and populates default configuration data.
Run this script once during initial system setup.
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from database.models import Base, TaskModel, SampleModel, ActionLogModel, SystemConfigModel
from database.repository import db_manager


def init_database():
    """Initialize the database with all tables and default data."""
    print("=" * 60)
    print("Initializing Sampling System Database")
    print("=" * 60)

    # Ensure data directory exists
    data_dir = Path("./data")
    data_dir.mkdir(parents=True, exist_ok=True)
    print(f"Data directory: {data_dir.absolute()}")

    # Initialize database (create tables)
    db_manager.init_db()
    print("Database tables created successfully")

    # Populate default system configuration
    default_configs = [
        ("system.name", "智能采样机械臂多智能体协同系统", "System name"),
        ("system.version", "2.0.0", "System version"),
        ("system.log_level", "INFO", "Logging level"),
        ("safety.max_joint_velocity", "500", "Maximum joint velocity (PWM/s)"),
        ("safety.emergency_stop_timeout", "100", "Emergency stop timeout (ms)"),
        ("safety.watchdog_interval", "50", "Watchdog feed interval (ms)"),
        ("safety.comm_timeout", "500", "Communication timeout (ms)"),
        ("safety.collision_current_threshold", "800", "Collision current threshold (mA)"),
        ("safety.max_temperature", "70", "Maximum servo temperature (°C)"),
        ("safety.min_voltage", "6.0", "Minimum power voltage (V)"),
        ("safety.max_voltage", "8.4", "Maximum power voltage (V)"),
        ("motion.speed_coefficient", "50", "Global speed coefficient (%)"),
        ("motion.acceleration_coefficient", "30", "Acceleration coefficient (%)"),
        ("motion.default_move_time", "1000", "Default movement time (ms)"),
        ("vision.frame_rate", "30", "Camera frame rate (FPS)"),
        ("vision.resolution", "QVGA", "Camera resolution"),
        ("network.host", "0.0.0.0", "Web server host"),
        ("network.port", "8000", "Web server port"),
        ("network.ws_port", "8001", "WebSocket server port"),
        ("cloud.enabled", "true", "Cloud sync enabled"),
        ("cloud.sync_interval", "60", "Cloud sync interval (seconds)"),
    ]

    with db_manager.get_session() as session:
        for key, value, description in default_configs:
            existing = session.query(SystemConfigModel).filter_by(key=key).first()
            if not existing:
                config = SystemConfigModel(
                    key=key,
                    value_json=json.dumps(value),
                )
                session.add(config)
        session.commit()
        print(f"Inserted {len(default_configs)} default configuration entries")

    print("=" * 60)
    print("Database initialization complete!")
    print("=" * 60)


if __name__ == "__main__":
    init_database()