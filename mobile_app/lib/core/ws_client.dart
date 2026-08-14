/// 多端互通中枢 WebSocket 客户端
///
/// 连接服务端 /ws/hub:
/// 1. 发送 hello 绑定 device_id (App 端)
/// 2. 订阅遥测 (telemetry) 与设备状态 (device_status)
/// 3. 下发命令 (command) 到 硬件/所有端
/// 4. 自动断线重连
library;

import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

import 'app_config.dart';

/// 中枢事件 (供 UI 监听)
enum HubEventType { connected, disconnected, telemetry, deviceStatus, command, ack, welcome, error }

class HubEvent {
  HubEvent(this.type, this.data);

  final HubEventType type;
  final Map<String, dynamic> data;
}

class HubClient {
  HubClient._();

  static final HubClient instance = HubClient._();

  WebSocketChannel? _channel;
  StreamSubscription? _sub;
  Timer? _reconnectTimer;
  bool _intentionalClose = false;

  final _events = StreamController<HubEvent>.broadcast();

  /// 对外暴露的事件流
  Stream<HubEvent> get events => _events.stream;

  bool get isConnected => _channel != null;

  Future<void> connect({String? deviceId}) async {
    _intentionalClose = false;
    _reconnectTimer?.cancel();

    final id = deviceId ??
        'app-${AppConfig.username.isEmpty ? 'anon' : AppConfig.username}';

    try {
      _channel = WebSocketChannel.connect(Uri.parse(AppConfig.wsUrl));
      await _channel!.ready;
    } catch (e) {
      _events.add(HubEvent(HubEventType.disconnected, {'error': e.toString()}));
      _scheduleReconnect();
      return;
    }

    // 发送 hello 绑定设备
    _channel!.sink.add(jsonEncode({
      'type': 'hello',
      'device_id': id,
      'client_type': AppConfig.clientType,
      'device_type': AppConfig.deviceType,
      'role': AppConfig.role == 'admin' ? 'controller' : 'observer',
      'name': 'App-${AppConfig.username}',
    }));

    _sub = _channel!.stream.listen(
      (raw) => _onMessage(raw),
      onError: (e) {
        _events.add(HubEvent(HubEventType.disconnected, {'error': e.toString()}));
        _scheduleReconnect();
      },
      onDone: () {
        if (!_intentionalClose) {
          _events.add(HubEvent(HubEventType.disconnected, {}));
          _scheduleReconnect();
        }
      },
    );

    _events.add(HubEvent(HubEventType.connected, {}));
  }

  void _onMessage(dynamic raw) {
    Map<String, dynamic>? msg;
    try {
      msg = jsonDecode(raw as String) as Map<String, dynamic>;
    } catch (_) {
      return;
    }
    switch (msg['type']) {
      case 'welcome':
        _events.add(HubEvent(HubEventType.welcome, msg));
        break;
      case 'telemetry':
        _events.add(HubEvent(HubEventType.telemetry, msg));
        break;
      case 'device_status':
        _events.add(HubEvent(HubEventType.deviceStatus, msg));
        break;
      case 'command':
        _events.add(HubEvent(HubEventType.command, msg));
        break;
      case 'command_ack':
        _events.add(HubEvent(HubEventType.ack, msg));
        break;
      case 'pong':
        break;
      default:
        _events.add(HubEvent(HubEventType.error, msg));
    }
  }

  /// 下发命令到目标端
  void sendCommand(String action, Map<String, dynamic> payload,
      {String target = 'all', int? seq}) {
    final ch = _channel;
    if (ch == null) return;
    ch.sink.add(jsonEncode({
      'type': 'command',
      'target': target,
      'action': action,
      'payload': payload,
      if (seq != null) 'seq': seq,
    }));
  }

  /// 上报遥测数据 (作为硬件端代理时使用)
  void sendTelemetry(Map<String, dynamic> data) {
    final ch = _channel;
    if (ch == null) return;
    ch.sink.add(jsonEncode({'type': 'telemetry', 'data': data}));
  }

  void _scheduleReconnect() {
    if (_intentionalClose || _reconnectTimer != null) return;
    _reconnectTimer = Timer(const Duration(seconds: 3), () {
      _reconnectTimer = null;
      connect();
    });
  }

  Future<void> close() async {
    _intentionalClose = true;
    _reconnectTimer?.cancel();
    _sub?.cancel();
    await _channel?.sink.close();
    _channel = null;
  }
}
