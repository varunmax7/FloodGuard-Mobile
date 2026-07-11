/// Home screen — matches §2 mockup: alert banner, overview metrics,
/// risk donut, top hotspot list — all from live /risk/overview.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/providers/api_providers.dart';
import '../../data/api/exceptions.dart';
import '../../data/models/risk_overview.dart';
import '../../design/theme/app_theme.dart';
import '../../design/widgets/alert_banner.dart';
import '../../design/widgets/fg_app_header.dart';
import '../../design/widgets/fg_card.dart';
import '../../design/widgets/risk_dot.dart';
import '../../design/widgets/risk_donut.dart';
import '../../design/widgets/skeleton_loader.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final overviewAsync = ref.watch(riskOverviewProvider);

    return Scaffold(
      appBar: const FgAppHeader(),
      backgroundColor: const Color(0xFFF1F5F9),
      body: overviewAsync.when(
        loading: () => const HomeSkeletonView(),
        error: (err, _) => err is StaleForecastException
            ? _NoLiveDataView(
                lastUpdate: err.lastUpdate,
                onRetry: () => ref.invalidate(riskOverviewProvider),
              )
            : _ErrorView(
                message: err.toString(),
                onRetry: () => ref.invalidate(riskOverviewProvider),
              ),
        data: (overview) => _HomeContent(overview: overview, ref: ref),
      ),
    );
  }
}

class _HomeContent extends StatelessWidget {
  final RiskOverview overview;
  final WidgetRef ref;

  const _HomeContent({required this.overview, required this.ref});

  @override
  Widget build(BuildContext context) {
    final highRiskHotspots = overview.hotspots
        .where((h) => h.riskLevel == 'HIGH' || h.riskLevel == 'SEVERE')
        .toList();

    return RefreshIndicator(
      onRefresh: () => ref.refresh(riskOverviewProvider.future),
      color: AppColors.blue600,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        children: [
          // ── Alert banner ────────────────────────────────────────────────
          if (highRiskHotspots.isNotEmpty) ...[
            AlertBanner(hotspots: highRiskHotspots),
            const SizedBox(height: 16),
          ],

          // ── Today's Overview ─────────────────────────────────────────────
          _SectionLabel("Today's Overview"),
          const SizedBox(height: 8),
          FgCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    _MetricChip(
                      value: '${overview.forecastRain24h.toStringAsFixed(0)}mm',
                      label: 'Forecast 24h',
                      icon: Icons.water_drop_outlined,
                      color: AppColors.blue600,
                    ),
                    const SizedBox(width: 12),
                    _MetricChip(
                      value: '${overview.maxRate1h.toStringAsFixed(1)}mm/h',
                      label: 'Max Rate 1h',
                      icon: Icons.speed_outlined,
                      color: AppColors.riskHigh,
                    ),
                    const SizedBox(width: 12),
                    _MetricChip(
                      value: '${overview.confidence}%',
                      label: 'Confidence',
                      icon: Icons.analytics_outlined,
                      color: AppColors.riskLow,
                    ),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // ── Risk Distribution ─────────────────────────────────────────────
          _SectionLabel('Risk Distribution'),
          const SizedBox(height: 8),
          FgCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${overview.totalHexes} hex cells · GHMC coverage',
                  style: const TextStyle(
                    fontSize: 12,
                    color: AppColors.textMuted,
                    fontWeight: FontWeight.w400,
                  ),
                ),
                const SizedBox(height: 16),
                RiskDonut(summary: overview.summary),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // ── Top High Risk Areas ───────────────────────────────────────────
          _SectionLabel('Top High Risk Areas'),
          const SizedBox(height: 8),
          FgCard(
            padding: EdgeInsets.zero,
            child: overview.hotspots.isEmpty
                ? const _EmptyHotspots()
                : Column(
                    children: [
                      for (int i = 0; i < overview.hotspots.length; i++) ...[
                        _HotspotRow(
                          hotspot: overview.hotspots[i],
                          rank: i + 1,
                        ),
                        if (i < overview.hotspots.length - 1)
                          const Divider(height: 1, indent: 56),
                      ],
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

// ── Sub-widgets ───────────────────────────────────────────────────────────────

class _SectionLabel extends StatelessWidget {
  final String text;
  const _SectionLabel(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(
        fontSize: 17,
        fontWeight: FontWeight.w600,
        color: AppColors.textPrimary,
      ),
    );
  }
}

class _MetricChip extends StatelessWidget {
  final String value;
  final String label;
  final IconData icon;
  final Color color;

  const _MetricChip({
    required this.value,
    required this.label,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: color.withAlpha(26),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: color, size: 18),
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: const TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w400,
              color: AppColors.textMuted,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

class _HotspotRow extends StatelessWidget {
  final Hotspot hotspot;
  final int rank;

  const _HotspotRow({required this.hotspot, required this.rank});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              color: const Color(0xFFF1F5F9),
              borderRadius: BorderRadius.circular(8),
            ),
            alignment: Alignment.center,
            child: Text(
              '#$rank',
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: AppColors.textMuted,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  hotspot.wardName?.isNotEmpty == true
                      ? hotspot.wardName!
                      : hotspot.h3Index.substring(0, 10),
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                    color: AppColors.textPrimary,
                  ),
                ),
                if (hotspot.rain1h != null) ...[
                  const SizedBox(height: 2),
                  Text(
                    '${hotspot.rain1h!.toStringAsFixed(1)} mm/h',
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppColors.textMuted,
                    ),
                  ),
                ],
              ],
            ),
          ),
          RiskBadge(level: hotspot.riskLevel),
        ],
      ),
    );
  }
}

class _EmptyHotspots extends StatelessWidget {
  const _EmptyHotspots();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.all(24),
      child: Center(
        child: Column(
          children: [
            Icon(Icons.check_circle_outline,
                color: AppColors.riskLow, size: 36),
            SizedBox(height: 8),
            Text(
              'No high risk areas currently',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w500,
                color: AppColors.textMuted,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NoLiveDataView extends StatelessWidget {
  final DateTime? lastUpdate;
  final VoidCallback onRetry;

  const _NoLiveDataView({required this.lastUpdate, required this.onRetry});

  String _formatLastUpdate(DateTime ts) {
    final local = ts.toLocal();
    final diff = DateTime.now().difference(local);
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes} min ago';
    if (diff.inHours < 24) return '${diff.inHours} h ago';
    return '${diff.inDays} d ago';
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.satellite_alt_outlined,
                size: 56, color: AppColors.blue600),
            const SizedBox(height: 16),
            const Text(
              'No live data yet',
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              lastUpdate != null
                  ? 'Weather feed last reported ${_formatLastUpdate(lastUpdate!)}. Waiting for the next update.'
                  : 'The weather feed has not started reporting yet.',
              style: const TextStyle(fontSize: 14, color: AppColors.textMuted),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Check again'),
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _ErrorView({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.cloud_off_outlined,
                size: 56, color: AppColors.textMuted),
            const SizedBox(height: 16),
            const Text(
              'Unable to load risk data',
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Check your connection and try again.',
              style: const TextStyle(fontSize: 14, color: AppColors.textMuted),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}
