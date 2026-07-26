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
  /// res 7 → ~1.2 km hex edge; matches the Assam state-scale hexgrid.
  static const int h3Resolution = 7;

  /// Region centre used for initial map centering. Guwahati sits near the
  /// geographic middle of Assam so the whole state fits in view at zoom ~7.5.
  static const double regionLatitude = 26.1445;
  static const double regionLongitude = 91.7362;
  static const double regionInitialZoom = 7.5;
  static const String regionName = 'Assam';

  // Legacy aliases kept so screens that still reference `hyd*` compile until
  // they're migrated. Value is now the Assam centre.
  static const double hydLatitude = regionLatitude;
  static const double hydLongitude = regionLongitude;
}
