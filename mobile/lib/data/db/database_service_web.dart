/// Web stub — no SQLite available in browsers, all operations are no-ops.
library;

class DatabaseService {
  Future<void> close() async {}
  Future<void> cacheRiskOverview(String json) async {}
  Future<String?> getCachedRiskOverviewJson() async => null;
  Future<void> enqueuePendingReport(Map<String, dynamic> data) async {}
  Future<List<Map<String, dynamic>>> getUnsynced() async => [];
  Future<void> markSynced(String id) async {}
}
