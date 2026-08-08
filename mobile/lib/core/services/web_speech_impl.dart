/// Web implementation — window.SpeechRecognition (webkit-prefixed on Chrome).
library;

// ignore: deprecated_member_use, avoid_web_libraries_in_flutter
import 'dart:js' as js;

dynamic _ctor() {
  final c = js.context['SpeechRecognition'] ?? js.context['webkitSpeechRecognition'];
  return c;
}

bool isSupported() {
  try {
    return _ctor() != null;
  } catch (_) {
    return false;
  }
}

void Function()? listen({
  required void Function(String transcript, bool isFinal) onResult,
  void Function(String reason)? onError,
  String lang = 'en-IN',
}) {
  try {
    final ctor = _ctor();
    if (ctor == null) {
      onError?.call('Voice input is not supported in this browser.');
      return null;
    }
    final rec = js.JsObject(ctor as js.JsFunction, []);
    rec['lang'] = lang;
    rec['interimResults'] = true;
    rec['continuous'] = false;
    rec['maxAlternatives'] = 1;

    rec['onresult'] = js.allowInterop((event) {
      try {
        final results = event['results'];
        final len = results['length'] as int;
        final buf = StringBuffer();
        bool isFinal = false;
        for (var i = 0; i < len; i++) {
          final r = results[i];
          buf.write(r[0]['transcript'] as String? ?? '');
          if (r['isFinal'] as bool? ?? false) isFinal = true;
        }
        onResult(buf.toString().trim(), isFinal);
      } catch (_) {}
    });

    rec['onerror'] = js.allowInterop((event) {
      final err = event['error']?.toString() ?? 'unknown';
      onError?.call(err);
    });

    rec.callMethod('start', []);
    return () {
      try {
        rec.callMethod('stop', []);
      } catch (_) {}
    };
  } catch (e) {
    onError?.call(e.toString());
    return null;
  }
}
