/// 设置页: 用户信息 / 服务端地址 / 登出
library;

import 'package:flutter/material.dart';

import '../core/app_config.dart';
import '../core/auth_store.dart';
import '../widgets/section_header.dart';
import 'login_page.dart';

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  final _hostCtrl = TextEditingController(text: AppConfig.serverHost);
  final _portCtrl = TextEditingController(text: AppConfig.serverPort.toString());

  @override
  void dispose() {
    _hostCtrl.dispose();
    _portCtrl.dispose();
    super.dispose();
  }

  Future<void> _saveServer() async {
    final port = int.tryParse(_portCtrl.text.trim()) ?? AppConfig.serverPort;
    await AppConfig.save(_hostCtrl.text, port);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('服务端地址已保存: ${AppConfig.baseUrl}'),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  Future<void> _logout() async {
    await AuthStore.instance.clear();
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginPage()),
      (_) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final store = AuthStore.instance;
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('设置')),
      body: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          // 用户信息
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 26,
                    backgroundColor: scheme.primaryContainer,
                    child: Text(
                      (store.username ?? '?')[0].toUpperCase(),
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: scheme.onPrimaryContainer,
                      ),
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(store.username ?? '未登录',
                            style: Theme.of(context).textTheme.titleMedium),
                        const SizedBox(height: 2),
                        Text('角色: ${store.role ?? 'user'}',
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                  color: scheme.onSurfaceVariant,
                                )),
                      ],
                    ),
                  ),
                  Icon(Icons.verified_user, color: scheme.primary),
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),

          // 服务端地址
          const SectionHeader(icon: Icons.dns, title: '服务端地址'),
          Row(
            children: [
              Expanded(
                flex: 3,
                child: TextField(
                  controller: _hostCtrl,
                  decoration: const InputDecoration(
                    labelText: '主机',
                    prefixIcon: Icon(Icons.computer),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              SizedBox(
                width: 90,
                child: TextField(
                  controller: _portCtrl,
                  decoration: const InputDecoration(
                    labelText: '端口',
                    prefixIcon: Icon(Icons.numbers),
                  ),
                  keyboardType: TextInputType.number,
                ),
              ),
              const SizedBox(width: 8),
              FilledButton.tonal(
                onPressed: _saveServer,
                child: const Text('保存'),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Card(
            child: ListTile(
              leading: Icon(Icons.info_outline, color: scheme.primary),
              title: const Text('当前地址'),
              subtitle: Text(AppConfig.baseUrl),
            ),
          ),
          const SizedBox(height: 16),

          // 登出
          FilledButton.icon(
            onPressed: _logout,
            icon: const Icon(Icons.logout),
            label: const Text('退出登录'),
            style: FilledButton.styleFrom(
              backgroundColor: scheme.error,
              foregroundColor: scheme.onError,
            ),
          ),
          const SizedBox(height: 12),

          // 版本信息
          Text(
            '智能采样机械臂远程控制 · v1.1.0',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: scheme.onSurfaceVariant,
                ),
          ),
        ],
      ),
    );
  }
}
