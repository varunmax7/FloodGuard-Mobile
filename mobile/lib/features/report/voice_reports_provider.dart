/// Riverpod wiring for the live voice-agent reports feed.
///
/// `voiceReportsStreamProvider` — broadcast stream of individual
/// `VoiceReportEvent`s (submit + enrich + lagged). Wire into a widget
/// with `ref.watch(voiceReportsStreamProvider)` to get an
/// `AsyncValue<VoiceReportEvent>`.
///
/// `liveVoiceReportsProvider` — accumulates the last 100 unique reports
/// (keyed by `report_id`, newest first) so the map / list feeds have
/// something to render directly. Enriched events replace the earlier
/// submit for the same id.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers/api_providers.dart';
import '../../data/api/voice_reports_sse.dart';
import '../../data/models/voice_report.dart';

const int _kMaxLiveReports = 100;

final voiceReportsSseClientProvider = Provider<VoiceReportsSseClient>((ref) {
  final client = VoiceReportsSseClient(ref.watch(dioProvider));
  ref.onDispose(() {
    client.close();
  });
  return client;
});

final voiceReportsStreamProvider =
    StreamProvider<VoiceReportEvent>((ref) {
  final client = ref.watch(voiceReportsSseClientProvider);
  return client.events();
});

/// Rolling list of the newest voice reports (newest first, max 100).
/// A `report.enriched` for an existing id updates in place; a
/// `report.submitted` prepends.
final liveVoiceReportsProvider =
    StateNotifierProvider<_LiveVoiceReports, List<VoiceReport>>((ref) {
  final notifier = _LiveVoiceReports();
  final sub = ref.listen<AsyncValue<VoiceReportEvent>>(
    voiceReportsStreamProvider,
    (_, next) {
      final event = next.valueOrNull;
      if (event == null || event.report == null) return;
      notifier.upsert(event.report!);
    },
  );
  ref.onDispose(sub.close);
  return notifier;
});

class _LiveVoiceReports extends StateNotifier<List<VoiceReport>> {
  _LiveVoiceReports() : super(const []);

  void upsert(VoiceReport r) {
    final byId = <String, VoiceReport>{};
    byId[r.reportId] = r; // newest first
    for (final existing in state) {
      if (existing.reportId == r.reportId) continue;
      byId[existing.reportId] = existing;
      if (byId.length >= _kMaxLiveReports) break;
    }
    state = byId.values.toList(growable: false);
  }
}
