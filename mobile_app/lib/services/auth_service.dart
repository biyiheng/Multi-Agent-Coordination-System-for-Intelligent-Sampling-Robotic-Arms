/// 鉴权服务: 注册 / 登录 / 登出 / 当前用户
library;

import '../core/api_client.dart';
import '../core/auth_store.dart';

class AuthService {
  AuthService._();

  static final AuthService instance = AuthService._();

  /// 注册并自动登录
  Future<void> register(String username, String password) async {
    final data = await ApiClient.instance.post(
      '/api/v1/auth/register',
      {'username': username, 'password': password, 'role': 'user'},
      auth: false,
    );
    await _storeSession(data);
  }

  /// 登录
  Future<void> login(String username, String password) async {
    final data = await ApiClient.instance.post(
      '/api/v1/auth/login',
      {'username': username, 'password': password, 'scope': 'app'},
      auth: false,
    );
    await _storeSession(data);
  }

  Future<void> _storeSession(dynamic data) async {
    final token = data['access_token'] as String;
    final user = data['user'] as Map<String, dynamic>;
    await AuthStore.instance.save(
      token,
      user['username'] as String,
      user['role'] as String? ?? 'user',
    );
  }

  /// 登出 (吊销服务端 token 并清理本地)
  Future<void> logout() async {
    try {
      await ApiClient.instance.post('/api/v1/auth/logout', {});
    } catch (_) {
      // 服务端不可达时也清理本地
    }
    await AuthStore.instance.clear();
  }
}
