/// 机械臂控制服务: 关节/笛卡尔/夹爪/急停/回零
library;

import '../core/api_client.dart';

class ArmService {
  ArmService._();

  static final ArmService instance = ArmService._();

  Future<Map<String, dynamic>> getStatus() async {
    final d = await ApiClient.instance.get('/api/v1/arm/status');
    return (d as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> getPosition() async {
    final d = await ApiClient.instance.get('/api/v1/arm/position');
    return (d as Map).cast<String, dynamic>();
  }

  /// 单关节移动 (joint_id: 0-5, position: PWM 500-2500, time: 秒)
  Future<Map<String, dynamic>> moveJoint(int jointId, double position,
      {double time = 1.0}) async {
    final d = await ApiClient.instance.post('/api/v1/arm/move/joint', {
      'joint_id': jointId,
      'position': position,
      'time': time,
    });
    return (d as Map).cast<String, dynamic>();
  }

  /// 全部关节同时移动
  Future<Map<String, dynamic>> moveAll(List<double> positions,
      {double time = 1.0}) async {
    final d = await ApiClient.instance.post('/api/v1/arm/move/all', {
      'positions': positions,
      'time': time,
    });
    return (d as Map).cast<String, dynamic>();
  }

  /// 笛卡尔空间移动
  Future<Map<String, dynamic>> moveCartesian(
    double x,
    double y,
    double z, {
    double roll = 0,
    double pitch = 0,
    double yaw = 0,
    double time = 2.0,
  }) async {
    final d = await ApiClient.instance.post('/api/v1/arm/move/cartesian', {
      'x': x,
      'y': y,
      'z': z,
      'roll': roll,
      'pitch': pitch,
      'yaw': yaw,
      'time': time,
    });
    return (d as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> stop() async {
    final d = await ApiClient.instance.post('/api/v1/arm/stop', {});
    return (d as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> estop() async {
    final d = await ApiClient.instance.post('/api/v1/arm/estop', {});
    return (d as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> clearEstop() async {
    final d = await ApiClient.instance.post('/api/v1/arm/estop/clear', {});
    return (d as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> home() async {
    final d = await ApiClient.instance.post('/api/v1/arm/origin', {});
    return (d as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> openGripper() async {
    final d = await ApiClient.instance.post('/api/v1/arm/gripper/open', {});
    return (d as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> closeGripper({double force = 50}) async {
    final d = await ApiClient.instance
        .post('/api/v1/arm/gripper/close', {'force': force});
    return (d as Map).cast<String, dynamic>();
  }
}
