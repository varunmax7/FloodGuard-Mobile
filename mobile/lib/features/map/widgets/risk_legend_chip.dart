/// Glass risk legend chip — §2 spec: glass card, 4 coloured dots + labels.
library;

import 'dart:ui';
import 'package:flutter/material.dart';
import '../../../design/theme/app_theme.dart';

class RiskLegendChip extends StatelessWidget {
  /// 'risk' → coloured risk levels; 'rain' → 24h rainfall gradient.
  final String mode;
  const RiskLegendChip({super.key, this.mode = 'risk'});

  static const _riskItems = [
    ('Severe',   AppColors.riskSevere),
    ('High',     AppColors.riskHigh),
    ('Moderate', AppColors.riskModerate),
    ('Low',      AppColors.riskLow),
  ];

  // Kept in sync with _kRainFillColor in map_screen.dart.
  static const _rainItems = [
    ('60+ mm', Color(0xFF1E3A8A)),
    ('30 mm',  Color(0xFF1D4ED8)),
    ('15 mm',  Color(0xFF3B82F6)),
    ('5 mm',   Color(0xFF93C5FD)),
    ('1 mm',   Color(0xFFDBEAFE)),
    ('Dry',    Color(0xFFF1F5F9)),
  ];

  @override
  Widget build(BuildContext context) {
    final isRain = mode == 'rain';
    final items = isRain ? _rainItems : _riskItems;
    final title = isRain ? 'Rain (24h)' : 'Risk Level';

    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: AppColors.glass,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(title,
                  style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textMuted)),
              const SizedBox(height: 6),
              for (final item in items) ...[
                _LegendRow(label: item.$1, color: item.$2),
                const SizedBox(height: 4),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _LegendRow extends StatelessWidget {
  final String label;
  final Color color;

  const _LegendRow({required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
            width: 10, height: 10,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 8),
        Text(label,
            style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w500,
                color: AppColors.textPrimary)),
      ],
    );
  }
}
