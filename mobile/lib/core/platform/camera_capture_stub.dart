/// Non-web stub — native uses image_picker directly in the call site.
library;

import 'package:image_picker/image_picker.dart';

// Returns null; native call sites handle camera via image_picker directly.
Future<XFile?> captureWebcam() async => null;
