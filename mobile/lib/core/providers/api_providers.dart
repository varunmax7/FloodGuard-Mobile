/// Core Riverpod providers — Dio, FloodGuardApi, AppDatabase.
library;

import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import '../../data/api/floodguard_api.dart';
import '../../data/db/app_database.dart';
import '../../data/models/risk_overview.dart';
import '../network/dio_client.dart';

final dioProvider = Provider<Dio>((ref) => buildDio());

final apiProvider = Provider<FloodGuardApi>(
  (ref) => FloodGuardApi(ref.watch(dioProvider)),
);

final appDatabaseProvider = Provider<AppDatabase>((ref) {
  final db = AppDatabase();
  ref.onDispose(db.close);
  return db;
});

// ── Risk overview ─────────────────────────────────────────────────────────────

final riskOverviewProvider = FutureProvider<RiskOverview>((ref) async {
  final api = ref.watch(apiProvider);
  final db = ref.watch(appDatabaseProvider);

  try {
    final overview = await api.getRiskOverview();
    // Persist to cache (fire-and-forget)
    db.cacheRiskOverview(jsonEncode(overview.toJson())).ignore();
    return overview;
  } on DioException catch (_) {
    // Offline fallback — try local cache
    final cached = await db.getLatestRiskOverview();
    if (cached != null) {
      return RiskOverview.fromJson(
          jsonDecode(cached.json) as Map<String, dynamic>);
    }
    rethrow;
  }
});
