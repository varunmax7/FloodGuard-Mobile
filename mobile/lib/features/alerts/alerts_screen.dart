/// Alerts screen — Active / History tabs with alert cards.
library;

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/providers/alerts_providers.dart';
import '../../data/models/alert_event.dart';
import '../../design/theme/app_theme.dart';
import '../../design/widgets/fg_card.dart';
import '../../design/widgets/fg_app_header.dart';
import '../../design/widgets/risk_dot.dart';
import '../../design/widgets/skeleton_loader.dart';

final dismissedAlertsProvider = StateProvider<Set<String>>((ref) => {});

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
        data: (alerts) {
          final dismissed = ref.watch(dismissedAlertsProvider);
          final visibleAlerts = scope == 'active' 
              ? alerts.where((a) => !dismissed.contains(a.id)).toList()
              : alerts;

          return visibleAlerts.isEmpty
            ? _EmptyView(scope: scope)
            : ListView.separated(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
                itemCount: visibleAlerts.length,
                separatorBuilder: (_, __) => const SizedBox(height: 10),
                itemBuilder: (ctx, i) => AlertCard(
                  alert: visibleAlerts[i],
                  highlighted: visibleAlerts[i].h3Index == focusH3,
                  onDismiss: scope == 'active'
                      ? () => ref.read(dismissedAlertsProvider.notifier).update((s) => {...s, visibleAlerts[i].id})
                      : null,
                ),
              );
        },
      ),
    );
  }
}

// ── Alert card ────────────────────────────────────────────────────────────────

class AlertCard extends StatelessWidget {
  final AlertEvent alert;
  final bool highlighted;
  final VoidCallback? onDismiss;

  const AlertCard({super.key, required this.alert, this.highlighted = false, this.onDismiss});

  @override
  Widget build(BuildContext context) {
    return alert.isReport
        ? _ReportAlertCard(alert: alert, highlighted: highlighted, onDismiss: onDismiss)
        : _RiskAlertCard(alert: alert, highlighted: highlighted, onDismiss: onDismiss);
  }
}

// ── Risk-engine alert card (existing style) ───────────────────────────────────

class _RiskAlertCard extends StatelessWidget {
  final AlertEvent alert;
  final bool highlighted;
  final VoidCallback? onDismiss;
  const _RiskAlertCard({required this.alert, required this.highlighted, this.onDismiss});

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
                        if (onDismiss != null) ...[
                          const SizedBox(width: 8),
                          GestureDetector(
                            onTap: onDismiss,
                            child: const Icon(Icons.close, size: 16, color: AppColors.textMuted),
                          ),
                        ],
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

// ── Verified-report alert card (new, with photo) ──────────────────────────────

class _ReportAlertCard extends StatelessWidget {
  final AlertEvent alert;
  final bool highlighted;
  final VoidCallback? onDismiss;
  const _ReportAlertCard({required this.alert, required this.highlighted, this.onDismiss});

  @override
  Widget build(BuildContext context) {
    final accentColor = riskColor(alert.riskLevel);

    return FgCard(
      padding: EdgeInsets.zero,
      color: highlighted ? accentColor.withAlpha(15) : AppColors.white,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Photo (full width, if available) ────────────────────────────
          if (alert.photoUrl != null && alert.photoUrl!.isNotEmpty)
            ClipRRect(
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(16),
                topRight: Radius.circular(16),
              ),
              child: CachedNetworkImage(
                imageUrl: alert.photoUrl!,
                height: 160,
                width: double.infinity,
                fit: BoxFit.cover,
                placeholder: (_, __) => Container(
                  height: 160,
                  color: const Color(0xFFF1F5F9),
                  child: const Center(
                    child: Icon(Icons.image_outlined,
                        size: 32, color: AppColors.textMuted),
                  ),
                ),
                errorWidget: (_, __, ___) => const SizedBox.shrink(),
              ),
            ),

          // ── Body ─────────────────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header row
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 7, vertical: 3),
                      decoration: BoxDecoration(
                        color: accentColor.withAlpha(20),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.verified_outlined,
                              size: 12, color: accentColor),
                          const SizedBox(width: 4),
                          Text(
                            'Verified Report',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: accentColor,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Spacer(),
                    RiskBadge(level: alert.riskLevel),
                    if (onDismiss != null) ...[
                      const SizedBox(width: 8),
                      GestureDetector(
                        onTap: onDismiss,
                        child: const Icon(Icons.close, size: 16, color: AppColors.textMuted),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 8),

                // Location
                Row(
                  children: [
                    const Icon(Icons.location_on_outlined,
                        size: 14, color: AppColors.textMuted),
                    const SizedBox(width: 4),
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
                  ],
                ),
                const SizedBox(height: 6),

                // Depth + Road chips
                if (alert.depth != null || alert.road != null)
                  Wrap(
                    spacing: 6,
                    children: [
                      if (alert.depth != null)
                        _InfoChip(
                          icon: Icons.water_outlined,
                          label: alert.depthLabel,
                          color: accentColor,
                        ),
                      if (alert.road != null)
                        _InfoChip(
                          icon: Icons.directions_car_outlined,
                          label: alert.roadLabel,
                          color: alert.road == 'BLOCKED'
                              ? AppColors.riskSevere
                              : alert.road == 'DIFFICULT'
                                  ? const Color(0xFFF59E0B)
                                  : AppColors.textMuted,
                        ),
                    ],
                  ),
                const SizedBox(height: 8),

                // Footer
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
        ],
      ),
    );
  }
}

class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  const _InfoChip(
      {required this.icon, required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withAlpha(15),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withAlpha(40)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: color),
          const SizedBox(width: 4),
          Text(label,
              style: TextStyle(
                  fontSize: 11, color: color, fontWeight: FontWeight.w500)),
        ],
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
