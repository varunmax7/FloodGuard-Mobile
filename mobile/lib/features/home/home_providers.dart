/// Riverpod providers specific to the Home screen.
///
/// [personalRiskProvider] resolves the device's current GPS location, calls
/// /risk/location, and returns a [PersonalRisk]. Distinct failure modes are
/// surfaced as typed exceptions so the widget can render friendly states
/// instead of dumping raw error strings.
library;

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';

import '../../core/providers/api_providers.dart';
import '../../data/models/risk_location.dart';

class PersonalRisk {
  final double lat;
  final double lng;
  final RiskLocationData risk;

  const PersonalRisk({
    required this.lat,
    required this.lng,
    required this.risk,
  });
}

class LocationPermissionDeniedException implements Exception {
  final bool permanent;
  const LocationPermissionDeniedException({this.permanent = false});
  @override
  String toString() => 'Location permission denied';
}

class LocationServiceDisabledException implements Exception {
  const LocationServiceDisabledException();
  @override
  String toString() => 'Location services are turned off';
}

class OutsideCoverageException implements Exception {
  const OutsideCoverageException();
  @override
  String toString() => 'Location is outside the covered area';
}

final personalRiskProvider = FutureProvider<PersonalRisk>((ref) async {
  final serviceOn = await Geolocator.isLocationServiceEnabled();
  if (!serviceOn) throw const LocationServiceDisabledException();

  var perm = await Geolocator.checkPermission();
  if (perm == LocationPermission.denied) {
    perm = await Geolocator.requestPermission();
  }
  if (perm == LocationPermission.deniedForever) {
    throw const LocationPermissionDeniedException(permanent: true);
  }
  if (perm == LocationPermission.denied) {
    throw const LocationPermissionDeniedException();
  }

  final pos = await Geolocator.getCurrentPosition(
    locationSettings: const LocationSettings(accuracy: LocationAccuracy.medium),
  );

  try {
    final raw = await ref
        .read(apiProvider)
        .getRiskLocation(pos.latitude, pos.longitude);
    return PersonalRisk(
      lat: pos.latitude,
      lng: pos.longitude,
      risk: RiskLocationData.fromJson(raw),
    );
  } on DioException catch (e) {
    if (e.response?.statusCode == 404) {
      throw const OutsideCoverageException();
    }
    rethrow;
  }
});
