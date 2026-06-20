/// Location risk bottom card — shown after "My Location" tap.
library;

import 'package:flutter/material.dart';
import '../../../design/theme/app_theme.dart';
import '../../../design/widgets/risk_dot.dart';

class LocationCard extends StatelessWidget {
  final Map<String, dynamic> data;
  final VoidCallback onDismiss;
  final VoidCallback? onViewDetail;

  const LocationCard({
    super.key,
    required this.data,
    required this.onDismiss,
    this.onViewDetail,
  });

  @override
  Widget build(BuildContext context) {
    final riskLevel = (data['risk_level'] as String? ?? 'LOW').toUpperCase();
    final plainText = data['plain_text'] as String? ?? 'No data available';
    final advice = data['advice'] as String? ?? '';
    final rain1h = (data['rain_1h'] as num?)?.toStringAsFixed(1);
    final confidence = data['confidence'] as int? ?? 0;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: const [
          BoxShadow(
              color: Color(0x200F172A), blurRadius: 20, offset: Offset(0, -4)),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Drag handle
          Center(
            child: Container(
              margin: const EdgeInsets.only(top: 10),
              width: 36,
              height: 4,
              decoration: BoxDecoration(
                color: const Color(0xFFE2E8F0),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    RiskBadge(level: riskLevel),
                    const Spacer(),
                    if (rain1h != null)
                      Text('$rain1h mm/h',
                          style: const TextStyle(
                              fontSize: 12, color: AppColors.textMuted)),
                    const SizedBox(width: 8),
                    Text('$confidence% confidence',
                        style: const TextStyle(
                            fontSize: 12, color: AppColors.textMuted)),
                    const SizedBox(width: 8),
                    GestureDetector(
                      onTap: onDismiss,
                      child: const Icon(Icons.close,
                          size: 18, color: AppColors.textMuted),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Text(plainText,
                    style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: AppColors.textPrimary)),
                if (advice.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(advice,
                      style: const TextStyle(
                          fontSize: 13, color: AppColors.textMuted)),
                ],
                if (onViewDetail != null) ...[
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton(
                      onPressed: onViewDetail,
                      child: const Text('View Area Detail'),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
