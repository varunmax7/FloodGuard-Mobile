/// AppConfig — reads dart-define values injected at build time.
/// Usage: flutter run --dart-define=API_BASE_URL=https://api.floodguard.in
class AppConfig {
  AppConfig._();

  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  static const String environment = String.fromEnvironment(
    'ENV',
    defaultValue: 'dev',
  );

  static bool get isDev => environment == 'dev';
  static bool get isProd => environment == 'prod';

  /// H3 resolution used by the backend (must match settings.H3_RESOLUTION).
  /// res 7 → ~1.2 km hex edge; matches the TG + AP multi-state hexgrid.
  static const int h3Resolution = 7;

  /// Region centre used for initial map centering. Vijayawada area sits near
  /// the geographic middle of the TG + AP union, so both states fit in view
  /// at zoom ~6.8.
  static const double regionLatitude = 16.5000;
  static const double regionLongitude = 80.0000;
  static const double regionInitialZoom = 6.8;
  static const String regionName = 'Telangana & Andhra Pradesh';

  /// Combined bbox for the TG + AP region — (minLng, minLat, maxLng, maxLat).
  /// Used by the map search viewport.
  static const double regionMinLng = 76.5;
  static const double regionMinLat = 12.5;
  static const double regionMaxLng = 84.8;
  static const double regionMaxLat = 19.9;

  // Legacy aliases kept so screens that still reference `hyd*` compile until
  // they're migrated. Value is now the region centre (NOT Hyderabad specifically).
  static const double hydLatitude = regionLatitude;
  static const double hydLongitude = regionLongitude;
}
