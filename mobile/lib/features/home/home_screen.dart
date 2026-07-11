/// Home screen — matches §2 mockup: alert banner, overview metrics,
/// risk donut, top hotspot list — all from live /risk/overview.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart' hide LocationServiceDisabledException;
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
import 'package:go_router/go_router.dart';
import 'home_providers.dart';

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
      onRefresh: () async {
        ref.invalidate(personalRiskProvider);
        ref.invalidate(riskOverviewProvider);
        await ref.read(riskOverviewProvider.future);
      },
      color: AppColors.blue600,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        children: [
          // ── Personal risk card (top — user's current location) ──────────
          const _PersonalRiskCard(),
          const SizedBox(height: 16),

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

// ── Personal risk card ────────────────────────────────────────────────────────

class _PersonalRiskCard extends ConsumerWidget {
  const _PersonalRiskCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(personalRiskProvider);

    return async.when(
      loading: () => const _PersonalRiskSkeleton(),
      error: (err, _) {
        if (err is LocationPermissionDeniedException) {
          return _PersonalRiskPrompt(
            icon: Icons.location_off_outlined,
            title: 'See risk at your exact spot',
            message: err.permanent
                ? 'Location permission is turned off. Enable it in Settings.'
                : 'Share your location to see risk right where you are.',
            actionLabel: err.permanent ? 'Open settings' : 'Allow location',
            onAction: () async {
              if (err.permanent) {
                await Geolocator.openAppSettings();
              }
              ref.invalidate(personalRiskProvider);
            },
          );
        }
        if (err is LocationServiceDisabledException) {
          return _PersonalRiskPrompt(
            icon: Icons.gps_off_outlined,
            title: 'Turn on Location Services',
            message: 'Your device has location turned off. Enable it to see your personal risk.',
            actionLabel: 'Open settings',
            onAction: () async {
              await Geolocator.openLocationSettings();
              ref.invalidate(personalRiskProvider);
            },
          );
        }
        if (err is OutsideCoverageException) {
          return const _PersonalRiskInfo(
            icon: Icons.explore_off_outlined,
            title: 'Outside coverage',
            message: 'FloodGuard currently covers only the GHMC area (Hyderabad).',
          );
        }
        if (err is StaleForecastException) {
          return _PersonalRiskInfo(
            icon: Icons.satellite_alt_outlined,
            title: 'Waiting for live data',
            message: err.lastUpdate != null
                ? 'Feed last reported at ${err.lastUpdate!.toLocal().hour.toString().padLeft(2, "0")}:${err.lastUpdate!.toLocal().minute.toString().padLeft(2, "0")}.'
                : 'Weather feed has not started reporting yet.',
          );
        }
        return _PersonalRiskPrompt(
          icon: Icons.cloud_off_outlined,
          title: 'Couldn\'t load your risk',
          message: 'Something went wrong. Try again in a moment.',
          actionLabel: 'Retry',
          onAction: () => ref.invalidate(personalRiskProvider),
        );
      },
      data: (personal) => _PersonalRiskContent(
        personal: personal,
        onViewDetails: () {
          final h3 = personal.risk.h3Index;
          if (h3 == null) return;
          final uri = Uri(
            path: '/area/$h3',
            queryParameters: {
              'lat': personal.lat.toString(),
              'lng': personal.lng.toString(),
            },
          );
          context.push(uri.toString());
        },
      ),
    );
  }
}

class _PersonalRiskContent extends StatelessWidget {
  final PersonalRisk personal;
  final VoidCallback onViewDetails;

  const _PersonalRiskContent({
    required this.personal,
    required this.onViewDetails,
  });

  Color _tint(String level) {
    switch (level) {
      case 'SEVERE': return AppColors.riskSevere;
      case 'HIGH':   return AppColors.riskHigh;
      case 'MODERATE': return AppColors.riskModerate;
      default: return AppColors.riskLow;
    }
  }

  @override
  Widget build(BuildContext context) {
    final r = personal.risk;
    final tint = _tint(r.riskLevel);
    final locationLabel = personal.areaName?.isNotEmpty == true
        ? personal.areaName!
        : '${personal.lat.toStringAsFixed(3)}° N, ${personal.lng.toStringAsFixed(3)}° E';

    return FgCard(
      padding: EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Colored accent bar at top matches the risk level
          Container(height: 4, color: tint),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 34,
                      height: 34,
                      decoration: BoxDecoration(
                        color: tint.withAlpha(26),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(Icons.my_location, color: tint, size: 18),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'You are here',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w500,
                              color: AppColors.textMuted,
                            ),
                          ),
                          Text(
                            locationLabel,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w600,
                              color: AppColors.textPrimary,
                            ),
                          ),
                        ],
                      ),
                    ),
                    RiskBadge(level: r.riskLevel),
                  ],
                ),
                if (r.plainText.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Text(
                    r.plainText,
                    style: const TextStyle(
                      fontSize: 13,
                      color: AppColors.textPrimary,
                      height: 1.35,
                    ),
                  ),
                ],
                const SizedBox(height: 14),
                Row(
                  children: [
                    _MiniStat(
                      value: (r.rain1h ?? 0).toStringAsFixed(1),
                      unit: 'mm',
                      label: 'Rain 1h',
                      color: AppColors.blue600,
                    ),
                    _MiniStat(
                      value: '${r.confidence}',
                      unit: '%',
                      label: 'Confidence',
                      color: AppColors.riskLow,
                    ),
                    _MiniStat(
                      value: r.hourly.length.toString(),
                      unit: 'h',
                      label: 'Forecast',
                      color: AppColors.riskModerate,
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: r.h3Index == null ? null : onViewDetails,
                    icon: const Icon(Icons.arrow_forward, size: 16),
                    label: const Text('View area details'),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MiniStat extends StatelessWidget {
  final String value;
  final String unit;
  final String label;
  final Color color;

  const _MiniStat({
    required this.value,
    required this.unit,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          RichText(
            text: TextSpan(
              children: [
                TextSpan(
                  text: value,
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: color,
                  ),
                ),
                TextSpan(
                  text: unit,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w500,
                    color: color,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: const TextStyle(
              fontSize: 11,
              color: AppColors.textMuted,
            ),
          ),
        ],
      ),
    );
  }
}

class _PersonalRiskPrompt extends StatelessWidget {
  final IconData icon;
  final String title;
  final String message;
  final String actionLabel;
  final VoidCallback onAction;

  const _PersonalRiskPrompt({
    required this.icon,
    required this.title,
    required this.message,
    required this.actionLabel,
    required this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    return FgCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                width: 34, height: 34,
                decoration: BoxDecoration(
                  color: AppColors.blue600.withAlpha(26),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: AppColors.blue600, size: 18),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      message,
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppColors.textMuted,
                        height: 1.35,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: onAction,
              child: Text(actionLabel),
            ),
          ),
        ],
      ),
    );
  }
}

class _PersonalRiskInfo extends StatelessWidget {
  final IconData icon;
  final String title;
  final String message;

  const _PersonalRiskInfo({
    required this.icon,
    required this.title,
    required this.message,
  });

  @override
  Widget build(BuildContext context) {
    return FgCard(
      child: Row(
        children: [
          Container(
            width: 34, height: 34,
            decoration: BoxDecoration(
              color: AppColors.blue600.withAlpha(26),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: AppColors.blue600, size: 18),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  message,
                  style: const TextStyle(
                    fontSize: 12,
                    color: AppColors.textMuted,
                    height: 1.35,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _PersonalRiskSkeleton extends StatelessWidget {
  const _PersonalRiskSkeleton();

  @override
  Widget build(BuildContext context) {
    return FgCard(
      child: Row(
        children: const [
          SkeletonBox(width: 34, height: 34, radius: 10),
          SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SkeletonBox(width: 90, height: 10),
                SizedBox(height: 6),
                SkeletonBox(width: 180, height: 14),
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
