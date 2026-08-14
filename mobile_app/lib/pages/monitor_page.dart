/// 监控页: 传感器数据 + 多端设备状态
library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/ws_client.dart';
import '../widgets/section_header.dart';
import '../widgets/status_card.dart';

class MonitorPage extends StatefulWidget {
  const MonitorPage({super.key});

  @override
  State<MonitorPage> createState() => _MonitorPageState();
}

class _MonitorPageState extends State<MonitorPage> {
  final _hub = HubClient.instance;
  final _api = ApiClient.instance;

  Map<String, dynamic> _armStatus = {};
  Map<String, dynamic> _sensors = {};
  Map<String, dynamic> _hubDevices = {};
  bool _hubConnected = false;
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    _hub.events.listen((e) {
      if (!mounted) return;
      switch (e.type) {
        case HubEventType.connected:
          setState(() => _hubConnected = true);
          break;
        case HubEventType.disconnected:
          setState(() => _hubConnected = false);
          break;
        case HubEventType.telemetry:
          setState(() => _sensors = e.data['data'] as Map<String, dynamic>? ?? _sensors);
          break;
        case HubEventType.deviceStatus:
          _fetchHubDevices();
          break;
        default:
          break;
      }
    });
    _hub.connect();
    _fetchData();
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) => _fetchData());
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _hub.close();
    super.dispose();
  }

  Future<void> _fetchData() async {
    try {
      final s = await _api.get('/api/v1/monitor/status');
      if (mounted) setState(() => _armStatus = (s as Map).cast<String, dynamic>());
    } catch (_) {}
    try {
      final h = await _api.get('/api/v1/hub/devices');
      if (mounted) {
        final m = h as Map;
        setState(() => _hubDevices = (m['devices'] as Map).cast<String, dynamic>());
      }
    } catch (_) {}
  }

  Future<void> _fetchHubDevices() async {
    try {
      final h = await _api.get('/api/v1/hub/devices');
      if (mounted) {
        final m = h as Map;
        setState(() => _hubDevices = (m['devices'] as Map).cast<String, dynamic>());
      }
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('实时监控'),
        actions: [
          Container(
            width: 12,
            height: 12,
            margin: const EdgeInsets.only(right: 16),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: _hubConnected ? Colors.green : Colors.red,
            ),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          // 中枢连接状态
          StatusCard(
            title: '多端中枢',
            value: _hubConnected ? '已连接' : '离线',
            color: _hubConnected ? Colors.green : Colors.red,
            icon: Icons.hub,
          ),
          const SizedBox(height: 8),

          // 机械臂状态
          const SectionHeader(icon: Icons.settings_input_component, title: '机械臂'),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            childAspectRatio: 2.5,
            mainAxisSpacing: 4,
            crossAxisSpacing: 4,
            children: [
              StatusCard(
                title: '运行状态',
                value: (_armStatus['is_moving'] == true) ? '运动中' : '待机',
                color: (_armStatus['is_moving'] == true) ? Colors.orange : Colors.green,
                icon: Icons.settings_input_component,
              ),
              StatusCard(
                title: '夹爪',
                value: (_armStatus['gripper_state'] ?? '--').toString(),
                icon: Icons.gesture,
              ),
            ],
          ),
          const SizedBox(height: 12),

          // 传感器数据
          const SectionHeader(icon: Icons.sensors, title: '传感器'),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            childAspectRatio: 2.5,
            mainAxisSpacing: 4,
            crossAxisSpacing: 4,
            children: [
              StatusCard(title: '温度', value: '${_sensors['temperature'] ?? '--'} °C'),
              StatusCard(title: '湿度', value: '${_sensors['humidity'] ?? '--'} %'),
              StatusCard(title: '电压', value: '${_sensors['voltage'] ?? '--'} V'),
              StatusCard(title: '电流', value: '${_sensors['current'] ?? '--'} A'),
            ],
          ),
          const SizedBox(height: 12),

          // 在线设备
          const SectionHeader(icon: Icons.devices, title: '在线设备'),
          if (_hubDevices.isEmpty)
            const Text('暂无在线设备', style: TextStyle(color: Colors.grey))
          else
            ..._hubDevices.entries.map((entry) => Card(
                  child: ListTile(
                    leading: const Icon(Icons.devices),
                    title: Text(entry.key),
                    subtitle: Text('${entry.value['device_type']} · ${entry.value['role']}'),
                    trailing: Text(entry.value['client_type'] ?? ''),
                  ),
                )),
        ],
      ),
    );
  }
}