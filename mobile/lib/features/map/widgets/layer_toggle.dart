/// Risk / Radar layer toggle chip.
library;

import 'package:flutter/material.dart';
import '../../../design/theme/app_theme.dart';

class LayerToggle extends StatelessWidget {
  final String active; // 'risk' | 'rain' | 'radar'
  final ValueChanged<String> onToggle;

  const LayerToggle({super.key, required this.active, required this.onToggle});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(24),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white.withAlpha(230),
          borderRadius: BorderRadius.circular(24),
          boxShadow: const [
            BoxShadow(color: Color(0x1A0F172A), blurRadius: 8, offset: Offset(0, 2)),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _Chip(label: 'Risk',  icon: Icons.layers,     isActive: active == 'risk',
                onTap: () => onToggle('risk')),
            _Chip(label: 'Rain',  icon: Icons.water_drop, isActive: active == 'rain',
                onTap: () => onToggle('rain')),
            _Chip(label: 'Radar', icon: Icons.radar,      isActive: active == 'radar',
                onTap: () => onToggle('radar')),
          ],
        ),
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool isActive;
  final VoidCallback onTap;

  const _Chip({required this.label, required this.icon,
      required this.isActive, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: isActive ? AppColors.blue600 : Colors.transparent,
          borderRadius: BorderRadius.circular(24),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16,
                color: isActive ? Colors.white : AppColors.textMuted),
            const SizedBox(width: 6),
            Text(label,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: isActive ? Colors.white : AppColors.textMuted,
                )),
          ],
        ),
      ),
    );
  }
}
