/// Typed exceptions raised by [FloodGuardApi] for cases the UI should
/// distinguish from generic network failures.
library;

/// Thrown when the backend reports that the upstream weather feed hasn't
/// produced fresh data recently (HTTP 503 + `code: "STALE_FORECAST"`).
///
/// The UI should render a "no live data yet" state rather than a generic
/// "unable to load" error, so users can trust that a blank screen means
/// "nothing to show right now" and not "the app is broken".
class StaleForecastException implements Exception {
  final DateTime? lastUpdate;
  final int maxAgeHours;
  final String detail;

  const StaleForecastException({
    this.lastUpdate,
    this.maxAgeHours = 0,
    this.detail = 'No live forecast data available.',
  });

  @override
  String toString() => detail;
}
