/// UI 冒烟测试: 验证关键页面可正常构建渲染, 无异常抛出。
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:smart_sampling_arm_app/pages/login_page.dart';
import 'package:smart_sampling_arm_app/pages/control_page.dart';
import 'package:smart_sampling_arm_app/pages/monitor_page.dart';
import 'package:smart_sampling_arm_app/pages/wifi_page.dart';
import 'package:smart_sampling_arm_app/pages/settings_page.dart';
import 'package:smart_sampling_arm_app/widgets/section_header.dart';
import 'package:smart_sampling_arm_app/widgets/status_card.dart';
import 'package:smart_sampling_arm_app/widgets/joint_slider.dart';

void main() {
  group('页面渲染冒烟测试', () {
    Future<void> pumpPage(WidgetTester tester, Widget page) async {
      await tester.pumpWidget(MaterialApp(home: page));
      await tester.pump(const Duration(milliseconds: 100));
    }

    testWidgets('登录页可渲染', (tester) async {
      await pumpPage(tester, const LoginPage());
      expect(find.text('智能采样机械臂'), findsOneWidget);
      expect(find.text('登录'), findsOneWidget);
    });

    testWidgets('控制页可渲染 (含 6 关节滑杆与急停按钮)', (tester) async {
      await pumpPage(tester, const ControlPage());
      expect(find.text('远程控制'), findsOneWidget);
      expect(find.byType(JointSlider), findsNWidgets(6));
      // 滚动到底部确认安全操作区存在
      await tester.drag(find.byType(ListView), const Offset(0, -800));
      await tester.pump();
      expect(find.text('急停'), findsOneWidget);
    });

    testWidgets('监控页可渲染', (tester) async {
      await pumpPage(tester, const MonitorPage());
      expect(find.text('实时监控'), findsOneWidget);
      expect(find.text('多端中枢'), findsOneWidget);
    });

    testWidgets('WiFi 页可渲染', (tester) async {
      await pumpPage(tester, const WifiPage());
      expect(find.text('WiFi 配网'), findsOneWidget);
      expect(find.text('连接热点 (STA)'), findsOneWidget);
    });

    testWidgets('设置页可渲染', (tester) async {
      await pumpPage(tester, const SettingsPage());
      expect(find.text('设置'), findsOneWidget);
      expect(find.text('退出登录'), findsOneWidget);
    });

    testWidgets('通用组件可渲染', (tester) async {
      await pumpPage(
        tester,
        Scaffold(
          body: Column(children: [
            const SectionHeader(icon: Icons.tune, title: '测试分区'),
            const StatusCard(title: '状态', value: '正常', color: Colors.green),
            JointSlider(label: 'J1', value: 1500, onChanged: (_) {}, min: 500, max: 2500),
          ]),
        ),
      );
      expect(find.text('测试分区'), findsOneWidget);
      expect(find.text('正常'), findsOneWidget);
      expect(find.text('J1'), findsOneWidget);
    });
  });
}
