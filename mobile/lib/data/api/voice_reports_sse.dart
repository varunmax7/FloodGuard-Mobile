/// SSE listener + polling fallback for the voice-agent reports feed.
///
/// Wire — spec §13.2 item 2: "Subscribe to the SSE stream for live feed
/// updates; fall back to 15 s polling if SSE drops." The polling
/// fallback matches the SSE keepalive interval on the server (see
/// `KEEPALIVE_INTERVAL_SEC` in `routes_reports.py`), so a dropped
/// connection recovers within one server keepalive window.
///
/// The endpoint is admin-gated (`X-Admin-Api-Key` — see
/// `require_admin_api_key` in the voice-agent repo), so this client
/// accepts the key via dart-define `VOICE_ADMIN_API_KEY` at build
/// time. In-app: only ops-role users see the stream. Empty key →
/// stream returns 401 immediately and the fallback poller kicks in
/// (which will also 401, so the caller gets an error — surface it in
/// the UI as "not authorised" rather than spinning).
library;

import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';

import '../models/voice_report.dart';

const String _kAdminKeyHeader = 'X-Admin-Api-Key';

/// Compile-time admin key. Injected via
/// `--dart-define=VOICE_ADMIN_API_KEY=...`.
const String kVoiceAdminApiKey =
    String.fromEnvironment('VOICE_ADMIN_API_KEY', defaultValue: '');

/// Fallback poll cadence when SSE isn't up. Matches the server's SSE
/// keepalive so callers get one refresh per keepalive miss.
const Duration kPollFallbackInterval = Duration(seconds: 15);

/// Reconnect delay after an SSE drop before we retry the stream (and
/// while retrying, the fallback poller keeps the UI moving).
const Duration kSseReconnectDelay = Duration(seconds: 3);

class VoiceReportsSseClient {
  final Dio _dio;
  final String _adminKey;
  final Duration _pollInterval;
  final Duration _reconnectDelay;

  StreamController<VoiceReportEvent>? _controller;
  StreamSubscription<String>? _sseSub;
  Timer? _pollTimer;
  DateTime? _lastSeenCreatedAt;
  bool _sseUp = false;
  bool _closed = false;

  VoiceReportsSseClient(
    this._dio, {
    String? adminKey,
    Duration? pollInterval,
    Duration? reconnectDelay,
  })  : _adminKey = adminKey ?? kVoiceAdminApiKey,
        _pollInterval = pollInterval ?? kPollFallbackInterval,
        _reconnectDelay = reconnectDelay ?? kSseReconnectDelay;

  /// Broadcast stream — safe to attach multiple listeners; upstream
  /// SSE + polling only run while at least one listener is attached.
  Stream<VoiceReportEvent> events() {
    _controller ??= StreamController<VoiceReportEvent>.broadcast(
      onListen: _start,
      onCancel: _stopIfIdle,
    );
    return _controller!.stream;
  }

  Future<void> close() async {
    _closed = true;
    await _sseSub?.cancel();
    _sseSub = null;
    _pollTimer?.cancel();
    _pollTimer = null;
    await _controller?.close();
    _controller = null;
  }

  // ── SSE ──────────────────────────────────────────────────────────

  void _start() {
    _closed = false;
    _startPoller();
    _startSse();
  }

  void _stopIfIdle() {
    if (_controller?.hasListener == false) {
      _sseSub?.cancel();
      _sseSub = null;
      _pollTimer?.cancel();
      _pollTimer = null;
    }
  }

  Future<void> _startSse() async {
    if (_closed || _controller == null) return;
    try {
      final res = await _dio.get<ResponseBody>(
        '/reports/stream',
        options: Options(
          responseType: ResponseType.stream,
          headers: {
            'Accept': 'text/event-stream',
            if (_adminKey.isNotEmpty) _kAdminKeyHeader: _adminKey,
          },
          receiveTimeout: Duration.zero,
        ),
      );
      final body = res.data;
      if (body == null) {
        _scheduleSseReconnect();
        return;
      }
      _sseUp = true;
      final lineStream = body.stream
          .cast<List<int>>()
          .transform(utf8.decoder)
          .transform(const LineSplitter());
      final buffer = <String>[];
      _sseSub = lineStream.listen(
        (line) {
          if (line.isEmpty) {
            _emitFromBuffer(buffer);
            buffer.clear();
            return;
          }
          if (line.startsWith(':')) return; // comment (keepalive/connected)
          buffer.add(line);
        },
        onError: (Object _) {
          _sseUp = false;
          _scheduleSseReconnect();
        },
        onDone: () {
          _sseUp = false;
          _scheduleSseReconnect();
        },
        cancelOnError: true,
      );
    } on DioException {
      _sseUp = false;
      _scheduleSseReconnect();
    }
  }

  void _scheduleSseReconnect() {
    _sseSub?.cancel();
    _sseSub = null;
    if (_closed || _controller?.hasListener != true) return;
    Future.delayed(_reconnectDelay, _startSse);
  }

  void _emitFromBuffer(List<String> lines) {
    String? eventType;
    final dataParts = <String>[];
    for (final line in lines) {
      if (line.startsWith('event: ')) {
        eventType = line.substring('event: '.length).trim();
      } else if (line.startsWith('data: ')) {
        dataParts.add(line.substring('data: '.length));
      }
    }
    if (eventType == null) return;
    final dataStr = dataParts.join('\n');
    if (eventType == 'lagged') {
      _controller?.add(VoiceReportEvent.laggedSentinel());
      return;
    }
    if (dataStr.isEmpty) return;
    final Map<String, dynamic> payload;
    try {
      payload = jsonDecode(dataStr) as Map<String, dynamic>;
    } catch (_) {
      return; // malformed — the relay contract guarantees JSON, so
              // silently swallow rather than propagate a stream error.
    }
    if (!payload.containsKey('report_id')) return;
    final report = VoiceReport.fromJson(payload);
    _lastSeenCreatedAt = report.createdAt;
    if (eventType == 'report.submitted') {
      _controller?.add(VoiceReportEvent.submitted(report));
    } else if (eventType == 'report.enriched') {
      _controller?.add(VoiceReportEvent.enriched(report));
    }
  }

  // ── Polling fallback ─────────────────────────────────────────────

  void _startPoller() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(_pollInterval, (_) => _pollOnce());
    // Prime with an immediate poll so the UI has a page of data even
    // if SSE never comes up.
    unawaited(_pollOnce());
  }

  Future<void> _pollOnce() async {
    if (_closed || _controller == null) return;
    if (_sseUp) return; // SSE covers it — skip this tick to save the RTT.
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        '/reports',
        queryParameters: {'source': 'voice', 'limit': 50},
        options: Options(
          headers: {
            if (_adminKey.isNotEmpty) _kAdminKeyHeader: _adminKey,
          },
        ),
      );
      final items = (res.data?['items'] as List?) ?? const [];
      // Backend returns newest-first; iterate in reverse so
      // listeners see events in chronological order.
      for (final raw in items.reversed) {
        final report = VoiceReport.fromJson(raw as Map<String, dynamic>);
        final seen = _lastSeenCreatedAt;
        if (seen != null && !report.createdAt.isAfter(seen)) continue;
        _lastSeenCreatedAt = report.createdAt;
        _controller?.add(VoiceReportEvent.submitted(report));
      }
    } on DioException {
      // Poll failed — next tick will retry. Don't propagate; a
      // transient 5xx shouldn't tear down the whole stream.
    }
  }
}
