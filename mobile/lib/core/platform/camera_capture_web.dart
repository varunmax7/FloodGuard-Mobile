/// Web webcam capture using getUserMedia + a native HTML DOM overlay.
/// No Flutter widgets needed — avoids HtmlElementView complexity.
library;

import 'dart:async';
import 'dart:convert' show base64Decode;
// ignore: avoid_web_libraries_in_flutter
import 'dart:html' as html;

import 'package:image_picker/image_picker.dart';

Future<XFile?> captureWebcam() async {
  // Request camera permission and stream.
  final mediaDevices = html.window.navigator.mediaDevices;
  if (mediaDevices == null) return null;

  html.MediaStream stream;
  try {
    stream = await mediaDevices.getUserMedia({
      'video': {'facingMode': 'user', 'width': 1280, 'height': 720},
      'audio': false,
    });
  } catch (_) {
    // Permission denied or no camera available.
    return null;
  }

  final completer = Completer<XFile?>();

  // ── Build a full-screen HTML overlay ────────────────────────────────────────

  final overlay = html.DivElement()
    ..style.position = 'fixed'
    ..style.top = '0'
    ..style.left = '0'
    ..style.right = '0'
    ..style.bottom = '0'
    ..style.zIndex = '2147483647'
    ..style.backgroundColor = 'rgba(0,0,0,0.92)'
    ..style.display = 'flex'
    ..style.flexDirection = 'column'
    ..style.alignItems = 'center'
    ..style.justifyContent = 'center'
    ..style.gap = '16px'
    ..style.fontFamily = 'Inter, system-ui, sans-serif';

  final title = html.SpanElement()
    ..text = 'Take a photo'
    ..style.color = 'white'
    ..style.fontSize = '18px'
    ..style.fontWeight = '600';

  final video = html.VideoElement()
    ..autoplay = true
    ..style.width = '100%'
    ..style.maxWidth = '420px'
    ..style.borderRadius = '14px'
    ..style.objectFit = 'cover'
    ..style.background = '#111';
  video.srcObject = stream;

  final btnRow = html.DivElement()
    ..style.display = 'flex'
    ..style.gap = '12px'
    ..style.marginTop = '4px';

  final captureBtn = html.ButtonElement()
    ..text = '📸  Capture'
    ..style.padding = '12px 32px'
    ..style.fontSize = '15px'
    ..style.fontWeight = '600'
    ..style.borderRadius = '10px'
    ..style.border = 'none'
    ..style.backgroundColor = '#2563EB'
    ..style.color = 'white'
    ..style.cursor = 'pointer';

  final cancelBtn = html.ButtonElement()
    ..text = 'Cancel'
    ..style.padding = '12px 20px'
    ..style.fontSize = '14px'
    ..style.borderRadius = '10px'
    ..style.border = '1.5px solid rgba(255,255,255,0.35)'
    ..style.backgroundColor = 'transparent'
    ..style.color = 'white'
    ..style.cursor = 'pointer';

  btnRow.children.addAll([captureBtn, cancelBtn]);
  overlay.children.addAll([title, video, btnRow]);
  html.document.body!.append(overlay);

  void cleanup() {
    stream.getTracks().forEach((t) => t.stop());
    overlay.remove();
  }

  // Capture button: draw video frame → canvas → data URL → XFile
  captureBtn.onClick.listen((_) {
    final canvas = html.CanvasElement(
      width: video.videoWidth > 0 ? video.videoWidth : 1280,
      height: video.videoHeight > 0 ? video.videoHeight : 720,
    );
    canvas.context2D.drawImage(video, 0, 0);

    final dataUrl = canvas.toDataUrl('image/jpeg', 0.85);
    final base64Part = dataUrl.substring(dataUrl.indexOf(',') + 1);
    final bytes = base64Decode(base64Part);

    final blob = html.Blob([bytes], 'image/jpeg');
    final blobUrl = html.Url.createObjectUrl(blob);

    cleanup();
    completer.complete(XFile(blobUrl, mimeType: 'image/jpeg', bytes: bytes));
  });

  cancelBtn.onClick.listen((_) {
    cleanup();
    completer.complete(null);
  });

  return completer.future;
}
