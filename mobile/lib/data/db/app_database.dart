/// Drift database — risk overview cache + offline report outbox.
/// Run `flutter pub run build_runner build` to regenerate app_database.g.dart.
library;

import 'dart:io';
import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;

part 'app_database.g.dart';

// ── Tables ────────────────────────────────────────────────────────────────────

/// Single-row cache for the latest /risk/overview response.
class RiskOverviewCaches extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get json => text()();
  DateTimeColumn get cachedAt => dateTime()();
}

/// Offline report queue — flushed by workmanager in Phase 8.
class PendingReports extends Table {
  TextColumn get id => text()();
  RealColumn get lat => real()();
  RealColumn get lng => real()();
  TextColumn get depth => text()(); // ANKLE|KNEE|WAIST|VEHICLE
  TextColumn get road => text()();  // PASSABLE|DIFFICULT|BLOCKED
  TextColumn get photoPath => text().nullable()();
  DateTimeColumn get observedAt => dateTime()();
  DateTimeColumn get createdAt => dateTime()();
  TextColumn get clientUuid => text()();
  BoolColumn get synced => boolean().withDefault(const Constant(false))();

  @override
  Set<Column> get primaryKey => {id};
}

// ── Database ──────────────────────────────────────────────────────────────────

@DriftDatabase(tables: [RiskOverviewCaches, PendingReports])
class AppDatabase extends _$AppDatabase {
  AppDatabase() : super(_openConnection());

  @override
  int get schemaVersion => 1;

  // ── Risk overview cache ───────────────────────────────────────────────────

  Future<void> cacheRiskOverview(String json) async {
    await transaction(() async {
      await delete(riskOverviewCaches).go();
      await into(riskOverviewCaches).insert(
        RiskOverviewCachesCompanion.insert(json: json, cachedAt: DateTime.now()),
      );
    });
  }

  Future<RiskOverviewCache?> getLatestRiskOverview() {
    return (select(riskOverviewCaches)
          ..orderBy([(t) => OrderingTerm.desc(t.cachedAt)])
          ..limit(1))
        .getSingleOrNull();
  }

  // ── Pending reports (Phase 8) ─────────────────────────────────────────────

  Future<void> enqueuePendingReport(PendingReportsCompanion entry) =>
      into(pendingReports).insert(entry);

  Future<List<PendingReport>> getUnsynced() =>
      (select(pendingReports)..where((t) => t.synced.equals(false))).get();

  Future<void> markSynced(String id) => (update(pendingReports)
        ..where((t) => t.id.equals(id)))
      .write(const PendingReportsCompanion(synced: Value(true)));
}

LazyDatabase _openConnection() {
  return LazyDatabase(() async {
    final dbFolder = await getApplicationDocumentsDirectory();
    final file = File(p.join(dbFolder.path, 'floodguard.sqlite'));
    return NativeDatabase.createInBackground(file);
  });
}
