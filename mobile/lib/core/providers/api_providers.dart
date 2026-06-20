/// Core Riverpod providers — Dio, FloodGuardApi, DatabaseService.
library;

import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import '../../data/api/floodguard_api.dart';
import '../../data/db/database_service.dart';
import '../../data/models/risk_overview.dart';
import '../network/dio_client.dart';

final dioProvider = Provider<Dio>((ref) => buildDio());

final apiProvider = Provider<FloodGuardApi>(
  (ref) => FloodGuardApi(ref.watch(dioProvider)),
);

// Works on all platforms: native uses Drift, web uses a no-op stub.
final dbServiceProvider = Provider<DatabaseService>((ref) {
  final svc = DatabaseService();
  ref.onDispose(svc.close);
  return svc;
});

// ── Risk overview ─────────────────────────────────────────────────────────────

final riskOverviewProvider = FutureProvider<RiskOverview>((ref) async {
  final api = ref.watch(apiProvider);
  final db = ref.watch(dbServiceProvider);

  try {
    final overview = await api.getRiskOverview();
    db.cacheRiskOverview(jsonEncode(overview.toJson())).ignore();
    return overview;
  } on DioException catch (_) {
    final cached = await db.getCachedRiskOverviewJson();
    if (cached != null) {
      return RiskOverview.fromJson(
          jsonDecode(cached) as Map<String, dynamic>);
    }
    rethrow;
  }
});
