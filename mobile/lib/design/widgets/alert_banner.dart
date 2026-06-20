/// AlertBanner — orange/red strip shown when HIGH or SEVERE hotspots exist.
library;

import 'package:flutter/material.dart';
import '../../data/models/risk_overview.dart';
import '../theme/app_theme.dart';

class AlertBanner extends StatelessWidget {
  final List<Hotspot> hotspots;
  final VoidCallback? onTap;

  const AlertBanner({super.key, required this.hotspots, this.onTap});

  @override
  Widget build(BuildContext context) {
    if (hotspots.isEmpty) return const SizedBox.shrink();

    final topLevel = hotspots.first.riskLevel.toUpperCase();
    final isSevere = topLevel == 'SEVERE';
    final bgColor = isSevere ? AppColors.severeBg : const Color(0xFFFFF7ED);
    final borderColor = isSevere ? AppColors.riskSevere : AppColors.riskHigh;
    final icon = isSevere ? Icons.warning_rounded : Icons.warning_amber_rounded;
    final label = isSevere ? 'SEVERE FLOOD WARNING' : 'HIGH RISK ALERT';
    final areas = hotspots
        .take(3)
        .map((h) => h.wardName ?? h.h3Index.substring(0, 8))
        .join(', ');

    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.fromLTRB(16, 12, 16, 0),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: borderColor.withAlpha(102), width: 1),
        ),
        child: Row(
          children: [
            Icon(icon, color: borderColor, size: 22),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: TextStyle(
                      color: borderColor,
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.3,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    areas,
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 13,
                      fontWeight: FontWeight.w400,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, color: AppColors.textMuted, size: 20),
          ],
        ),
      ),
    );
  }
}
