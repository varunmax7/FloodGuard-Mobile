/// Voice-to-text via the browser Web Speech API.
/// No-op on non-web platforms so callers don't need to guard with kIsWeb.
library;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'web_speech_impl.dart' if (dart.library.io) 'web_speech_stub.dart' as impl;

class WebSpeech {
  /// True if the current browser exposes SpeechRecognition/webkitSpeechRecognition.
  static bool isSupported() => kIsWeb && impl.isSupported();

  /// Start listening. onResult fires with the interim + final transcript.
  /// Returns a stop-function that ends the recording early.
  /// On error or unsupported, returns null.
  static void Function()? listen({
    required void Function(String transcript, bool isFinal) onResult,
    void Function(String reason)? onError,
    String lang = 'en-IN',
  }) {
    if (!kIsWeb) {
      onError?.call('Voice input is only available on the web.');
      return null;
    }
    return impl.listen(onResult: onResult, onError: onError, lang: lang);
  }
}
