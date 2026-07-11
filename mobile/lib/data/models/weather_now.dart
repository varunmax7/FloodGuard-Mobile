/// Typed model for GET /risk/weather-now — current conditions at the Hyderabad
/// centroid. Includes helpers to map the WMO weather code to an icon and to
/// convert the wind direction into a compass label.
library;

import 'package:flutter/material.dart';

class WeatherNow {
  final DateTime generatedAt;
  final DateTime? observedAt;
  final double temperatureC;
  final int humidityPct;
  final double windKmh;
  final int windDirDeg;
  final int weatherCode;
  final String description;

  const WeatherNow({
    required this.generatedAt,
    required this.observedAt,
    required this.temperatureC,
    required this.humidityPct,
    required this.windKmh,
    required this.windDirDeg,
    required this.weatherCode,
    required this.description,
  });

  factory WeatherNow.fromJson(Map<String, dynamic> j) => WeatherNow(
        generatedAt: DateTime.parse(j['generated_at'] as String),
        observedAt: j['observed_at'] is String
            ? DateTime.tryParse('${j['observed_at']}Z')
            : null,
        temperatureC: (j['temperature_c'] as num?)?.toDouble() ?? 0,
        humidityPct: (j['humidity_pct'] as num?)?.toInt() ?? 0,
        windKmh: (j['wind_kmh'] as num?)?.toDouble() ?? 0,
        windDirDeg: (j['wind_dir_deg'] as num?)?.toInt() ?? 0,
        weatherCode: (j['weather_code'] as num?)?.toInt() ?? 0,
        description: (j['description'] as String?) ?? 'Unknown',
      );

  /// 16-point compass label ("N", "NE", "SW", ...) for wind direction.
  String get windDirCompass {
    const points = [
      'N', 'NNE', 'NE', 'ENE',
      'E', 'ESE', 'SE', 'SSE',
      'S', 'SSW', 'SW', 'WSW',
      'W', 'WNW', 'NW', 'NNW',
    ];
    final idx = ((windDirDeg % 360) / 22.5).round() % 16;
    return points[idx];
  }

  /// Material icon roughly matching the WMO weather code.
  IconData get icon {
    switch (weatherCode) {
      case 0:
      case 1:
        return Icons.wb_sunny_outlined;
      case 2:
        return Icons.wb_cloudy_outlined;
      case 3:
        return Icons.cloud_outlined;
      case 45:
      case 48:
        return Icons.foggy;
      case 51:
      case 53:
      case 55:
      case 56:
      case 57:
        return Icons.grain;
      case 61:
      case 63:
      case 65:
      case 66:
      case 67:
      case 80:
      case 81:
      case 82:
        return Icons.umbrella_outlined;
      case 71:
      case 73:
      case 75:
      case 77:
      case 85:
      case 86:
        return Icons.ac_unit;
      case 95:
      case 96:
      case 99:
        return Icons.thunderstorm_outlined;
      default:
        return Icons.wb_cloudy_outlined;
    }
  }
}
