/// FloodReport public fields returned by /reports/nearby.
library;

class FloodReport {
  final String id;
  final String depth;   // ANKLE | KNEE | WAIST | VEHICLE
  final String road;    // PASSABLE | DIFFICULT | BLOCKED
  final String status;  // PENDING | VERIFIED
  final String? photoUrl;
  final String? observedAt;
  final String? timeAgo;
  final double? lat;
  final double? lng;

  const FloodReport({
    required this.id,
    required this.depth,
    required this.road,
    required this.status,
    this.photoUrl,
    this.observedAt,
    this.timeAgo,
    this.lat,
    this.lng,
  });

  factory FloodReport.fromJson(Map<String, dynamic> j) => FloodReport(
        id: j['id'] as String,
        depth: j['depth'] as String,
        road: j['road'] as String,
        status: j['status'] as String,
        photoUrl: j['photo_url'] as String?,
        observedAt: j['observed_at'] as String?,
        timeAgo: j['time_ago'] as String?,
        lat: (j['lat'] as num?)?.toDouble(),
        lng: (j['lng'] as num?)?.toDouble(),
      );

  String get depthLabel => switch (depth) {
        'ANKLE' => 'Ankle deep',
        'KNEE' => 'Knee deep',
        'WAIST' => 'Waist deep',
        'VEHICLE' => 'Vehicle level',
        _ => depth,
      };

  String get roadLabel => switch (road) {
        'PASSABLE' => 'Passable',
        'DIFFICULT' => 'Difficult',
        'BLOCKED' => 'Blocked',
        _ => road,
      };
}
