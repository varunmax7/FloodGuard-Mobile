/// Alerts screen — Active / History tabs with alert cards.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/providers/alerts_providers.dart';
import '../../data/models/alert_event.dart';
import '../../design/theme/app_theme.dart';
import '../../design/widgets/fg_card.dart';
import '../../design/widgets/fg_app_header.dart';
import '../../design/widgets/fg_card.dart';
import '../../design/widgets/risk_dot.dart';
import '../../design/widgets/skeleton_loader.dart';

class AlertsScreen extends ConsumerWidget {
  final String? focusH3;
  const AlertsScreen({super.key, this.focusH3});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: const FgAppHeader(
          bottom: TabBar(
            tabs: [
              Tab(text: 'Active'),
              Tab(text: 'History'),
            ],
            labelColor: Colors.white,
            unselectedLabelColor: Color(0x99FFFFFF),
            indicatorColor: Colors.white,
            indicatorWeight: 2,
          ),
        ),
        backgroundColor: const Color(0xFFF1F5F9),
        body: TabBarView(
          children: [
            _AlertsList(scope: 'active', focusH3: focusH3, ref: ref),
            _AlertsList(scope: 'history', ref: ref),
          ],
        ),
      ),
    );
  }
}

// ── Alerts list ───────────────────────────────────────────────────────────────

class _AlertsList extends ConsumerWidget {
  final String scope;
  final String? focusH3;
  final WidgetRef ref;

  const _AlertsList({required this.scope, this.focusH3, required this.ref});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);

    // Not signed in — skip API call, show prompt instead.
    if (!auth.isLoggedIn) {
      return const _SignInPrompt();
    }

    final alertsAsync = ref.watch(alertsProvider(scope));

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(alertsProvider(scope));
        await ref.read(alertsProvider(scope).future).catchError((_) {});
      },
      color: AppColors.blue600,
      child: alertsAsync.when(
        loading: () => _LoadingView(),
        error: (e, _) => _ErrorView(
          onRetry: () => ref.invalidate(alertsProvider(scope)),
        ),
        data: (alerts) => alerts.isEmpty
            ? _EmptyView(scope: scope)
            : ListView.separated(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
                itemCount: alerts.length,
                separatorBuilder: (_, __) => const SizedBox(height: 10),
                itemBuilder: (ctx, i) => AlertCard(
                  alert: alerts[i],
                  highlighted: alerts[i].h3Index == focusH3,
                ),
              ),
      ),
    );
  }
}

// ── Alert card ────────────────────────────────────────────────────────────────

class AlertCard extends StatelessWidget {
  final AlertEvent alert;
  final bool highlighted;

  const AlertCard({super.key, required this.alert, this.highlighted = false});

  @override
  Widget build(BuildContext context) {
    final bg = alert.isSevere ? AppColors.severeBg : AppColors.white;
    final accentColor = riskColor(alert.riskLevel);

    return FgCard(
      color: highlighted ? accentColor.withAlpha(15) : bg,
      padding: EdgeInsets.zero,
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Left risk-colour bar
            Container(
              width: 4,
              decoration: BoxDecoration(
                color: accentColor,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(16),
                  bottomLeft: Radius.circular(16),
                ),
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 14, 14, 14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.warning_amber_rounded,
                            size: 16, color: accentColor),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            alert.areaLabel,
                            style: const TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                              color: AppColors.textPrimary,
                            ),
                          ),
                        ),
                        RiskBadge(level: alert.riskLevel),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      alert.message,
                      style: const TextStyle(
                          fontSize: 13, color: AppColors.textPrimary),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        const Icon(Icons.access_time,
                            size: 12, color: AppColors.textMuted),
                        const SizedBox(width: 4),
                        Text(
                          alert.timeAgo,
                          style: const TextStyle(
                              fontSize: 12, color: AppColors.textMuted),
                        ),
                        const Spacer(),
                        if (alert.h3Index != null)
                          _ViewDetailButton(alert: alert),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ViewDetailButton extends StatelessWidget {
  final AlertEvent alert;
  const _ViewDetailButton({required this.alert});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
        final lat = 17.3850, lng = 78.4867; // fallback — replace with hex centroid
        final uri = Uri(
          path: '/area/${alert.h3Index}',
          queryParameters: {'lat': lat.toString(), 'lng': lng.toString()},
        );
        context.push(uri.toString());
      },
      child: const Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('View detail',
              style: TextStyle(
                  fontSize: 12,
                  color: AppColors.blue600,
                  fontWeight: FontWeight.w500)),
          SizedBox(width: 2),
          Icon(Icons.chevron_right, size: 14, color: AppColors.blue600),
        ],
      ),
    );
  }
}

// ── States ────────────────────────────────────────────────────────────────────

class _SignInPrompt extends StatelessWidget {
  const _SignInPrompt();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: FgCard(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.notifications_none_outlined,
                  size: 48, color: AppColors.textMuted),
              const SizedBox(height: 16),
              const Text(
                'Sign in to see alerts',
                style: TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary),
              ),
              const SizedBox(height: 8),
              const Text(
                'Flood alerts are sent to your saved places.\nSign in to set them up.',
                style: TextStyle(fontSize: 14, color: AppColors.textMuted),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 20),
              FilledButton.icon(
                onPressed: () => context.push('/settings'),
                icon: const Icon(Icons.person_outline, size: 18),
                label: const Text('Go to Settings'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _LoadingView extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: 4,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (_, __) =>
          const SkeletonBox(width: double.infinity, height: 90),
    );
  }
}

class _EmptyView extends StatelessWidget {
  final String scope;
  const _EmptyView({required this.scope});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.notifications_none_outlined,
                size: 56, color: AppColors.textMuted),
            const SizedBox(height: 16),
            Text(
              scope == 'active'
                  ? 'No active alerts'
                  : 'No alert history yet',
              style: const TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary),
            ),
            const SizedBox(height: 8),
            const Text(
              'Alerts appear here when flood risk rises\nat your saved places.',
              style: TextStyle(fontSize: 14, color: AppColors.textMuted),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final VoidCallback onRetry;
  const _ErrorView({required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.cloud_off_outlined,
              size: 40, color: AppColors.textMuted),
          const SizedBox(height: 12),
          const Text('Could not load alerts',
              style:
                  TextStyle(fontSize: 15, color: AppColors.textMuted)),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh, size: 16),
            label: const Text('Retry'),
          ),
        ],
      ),
    );
  }
}
