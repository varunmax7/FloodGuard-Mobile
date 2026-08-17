/// Voice-agent report model + SSE event envelope.
///
/// Mirrors `ReportOut` from `ai-calling-agent/src/fg_voice/api/routes_reports.py`.
/// Kept a separate model from the app-native `FloodReport` (which comes from
/// `/reports/nearby` in the main backend) because the two feeds carry
/// different columns: voice reports include `short_ref`, `hazard_type`,
/// PII-redacted `description_clean`, `life_safety_flag` in `flags`, and a
/// post-enrichment `location_resolved` string. The unified feed contract
/// in spec §13.1 keeps `source` as the discriminator so both flavours
/// can render on the same map/list once §13.2 UI lands.
library;

class VoiceReport {
  final String reportId;
  final String shortRef;
  final String source;
  final String callSid;
  final String? hazardType;
  final String? severity;
  final int? waterDepthCm;
  final String? descriptionClean;
  final String? locationRaw;
  final String? locationResolved;
  final String? dedupeGroupId;
  final int? priorityScore;
  final bool lifeSafetyFlag;
  final String status;
  final DateTime createdAt;
  final DateTime updatedAt;

  const VoiceReport({
    required this.reportId,
    required this.shortRef,
    required this.source,
    required this.callSid,
    required this.hazardType,
    required this.severity,
    required this.waterDepthCm,
    required this.descriptionClean,
    required this.locationRaw,
    required this.locationResolved,
    required this.dedupeGroupId,
    required this.priorityScore,
    required this.lifeSafetyFlag,
    required this.status,
    required this.createdAt,
    required this.updatedAt,
  });

  factory VoiceReport.fromJson(Map<String, dynamic> j) {
    final flags = j['flags'];
    return VoiceReport(
      reportId: j['report_id'] as String,
      shortRef: j['short_ref'] as String,
      source: (j['source'] as String?) ?? 'voice',
      callSid: (j['call_sid'] as String?) ?? '',
      hazardType: j['hazard_type'] as String?,
      severity: j['severity'] as String?,
      waterDepthCm: (j['water_depth_cm'] as num?)?.toInt(),
      descriptionClean: j['description_clean'] as String?,
      locationRaw: j['location_raw'] as String?,
      locationResolved: j['location_resolved'] as String?,
      dedupeGroupId: j['dedupe_group_id'] as String?,
      priorityScore: (j['priority_score'] as num?)?.toInt(),
      lifeSafetyFlag:
          flags is Map && flags['life_safety'] == true,
      status: (j['status'] as String?) ?? 'pending_enrichment',
      createdAt: DateTime.parse(j['created_at'] as String),
      updatedAt: DateTime.parse(j['updated_at'] as String),
    );
  }
}

/// One SSE frame from `/api/v1/reports/stream`. The backend fans a subset
/// of outbox rows: `report.submitted`, `report.enriched`, plus a
/// `lagged` sentinel when this subscriber's queue fills up.
///
/// The relay's outbox payload is the same JSON shape as `ReportOut`, so we
/// can parse straight into a `VoiceReport` for the two `report.*` types.
/// The `lagged` frame carries only a note — the client should refetch a
/// page from `GET /reports` to catch up.
class VoiceReportEvent {
  final String eventType;
  final VoiceReport? report;
  final bool lagged;

  const VoiceReportEvent._({
    required this.eventType,
    this.report,
    this.lagged = false,
  });

  factory VoiceReportEvent.submitted(VoiceReport r) =>
      VoiceReportEvent._(eventType: 'report.submitted', report: r);

  factory VoiceReportEvent.enriched(VoiceReport r) =>
      VoiceReportEvent._(eventType: 'report.enriched', report: r);

  factory VoiceReportEvent.laggedSentinel() =>
      const VoiceReportEvent._(eventType: 'lagged', lagged: true);
}
