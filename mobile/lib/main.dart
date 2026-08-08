import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:sentry_flutter/sentry_flutter.dart';
import 'core/network/dio_client.dart' show getAccessToken;
import 'core/providers/alerts_providers.dart' show authProvider;
import 'core/providers/api_providers.dart' show apiProvider;
import 'core/router/app_router.dart';
import 'core/services/web_notifications.dart';
import 'design/theme/app_theme.dart';
import 'features/report/report_sync.dart';
import 'firebase_options.dart';

/// True only when Firebase.initializeApp() succeeded.
/// Every Firebase call site must check this before use.
bool firebaseReady = false;

/// Global handle so background pollers can surface in-app banners/snackbars
/// without needing a BuildContext.
final GlobalKey<ScaffoldMessengerState> scaffoldMessengerKey =
    GlobalKey<ScaffoldMessengerState>();

// Injected at build time: --dart-define=SENTRY_DSN=https://...
const _sentryDsn = String.fromEnvironment('SENTRY_DSN');

@pragma('vm:entry-point')
Future<void> _fcmBackgroundHandler(RemoteMessage message) async {
  // Background isolate — Firebase may need re-init here.
  try {
    await Firebase.initializeApp();
  } catch (_) {}
}

Future<void> _appInit() async {
  WidgetsFlutterBinding.ensureInitialized();

  try {
    await Firebase.initializeApp(
      options: DefaultFirebaseOptions.currentPlatform,
    );
    firebaseReady = true;
    FirebaseMessaging.onBackgroundMessage(_fcmBackgroundHandler);
    await FirebaseMessaging.instance.requestPermission(
      alert: true, badge: true, sound: true,
    );
  } catch (e) {
    debugPrint('Firebase unavailable (dev mode — configure FlutterFire for push): $e');
  }

  await initWorkManager();
}

void main() async {
  if (_sentryDsn.isNotEmpty) {
    await SentryFlutter.init(
      (options) {
        options.dsn = _sentryDsn;
        options.tracesSampleRate = 0.1;
        options.environment = const bool.fromEnvironment('dart.vm.product')
            ? 'production'
            : 'development';
      },
      appRunner: () async {
        await _appInit();
        runApp(const ProviderScope(child: FloodGuardApp()));
      },
    );
  } else {
    await _appInit();
    runApp(const ProviderScope(child: FloodGuardApp()));
  }
}

class FloodGuardApp extends ConsumerWidget {
  const FloodGuardApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(appRouterProvider);
    return MaterialApp.router(
      title: 'FloodGuard',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.system,
      routerConfig: router,
      scaffoldMessengerKey: scaffoldMessengerKey,
      builder: (context, child) => _FcmListener(
        router: ref.read(appRouterProvider),
        child: _AlertPoller(child: child!),
      ),
    );
  }
}

/// Polls `/api/v1/alerts/?scope=active` every 60 s while the user is logged in.
/// When a new alert appears (including admin-verified user reports for hexes
/// near a saved place), fires a browser notification with the report image.
/// No-op on non-web platforms.
class _AlertPoller extends ConsumerStatefulWidget {
  final Widget child;
  const _AlertPoller({required this.child});
  @override
  ConsumerState<_AlertPoller> createState() => _AlertPollerState();
}

class _AlertPollerState extends ConsumerState<_AlertPoller> {
  Timer? _timer;
  final Set<String> _seen = <String>{};
  bool _isFirstPoll = true;
  bool _loggedIn = false;

  @override
  void initState() {
    super.initState();
    if (!kIsWeb) return;
    // React to login/logout: start/stop the poller.
    Future.microtask(() {
      ref.listenManual<dynamic>(authProvider, (_, next) => _syncTimer(next));
      _syncTimer(ref.read(authProvider));
    });
  }

  void _syncTimer(dynamic auth) {
    final loggedIn = (auth as dynamic)?.isLoggedIn == true;
    if (loggedIn == _loggedIn) return;
    _loggedIn = loggedIn;
    _timer?.cancel();
    if (!loggedIn) {
      _seen.clear();
      _isFirstPoll = true;
      return;
    }
    // Fire once immediately, then every 60 s.
    _poll();
    _timer = Timer.periodic(const Duration(seconds: 60), (_) => _poll());
  }

  Future<void> _poll() async {
    try {
      final token = await getAccessToken();
      if (token == null) return;
      final api = ref.read(apiProvider);
      final raw = await api.getAlerts(scope: 'active');
      final currentIds = <String>{};
      for (final a in raw) {
        if (a is! Map<String, dynamic>) continue;
        final id = a['id']?.toString();
        if (id != null) currentIds.add(id);
      }
      if (!_isFirstPoll) {
        final newIds = currentIds.difference(_seen);
        for (final a in raw) {
          if (a is! Map<String, dynamic>) continue;
          final id = a['id']?.toString();
          if (id == null || !newIds.contains(id)) continue;
          final ward = (a['ward_name'] as String?)?.trim().isNotEmpty == true
              ? a['ward_name'] as String
              : 'your area';
          final risk = (a['risk_level'] as String?) ?? 'ALERT';
          final title = a['source'] == 'REPORT'
              ? 'Flood report verified near $ward'
              : 'Flood alert: $risk — $ward';
          final body = (a['message'] as String?) ?? 'Tap to see details.';
          final description = (a['description'] as String?) ?? '';
          final photo = a['photo_url'] as String?;
          // Fire OS-level notification (Chrome desktop shows the image;
          // macOS/Safari fall back to icon-only).
          WebNotifications.show(title: title, body: body, image: photo, tag: id);
          // ALSO show an in-app banner with the photo — this is what
          // guarantees the operator/user actually sees the report image
          // regardless of browser notification quirks.
          _showInAppAlertBanner(
            title: title,
            body: body,
            description: description,
            photo: photo,
          );
        }
      }
      _seen
        ..clear()
        ..addAll(currentIds);
      _isFirstPoll = false;
    } catch (_) {
      // Silent — offline or unauthenticated. Next tick will retry.
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  /// Shows a MaterialBanner at the top of every Scaffold with the photo,
  /// title, body, and description of a new alert. Dedupes silently — if
  /// the user's already got one on screen we don't stack them.
  void _showInAppAlertBanner({
    required String title,
    required String body,
    required String description,
    String? photo,
  }) {
    final messenger = scaffoldMessengerKey.currentState;
    if (messenger == null) return;
    messenger.clearMaterialBanners();
    messenger.showMaterialBanner(
      MaterialBanner(
        backgroundColor: Colors.white,
        elevation: 4,
        leading: photo != null && photo.isNotEmpty
            ? ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: Image.network(
                  photo,
                  width: 64,
                  height: 64,
                  fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => Container(
                    width: 64,
                    height: 64,
                    color: const Color(0xFFF1F5F9),
                    child: const Icon(Icons.warning_amber_rounded,
                        color: Color(0xFFEF4444)),
                  ),
                ),
              )
            : Container(
                width: 48,
                height: 48,
                decoration: const BoxDecoration(
                  color: Color(0xFFFEE2E2),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.warning_amber_rounded,
                    color: Color(0xFFEF4444)),
              ),
        content: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              title,
              style: const TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: 14,
                color: Color(0xFF0F172A),
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 2),
            Text(
              body,
              style: const TextStyle(fontSize: 12, color: Color(0xFF475569)),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            if (description.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(
                '"$description"',
                style: const TextStyle(
                  fontSize: 12,
                  color: Color(0xFF334155),
                  fontStyle: FontStyle.italic,
                ),
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => messenger.hideCurrentMaterialBanner(),
            child: const Text('Dismiss'),
          ),
        ],
      ),
    );
    // Auto-dismiss after 15 s so the banner doesn't linger forever.
    Future.delayed(const Duration(seconds: 15), () {
      scaffoldMessengerKey.currentState?.hideCurrentMaterialBanner();
    });
  }

  @override
  Widget build(BuildContext context) => widget.child;
}

/// Wires FCM tap events → go_router deep links.
/// Skipped entirely when Firebase is not configured.
class _FcmListener extends StatefulWidget {
  final GoRouter router;
  final Widget child;
  const _FcmListener({required this.router, required this.child});

  @override
  State<_FcmListener> createState() => _FcmListenerState();
}

class _FcmListenerState extends State<_FcmListener> {
  @override
  void initState() {
    super.initState();
    if (firebaseReady) _setupHandlers();
  }

  void _setupHandlers() {
    FirebaseMessaging.onMessage.listen((RemoteMessage msg) {
      final notif = msg.notification;
      if (notif == null) return;
      final ctx = widget.router.routerDelegate.navigatorKey.currentContext;
      if (ctx == null || !ctx.mounted) return;
      ScaffoldMessenger.of(ctx).showSnackBar(
        SnackBar(
          content: Text('${notif.title}: ${notif.body}'),
          action: SnackBarAction(
            label: 'View',
            onPressed: () => _route(msg),
          ),
        ),
      );
    });

    FirebaseMessaging.onMessageOpenedApp.listen(_route);

    FirebaseMessaging.instance.getInitialMessage().then((msg) {
      if (msg != null) _route(msg);
    });
  }

  void _route(RemoteMessage msg) {
    final h3 = msg.data['h3_index'] as String?;
    widget.router.go(h3 != null ? '/alerts?focus=$h3' : '/alerts');
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
