/// SavedPlace — response model for GET /places.
library;

class SavedPlace {
  final String id;
  final String label; // HOME | OFFICE | OTHER
  final double? latitude;
  final double? longitude;
  final String? hexId;
  final bool notify;

  const SavedPlace({
    required this.id,
    required this.label,
    this.latitude,
    this.longitude,
    this.hexId,
    required this.notify,
  });

  factory SavedPlace.fromJson(Map<String, dynamic> j) => SavedPlace(
        id: j['id'].toString(),
        label: (j['label'] as String).toUpperCase(),
        latitude: (j['latitude'] as num?)?.toDouble(),
        longitude: (j['longitude'] as num?)?.toDouble(),
        hexId: j['hex_id'] as String?,
        notify: j['notify'] as bool? ?? true,
      );

  SavedPlace copyWith({bool? notify}) => SavedPlace(
        id: id,
        label: label,
        latitude: latitude,
        longitude: longitude,
        hexId: hexId,
        notify: notify ?? this.notify,
      );

  String get labelEmoji => switch (label) {
        'HOME' => '🏠',
        'OFFICE' => '🏢',
        _ => '📍',
      };
}
