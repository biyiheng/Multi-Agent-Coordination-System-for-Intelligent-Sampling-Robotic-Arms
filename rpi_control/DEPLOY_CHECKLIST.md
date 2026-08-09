# 智能采样机械臂 - 部署检查清单 v2.2.0
# =============================================================================
# 使用说明：在部署前逐项检查，完成打 ✓
# =============================================================================

## 📦 所需应用下载链接

### 操作系统镜像
| 应用 | 下载链接 | 说明 |
|------|----------|------|
| Raspberry Pi OS Lite (64-bit) | [官方下载](https://downloads.raspberrypi.com/raspios_lite_arm64/images/raspios_lite_arm64-2025-10-02/2025-10-01-raspios-trixie-arm64-lite.img.xz) | 推荐 Debian Trixie 64-bit |
| Raspberry Pi OS Lite (64-bit) 清华镜像 | [清华镜像](https://mirrors.tuna.tsinghua.edu.cn/raspberry-pi-os-images/raspios_lite_arm64/images/) | 国内加速下载 |
| Raspberry Pi Imager | [官方下载](https://downloads.raspberrypi.com/imager/imager_latest.exe) | SD 卡烧录工具 |

### Docker 环境
| 应用 | 安装命令 | 说明 |
|------|----------|------|
| Docker Engine | `curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh` | 官方一键安装脚本 |
| Docker 文档 (RPi) | [官方文档](https://docs.docker.com/engine/install/raspberry-pi-os/) | Raspberry Pi OS 安装指南 |
| Docker 国内镜像 | [阿里云镜像](https://developer.aliyun.com/mirror/docker-ce) | 国内加速安装 |

### Python 环境
| 应用 | 安装命令 | 说明 |
|------|----------|------|
| Python 3.11+ | `sudo apt-get install -y python3 python3-pip python3-venv` | 系统包管理器安装 |
| pip 镜像 (清华) | `pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple` | 国内加速 |

### 辅助工具
| 应用 | 安装命令 | 说明 |
|------|----------|------|
| I2C 工具 | `sudo apt-get install -y i2c-tools` | I2C 总线调试 |
| 串口工具 | `sudo apt-get install -y minicom` | 串口通信调试 |
| GPIO 工具 | `sudo apt-get install -y libgpiod2 gpiod` | GPIO 控制 |
| 系统监控 | `sudo apt-get install -y htop` | 系统资源监控 |

---

## 1. 硬件检查
- [ ] Raspberry Pi 供电正常 (5V/3A)
- [ ] STM32 控制板连接正确 (GPIO14/15 UART)
- [ ] OpenMV 摄像头连接正确 (USB)
- [ ] 6 路舵机连接正常，无松动
- [ ] 机械臂结构稳固，无异常磨损
- [ ] 散热风扇工作正常
- [ ] 紧急停止按钮可用

## 2. 系统环境检查
- [ ] Raspberry Pi OS 已安装 (推荐 64-bit Lite)
  ```bash
  cat /proc/device-tree/model
  uname -m  # 应显示 aarch64
  ```
- [ ] 磁盘空间 ≥ 2GB（推荐 4GB+）
  ```bash
  df -h /
  # 预期: Available >= 2.0G
  ```
- [ ] Python 3.11+ 已安装
  ```bash
  python3 --version
  # 预期: Python 3.11.x 或更高
  ```
- [ ] 串口已启用
  ```bash
  # 检查 /boot/firmware/config.txt (Pi 5 Bookworm) 或 /boot/config.txt
  grep "enable_uart=1" /boot/firmware/config.txt || grep "enable_uart=1" /boot/config.txt
  # 如未启用，运行:
  sudo raspi-config  # Interface Options → Serial Port → No (login) → Yes (hardware)
  ls -la /dev/serial0
  ```
- [ ] I2C 已启用
  ```bash
  ls /dev/i2c-1  # 应存在
  ```
- [ ] 系统时区正确
  ```bash
  timedatectl set-timezone Asia/Shanghai
  ```
- [ ] 交换空间已配置（2GB 树莓派推荐）
  ```bash
  sudo dphys-swapfile swapoff
  sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=512/' /etc/dphys-swapfile
  sudo dphys-swapfile setup
  sudo dphys-swapfile swapon
  free -h  # 检查 Swap
  ```

## 3. 依赖安装
- [ ] pip 已更新
  ```bash
  pip install --upgrade pip
  ```
- [ ] 项目依赖已安装
  ```bash
  cd /path/to/rpi_control
  pip install -r requirements.txt
  ```
- [ ] Docker 已安装 (可选，用于容器化部署)
  ```bash
  curl -fsSL https://get.docker.com -o get-docker.sh
  sudo sh get-docker.sh
  sudo usermod -aG docker $USER
  # 重新登录后生效
  docker --version
  docker compose version
  ```

## 4. 配置文件
- [ ] .env 文件已创建（从 .env.example 复制）
  ```bash
  cp .env.example .env
  nano .env  # 根据需要修改
  ```
- [ ] settings.yaml 配置已检查
  - STM32 波特率正确 (38400 或 115200)
  - 工作空间范围正确
  - 安全参数已设置
  - 2GB RPi: 设置 `RPI_MEMORY_LIMIT=512M`, `RPI_CPU_LIMIT=1.0`

## 5. 固件检查
- [ ] STM32 固件已烧录
  ```bash
  python verify_firmware.py COM4 --baud 38400 --output report.json
  ```
- [ ] 所有伺服协议测试通过 (13/13)
- [ ] 固件版本正确

## 6. 模型检查
- [ ] 预训练模型文件存在
  ```bash
  ls -la models/
  # 应包含: motion_ik_model.pkl, safety_model.pkl, quality_model.pkl, collision_model.pkl
  ```
- [ ] 如需重新训练：
  ```bash
  # 标准训练（推荐 2-3 轮）
  python -m training.run_training --rounds 3
  # 或使用循环工程模式（自动迭代优化）：
  python -m training.run_training --loop --loop-iterations 10
  ```
- [ ] 模型元数据文件存在
  ```bash
  ls -la models/*_meta.json
  # 应包含: motion_ik_model_meta.json, safety_model_meta.json, quality_model_meta.json
  ```

## 7. 数据库检查
- [ ] 数据库文件已创建
  ```bash
  ls -la data/
  # 应包含 sampling.db
  ```

## 8. 启动前测试
- [ ] 单元测试全部通过
  ```bash
  python -m pytest tests/ -v
  ```
- [ ] Loop Engineering 测试通过
  ```bash
  python -m pytest loop_engineering/tests/ -v
  ```
- [ ] 串口通信测试通过
  ```bash
  python -c "import serial; s = serial.Serial('/dev/serial0', 38400, timeout=1); print('OK'); s.close()"
  ```
- [ ] 2GB 树莓派兼容性检查
  ```bash
  python -c "from utils.rpi_compat import check_2gb_compatibility; import json; print(json.dumps(check_2gb_compatibility(), indent=2, default=str))"
  ```

## 9. 启动服务
### 方式一：Docker 部署（推荐）
```bash
# 构建镜像
docker compose build

# 启动主控服务
docker compose up -d

# 查看状态
docker compose ps
docker compose logs -f rpi-control
```

### 方式二：直接部署（systemd）
```bash
sudo bash scripts/deploy.sh
```

### 方式三：开发模式
```bash
python main.py
```

## 10. 启动后验证
- [ ] API 健康检查
  ```bash
  curl http://localhost:8000/api/health
  # 预期: {"status": "ok", "stm32_connected": true, ...}
  ```
- [ ] API 文档可访问
  ```bash
  curl -s http://localhost:8000/docs | head -5
  # 或浏览器访问: http://<raspberry-pi-ip>:8000/docs
  ```
- [ ] WebSocket 连接测试
  ```bash
  # 安装 websocat: sudo apt-get install -y websocat
  websocat ws://localhost:8001/ws
  ```
- [ ] 日志正常
  ```bash
  tail -f logs/rpi_control.log
  ```

## 11. 安全配置
- [ ] 防火墙已配置 (仅允许 8000/8001 端口)
  ```bash
  sudo ufw allow 8000/tcp
  sudo ufw allow 8001/tcp
  sudo ufw enable
  sudo ufw status
  ```
- [ ] 非 root 用户运行
- [ ] 紧急停止功能正常
- [ ] 工作区域安全边界已设置

## 12. 备份
- [ ] 配置文件已备份
- [ ] 模型文件已备份
- [ ] 数据库已备份
- [ ] 部署脚本已备份

---

## 2GB 树莓派优化指南

### 内存优化
```bash
# 设置 Docker 内存限制
export RPI_MEMORY_LIMIT=512M
export RPI_CPU_LIMIT=1.0

# 禁用不必要的系统服务
sudo systemctl disable bluetooth
sudo systemctl disable avahi-daemon
sudo systemctl stop bluetooth avahi-daemon
```

### 磁盘优化
```bash
# 清理旧日志
sudo rm -rf logs/*.log

# 清理 Docker 缓存
docker system prune -a -f

# 清理 apt 缓存
sudo apt-get clean
sudo apt-get autoremove -y
```

### 性能监控
```bash
# 实时监控
htop

# 检查磁盘空间
df -h /

# 检查 Docker 资源使用
docker stats --no-stream
```

---

## 常见问题排查

### 串口无法打开
```bash
sudo chmod 666 /dev/serial0
sudo usermod -a -G dialout $USER
# 检查串口是否被其他进程占用
sudo lsof /dev/serial0
```

### Docker 权限问题
```bash
sudo usermod -a -G docker $USER
# 重新登录后生效
newgrp docker
```

### 模型加载失败
```bash
# 重新训练模型
python -m training.run_training --rounds 3
```

### 内存不足（2GB 树莓派）
```bash
# 增加交换空间
sudo dphys-swapfile swapoff
sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=1024/' /etc/dphys-swapfile
sudo dphys-swapfile setup
sudo dphys-swapfile swapon

# 限制 Docker 内存
docker compose up -d  # 自动读取 .env 中的 RPI_MEMORY_LIMIT
```

### 服务无法启动
```bash
# 检查端口占用
sudo lsof -i :8000
sudo lsof -i :8001

# 查看 Docker 日志
docker compose logs -f

# 查看 systemd 日志
journalctl -u rpi-sampling-arm -f

# 查看系统日志
sudo journalctl -xe
```

### Docker 镜像拉取慢
```bash
# 配置 Docker 国内镜像加速器
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<-'EOF'
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://dockerhub.timeweb.cloud"
  ]
}
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
```