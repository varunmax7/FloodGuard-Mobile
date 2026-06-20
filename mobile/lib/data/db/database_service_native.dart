/// Native implementation backed by Drift + SQLite.
library;

import 'app_database.dart';

class DatabaseService {
  final AppDatabase _db = AppDatabase();

  Future<void> close() => _db.close();

  Future<void> cacheRiskOverview(String json) =>
      _db.cacheRiskOverview(json);

  Future<String?> getCachedRiskOverviewJson() async {
    final row = await _db.getLatestRiskOverview();
    return row?.json;
  }

  Future<void> enqueuePendingReport(Map<String, dynamic> data) async {
    // Phase 8 will call db.enqueuePendingReport with a proper Companion
  }
}
