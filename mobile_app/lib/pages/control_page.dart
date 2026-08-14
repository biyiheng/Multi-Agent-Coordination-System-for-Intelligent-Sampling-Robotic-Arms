/// 控制页: 关节控制 + 笛卡尔控制 + 夹爪 + 急停
library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../services/arm_service.dart';
import '../widgets/joint_slider.dart';
import '../widgets/section_header.dart';
import '../widgets/status_card.dart';

class ControlPage extends StatefulWidget {
  const ControlPage({super.key});

  @override
  State<ControlPage> createState() => _ControlPageState();
}

class _ControlPageState extends State<ControlPage> {
  final _armService = ArmService.instance;

  // 6 关节 PWM 值
  final _joints = List<double>.generate(6, (_) => 1500.0);
  bool _estop = false;
  bool _gripperOpen = true;
  int _gripperForce = 50;

  // 笛卡尔目标
  final _cx = TextEditingController(text: '200');
  final _cy = TextEditingController(text: '0');
  final _cz = TextEditingController(text: '150');
  final _gripperForceCtrl = TextEditingController(text: '50');

  String _status = '未知';
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    _fetchStatus();
    _pollTimer = Timer.periodic(const Duration(seconds: 3), (_) => _fetchStatus());
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _cx.dispose();
    _cy.dispose();
    _cz.dispose();
    _gripperForceCtrl.dispose();
    super.dispose();
  }

  Future<void> _fetchStatus() async {
    try {
      final s = await _armService.getStatus();
      if (!mounted) return;
      setState(() {
        final safety = s['safety_status'] as Map<String, dynamic>?;
        _estop = safety?['emergency_stop'] == true;
        _status = _estop
            ? '急停'
            : (s['is_moving'] == true ? '运动中' : '在线');
      });
    } catch (_) {
      if (mounted) setState(() => _status = '离线');
    }
  }

  Future<void> _moveJoint(int idx) async {
    try {
      await _armService.moveJoint(idx, _joints[idx], time: 1.0);
    } catch (_) {}
  }

  Future<void> _moveAll() async {
    try {
      await _armService.moveAll(List.from(_joints), time: 1.0);
    } catch (_) {}
  }

  Future<void> _moveCartesian() async {
    final x = double.tryParse(_cx.text) ?? 200;
    final y = double.tryParse(_cy.text) ?? 0;
    final z = double.tryParse(_cz.text) ?? 150;
    try {
      await _armService.moveCartesian(x, y, z, time: 2.0);
    } catch (_) {}
  }

  Future<void> _toggleGripper() async {
    try {
      if (_gripperOpen) {
        await _armService.closeGripper(force: _gripperForce.toDouble());
      } else {
        await _armService.openGripper();
      }
      setState(() => _gripperOpen = !_gripperOpen);
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final online = _status != '离线';
    return Scaffold(
      appBar: AppBar(
        title: const Text('远程控制'),
        actions: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: online
                  ? Colors.green.withValues(alpha: 0.15)
                  : Colors.grey.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              children: [
                Icon(
                  online ? Icons.circle : Icons.circle_outlined,
                  size: 10,
                  color: online ? Colors.green : Colors.grey,
                ),
                const SizedBox(width: 6),
                Text(_status, style: Theme.of(context).textTheme.labelMedium),
              ],
            ),
          ),
          const SizedBox(width: 12),
        ],
      ),
      body: ListView(
        children: [
          // 状态卡片
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Row(
              children: [
                Expanded(
                  child: StatusCard(
                    title: '急停状态',
                    value: _estop ? '已触发' : '正常',
                    color: _estop ? Colors.red : Colors.green,
                    icon: _estop ? Icons.warning : Icons.check_circle,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: StatusCard(
                    title: '夹爪',
                    value: _gripperOpen ? '张开' : '闭合',
                    color: _gripperOpen ? Colors.blue : Colors.orange,
                    icon: _gripperOpen ? Icons.open_in_full : Icons.close_fullscreen,
                  ),
                ),
              ],
            ),
          ),

          // 关节滑杆
          const SectionHeader(icon: Icons.tune, title: '关节控制 (PWM)'),
          for (int i = 0; i < 6; i++)
            JointSlider(
              label: 'J${i + 1}',
              value: _joints[i],
              min: 500,
              max: 2500,
              onChanged: (v) => setState(() => _joints[i] = v),
              onMoveEnd: () => _moveJoint(i),
            ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            child: FilledButton.tonalIcon(
              onPressed: _moveAll,
              icon: const Icon(Icons.send),
              label: const Text('发送全部关节'),
            ),
          ),

          const Divider(height: 24),

          // 笛卡尔控制
          const SectionHeader(icon: Icons.open_in_full, title: '笛卡尔坐标 (mm)'),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            child: Row(
              children: [
                Expanded(child: TextField(controller: _cx, decoration: const InputDecoration(labelText: 'X', isDense: true))),
                const SizedBox(width: 8),
                Expanded(child: TextField(controller: _cy, decoration: const InputDecoration(labelText: 'Y', isDense: true))),
                const SizedBox(width: 8),
                Expanded(child: TextField(controller: _cz, decoration: const InputDecoration(labelText: 'Z', isDense: true))),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            child: FilledButton.tonalIcon(
              onPressed: _moveCartesian,
              icon: const Icon(Icons.gps_fixed),
              label: const Text('移动至目标点'),
            ),
          ),

          const Divider(height: 24),

          // 夹爪与安全
          const SectionHeader(icon: Icons.handshake, title: '夹爪与安全'),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            child: Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _toggleGripper,
                    icon: Icon(_gripperOpen ? Icons.handshake : Icons.back_hand),
                    label: Text(_gripperOpen ? '闭合夹爪' : '张开夹爪'),
                  ),
                ),
                const SizedBox(width: 8),
                SizedBox(
                  width: 100,
                  child: TextField(
                    controller: _gripperForceCtrl,
                    decoration: const InputDecoration(
                      labelText: '夹持力',
                      isDense: true,
                      prefixIcon: Icon(Icons.fitness_center, size: 18),
                    ),
                    keyboardType: TextInputType.number,
                    onChanged: (v) => _gripperForce = int.tryParse(v) ?? 50,
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: () async {
                      try {
                        await _armService.home();
                      } catch (_) {}
                    },
                    icon: const Icon(Icons.home),
                    label: const Text('回零'),
                    style: FilledButton.styleFrom(
                        backgroundColor: Colors.orange,
                        foregroundColor: Colors.white),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _estop
                        ? () async {
                            try {
                              await _armService.clearEstop();
                              setState(() => _estop = false);
                            } catch (_) {}
                          }
                        : () async {
                            try {
                              await _armService.estop();
                              setState(() => _estop = true);
                            } catch (_) {}
                          },
                    icon: Icon(_estop ? Icons.restart_alt : Icons.stop_circle),
                    label: Text(_estop ? '解除急停' : '急停'),
                    style: FilledButton.styleFrom(
                      backgroundColor: _estop ? Colors.green : Colors.red,
                      foregroundColor: Colors.white,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}