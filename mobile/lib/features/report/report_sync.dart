/// WorkManager outbox flush — runs on background connectivity event.
/// Only initialised on Android/iOS; no-op on web/macOS/desktop.
library;

import 'package:flutter/foundation.dart';
import 'package:workmanager/workmanager.dart';

import '../../core/network/dio_client.dart';
import '../../data/api/floodguard_api.dart';
import '../../data/db/database_service.dart';

const _kFlushTask = 'fg_flush_report_outbox';

// Top-level callback — runs in a fresh Dart isolate on Android/iOS.
@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((task, _) async {
    if (task == _kFlushTask) {
      final db = DatabaseService();
      try {
        await flushReportOutbox(db, FloodGuardApi(buildDio()));
      } finally {
        await db.close();
      }
    }
    return true;
  });
}

/// Flush all unsynced PendingReports to the server. Safe to call multiple times.
Future<void> flushReportOutbox(DatabaseService db, FloodGuardApi api) async {
  final pending = await db.getUnsynced();
  for (final report in pending) {
    try {
      await api.submitReport(
        lat: report['lat'] as double,
        lng: report['lng'] as double,
        depth: report['depth'] as String,
        road: report['road'] as String,
        clientUuid: report['clientUuid'] as String,
        observedAt: report['observedAt'] as DateTime,
        photoPath: report['photoPath'] as String?,
      );
      await db.markSynced(report['id'] as String);
    } catch (_) {
      // Leave for the next flush cycle.
    }
  }
}

/// Register WorkManager periodic flush task. Safe to call on every app launch.
Future<void> initWorkManager() async {
  if (kIsWeb) return;
  // Only Android / iOS support WorkManager.
  if (defaultTargetPlatform != TargetPlatform.android &&
      defaultTargetPlatform != TargetPlatform.iOS) return;

  await Workmanager().initialize(callbackDispatcher, isInDebugMode: false);
  await Workmanager().registerPeriodicTask(
    _kFlushTask,
    _kFlushTask,
    frequency: const Duration(minutes: 15),
    existingWorkPolicy: ExistingWorkPolicy.keep,
    constraints: Constraints(networkType: NetworkType.connected),
  );
}
