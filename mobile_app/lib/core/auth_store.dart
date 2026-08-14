/// 登录令牌存储 (内存 + shared_preferences 持久化)
library;

import 'package:shared_preferences/shared_preferences.dart';

class AuthStore {
  AuthStore._();

  static final AuthStore instance = AuthStore._();

  static const _keyToken = 'auth_token';
  static const _keyUsername = 'auth_username';
  static const _keyRole = 'auth_role';

  String? _token;
  String? _username;
  String? _role;

  String? get token => _token;
  String? get username => _username;
  String? get role => _role;
  bool get isLoggedIn => _token != null && _token!.isNotEmpty;

  /// 应用启动时恢复已保存的登录态
  Future<void> restore() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString(_keyToken);
    _username = prefs.getString(_keyUsername);
    _role = prefs.getString(_keyRole);
  }

  Future<void> save(String token, String username, String role) async {
    _token = token;
    _username = username;
    _role = role;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyToken, token);
    await prefs.setString(_keyUsername, username);
    await prefs.setString(_keyRole, role);
  }

  Future<void> clear() async {
    _token = null;
    _username = null;
    _role = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_keyToken);
    await prefs.remove(_keyUsername);
    await prefs.remove(_keyRole);
  }
}
