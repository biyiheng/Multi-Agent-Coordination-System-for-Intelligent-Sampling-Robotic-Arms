/// WiFi / ESP32 配网服务
library;

import '../core/api_client.dart';

class WifiService {
  WifiService._();

  static final WifiService instance = WifiService._();

  Future<Map<String, dynamic>> getStatus() async {
    final d = await ApiClient.instance.get('/api/v1/wifi/status');
    return (d as Map).cast<String, dynamic>();
  }

  /// STA 连接热点
  Future<Map<String, dynamic>> connect(String ssid, String password,
      {double timeout = 15}) async {
    final d = await ApiClient.instance.post('/api/v1/wifi/connect', {
      'ssid': ssid,
      'password': password,
      'timeout': timeout,
    });
    return (d as Map).cast<String, dynamic>();
  }

  /// AP 创建热点
  Future<Map<String, dynamic>> createHotspot(String ssid, String password,
      {int channel = 6}) async {
    final d = await ApiClient.instance.post('/api/v1/wifi/hotspot', {
      'ssid': ssid,
      'password': password,
      'channel': channel,
    });
    return (d as Map).cast<String, dynamic>();
  }

  /// 扫描周边 AP
  Future<List<Map<String, dynamic>>> scan() async {
    final d = await ApiClient.instance.get('/api/v1/wifi/scan');
    return (d as List).cast<Map<String, dynamic>>();
  }

  Future<Map<String, dynamic>> reset() async {
    final d = await ApiClient.instance.post('/api/v1/wifi/reset', {});
    return (d as Map).cast<String, dynamic>();
  }
}
