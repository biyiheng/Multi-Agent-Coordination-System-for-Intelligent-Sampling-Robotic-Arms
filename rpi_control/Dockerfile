# =============================================================================
# 智能采样机械臂多智能体系统 - 生产级 Dockerfile
# 多阶段构建：构建阶段 → 生产阶段
# 支持多架构：amd64 (x86_64) + arm64 (Raspberry Pi 4/5)
#
# 构建命令:
#   docker build --platform linux/arm64 -t sampling-arm:latest .   # RPi
#   docker build --platform linux/amd64 -t sampling-arm:latest .   # x86_64
#   docker buildx build --platform linux/amd64,linux/arm64 -t sampling-arm:latest .  # 多架构
# =============================================================================

# ---- 构建阶段 ----
FROM --platform=$BUILDPLATFORM python:3.11-slim-bookworm AS builder

WORKDIR /build

# 安装编译依赖（ARM 和 x86 通用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make \
    libatlas-base-dev \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装到临时目录
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- 生产阶段 ----
FROM python:3.11-slim-bookworm

# 元数据标签
LABEL maintainer="Sampling Arm Team" \
      description="Intelligent Sampling Robotic Arm Multi-Agent System" \
      version="2.1.0" \
      org.opencontainers.image.source="https://github.com/sampling-arm" \
      org.opencontainers.image.arch="arm64,amd64"

# 安装运行时依赖（Raspberry Pi 和 x86 通用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libatlas-base-dev \
    libopenblas-dev \
    libgomp1 \
    curl \
    i2c-tools \
    libgpiod2 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 创建非 root 用户
RUN groupadd -r sampling && useradd -r -g sampling -d /app -s /sbin/nologin sampling

# 设置工作目录
WORKDIR /app

# 从构建阶段复制安装的包
COPY --from=builder /install /usr/local

# 复制应用代码（保持 rpi_control 包结构）
COPY --chown=sampling:sampling . /app/rpi_control/

# 创建数据和日志目录
RUN mkdir -p /app/rpi_control/data /app/rpi_control/logs \
    /app/rpi_control/images /app/rpi_control/reports \
    && chown -R sampling:sampling /app

# 设置 PYTHONPATH 以便导入 rpi_control 包
ENV PYTHONPATH=/app

# 切换到非 root 用户
USER sampling

# 暴露端口
# 8000: REST API (FastAPI + Uvicorn)
# 8001: WebSocket 实时遥测
EXPOSE 8000 8001

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    LOG_LEVEL=INFO \
    DOCKER_ENV=true

# 启动命令（使用模块方式运行以保持包结构）
CMD ["python", "-m", "rpi_control.main"]