/// 全局应用配置
///
/// [serverHost] 为树莓派服务端地址。默认使用局域网地址,
/// 部署到真实硬件后请在设置页修改 (会持久化到 shared_preferences)。
library;

import 'package:shared_preferences/shared_preferences.dart';

class AppConfig {
  AppConfig._();

  static const String _defaultServerHost = '192.168.1.100';
  static const int _defaultServerPort = 8000;

  static const String _keyHost = 'server_host';
  static const String _keyPort = 'server_port';

  /// 服务端地址 (REST API 与 WebSocket 共用的主机)
  static String serverHost = _defaultServerHost;

  /// 服务端口 (与 rpi_control/web/server.py 一致)
  static int serverPort = _defaultServerPort;

  /// 客户端类型: app (Android/iOS 双端 App)
  static const String clientType = 'app';

  /// 设备类型
  static const String deviceType = 'app';

  /// 当前登录用户 (由 AuthService 注入)
  static String username = '';

  /// 当前用户角色
  static String role = 'user';

  static String get baseUrl => 'http://$serverHost:$serverPort';

  static String get wsUrl => 'ws://$serverHost:$serverPort/ws/hub';

  /// 应用启动时恢复已保存的服务端配置
  static Future<void> restore() async {
    final prefs = await SharedPreferences.getInstance();
    serverHost = prefs.getString(_keyHost) ?? _defaultServerHost;
    serverPort = prefs.getInt(_keyPort) ?? _defaultServerPort;
  }

  /// 保存服务端配置 (持久化, 立即生效)
  static Future<void> save(String host, int port) async {
    serverHost = host.trim().isEmpty ? _defaultServerHost : host.trim();
    serverPort = port;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyHost, serverHost);
    await prefs.setInt(_keyPort, serverPort);
  }
}
