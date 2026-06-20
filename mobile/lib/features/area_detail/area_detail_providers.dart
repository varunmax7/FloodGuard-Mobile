/// Riverpod providers for the Area Detail screen.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/providers/api_providers.dart';
import '../../data/models/flood_report.dart';
import '../../data/models/risk_location.dart';

/// Fetches risk data for a lat/lng pair from /risk/location.
final riskLocationDataProvider =
    FutureProvider.family<RiskLocationData, (double, double)>(
  (ref, coords) async {
    final raw =
        await ref.read(apiProvider).getRiskLocation(coords.$1, coords.$2);
    return RiskLocationData.fromJson(raw);
  },
);

/// Fetches nearby flood reports from /reports/nearby.
final nearbyReportsProvider = FutureProvider.family<List<FloodReport>,
    ({double lat, double lng, int sinceMin})>(
  (ref, args) async {
    final raw = await ref.read(apiProvider).getReportsNearby(
          lat: args.lat,
          lng: args.lng,
          sinceMin: args.sinceMin,
        );
    return raw
        .whereType<Map<String, dynamic>>()
        .map(FloodReport.fromJson)
        .toList();
  },
);
