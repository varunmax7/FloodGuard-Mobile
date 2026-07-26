/// go_router — 5-tab shell + sub-routes.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../config/app_config.dart';
import '../../design/theme/app_theme.dart';
import '../../features/alerts/alerts_screen.dart';
import '../../features/area_detail/area_detail_screen.dart';
import '../../features/auth/auth_screen.dart';
import '../../features/home/home_screen.dart';
import '../../features/map/map_screen.dart';
import '../../features/radar/radar_screen.dart';
import '../../features/report/report_screen.dart';
import '../../features/settings/settings_screen.dart';

class AppRoutes {
  static const home = '/';
  static const map = '/map';
  static const radar = '/radar';
  static const alerts = '/alerts';
  static const report = '/report';
  static const settings = '/settings';
  static const auth = '/auth';
  static const areaDetail = '/area/:h3Index';
  static const reportsNearby = '/reports/nearby';
}

final appRouterProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: AppRoutes.home,
    debugLogDiagnostics: false,
    routes: [
      ShellRoute(
        builder: (context, state, child) => _ShellScaffold(child: child),
        routes: [
          GoRoute(
            path: AppRoutes.home,
            name: 'home',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: HomeScreen(),
            ),
          ),
          GoRoute(
            path: AppRoutes.map,
            name: 'map',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: RiskMapScreen(),
            ),
          ),
          GoRoute(
            path: AppRoutes.radar,
            name: 'radar',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: RadarScreen(),
            ),
          ),
          GoRoute(
            path: AppRoutes.alerts,
            name: 'alerts',
            pageBuilder: (context, state) => NoTransitionPage(
              child: AlertsScreen(
                focusH3: state.uri.queryParameters['focus'],
              ),
            ),
          ),
          GoRoute(
            path: AppRoutes.report,
            name: 'report',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: ReportScreen(),
            ),
          ),
        ],
      ),
      // Full-screen sub-routes (outside bottom-nav shell)
      GoRoute(
        path: AppRoutes.settings,
        name: 'settings',
        builder: (context, state) => const SettingsScreen(),
      ),
      GoRoute(
        path: AppRoutes.auth,
        name: 'auth',
        builder: (context, state) => const AuthScreen(),
      ),
      GoRoute(
        path: AppRoutes.areaDetail,
        name: 'areaDetail',
        builder: (context, state) {
          final h3 = state.pathParameters['h3Index'] ?? '';
          final lat =
              double.tryParse(state.uri.queryParameters['lat'] ?? '') ??
                  AppConfig.regionLatitude;
          final lng =
              double.tryParse(state.uri.queryParameters['lng'] ?? '') ??
                  AppConfig.regionLongitude;
          return AreaDetailScreen(h3Index: h3, lat: lat, lng: lng);
        },
      ),
      GoRoute(
        path: AppRoutes.reportsNearby,
        name: 'reportsNearby',
        builder: (context, state) =>
            const _FullScreenPlaceholder(title: 'Nearby Reports'),
      ),
    ],
  );
});

// ── Bottom nav shell ──────────────────────────────────────────────────────────

class _ShellScaffold extends StatelessWidget {
  final Widget child;
  const _ShellScaffold({required this.child});

  static const _tabs = [
    (path: AppRoutes.home,   label: 'Home',       icon: Icons.home_outlined,          active: Icons.home),
    (path: AppRoutes.map,    label: 'Map',         icon: Icons.map_outlined,            active: Icons.map),
    (path: AppRoutes.radar,  label: 'Live Radar',  icon: Icons.radar_outlined,          active: Icons.radar),
    (path: AppRoutes.alerts, label: 'Alerts',      icon: Icons.notifications_outlined,  active: Icons.notifications),
    (path: AppRoutes.report, label: 'Report',      icon: Icons.add_circle_outline,      active: Icons.add_circle),
  ];

  int _selectedIndex(BuildContext context) {
    final loc = GoRouterState.of(context).matchedLocation;
    final idx = _tabs.indexWhere((t) => t.path == loc);
    return idx < 0 ? 0 : idx;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex(context),
        onDestinationSelected: (i) => context.go(_tabs[i].path),
        destinations: _tabs
            .map((t) => NavigationDestination(
                  icon: Icon(t.icon),
                  selectedIcon: Icon(t.active, color: AppColors.blue600),
                  label: t.label,
                ))
            .toList(),
      ),
    );
  }
}

class _FullScreenPlaceholder extends StatelessWidget {
  final String title;
  const _FullScreenPlaceholder({required this.title});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: const Center(child: Text('Coming soon')),
    );
  }
}
