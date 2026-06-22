/// AlertEvent — response model for GET /alerts.
library;

class AlertEvent {
  final String id;
  final String riskLevel;
  final String source;
  final String message;
  final DateTime windowStart;
  final DateTime windowEnd;
  final String? h3Index;
  final String? wardName;
  final bool isActive;
  final String? photoUrl;
  final String? depth;
  final String? road;
  final double? lat;
  final double? lon;

  const AlertEvent({
    required this.id,
    required this.riskLevel,
    this.source = 'RISK',
    required this.message,
    required this.windowStart,
    required this.windowEnd,
    this.h3Index,
    this.wardName,
    required this.isActive,
    this.photoUrl,
    this.depth,
    this.road,
    this.lat,
    this.lon,
  });

  factory AlertEvent.fromJson(Map<String, dynamic> j) => AlertEvent(
        id: j['id'] as String,
        riskLevel: (j['risk_level'] as String).toUpperCase(),
        source: (j['source'] as String? ?? 'RISK').toUpperCase(),
        message: j['message'] as String? ?? '',
        windowStart: DateTime.parse(j['window_start'] as String),
        windowEnd: DateTime.parse(j['window_end'] as String),
        h3Index: j['h3_index'] as String?,
        wardName: j['ward_name'] as String?,
        isActive: j['is_active'] as bool? ?? false,
        photoUrl: j['photo_url'] as String?,
        depth: j['depth'] as String?,
        road: j['road'] as String?,
        lat: (j['lat'] as num?)?.toDouble(),
        lon: (j['lon'] as num?)?.toDouble(),
      );

  bool get isReport => source == 'REPORT';
  bool get isSevere => riskLevel == 'SEVERE';
  bool get isHighOrAbove => riskLevel == 'HIGH' || riskLevel == 'SEVERE';

  String get areaLabel =>
      wardName?.isNotEmpty == true ? wardName! : (h3Index?.substring(0, 10) ?? 'Unknown area');

  String get depthLabel {
    switch (depth) {
      case 'ANKLE': return 'Ankle deep';
      case 'KNEE': return 'Knee deep';
      case 'WAIST': return 'Waist deep';
      case 'VEHICLE': return 'Vehicle level';
      default: return depth ?? '';
    }
  }

  String get roadLabel {
    switch (road) {
      case 'PASSABLE': return 'Road passable';
      case 'DIFFICULT': return 'Road difficult';
      case 'BLOCKED': return 'Road blocked';
      default: return road ?? '';
    }
  }

  String get timeAgo {
    final diff = DateTime.now().difference(windowStart);
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }
}
