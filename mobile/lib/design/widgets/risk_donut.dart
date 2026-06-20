/// RiskDonut — fl_chart pie chart + 4-row legend for risk distribution.
library;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import '../../data/models/risk_overview.dart';
import '../theme/app_theme.dart';

class RiskDonut extends StatelessWidget {
  final RiskSummary summary;

  const RiskDonut({super.key, required this.summary});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(
          width: 130,
          height: 130,
          child: _buildChart(),
        ),
        const SizedBox(width: 24),
        Expanded(child: _buildLegend(context)),
      ],
    );
  }

  Widget _buildChart() {
    final sections = _sections();
    if (sections.isEmpty) {
      // All zero — show grey placeholder
      return PieChart(PieChartData(
        sections: [
          PieChartSectionData(
            value: 100,
            color: const Color(0xFFE2E8F0),
            title: '',
            radius: 38,
          ),
        ],
        centerSpaceRadius: 42,
        sectionsSpace: 0,
      ));
    }
    return PieChart(PieChartData(
      sections: sections,
      centerSpaceRadius: 42,
      sectionsSpace: 2,
      startDegreeOffset: -90,
    ));
  }

  List<PieChartSectionData> _sections() {
    final data = [
      (summary.severe, AppColors.riskSevere),
      (summary.high, AppColors.riskHigh),
      (summary.moderate, AppColors.riskModerate),
      (summary.low, AppColors.riskLow),
    ];
    return data
        .where((d) => d.$1 > 0.1)
        .map((d) => PieChartSectionData(
              value: d.$1,
              color: d.$2,
              title: '',
              radius: 38,
            ))
        .toList();
  }

  Widget _buildLegend(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        _Row('Severe', AppColors.riskSevere, summary.severe),
        const SizedBox(height: 10),
        _Row('High', AppColors.riskHigh, summary.high),
        const SizedBox(height: 10),
        _Row('Moderate', AppColors.riskModerate, summary.moderate),
        const SizedBox(height: 10),
        _Row('Low', AppColors.riskLow, summary.low),
      ],
    );
  }
}

class _Row extends StatelessWidget {
  final String label;
  final Color color;
  final double value;

  const _Row(this.label, this.color, this.value);

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            label,
            style: const TextStyle(
                fontSize: 13, fontWeight: FontWeight.w500, color: AppColors.textPrimary),
          ),
        ),
        Text(
          '${value.toStringAsFixed(1)}%',
          style: const TextStyle(
              fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
        ),
      ],
    );
  }
}
