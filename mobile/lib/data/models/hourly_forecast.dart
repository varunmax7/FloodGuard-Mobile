/// Typed model for GET /risk/hourly-forecast — a 48-hour rainfall preview.
library;

class HourlyForecastPoint {
  final DateTime ts;
  final double rainMm;

  const HourlyForecastPoint({required this.ts, required this.rainMm});

  factory HourlyForecastPoint.fromJson(Map<String, dynamic> j) =>
      HourlyForecastPoint(
        ts: DateTime.parse('${j['ts']}Z').toUtc(),
        rainMm: (j['rain_mm'] as num?)?.toDouble() ?? 0.0,
      );
}

class HourlyForecast {
  final DateTime generatedAt;
  final List<HourlyForecastPoint> hours;

  const HourlyForecast({required this.generatedAt, required this.hours});

  factory HourlyForecast.fromJson(Map<String, dynamic> j) => HourlyForecast(
        generatedAt: DateTime.parse(j['generated_at'] as String),
        hours: ((j['hours'] as List?) ?? [])
            .whereType<Map<String, dynamic>>()
            .map(HourlyForecastPoint.fromJson)
            .toList(),
      );

  /// Total rainfall over the full forecast window.
  double get totalRainMm => hours.fold(0.0, (a, b) => a + b.rainMm);

  /// The hour with the highest predicted rain. Null if forecast is empty.
  HourlyForecastPoint? get peak {
    if (hours.isEmpty) return null;
    HourlyForecastPoint p = hours.first;
    for (final h in hours) {
      if (h.rainMm > p.rainMm) p = h;
    }
    return p;
  }
}
