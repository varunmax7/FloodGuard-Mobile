/// HourlyRiskStrip — 24 colored cells, one per forecast hour (NOT a chart).
library;

import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import 'risk_dot.dart';
import '../../data/models/risk_location.dart';

class HourlyRiskStrip extends StatelessWidget {
  final List<HourlyRisk> hourly;

  const HourlyRiskStrip({super.key, required this.hourly});

  @override
  Widget build(BuildContext context) {
    if (hourly.isEmpty) {
      return Container(
        height: 60,
        alignment: Alignment.center,
        child: const Text(
          'No hourly data available',
          style: TextStyle(fontSize: 13, color: AppColors.textMuted),
        ),
      );
    }

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          for (int i = 0; i < hourly.length; i++) ...[
            _HourCell(entry: hourly[i]),
            if (i < hourly.length - 1) const SizedBox(width: 3),
          ],
        ],
      ),
    );
  }
}

class _HourCell extends StatelessWidget {
  final HourlyRisk entry;

  const _HourCell({required this.entry});

  @override
  Widget build(BuildContext context) {
    final color = riskColor(entry.riskLevel);
    final label = entry.hour.toString().padLeft(2, '0');

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 26,
          height: 40,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(5),
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: const TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w500,
            color: AppColors.textMuted,
          ),
        ),
      ],
    );
  }
}

/// Compact 4-color legend row for use below the strip.
class HourlyStripLegend extends StatelessWidget {
  const HourlyStripLegend({super.key});

  static const _items = [
    ('Low', AppColors.riskLow),
    ('Moderate', AppColors.riskModerate),
    ('High', AppColors.riskHigh),
    ('Severe', AppColors.riskSevere),
  ];

  @override
  Widget build(BuildContext context) {
    return Row(
      children: _items
          .map(
            (item) => Expanded(
              child: Row(
                children: [
                  Container(
                    width: 10,
                    height: 10,
                    decoration: BoxDecoration(
                      color: item.$2,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                  const SizedBox(width: 4),
                  Text(
                    item.$1,
                    style: const TextStyle(fontSize: 10, color: AppColors.textMuted),
                  ),
                ],
              ),
            ),
          )
          .toList(),
    );
  }
}
