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

  /// H3 resolution used by the backend (must match).
  static const int h3Resolution = 9;

  /// Hyderabad bounding box (used for initial map centering).
  static const double hydLatitude = 17.3850;
  static const double hydLongitude = 78.4867;
}
