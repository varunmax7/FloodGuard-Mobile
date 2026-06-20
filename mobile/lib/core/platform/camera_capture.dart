/// Platform-conditional camera capture.
/// Web → getUserMedia overlay.  Native → image_picker camera.
library;

export 'camera_capture_stub.dart'
    if (dart.library.html) 'camera_capture_web.dart';
