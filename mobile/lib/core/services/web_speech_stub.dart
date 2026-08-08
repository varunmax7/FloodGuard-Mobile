/// Non-web stub — every call is a no-op.
library;

bool isSupported() => false;
void Function()? listen({
  required void Function(String transcript, bool isFinal) onResult,
  void Function(String reason)? onError,
  String lang = 'en-IN',
}) => null;
