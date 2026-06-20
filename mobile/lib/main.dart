import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:sentry_flutter/sentry_flutter.dart';
import 'core/router/app_router.dart';
import 'design/theme/app_theme.dart';
import 'features/report/report_sync.dart';
import 'firebase_options.dart';

/// True only when Firebase.initializeApp() succeeded.
/// Every Firebase call site must check this before use.
bool firebaseReady = false;

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
      builder: (context, child) => _FcmListener(
        router: ref.read(appRouterProvider),
        child: child!,
      ),
    );
  }
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
