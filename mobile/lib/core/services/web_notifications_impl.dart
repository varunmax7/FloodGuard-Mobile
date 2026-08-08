/// Web implementation — talks to window.Notification via JS interop.
library;

import 'dart:async';
// ignore: deprecated_member_use, avoid_web_libraries_in_flutter
import 'dart:js' as js;

Future<bool> requestPermission() async {
  try {
    final n = js.context['Notification'];
    if (n == null) return false;
    final current = (n['permission'] as String?) ?? 'default';
    if (current == 'granted') return true;
    if (current == 'denied') return false;
    final done = Completer<String>();
    n.callMethod('requestPermission', [
      js.allowInterop((result) {
        if (!done.isCompleted) done.complete(result?.toString() ?? 'default');
      }),
    ]);
    final result = await done.future;
    return result == 'granted';
  } catch (_) {
    return false;
  }
}

void show({
  required String title,
  required String body,
  String? image,
  String? tag,
}) {
  try {
    final n = js.context['Notification'];
    if (n == null) return;
    if (n['permission'] != 'granted') return;
    // Keep `icon` small + reliable (Chrome will silently drop the whole
    // notification if the icon fetch fails — e.g. an S3 signed URL that's
    // too big or slow). The photo goes in `image`, which Chrome desktop
    // renders as a large banner; browsers that ignore `image` still get the
    // small icon plus the in-app MaterialBanner that shows the real photo.
    final hasImage = image != null && image.isNotEmpty;
    final opts = <String, dynamic>{
      'body': body,
      'icon': '/icons/Icon-192.png',
      'badge': '/icons/Icon-192.png',
      if (hasImage) 'image': image,
      if (tag != null && tag.isNotEmpty) 'tag': tag,
      'renotify': tag != null && tag.isNotEmpty,
    };
    js.JsObject(n, [title, js.JsObject.jsify(opts)]);
  } catch (_) {
    // Notification blocked or unavailable — silently skip.
  }
}
