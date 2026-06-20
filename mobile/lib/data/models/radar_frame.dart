/// RadarFrame — matches GET /api/v1/radar/frames response shape.
library;

class RadarIntensityBand {
  final int dbzMin;
  final int dbzMax;
  final String color;
  final String label;

  // Named positional constructor so const list literals work in radar_screen.dart
  const RadarIntensityBand({
    required this.dbzMin,
    required this.dbzMax,
    required this.color,
    required this.label,
  });

  factory RadarIntensityBand.fromJson(Map<String, dynamic> j) =>
      RadarIntensityBand(
        dbzMin: (j['dbz_min'] as num).toInt(),
        dbzMax: (j['dbz_max'] as num).toInt(),
        color: j['color'] as String,
        label: j['label'] as String,
      );
}

class RadarFrame {
  final DateTime ts;
  final String tileUrlTemplate;
  final int dbzMin;
  final int dbzMax;
  final bool anomaly;
  final List<RadarIntensityBand> intensityLegend;

  const RadarFrame({
    required this.ts,
    required this.tileUrlTemplate,
    required this.dbzMin,
    required this.dbzMax,
    required this.anomaly,
    required this.intensityLegend,
  });

  factory RadarFrame.fromJson(Map<String, dynamic> j) => RadarFrame(
        ts: DateTime.parse(j['ts'] as String),
        tileUrlTemplate: j['tile_url_template'] as String,
        dbzMin: (j['dbz_min'] as num? ?? 0).toInt(),
        dbzMax: (j['dbz_max'] as num? ?? 75).toInt(),
        anomaly: j['anomaly'] as bool? ?? false,
        intensityLegend: (j['intensity_legend'] as List<dynamic>? ?? [])
            .map((e) =>
                RadarIntensityBand.fromJson(e as Map<String, dynamic>))
            .toList(),
      );

  /// XYZ tile URL — MapLibre expects {z}/{x}/{y} placeholders.
  String get tileUrl => tileUrlTemplate;
}
