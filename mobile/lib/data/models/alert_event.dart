/// AlertEvent — response model for GET /alerts.
library;

class AlertEvent {
  final String id;
  final String riskLevel;
  final String message;
  final DateTime windowStart;
  final DateTime windowEnd;
  final String? h3Index;
  final String? wardName;
  final bool isActive;

  const AlertEvent({
    required this.id,
    required this.riskLevel,
    required this.message,
    required this.windowStart,
    required this.windowEnd,
    this.h3Index,
    this.wardName,
    required this.isActive,
  });

  factory AlertEvent.fromJson(Map<String, dynamic> j) => AlertEvent(
        id: j['id'] as String,
        riskLevel: (j['risk_level'] as String).toUpperCase(),
        message: j['message'] as String? ?? '',
        windowStart: DateTime.parse(j['window_start'] as String),
        windowEnd: DateTime.parse(j['window_end'] as String),
        h3Index: j['h3_index'] as String?,
        wardName: j['ward_name'] as String?,
        isActive: j['is_active'] as bool? ?? false,
      );

  bool get isSevere => riskLevel == 'SEVERE';
  bool get isHighOrAbove => riskLevel == 'HIGH' || riskLevel == 'SEVERE';

  String get areaLabel =>
      wardName?.isNotEmpty == true ? wardName! : (h3Index?.substring(0, 10) ?? 'Unknown area');

  String get timeAgo {
    final diff = DateTime.now().difference(windowStart);
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }
}
