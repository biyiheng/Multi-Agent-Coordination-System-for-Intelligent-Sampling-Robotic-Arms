#!/bin/bash
# Deployment script for the Intelligent Sampling Robotic Arm system
# Usage:
#   bash deploy.sh              # Direct deployment (systemd)
#   bash deploy.sh --docker     # Docker deployment

set -e

echo "============================================"
echo "  Robotic Arm System Deployment"
echo "============================================"
echo ""

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "Project directory: $PROJECT_DIR"

# Check deployment mode
DEPLOY_MODE="direct"
if [ "$1" == "--docker" ]; then
    DEPLOY_MODE="docker"
fi
echo "Deployment mode: $DEPLOY_MODE"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "WARNING: Not running as root. Some operations may fail."
    echo "Consider running with: sudo bash deploy.sh"
    echo ""
fi

# ===========================================================================
# 0. System Pre-checks (Storage, Memory, Platform)
# ===========================================================================
echo "[0/7] Running system pre-checks..."

# Check available disk space (2GB minimum for Raspberry Pi)
AVAILABLE_DISK_KB=$(df -k "$PROJECT_DIR" | tail -1 | awk '{print $4}')
AVAILABLE_DISK_MB=$((AVAILABLE_DISK_KB / 1024))
echo "  Available disk space: ${AVAILABLE_DISK_MB}MB"

if [ "$AVAILABLE_DISK_MB" -lt 2048 ]; then
    echo "  WARNING: Less than 2GB disk space available (${AVAILABLE_DISK_MB}MB)"
    echo "  The system requires at least 2GB for models, data, logs, and Docker images."
    echo "  Consider cleaning up old logs and data:"
    echo "    rm -rf $PROJECT_DIR/logs/*.log"
    echo "    docker system prune -a  # If using Docker"
    echo ""
    read -p "Continue anyway? [y/N]: " continue_anyway
    if [ "$continue_anyway" != "y" ] && [ "$continue_anyway" != "Y" ]; then
        echo "Deployment aborted due to insufficient disk space."
        exit 1
    fi
fi

# Check memory for 2GB Raspberry Pi
if [ -f /proc/meminfo ]; then
    TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    TOTAL_MEM_MB=$((TOTAL_MEM_KB / 1024))
    echo "  Total memory: ${TOTAL_MEM_MB}MB"
    if [ "$TOTAL_MEM_MB" -lt 2048 ]; then
        echo "  WARNING: Less than 2GB memory detected (${TOTAL_MEM_MB}MB)"
        echo "  Reducing Docker memory limit to 512M..."
        export RPI_MEMORY_LIMIT="512M"
        export RPI_CPU_LIMIT="1.0"
    fi
fi

echo "  Done."
echo ""

# ===========================================================================
# Docker Deployment
# ===========================================================================
if [ "$DEPLOY_MODE" == "docker" ]; then
    echo "--- Docker Deployment ---"
    echo ""

    # Check Docker installation
    if ! command -v docker &> /dev/null; then
        echo "ERROR: Docker is not installed. Please install Docker first."
        echo "  curl -fsSL https://get.docker.com | sh"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        echo "ERROR: Docker Compose is not installed."
        exit 1
    fi

    # Setup .env if not exists
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        echo "[1/4] Creating .env from .env.example..."
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        echo "  Created .env file. Please review and adjust settings."
        echo "  nano $PROJECT_DIR/.env"
    else
        echo "[1/4] .env file already exists, skipping"
    fi

    # Create data directories for volume mounts
    echo "[2/4] Creating data directories..."
    mkdir -p "$PROJECT_DIR/data"
    mkdir -p "$PROJECT_DIR/logs"
    mkdir -p "$PROJECT_DIR/images"
    mkdir -p "$PROJECT_DIR/reports"
    echo "  Done."

    # Configure UART permissions (same as direct mode)
    echo "[3/4] Configuring UART permissions..."
    if [ -n "$SUDO_USER" ]; then
        usermod -a -G dialout "$SUDO_USER" 2>/dev/null || echo "  Could not add user to dialout group"
    fi
    if [ -e /dev/ttyAMA0 ]; then
        chmod 666 /dev/ttyAMA0 2>/dev/null || echo "  Could not set ttyAMA0 permissions"
    fi
    if [ -e /dev/ttyS0 ]; then
        chmod 666 /dev/ttyS0 2>/dev/null || echo "  Could not set ttyS0 permissions"
    fi
    if [ -e /dev/ttyUSB0 ]; then
        chmod 666 /dev/ttyUSB0 2>/dev/null || echo "  Could not set ttyUSB0 permissions"
    fi
    echo "  Done."

    # Build and start
    echo "[4/4] Building and starting Docker services..."
    cd "$PROJECT_DIR"
    docker-compose build
    docker-compose up -d
    echo "  Done."

    # Summary
    echo ""
    echo "============================================"
    echo "  Docker Deployment Complete!"
    echo "============================================"
    echo ""
    echo "Service status:"
    docker-compose ps
    echo ""
    echo "View logs:"
    echo "  docker-compose logs -f rpi-control"
    echo ""
    echo "Stop services:"
    echo "  docker-compose down"
    echo ""
    echo "API documentation:"
    echo "  http://<raspberry-pi-ip>:8000/docs"
    echo ""
    exit 0
fi

# ===========================================================================
# Direct Deployment (systemd)
# ===========================================================================

# -------------------------------------------------------------------
# 1. Detect Raspberry Pi model and configure hardware
# -------------------------------------------------------------------
echo "[1/7] Detecting Raspberry Pi model..."

RPI_MODEL="unknown"
if [ -f /proc/device-tree/model ]; then
    RPI_MODEL=$(tr -d '\0' < /proc/device-tree/model)
    echo "  Detected: $RPI_MODEL"
else
    echo "  Not running on Raspberry Pi (or /proc/device-tree not available)"
fi

# Detect Pi generation
RPI_GEN=""
if echo "$RPI_MODEL" | grep -q "Raspberry Pi 5"; then
    RPI_GEN="pi5"
    UART_DEVICE="/dev/ttyAMA0"
    GPIO_CHIP="gpiochip4"
elif echo "$RPI_MODEL" | grep -q "Raspberry Pi 4"; then
    RPI_GEN="pi4"
    UART_DEVICE="/dev/serial0"
    GPIO_CHIP="gpiochip0"
elif echo "$RPI_MODEL" | grep -q "Raspberry Pi 3"; then
    RPI_GEN="pi3"
    UART_DEVICE="/dev/serial0"
    GPIO_CHIP="gpiochip0"
else
    RPI_GEN="generic"
    UART_DEVICE="/dev/ttyAMA0"
    GPIO_CHIP="gpiochip0"
fi
echo "  Pi Generation: $RPI_GEN"
echo "  UART Device: $UART_DEVICE"
echo ""

# -------------------------------------------------------------------
# 2. Enable UART and I2C (Raspberry Pi specific)
# -------------------------------------------------------------------
echo "[2/7] Configuring hardware interfaces..."

# Enable UART in config.txt if needed
if [ "$RPI_GEN" != "generic" ] && [ -f /boot/config.txt ]; then
    if ! grep -q "^enable_uart=1" /boot/config.txt 2>/dev/null; then
        echo "  Enabling UART in /boot/config.txt..."
        echo "enable_uart=1" >> /boot/config.txt
        echo "  NOTE: Reboot required for UART changes to take effect"
    else
        echo "  UART already enabled in /boot/config.txt"
    fi
fi

# Enable I2C via raspi-config
if [ "$RPI_GEN" != "generic" ] && command -v raspi-config &> /dev/null; then
    echo "  Enabling I2C interface..."
    raspi-config nonint do_i2c 0 2>/dev/null || echo "    Could not enable I2C (may already be enabled)"
fi

# Install system dependencies
echo "  Installing system dependencies..."
if command -v apt-get &> /dev/null; then
    apt-get update -qq
    apt-get install -y -qq \
        python3 python3-pip python3-venv \
        git \
        i2c-tools \
        libgpiod2 \
        libatlas-base-dev \
        libopenjp2-7 \
        libtiff5 \
        libjpeg-dev \
        libpng-dev \
        || echo "    Warning: Some packages may not have installed"
else
    echo "    apt-get not found, skipping system package installation"
fi
echo "  Done."

# -------------------------------------------------------------------
# 3. Install Python dependencies
# -------------------------------------------------------------------
echo "[3/7] Installing Python dependencies..."

if [ ! -d "$PROJECT_DIR/venv" ]; then
    python3 -m venv "$PROJECT_DIR/venv"
    echo "  Virtual environment created at $PROJECT_DIR/venv"
fi

source "$PROJECT_DIR/venv/bin/activate"

pip install --upgrade pip -q
pip install -r "$PROJECT_DIR/requirements.txt" -q || {
    echo "  requirements.txt not found, installing core packages..."
    pip install fastapi uvicorn[standard] sqlalchemy pydantic websockets -q
}

echo "  Done."

# -------------------------------------------------------------------
# 4. Create data directories
# -------------------------------------------------------------------
echo "[4/7] Creating data directories..."
mkdir -p "$PROJECT_DIR/data/snapshots"
mkdir -p "$PROJECT_DIR/data/reports"
mkdir -p "$PROJECT_DIR/data/logs"
echo "  Done."

# -------------------------------------------------------------------
# 5. Configure UART permissions
# -------------------------------------------------------------------
echo "[5/7] Configuring UART permissions..."

# Add user to dialout group for serial access
if [ -n "$SUDO_USER" ]; then
    usermod -a -G dialout "$SUDO_USER" 2>/dev/null || echo "  Could not add user to dialout group"
fi

# Set UART permissions
if [ -e /dev/ttyAMA0 ]; then
    chmod 666 /dev/ttyAMA0 2>/dev/null || echo "  Could not set ttyAMA0 permissions"
fi
if [ -e /dev/ttyS0 ]; then
    chmod 666 /dev/ttyS0 2>/dev/null || echo "  Could not set ttyS0 permissions"
fi
if [ -e /dev/ttyUSB0 ]; then
    chmod 666 /dev/ttyUSB0 2>/dev/null || echo "  Could not set ttyUSB0 permissions"
fi

echo "  Done."

# -------------------------------------------------------------------
# 6. Setup systemd service
# -------------------------------------------------------------------
echo "[6/7] Setting up systemd service..."

SERVICE_FILE="/etc/systemd/system/rpi-sampling-arm.service"

cat > "$SERVICE_FILE" << SERVICE_EOF
[Unit]
Description=Intelligent Sampling Robotic Arm Server
After=network.target

[Service]
Type=simple
User=${SUDO_USER:-pi}
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PROJECT_DIR/venv/bin/python -m rpi_control.web.server
Restart=on-failure
RestartSec=5
StandardOutput=append:$PROJECT_DIR/data/logs/server.log
StandardError=append:$PROJECT_DIR/data/logs/server_error.log

[Install]
WantedBy=multi-user.target
SERVICE_EOF

systemctl daemon-reload
systemctl enable rpi-sampling-arm.service 2>/dev/null || echo "  Could not enable service"

echo "  Done."

# -------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------
echo ""
echo "============================================"
echo "  Deployment Complete!"
echo "============================================"
echo ""
echo "To start the server:"
echo "  sudo systemctl start rpi-sampling-arm"
echo ""
echo "To check status:"
echo "  sudo systemctl status rpi-sampling-arm"
echo ""
echo "API documentation:"
echo "  http://<raspberry-pi-ip>:8000/docs"
echo ""
echo "Logs:"
echo "  $PROJECT_DIR/data/logs/"
echo ""

# Start the service if requested
read -p "Start the service now? [y/N]: " start_now
if [ "$start_now" = "y" ] || [ "$start_now" = "Y" ]; then
    systemctl start rpi-sampling-arm.service
    echo "Service started. Checking status..."
    sleep 2
    systemctl status rpi-sampling-arm.service --no-pager
fi