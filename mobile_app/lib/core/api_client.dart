/// 统一 REST API 客户端
///
/// 所有 /api/v1/* 请求经此封装:
/// - 自动附加 Authorization: Bearer <token>
/// - 统一错误处理 (网络错误 / HTTP 状态码)
/// - 可选超时
library;

import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'app_config.dart';
import 'auth_store.dart';

class ApiException implements Exception {
  ApiException(this.statusCode, this.message, {this.data});

  final int statusCode;
  final String message;
  final dynamic data;

  @override
  String toString() => 'ApiException($statusCode): $message';
}

class ApiClient {
  ApiClient._();

  static final ApiClient instance = ApiClient._();

  static const Duration _timeout = Duration(seconds: 10);

  /// 底层请求方法
  Future<dynamic> _send(
    String method,
    String path, {
    Map<String, dynamic>? body,
    bool auth = true,
  }) async {
    final uri = Uri.parse('${AppConfig.baseUrl}$path');
    final headers = <String, String>{
      'Content-Type': 'application/json',
      if (auth) 'Authorization': 'Bearer ${AuthStore.instance.token ?? ''}',
    };

    late http.Response resp;
    try {
      final req = http.Request(method, uri)..headers.addAll(headers);
      if (body != null) {
        req.body = jsonEncode(body);
      }
      final streamed = await req.send().timeout(_timeout);
      resp = await http.Response.fromStream(streamed);
    } on TimeoutException {
      throw ApiException(0, '请求超时, 请检查网络或服务端地址');
    } catch (e) {
      throw ApiException(0, '网络错误: $e');
    }

    dynamic data;
    try {
      data = resp.body.isEmpty ? null : jsonDecode(resp.body);
    } catch (_) {
      data = resp.body;
    }

    if (resp.statusCode >= 200 && resp.statusCode < 300) {
      return data;
    }

    String message = '请求失败 (${resp.statusCode})';
    if (data is Map && data['detail'] != null) {
      message = data['detail'].toString();
    }
    throw ApiException(resp.statusCode, message, data: data);
  }

  // ============ 公开方法 ============

  Future<dynamic> get(String path, {bool auth = true}) =>
      _send('GET', path, auth: auth);

  Future<dynamic> post(String path, Map<String, dynamic> body,
          {bool auth = true}) =>
      _send('POST', path, body: body, auth: auth);

  Future<dynamic> put(String path, Map<String, dynamic> body,
          {bool auth = true}) =>
      _send('PUT', path, body: body, auth: auth);

  Future<dynamic> delete(String path, {bool auth = true}) =>
      _send('DELETE', path, auth: auth);
}
