/// Centralized tuning constants for the Report Flooding feature.
library;

class ReportConstants {
  ReportConstants._();

  /// Radius used for "nearby" pre-submit context strip.
  static const int nearbyRadiusM = 1000;

  /// Time window (minutes) for nearby context strip.
  static const int nearbyContextMinutes = 60;

  /// JPEG quality for photo compression (0-100).
  static const int compressQuality = 75;

  /// Max dimension (px) for photo compression.
  static const int compressMaxDim = 1024;
}
