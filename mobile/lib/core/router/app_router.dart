import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Route paths
class AppRoutes {
  static const home = '/';
  static const map = '/map';
  static const radar = '/radar';
  static const alerts = '/alerts';
  static const report = '/report';
  static const settings = '/settings';
  static const areaDetail = '/area/:h3Index';
}

/// App router provider (Riverpod)
final appRouterProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: AppRoutes.home,
    debugLogDiagnostics: true,
    routes: [
      ShellRoute(
        builder: (context, state, child) => _ShellScaffold(child: child),
        routes: [
          GoRoute(
            path: AppRoutes.home,
            name: 'home',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: _PlaceholderScreen(title: 'Home', icon: Icons.home),
            ),
          ),
          GoRoute(
            path: AppRoutes.map,
            name: 'map',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: _PlaceholderScreen(title: 'Risk Map', icon: Icons.map),
            ),
          ),
          GoRoute(
            path: AppRoutes.radar,
            name: 'radar',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: _PlaceholderScreen(title: 'Live Radar', icon: Icons.radar),
            ),
          ),
          GoRoute(
            path: AppRoutes.alerts,
            name: 'alerts',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: _PlaceholderScreen(title: 'Alerts', icon: Icons.notifications),
            ),
          ),
          GoRoute(
            path: AppRoutes.report,
            name: 'report',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: _PlaceholderScreen(title: 'Report Flood', icon: Icons.report),
            ),
          ),
        ],
      ),
    ],
  );
});

/// Bottom navigation shell (5 tabs per spec)
class _ShellScaffold extends StatelessWidget {
  final Widget child;
  const _ShellScaffold({required this.child});

  static const _tabs = [
    (path: AppRoutes.home, label: 'Home', icon: Icons.home_outlined, activeIcon: Icons.home),
    (path: AppRoutes.map, label: 'Map', icon: Icons.map_outlined, activeIcon: Icons.map),
    (path: AppRoutes.radar, label: 'Live Radar', icon: Icons.radar_outlined, activeIcon: Icons.radar),
    (path: AppRoutes.alerts, label: 'Alerts', icon: Icons.notifications_outlined, activeIcon: Icons.notifications),
    (path: AppRoutes.report, label: 'Report', icon: Icons.add_circle_outline, activeIcon: Icons.add_circle),
  ];

  int _selectedIndex(BuildContext context) {
    final location = GoRouterState.of(context).matchedLocation;
    final idx = _tabs.indexWhere((t) => t.path == location);
    return idx < 0 ? 0 : idx;
  }

  @override
  Widget build(BuildContext context) {
    final selectedIndex = _selectedIndex(context);
    final theme = Theme.of(context);

    return Scaffold(
      body: child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: selectedIndex,
        onDestinationSelected: (i) => context.go(_tabs[i].path),
        destinations: _tabs.map((tab) => NavigationDestination(
          icon: Icon(tab.icon),
          selectedIcon: Icon(tab.activeIcon, color: theme.colorScheme.primary),
          label: tab.label,
        )).toList(),
      ),
    );
  }
}

/// Placeholder screen for Phase 0 — replaced in Phases 5–9
class _PlaceholderScreen extends StatelessWidget {
  final String title;
  final IconData icon;
  const _PlaceholderScreen({required this.title, required this.icon});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            Icon(Icons.shield, color: Colors.white),
            SizedBox(width: 8),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('FloodGuard',
                    style: TextStyle(
                        color: Colors.white, fontWeight: FontWeight.bold, fontSize: 17)),
                Text('Hyderabad Flood Alert',
                    style: TextStyle(color: Colors.white70, fontSize: 11)),
              ],
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined, color: Colors.white),
            onPressed: () {},
          ),
        ],
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 80, color: theme.colorScheme.primary.withOpacity(0.4)),
            const SizedBox(height: 16),
            Text(title,
                style: theme.textTheme.headlineSmall
                    ?.copyWith(color: theme.colorScheme.onSurface)),
            const SizedBox(height: 8),
            Text('Phase 5–9 implementation',
                style: theme.textTheme.bodyMedium
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
          ],
        ),
      ),
    );
  }
}
