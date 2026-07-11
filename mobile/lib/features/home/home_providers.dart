/// Riverpod providers specific to the Home screen.
///
/// [personalRiskProvider] resolves the device's current GPS location, calls
/// /risk/location, and returns a [PersonalRisk]. Distinct failure modes are
/// surfaced as typed exceptions so the widget can render friendly states
/// instead of dumping raw error strings.
library;

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geocoding/geocoding.dart' as geo;
import 'package:geolocator/geolocator.dart';

import '../../core/providers/api_providers.dart';
import '../../data/models/risk_location.dart';

class PersonalRisk {
  final double lat;
  final double lng;
  final RiskLocationData risk;
  final String? areaName;

  const PersonalRisk({
    required this.lat,
    required this.lng,
    required this.risk,
    this.areaName,
  });
}

/// Reverse-geocode a coordinate to a human-friendly area name (e.g. "Madhapur").
/// Tries the OS geocoder first (fast, uses Apple/Google services), then falls
/// back to Nominatim / OpenStreetMap (network, works on emulators without GMS).
/// Returns null only if both approaches fail.
Future<String?> _reverseGeocode(double lat, double lng, Dio dio) async {
  // 1. OS geocoder
  try {
    final marks = await geo.placemarkFromCoordinates(lat, lng);
    for (final m in marks) {
      for (final c in [m.subLocality, m.locality, m.name, m.subAdministrativeArea]) {
        if (c != null && c.trim().isNotEmpty) return c.trim();
      }
    }
  } catch (_) {
    // Fall through to Nominatim.
  }

  // 2. Nominatim (free, no key). Respect their usage policy with a UA header.
  try {
    final res = await dio.get<Map<String, dynamic>>(
      'https://nominatim.openstreetmap.org/reverse',
      queryParameters: {
        'lat': lat, 'lon': lng, 'format': 'json', 'zoom': 16,
      },
      options: Options(
        headers: {'User-Agent': 'FloodGuard-Mobile/1.0'},
        // Nominatim isn't our own API — no auth needed
        extra: {'skipAuth': true},
      ),
    );
    final addr = res.data?['address'] as Map<String, dynamic>?;
    if (addr != null) {
      for (final key in ['suburb', 'neighbourhood', 'village', 'town', 'city_district', 'city']) {
        final v = addr[key];
        if (v is String && v.trim().isNotEmpty) return v.trim();
      }
    }
    final display = res.data?['display_name'] as String?;
    if (display != null && display.isNotEmpty) {
      return display.split(',').first.trim();
    }
  } catch (_) {
    // Final null → caller uses lat/lng fallback.
  }
  return null;
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
    // Nominatim needs its own Dio (different base URL); geocoding uses our own dio for reverse fallback.
    final nominatimDio = Dio();
    // Fetch risk and reverse-geocode in parallel — both are network calls.
    final results = await Future.wait([
      ref.read(apiProvider).getRiskLocation(pos.latitude, pos.longitude),
      _reverseGeocode(pos.latitude, pos.longitude, nominatimDio),
    ]);
    final riskRaw = results[0] as Map<String, dynamic>;
    final risk = RiskLocationData.fromJson(riskRaw);
    // If the backend has a real ward name, prefer it over reverse-geocoding.
    final areaName = (risk.wardName?.isNotEmpty == true)
        ? risk.wardName
        : results[1] as String?;

    return PersonalRisk(
      lat: pos.latitude,
      lng: pos.longitude,
      risk: risk,
      areaName: areaName,
    );
  } on DioException catch (e) {
    if (e.response?.statusCode == 404) {
      throw const OutsideCoverageException();
    }
    rethrow;
  }
});
