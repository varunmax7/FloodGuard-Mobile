/// Typed model for GET /risk/location response.
library;

class HourlyRisk {
  final String ts;
  final String riskLevel;

  const HourlyRisk({required this.ts, required this.riskLevel});

  factory HourlyRisk.fromJson(Map<String, dynamic> j) => HourlyRisk(
        ts: j['ts'] as String? ?? '',
        riskLevel: (j['risk_level'] as String? ?? 'LOW').toUpperCase(),
      );

  int get hour {
    try {
      return DateTime.parse(ts).toLocal().hour;
    } catch (_) {
      return 0;
    }
  }
}

class RiskLocationData {
  final String riskLevel;
  final String plainText;
  final String explanation;
  final int confidence;
  final double? rain1h;
  final String? h3Index;
  final String? wardName;
  final List<HourlyRisk> hourly;

  const RiskLocationData({
    required this.riskLevel,
    required this.plainText,
    required this.explanation,
    required this.confidence,
    this.rain1h,
    this.h3Index,
    this.wardName,
    required this.hourly,
  });

  factory RiskLocationData.fromJson(Map<String, dynamic> j) => RiskLocationData(
        riskLevel: (j['risk_level'] as String? ?? 'LOW').toUpperCase(),
        plainText: j['plain_text'] as String? ?? '',
        explanation: j['explanation'] as String? ?? '',
        confidence: (j['confidence'] as num?)?.toInt() ?? 0,
        rain1h: (j['rain_1h'] as num?)?.toDouble(),
        h3Index: j['h3_index'] as String?,
        wardName: j['ward_name'] as String?,
        hourly: (j['hourly'] as List<dynamic>? ?? [])
            .map((h) => HourlyRisk.fromJson(h as Map<String, dynamic>))
            .toList(),
      );
}
