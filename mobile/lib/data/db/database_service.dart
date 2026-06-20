/// Platform-conditional database service.
/// Web → stub (no SQLite).  Native → Drift-backed implementation.
library;

export 'database_service_web.dart'
    if (dart.library.io) 'database_service_native.dart';
