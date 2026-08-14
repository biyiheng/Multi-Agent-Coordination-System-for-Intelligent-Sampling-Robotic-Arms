/// 任务服务: 创建 / 列表 / 详情 / 启动 / 暂停
library;

import '../core/api_client.dart';

class TaskService {
  TaskService._();

  static final TaskService instance = TaskService._();

  Future<Map<String, dynamic>> create(Map<String, dynamic> taskData) async {
    final d = await ApiClient.instance.post('/api/v1/task/create', taskData);
    return (d as Map).cast<String, dynamic>();
  }

  Future<List<Map<String, dynamic>>> list({String? status, int limit = 50}) async {
    var path = '/api/v1/task/list?limit=$limit&offset=0';
    if (status != null && status.isNotEmpty) {
      path += '&status=$status';
    }
    final d = await ApiClient.instance.get(path);
    final raw = d is Map ? d['tasks'] ?? d['items'] ?? [] : d;
    return (raw as List).cast<Map<String, dynamic>>();
  }

  Future<Map<String, dynamic>> get(String taskId) async {
    final d = await ApiClient.instance.get('/api/v1/task/$taskId');
    return (d as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> start(String taskId) async {
    final d = await ApiClient.instance.post('/api/v1/task/$taskId/start', {});
    return (d as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> pause(String taskId) async {
    final d = await ApiClient.instance.post('/api/v1/task/$taskId/pause', {});
    return (d as Map).cast<String, dynamic>();
  }
}
