import 'package:floodguard/data/models/voice_report.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('VoiceReport.fromJson', () {
    test('parses a submitted-report payload', () {
      final r = VoiceReport.fromJson({
        'report_id': '5b7c3f60-b6c9-4c9f-9dbe-49b4a8b0e0aa',
        'short_ref': 'FG-7K3M',
        'source': 'voice',
        'call_sid': 'CA_abc',
        'caller_hash': 'deadbeef',
        'hazard_type': 'abnormal_tide',
        'severity': 'extreme',
        'water_depth_cm': 60,
        'description': 'water is entering my house',
        'description_clean': 'water is entering my house',
        'location_raw': 'near bheemili beach',
        'location_resolved': 'Bheemunipatnam Beach',
        'dedupe_group_id': null,
        'priority_score': null,
        'flags': {'life_safety': true},
        'status': 'pending_enrichment',
        'sampled_for_qa': false,
        'qa_reviewed_at': null,
        'qa_notes': null,
        'created_at': '2026-08-18T10:15:00Z',
        'updated_at': '2026-08-18T10:15:00Z',
      });
      expect(r.shortRef, 'FG-7K3M');
      expect(r.source, 'voice');
      expect(r.hazardType, 'abnormal_tide');
      expect(r.severity, 'extreme');
      expect(r.waterDepthCm, 60);
      expect(r.locationResolved, 'Bheemunipatnam Beach');
      expect(r.lifeSafetyFlag, isTrue);
      expect(r.createdAt.isUtc, isTrue);
    });

    test('missing flags → lifeSafetyFlag=false, tolerant of null slots', () {
      final r = VoiceReport.fromJson({
        'report_id': '00000000-0000-0000-0000-000000000000',
        'short_ref': 'FG-0000',
        'call_sid': 'CA_x',
        'caller_hash': 'x',
        'hazard_type': null,
        'severity': null,
        'water_depth_cm': null,
        'description': null,
        'description_clean': null,
        'location_raw': null,
        'location_resolved': null,
        'dedupe_group_id': null,
        'priority_score': null,
        'flags': null,
        'status': 'pending_enrichment',
        'sampled_for_qa': false,
        'qa_reviewed_at': null,
        'qa_notes': null,
        'created_at': '2026-08-18T10:15:00Z',
        'updated_at': '2026-08-18T10:15:00Z',
      });
      expect(r.lifeSafetyFlag, isFalse);
      expect(r.hazardType, isNull);
      expect(r.source, 'voice'); // default when omitted
    });
  });

  test('VoiceReportEvent factories carry the right type + report', () {
    final r = VoiceReport.fromJson({
      'report_id': '11111111-1111-1111-1111-111111111111',
      'short_ref': 'FG-1111',
      'call_sid': 'CA_1',
      'caller_hash': 'h',
      'hazard_type': 'flooding',
      'severity': 'moderate',
      'water_depth_cm': 40,
      'description': null,
      'description_clean': null,
      'location_raw': null,
      'location_resolved': null,
      'dedupe_group_id': null,
      'priority_score': null,
      'flags': null,
      'status': 'pending_enrichment',
      'sampled_for_qa': false,
      'qa_reviewed_at': null,
      'qa_notes': null,
      'created_at': '2026-08-18T10:15:00Z',
      'updated_at': '2026-08-18T10:15:00Z',
    });
    final submitted = VoiceReportEvent.submitted(r);
    expect(submitted.eventType, 'report.submitted');
    expect(submitted.report, isNotNull);
    expect(submitted.lagged, isFalse);

    final enriched = VoiceReportEvent.enriched(r);
    expect(enriched.eventType, 'report.enriched');

    final lagged = VoiceReportEvent.laggedSentinel();
    expect(lagged.eventType, 'lagged');
    expect(lagged.lagged, isTrue);
    expect(lagged.report, isNull);
  });
}
