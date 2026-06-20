/// ReportCard — photo thumbnail + depth category + road status + time-ago.
library;

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import 'fg_card.dart';
import '../../data/models/flood_report.dart';

class ReportCard extends StatelessWidget {
  final FloodReport report;

  const ReportCard({super.key, required this.report});

  @override
  Widget build(BuildContext context) {
    return FgCard(
      padding: EdgeInsets.zero,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _PhotoThumbnail(url: report.photoUrl),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 13, 14, 13),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Wrap(
                    spacing: 6,
                    runSpacing: 4,
                    children: [
                      _InfoChip(
                        icon: Icons.water_outlined,
                        label: report.depthLabel,
                        color: AppColors.blue600,
                      ),
                      _InfoChip(
                        icon: Icons.directions_car_outlined,
                        label: report.roadLabel,
                        color: _roadColor(report.road),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      const Icon(Icons.access_time,
                          size: 12, color: AppColors.textMuted),
                      const SizedBox(width: 4),
                      Text(
                        report.timeAgo ?? _timeAgo(report.observedAt),
                        style: const TextStyle(
                            fontSize: 12, color: AppColors.textMuted),
                      ),
                      const Spacer(),
                      if (report.status == 'VERIFIED')
                        const Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.verified_outlined,
                                size: 12, color: AppColors.riskLow),
                            SizedBox(width: 3),
                            Text(
                              'Verified',
                              style: TextStyle(
                                  fontSize: 11, color: AppColors.riskLow),
                            ),
                          ],
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Color _roadColor(String road) => switch (road) {
        'BLOCKED' => AppColors.riskSevere,
        'DIFFICULT' => AppColors.riskHigh,
        _ => AppColors.riskLow,
      };
}

String _timeAgo(String? iso) {
  if (iso == null || iso.isEmpty) return '';
  try {
    final diff = DateTime.now().difference(DateTime.parse(iso));
    if (diff.inMinutes < 2) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  } catch (_) {
    return '';
  }
}

class _PhotoThumbnail extends StatelessWidget {
  final String? url;
  const _PhotoThumbnail({this.url});

  static const _borderRadius = BorderRadius.only(
    topLeft: Radius.circular(16),
    bottomLeft: Radius.circular(16),
  );

  static const _placeholder = Color(0xFFF1F5F9);

  @override
  Widget build(BuildContext context) {
    if (url == null || url!.isEmpty) {
      return ClipRRect(
        borderRadius: _borderRadius,
        child: Container(
          width: 72,
          height: 72,
          color: _placeholder,
          child: const Icon(Icons.water_outlined,
              color: AppColors.textMuted, size: 28),
        ),
      );
    }

    return ClipRRect(
      borderRadius: _borderRadius,
      child: CachedNetworkImage(
        imageUrl: url!,
        width: 72,
        height: 72,
        fit: BoxFit.cover,
        placeholder: (_, __) => Container(
          width: 72,
          height: 72,
          color: _placeholder,
          child: const Center(
            child: SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
          ),
        ),
        errorWidget: (_, __, ___) => Container(
          width: 72,
          height: 72,
          color: _placeholder,
          child: const Icon(Icons.broken_image_outlined,
              color: AppColors.textMuted, size: 24),
        ),
      ),
    );
  }
}

class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;

  const _InfoChip({
    required this.icon,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withAlpha(20),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
                fontSize: 11, fontWeight: FontWeight.w500, color: color),
          ),
        ],
      ),
    );
  }
}
