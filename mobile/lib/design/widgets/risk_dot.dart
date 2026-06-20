/// RiskDot — coloured circle indicating risk/hazard level.
library;

import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

Color riskColor(String level) => switch (level.toUpperCase()) {
      'LOW' => AppColors.riskLow,
      'MODERATE' => AppColors.riskModerate,
      'HIGH' => AppColors.riskHigh,
      'SEVERE' => AppColors.riskSevere,
      _ => AppColors.textMuted,
    };

class RiskDot extends StatelessWidget {
  final String level;
  final double size;

  const RiskDot({super.key, required this.level, this.size = 10});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: riskColor(level),
        shape: BoxShape.circle,
      ),
    );
  }
}

class RiskBadge extends StatelessWidget {
  final String level;

  const RiskBadge({super.key, required this.level});

  @override
  Widget build(BuildContext context) {
    final color = riskColor(level);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withAlpha(26), // 10% opacity
        borderRadius: BorderRadius.circular(100),
        border: Border.all(color: color.withAlpha(77), width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          RiskDot(level: level, size: 8),
          const SizedBox(width: 6),
          Text(
            _label(level),
            style: TextStyle(
              color: color,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  String _label(String level) =>
      level[0].toUpperCase() + level.substring(1).toLowerCase();
}
