/// Area Detail screen — current risk, 24h hourly strip, explanation,
/// and nearby reports with 1h/6h/24h time filter.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/models/flood_report.dart';
import '../../data/models/risk_location.dart';
import '../../design/theme/app_theme.dart';
import '../../design/widgets/fg_card.dart';
import '../../design/widgets/hourly_risk_strip.dart';
import '../../design/widgets/report_card.dart';
import '../../design/widgets/risk_dot.dart';
import '../../design/widgets/skeleton_loader.dart';
import 'area_detail_providers.dart';

class AreaDetailScreen extends ConsumerStatefulWidget {
  final String h3Index;
  final double lat;
  final double lng;

  const AreaDetailScreen({
    super.key,
    required this.h3Index,
    required this.lat,
    required this.lng,
  });

  @override
  ConsumerState<AreaDetailScreen> createState() => _AreaDetailScreenState();
}

class _AreaDetailScreenState extends ConsumerState<AreaDetailScreen> {
  int _sinceMin = 60;

  (double, double) get _coords => (widget.lat, widget.lng);

  ({double lat, double lng, int sinceMin}) get _reportsArgs =>
      (lat: widget.lat, lng: widget.lng, sinceMin: _sinceMin);

  Future<void> _refresh() async {
    ref.invalidate(riskLocationDataProvider(_coords));
    ref.invalidate(nearbyReportsProvider(_reportsArgs));
    try {
      await Future.wait([
        ref.read(riskLocationDataProvider(_coords).future),
        ref.read(nearbyReportsProvider(_reportsArgs).future),
      ]);
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final locationAsync = ref.watch(riskLocationDataProvider(_coords));
    final reportsAsync = ref.watch(nearbyReportsProvider(_reportsArgs));

    final areaName = locationAsync.value?.wardName?.isNotEmpty == true
        ? locationAsync.value!.wardName!
        : '${widget.h3Index.substring(0, 10)}…';

    return Scaffold(
      backgroundColor: const Color(0xFFF1F5F9),
      appBar: AppBar(
        backgroundColor: AppColors.navyDark,
        foregroundColor: Colors.white,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              areaName,
              style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: Colors.white),
            ),
            const Text(
              'Area Detail',
              style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w400,
                  color: Color(0xB3FFFFFF)),
            ),
          ],
        ),
        actions: [
          if (locationAsync.value != null)
            Padding(
              padding: const EdgeInsets.only(right: 16),
              child:
                  Center(child: RiskBadge(level: locationAsync.value!.riskLevel)),
            ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        color: AppColors.blue600,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
          children: [
            // ── Risk overview card ────────────────────────────────────────────
            locationAsync.when(
              loading: () => const _RiskCardSkeleton(),
              error: (e, _) => _ErrorCard(
                message: 'Failed to load risk data',
                onRetry: () =>
                    ref.invalidate(riskLocationDataProvider(_coords)),
              ),
              data: (data) => _RiskOverviewCard(data: data),
            ),

            const SizedBox(height: 20),

            // ── Nearby reports header ─────────────────────────────────────────
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                const Expanded(
                  child: Text(
                    'Nearby Reports',
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ),
                _TimeToggle(
                  selected: _sinceMin,
                  onChanged: (v) {
                    if (v == _sinceMin) return;
                    setState(() => _sinceMin = v);
                  },
                ),
              ],
            ),
            const SizedBox(height: 8),

            // ── Nearby reports list ───────────────────────────────────────────
            reportsAsync.when(
              loading: () => const _ReportsLoadingView(),
              error: (e, _) => _ErrorCard(
                message: 'Failed to load nearby reports',
                onRetry: () =>
                    ref.invalidate(nearbyReportsProvider(_reportsArgs)),
              ),
              data: (reports) => reports.isEmpty
                  ? const _EmptyReportsView()
                  : _ReportsList(reports: reports),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Risk overview card ─────────────────────────────────────────────────────────

class _RiskOverviewCard extends StatelessWidget {
  final RiskLocationData data;
  const _RiskOverviewCard({required this.data});

  @override
  Widget build(BuildContext context) {
    return FgCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Current risk row
          Row(
            children: [
              RiskBadge(level: data.riskLevel),
              const SizedBox(width: 10),
              if (data.rain1h != null)
                Text(
                  '${data.rain1h!.toStringAsFixed(1)} mm/h',
                  style: const TextStyle(
                      fontSize: 13, color: AppColors.textMuted),
                ),
              const Spacer(),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.blue600.withAlpha(20),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  '${data.confidence}% confidence',
                  style: const TextStyle(
                      fontSize: 11, color: AppColors.blue600),
                ),
              ),
            ],
          ),

          // Explanation line
          if (data.explanation.isNotEmpty) ...[
            const SizedBox(height: 12),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.info_outline,
                    size: 15, color: AppColors.blue600),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    data.explanation,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ),
              ],
            ),
          ],

          // 24h strip
          const SizedBox(height: 16),
          const Text(
            '24-Hour Forecast',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppColors.textMuted,
              letterSpacing: 0.4,
            ),
          ),
          const SizedBox(height: 8),
          HourlyRiskStrip(hourly: data.hourly),
          const SizedBox(height: 10),
          const HourlyStripLegend(),
        ],
      ),
    );
  }
}

// ── Time toggle ────────────────────────────────────────────────────────────────

class _TimeToggle extends StatelessWidget {
  final int selected;
  final ValueChanged<int> onChanged;

  const _TimeToggle({required this.selected, required this.onChanged});

  static const _options = [
    (label: '1h', value: 60),
    (label: '6h', value: 360),
    (label: '24h', value: 1440),
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(2),
      decoration: BoxDecoration(
        color: const Color(0xFFE2E8F0),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: _options.map((opt) {
          final isSelected = selected == opt.value;
          return GestureDetector(
            onTap: () => onChanged(opt.value),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 150),
              padding:
                  const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: isSelected ? AppColors.blue600 : Colors.transparent,
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                opt.label,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: isSelected ? Colors.white : AppColors.textMuted,
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}

// ── Reports list ───────────────────────────────────────────────────────────────

class _ReportsList extends StatelessWidget {
  final List<FloodReport> reports;
  const _ReportsList({required this.reports});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        for (int i = 0; i < reports.length; i++) ...[
          ReportCard(report: reports[i]),
          if (i < reports.length - 1) const SizedBox(height: 10),
        ],
      ],
    );
  }
}

// ── Loading / empty / error states ────────────────────────────────────────────

class _RiskCardSkeleton extends StatelessWidget {
  const _RiskCardSkeleton();

  @override
  Widget build(BuildContext context) {
    return FgCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const SkeletonBox(width: 82, height: 28, radius: 100),
              const SizedBox(width: 12),
              const SkeletonBox(width: 60, height: 14),
              const Spacer(),
              const SkeletonBox(width: 96, height: 26, radius: 6),
            ],
          ),
          const SizedBox(height: 12),
          const SkeletonBox(width: double.infinity, height: 14),
          const SizedBox(height: 6),
          const SkeletonBox(width: 200, height: 14),
          const SizedBox(height: 16),
          const SkeletonBox(width: 120, height: 12),
          const SizedBox(height: 8),
          const SkeletonBox(width: double.infinity, height: 58),
        ],
      ),
    );
  }
}

class _ReportsLoadingView extends StatelessWidget {
  const _ReportsLoadingView();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: List.generate(
        3,
        (i) => Padding(
          padding: EdgeInsets.only(bottom: i < 2 ? 10 : 0),
          child: FgCard(
            padding: EdgeInsets.zero,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SkeletonBox(width: 72, height: 72, radius: 0),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(12, 13, 14, 13),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: const [
                            SkeletonBox(width: 80, height: 22, radius: 6),
                            SizedBox(width: 8),
                            SkeletonBox(width: 80, height: 22, radius: 6),
                          ],
                        ),
                        const SizedBox(height: 8),
                        const SkeletonBox(width: 100, height: 12),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _EmptyReportsView extends StatelessWidget {
  const _EmptyReportsView();

  @override
  Widget build(BuildContext context) {
    return FgCard(
      child: Column(
        children: [
          Icon(Icons.search_off_outlined,
              size: 40,
              color: AppColors.textMuted.withAlpha(128)),
          const SizedBox(height: 12),
          const Text(
            'No reports nearby',
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w600,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'No flood reports found within 1 km in this time window.',
            style: TextStyle(fontSize: 13, color: AppColors.textMuted),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _ErrorCard({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return FgCard(
      child: Column(
        children: [
          const Icon(Icons.cloud_off_outlined,
              size: 36, color: AppColors.textMuted),
          const SizedBox(height: 8),
          Text(
            message,
            style:
                const TextStyle(fontSize: 14, color: AppColors.textMuted),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh, size: 16),
            label: const Text('Retry'),
          ),
        ],
      ),
    );
  }
}
