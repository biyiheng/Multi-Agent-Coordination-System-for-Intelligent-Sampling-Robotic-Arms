# Android / iOS 双端 App - 智能采样机械臂远程控制

基于 Flutter 的 Android/iOS 双端远程控制 App, 与服务端 (`rpi_control/web/server.py`)
通过 REST + WebSocket 多端互通中枢 (`/ws/hub`) 通信。

## 功能

- **登录/注册**: 与服务端共享账号体系, token 本地持久化
- **远程控制**: 6 关节滑杆控制 / 笛卡尔坐标移动 / 夹爪控制 / 回零 / 急停
- **实时监控**: 传感器数据 (温度/湿度/电压/电流) + 多端在线设备状态
- **WiFi 配网**: 扫描周边 AP / STA 连接 / AP 创建热点 / 状态查询
- **多端互通**: 通过 `/ws/hub` 与 小程序/Web/硬件端 数据互通

> **v1.1 更新**: 统一 Material 3 主题美化（圆角卡片 / SectionHeader / StatusCard / 夜间模式）; 服务端地址经 `shared_preferences` 持久化, 重启自动恢复; 新增 UI 冒烟测试 `test/smoke_test.dart`（6/6 通过）。
>
> **v1.2 更新**: 服务端遥测推送升级至 20 Hz, App 监控面板数据刷新更平滑（与 `settings.yaml → protocol.telemetry_push_rate` 联动）; 后端安全监控新增温度/电流过载事件, 监控面板展示对应告警; 全量回归测试通过, 详见 [20-更新报告v1.2.md](../项目文档/20-更新报告v1.2.md)。

## 环境要求

- Flutter SDK >= 3.0 (建议 3.16+)
- Android Studio (Android SDK) 或 Xcode (iOS)
- 服务端已运行: `python start_all.sh` (或 `uvicorn rpi_control.web.server:app`)

## 目录结构

```
mobile_app/
├── lib/
│   ├── main.dart              # 入口
│   ├── core/                  # 配置 / REST 客户端 / WebSocket 客户端 / 令牌存储
│   ├── models/                # (预留)
│   ├── services/              # 鉴权 / 机械臂 / WiFi / 任务 服务
│   ├── pages/                 # 登录 / 控制 / 监控 / WiFi / 设置
│   └── widgets/               # 关节滑杆 / 状态卡片
├── android/                   # Android 平台配置
├── ios/                       # iOS 平台配置
└── pubspec.yaml
```

## 构建与运行

```bash
cd mobile_app
flutter pub get

# Android
flutter build apk --release
# 或安装到设备
flutter run -d <device-id>

# iOS
flutter build ios --release
# 或安装到模拟器
flutter run -d ios
```

> 如果平台目录缺失, 可先执行 `flutter create . --platforms=android,ios` 重新生成,
> 再复制 `lib/` 与 `pubspec.yaml`。

## 配置服务端地址

默认连接 `192.168.1.100:8000`。可在 App「设置」页修改, 或在
`lib/core/app_config.dart` 中修改 `serverHost` / `serverPort`。

## 与后端接口对应关系

| App 功能 | REST 接口 |
| --- | --- |
| 登录 | `POST /api/v1/auth/login` |
| 注册 | `POST /api/v1/auth/register` |
| 关节/笛卡尔控制 | `POST /api/v1/arm/*` |
| 系统状态 | `GET /api/v1/monitor/status` |
| WiFi 配网 | `GET/POST /api/v1/wifi/*` |
| 实时数据 | `WS /ws/hub` (hello/command/telemetry) |
