# ESP32 WiFi 模块配网固件

智能采样机械臂的 ESP32 WiFi 模块固件 (Arduino 框架)。

> 说明: 本项目主架构采用「外接 ESP32 AT 模块 + 树莓派 AT 指令驱动」
> (`rpi_control/hardware/esp32_wifi.py`)。本固件为**独立配网固件**,
> 适用于 ESP32 直接嵌入设备(无树莓派)或作为配网前端场景。

## 功能

1. **配网 (SoftAP 方式)**: 无配置或连不上时, ESP32 开启热点
   `SmartArm-XXXX` (XXXX 为芯片 ID 后 4 位), 浏览器访问 `192.168.4.1`
   填写 WiFi 账号密码。
2. **配置持久化**: 凭据写入 NVS (Preferences), 重启自动重连。
3. **状态上报**: 通过串口输出 `WIFI CONNECTED / SSID=xx / IP=xx`,
   供树莓派主控或宿主机解析。
4. **一键复位**: 长按 GPIO0 (BOOT) 5 秒清除配置并重新进入配网模式。

## 目录

```
esp32_firmware/
└── esp32_wifi_provisioning/
    └── esp32_wifi_provisioning.ino   # Arduino 源码
```

## 烧录

环境: Arduino IDE 或 PlatformIO, 安装 esp32 开发板支持包。

```bash
# Arduino IDE:
# 1. 文件 -> 首选项 -> 附加开发板管理器网址:
#    https://espressif.github.io/arduino-esp32/package_esp32_index.json
# 2. 工具 -> 开发板 -> esp32 -> ESP32 Dev Module
# 3. 打开 .ino 文件, 选择端口, 点击上传
```

## 使用

1. 首次上电, 手机/电脑连接热点 `SmartArm-XXXX`。
2. 打开浏览器访问 `192.168.4.1`, 填写目标 WiFi 的 SSID 与密码。
3. 保存后 ESP32 重启并自动连接, 串口输出连接状态与 IP。
4. 若更换 WiFi, 长按 GPIO0 5 秒清除配置后重新配网。

## 与树莓派主控的联动

- 方案 A (推荐): ESP32 刷 **Espressif AT 固件**, 树莓派用
  `esp32_wifi.py` 通过 AT 指令控制 (STA/AP/扫描)。
- 方案 B (本固件): ESP32 独立配网, 通过串口向树莓派输出
  `WIFI CONNECTED / IP=...`, 树莓派解析后即可知道设备已联网。
