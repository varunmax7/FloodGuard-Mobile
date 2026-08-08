/// Lightweight wrapper around the browser Notification API.
///
/// On non-web platforms every call is a no-op so callers don't need to guard
/// with kIsWeb — they can just call `WebNotifications.show(...)`.
///
/// Uses the deprecated-but-still-supported `dart:js_interop` to avoid pulling
/// in `dart:html` (banned in Dart 3+ web builds).
library;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'web_notifications_impl.dart' if (dart.library.io) 'web_notifications_stub.dart' as impl;

class WebNotifications {
  /// Ask the user to grant notification permission. Returns true if granted.
  /// Called from map_screen once per session; browsers dedupe the popup.
  static Future<bool> requestPermission() async {
    if (!kIsWeb) return false;
    return impl.requestPermission();
  }

  /// Fire a browser notification. Silently no-ops if permission was denied,
  /// so callers never need to check status.
  /// [image] is a full URL rendered as a large banner (Chrome/Edge desktop);
  /// [tag] dedupes repeated notifications with the same identifier.
  static void show({
    required String title,
    required String body,
    String? image,
    String? tag,
  }) {
    if (!kIsWeb) return;
    impl.show(title: title, body: body, image: image, tag: tag);
  }
}
