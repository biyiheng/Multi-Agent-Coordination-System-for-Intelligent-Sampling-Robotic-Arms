/// WiFi 配网页: 扫描 / 连接 / 创建热点 / 状态
library;

import 'package:flutter/material.dart';

import '../services/wifi_service.dart';
import '../widgets/section_header.dart';
import '../widgets/status_card.dart';

class WifiPage extends StatefulWidget {
  const WifiPage({super.key});

  @override
  State<WifiPage> createState() => _WifiPageState();
}

class _WifiPageState extends State<WifiPage> {
  final _wifi = WifiService.instance;
  final _ssidCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  final _apSsidCtrl = TextEditingController();
  final _apPassCtrl = TextEditingController();

  Map<String, dynamic> _status = {};
  List<Map<String, dynamic>> _scanResults = [];
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _refreshStatus();
  }

  @override
  void dispose() {
    _ssidCtrl.dispose();
    _passCtrl.dispose();
    _apSsidCtrl.dispose();
    _apPassCtrl.dispose();
    super.dispose();
  }

  Future<void> _refreshStatus() async {
    try {
      final s = await _wifi.getStatus();
      if (mounted) setState(() => _status = s);
    } catch (_) {}
  }

  Future<void> _scan() async {
    setState(() => _loading = true);
    try {
      final r = await _wifi.scan();
      if (mounted) setState(() => _scanResults = r);
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _connect() async {
    setState(() => _loading = true);
    try {
      await _wifi.connect(_ssidCtrl.text.trim(), _passCtrl.text);
      await _refreshStatus();
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _createAp() async {
    setState(() => _loading = true);
    try {
      await _wifi.createHotspot(_apSsidCtrl.text.trim(), _apPassCtrl.text);
      await _refreshStatus();
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    final connected = _status['connected'] == true;
    final ssid = _status['ssid'] ?? '--';
    final ip = _status['ip'] ?? '--';
    final mode = _status['mode'] ?? 'unknown';

    return Scaffold(
      appBar: AppBar(title: const Text('WiFi 配网')),
      body: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          // 状态卡片
          StatusCard(
            title: 'WiFi 状态',
            value: connected ? '已连接 ($ssid)' : '未连接',
            color: connected ? Colors.green : Colors.grey,
            icon: connected ? Icons.wifi : Icons.wifi_off,
          ),
          const SizedBox(height: 4),
          Text('IP: $ip  模式: $mode',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  )),
          const SizedBox(height: 12),

          // STA 连接
          const SectionHeader(icon: Icons.wifi_find, title: '连接热点 (STA)'),
          TextField(
            controller: _ssidCtrl,
            decoration: const InputDecoration(
              labelText: 'SSID',
              prefixIcon: Icon(Icons.wifi),
            ),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _passCtrl,
            obscureText: true,
            decoration: const InputDecoration(
              labelText: '密码',
              prefixIcon: Icon(Icons.lock),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: FilledButton.tonalIcon(
                  onPressed: _loading ? null : _connect,
                  icon: const Icon(Icons.wifi_find),
                  label: const Text('连接'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _loading ? null : _scan,
                  icon: const Icon(Icons.search),
                  label: const Text('扫描'),
                ),
              ),
            ],
          ),

          const SizedBox(height: 8),
          if (_loading) const LinearProgressIndicator(),
          const Divider(height: 24),

          // 扫描结果
          if (_scanResults.isNotEmpty) ...[
            const SectionHeader(icon: Icons.network_wifi, title: '附近网络'),
            ..._scanResults.map((ap) => Card(
                  margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 3),
                  child: ListTile(
                    leading: Icon(
                      (ap['rssi'] as int? ?? -100) > -60
                          ? Icons.wifi
                          : Icons.wifi_2_bar,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                    title: Text(ap['ssid'] ?? ''),
                    subtitle: Text('信号: ${ap['rssi']} dBm  CH: ${ap['channel']}'),
                    onTap: () => _ssidCtrl.text = ap['ssid'] ?? '',
                  ),
                )),
            const Divider(height: 24),
          ],

          // AP 创建
          const SectionHeader(icon: Icons.wifi_tethering, title: '创建热点 (AP)'),
          TextField(
            controller: _apSsidCtrl,
            decoration: const InputDecoration(
              labelText: '热点名称',
              prefixIcon: Icon(Icons.dns),
            ),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _apPassCtrl,
            obscureText: true,
            decoration: const InputDecoration(
              labelText: '密码 (可选)',
              prefixIcon: Icon(Icons.password),
            ),
          ),
          const SizedBox(height: 8),
          FilledButton.icon(
            onPressed: _loading ? null : _createAp,
            icon: const Icon(Icons.wifi_tethering),
            label: const Text('创建热点'),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}