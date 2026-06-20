/// Risk overview response models — manual fromJson/toJson (no codegen needed).
library;

class RiskSummary {
  final double severe;
  final double high;
  final double moderate;
  final double low;

  const RiskSummary({
    required this.severe,
    required this.high,
    required this.moderate,
    required this.low,
  });

  factory RiskSummary.fromJson(Map<String, dynamic> j) => RiskSummary(
        severe: (j['severe'] as num).toDouble(),
        high: (j['high'] as num).toDouble(),
        moderate: (j['moderate'] as num).toDouble(),
        low: (j['low'] as num).toDouble(),
      );

  Map<String, dynamic> toJson() => {
        'severe': severe,
        'high': high,
        'moderate': moderate,
        'low': low,
      };

  double get total => severe + high + moderate + low;
}

class Hotspot {
  final String h3Index;
  final String riskLevel;
  final double? rain1h;
  final String? wardName;
  final double? lat;
  final double? lng;

  const Hotspot({
    required this.h3Index,
    required this.riskLevel,
    this.rain1h,
    this.wardName,
    this.lat,
    this.lng,
  });

  factory Hotspot.fromJson(Map<String, dynamic> j) => Hotspot(
        h3Index: j['h3_index'] as String,
        riskLevel: j['risk_level'] as String,
        rain1h: (j['rain_1h'] as num?)?.toDouble(),
        wardName: j['ward_name'] as String?,
        lat: (j['lat'] as num?)?.toDouble(),
        lng: (j['lng'] as num?)?.toDouble(),
      );

  Map<String, dynamic> toJson() => {
        'h3_index': h3Index,
        'risk_level': riskLevel,
        'rain_1h': rain1h,
        'ward_name': wardName,
        'lat': lat,
        'lng': lng,
      };
}

class RiskOverview {
  final String? ts;
  final double forecastRain24h;
  final double maxRate1h;
  final int confidence;
  final int totalHexes;
  final RiskSummary summary;
  final List<Hotspot> hotspots;

  const RiskOverview({
    this.ts,
    required this.forecastRain24h,
    required this.maxRate1h,
    required this.confidence,
    required this.totalHexes,
    required this.summary,
    required this.hotspots,
  });

  factory RiskOverview.fromJson(Map<String, dynamic> j) => RiskOverview(
        ts: j['ts'] as String?,
        forecastRain24h: (j['forecast_rain_24h'] as num).toDouble(),
        maxRate1h: (j['max_rate_1h'] as num).toDouble(),
        confidence: (j['confidence'] as num).toInt(),
        totalHexes: (j['total_hexes'] as num?)?.toInt() ?? 0,
        summary: RiskSummary.fromJson(j['summary'] as Map<String, dynamic>),
        hotspots: (j['hotspots'] as List<dynamic>)
            .map((h) => Hotspot.fromJson(h as Map<String, dynamic>))
            .toList(),
      );

  Map<String, dynamic> toJson() => {
        'ts': ts,
        'forecast_rain_24h': forecastRain24h,
        'max_rate_1h': maxRate1h,
        'confidence': confidence,
        'total_hexes': totalHexes,
        'summary': summary.toJson(),
        'hotspots': hotspots.map((h) => h.toJson()).toList(),
      };

  static RiskOverview get empty => RiskOverview(
        forecastRain24h: 0,
        maxRate1h: 0,
        confidence: 0,
        totalHexes: 0,
        summary: const RiskSummary(severe: 0, high: 0, moderate: 0, low: 100),
        hotspots: [],
      );
}
