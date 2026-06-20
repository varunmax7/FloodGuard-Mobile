/// Dio client factory — base options + JWT auth interceptor + logging.
library;

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../config/app_config.dart';

const _kAccessTokenKey = 'fg_access_token';
const _kRefreshTokenKey = 'fg_refresh_token';

/// Persist tokens after login.
Future<void> saveTokens({required String access, required String refresh}) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString(_kAccessTokenKey, access);
  await prefs.setString(_kRefreshTokenKey, refresh);
}

/// Clear tokens on logout.
Future<void> clearTokens() async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.remove(_kAccessTokenKey);
  await prefs.remove(_kRefreshTokenKey);
}

Future<String?> getAccessToken() async {
  final prefs = await SharedPreferences.getInstance();
  return prefs.getString(_kAccessTokenKey);
}

Dio buildDio() {
  final dio = Dio(BaseOptions(
    baseUrl: '${AppConfig.apiBaseUrl}/api/v1',
    connectTimeout: const Duration(seconds: 15),
    receiveTimeout: const Duration(seconds: 15),
    headers: {'Accept': 'application/json'},
  ));

  dio.interceptors.add(_AuthInterceptor(dio));

  if (kDebugMode) {
    dio.interceptors.add(LogInterceptor(
      requestBody: false,
      responseBody: false,
      logPrint: (o) => debugPrint('[Dio] $o'),
    ));
  }

  return dio;
}

class _AuthInterceptor extends Interceptor {
  final Dio _dio;
  _AuthInterceptor(this._dio);

  @override
  void onRequest(
      RequestOptions options, RequestInterceptorHandler handler) async {
    final token = await getAccessToken();
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    if (err.response?.statusCode == 401) {
      // Token expired — attempt refresh
      final prefs = await SharedPreferences.getInstance();
      final refresh = prefs.getString(_kRefreshTokenKey);
      if (refresh != null) {
        try {
          final res = await _dio.post<Map<String, dynamic>>(
            '/auth/token/refresh/',
            data: {'refresh': refresh},
            options: Options(headers: {}),
          );
          final newAccess = res.data?['access'] as String?;
          if (newAccess != null) {
            await prefs.setString(_kAccessTokenKey, newAccess);
            // Retry original request
            final retryOpts = err.requestOptions;
            retryOpts.headers['Authorization'] = 'Bearer $newAccess';
            final retryRes = await _dio.fetch<dynamic>(retryOpts);
            return handler.resolve(retryRes);
          }
        } catch (_) {
          await clearTokens();
        }
      }
    }
    handler.next(err);
  }
}
