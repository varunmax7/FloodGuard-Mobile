/// Native implementation backed by Drift + SQLite.
library;

import 'app_database.dart';
import 'package:drift/drift.dart' show Value;

class DatabaseService {
  final AppDatabase _db = AppDatabase();

  Future<void> close() => _db.close();

  // ── Risk overview cache ───────────────────────────────────────────────────

  Future<void> cacheRiskOverview(String json) => _db.cacheRiskOverview(json);

  Future<String?> getCachedRiskOverviewJson() async {
    final row = await _db.getLatestRiskOverview();
    return row?.json;
  }

  // ── Report outbox ─────────────────────────────────────────────────────────

  Future<void> enqueuePendingReport(Map<String, dynamic> data) =>
      _db.enqueuePendingReport(PendingReportsCompanion(
        id: Value(data['id'] as String),
        lat: Value(data['lat'] as double),
        lng: Value(data['lng'] as double),
        depth: Value(data['depth'] as String),
        road: Value(data['road'] as String),
        photoPath: Value(data['photoPath'] as String?),
        observedAt: Value(data['observedAt'] as DateTime),
        createdAt: Value(DateTime.now()),
        clientUuid: Value(data['clientUuid'] as String),
      ));

  /// Returns unsynced rows as plain maps so the web stub can share the same type.
  Future<List<Map<String, dynamic>>> getUnsynced() async {
    final rows = await _db.getUnsynced();
    return rows
        .map((r) => {
              'id': r.id,
              'lat': r.lat,
              'lng': r.lng,
              'depth': r.depth,
              'road': r.road,
              'photoPath': r.photoPath,
              'observedAt': r.observedAt,
              'clientUuid': r.clientUuid,
            })
        .toList();
  }

  Future<void> markSynced(String id) => _db.markSynced(id);
}
