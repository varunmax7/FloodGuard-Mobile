/// Typed API client wrapping Dio — no Retrofit codegen needed.
library;

import 'package:dio/dio.dart';
import '../models/risk_overview.dart';

class FloodGuardApi {
  final Dio _dio;

  FloodGuardApi(this._dio);

  Future<RiskOverview> getRiskOverview() async {
    final res = await _dio.get<Map<String, dynamic>>('/risk/overview/');
    return RiskOverview.fromJson(res.data!);
  }

  Future<Map<String, dynamic>> getRiskLocation(double lat, double lng) async {
    final res = await _dio.get<Map<String, dynamic>>(
      '/risk/location/',
      queryParameters: {'lat': lat, 'lng': lng},
    );
    return res.data!;
  }

  Future<Map<String, dynamic>> getRiskHexes(String bbox, {String? ts}) async {
    final res = await _dio.get<Map<String, dynamic>>(
      '/risk/hexes/',
      queryParameters: {'bbox': bbox, if (ts != null) 'ts': ts},
    );
    return res.data!;
  }

  Future<List<dynamic>> getRadarFrames({String? since}) async {
    final res = await _dio.get<List<dynamic>>(
      '/radar/frames/',
      queryParameters: {if (since != null) 'since': since},
    );
    return res.data ?? [];
  }

  Future<Map<String, dynamic>> verifyOtp(String idToken, {String fcmToken = ''}) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/auth/otp/verify/',
      data: {'id_token': idToken, 'fcm_token': fcmToken},
    );
    return res.data!;
  }

  Future<List<dynamic>> getPlaces() async {
    final res = await _dio.get<List<dynamic>>('/places/');
    return res.data ?? [];
  }

  Future<Map<String, dynamic>> createPlace(
      String label, double lat, double lng, bool notify) async {
    final res = await _dio.post<Map<String, dynamic>>(
      '/places/',
      data: {'label': label, 'lat': lat, 'lng': lng, 'notify': notify},
    );
    return res.data!;
  }

  Future<void> updateDeviceToken(String fcmToken) async {
    await _dio.post<void>('/devices/token/', data: {'fcm_token': fcmToken});
  }

  Future<List<dynamic>> getReportsNearby({
    required double lat,
    required double lng,
    int radiusM = 1000,
    int sinceMin = 60,
  }) async {
    final res = await _dio.get<List<dynamic>>(
      '/reports/nearby/',
      queryParameters: {
        'lat': lat,
        'lng': lng,
        'radius_m': radiusM,
        'since_min': sinceMin,
      },
    );
    return res.data ?? [];
  }
}
