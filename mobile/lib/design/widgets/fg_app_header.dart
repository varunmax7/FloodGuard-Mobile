/// FgAppHeader — navy vertical gradient, shield+drop logo, FloodGuard title, bell.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import '../theme/app_theme.dart';

class FgAppHeader extends StatelessWidget implements PreferredSizeWidget {
  final List<Widget>? actions;
  final VoidCallback? onBellTap;
  final PreferredSizeWidget? bottom;

  const FgAppHeader({super.key, this.actions, this.onBellTap, this.bottom});

  @override
  Size get preferredSize => Size.fromHeight(
        kToolbarHeight + (bottom?.preferredSize.height ?? 0),
      );

  @override
  Widget build(BuildContext context) {
    return AppBar(
      systemOverlayStyle: SystemUiOverlayStyle.light,
      flexibleSpace: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [AppColors.navyDark, AppColors.navyMid],
          ),
        ),
      ),
      backgroundColor: Colors.transparent,
      elevation: 0,
      titleSpacing: 16,
      title: const _HeaderTitle(),
      bottom: bottom,
      actions: actions ??
          [
            IconButton(
              icon: const Icon(Icons.notifications_outlined,
                  color: Colors.white, size: 24),
              onPressed: onBellTap ?? () => context.go('/alerts'),
              tooltip: 'Alerts',
            ),
            IconButton(
              icon: const Icon(Icons.settings_outlined,
                  color: Colors.white, size: 22),
              onPressed: () => context.push('/settings'),
              tooltip: 'Settings',
            ),
            const SizedBox(width: 4),
          ],
    );
  }
}

class _HeaderTitle extends StatelessWidget {
  const _HeaderTitle();

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        // FloodGuard brand logo — white pill so the navy mark stays readable
        // against the navy header gradient.
        Container(
          width: 34,
          height: 34,
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(8),
          ),
          clipBehavior: Clip.antiAlias,
          child: Image.asset(
            'assets/images/logo.png',
            fit: BoxFit.contain,
          ),
        ),
        const SizedBox(width: 10),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'FloodGuard',
              style: TextStyle(
                color: Colors.white,
                fontSize: 17,
                fontWeight: FontWeight.w700,
                letterSpacing: -0.2,
              ),
            ),
            Text(
              'TG & AP Flood Alert',
              style: TextStyle(
                color: Colors.white.withAlpha(204), // 80% opacity
                fontSize: 11,
                fontWeight: FontWeight.w400,
              ),
            ),
          ],
        ),
      ],
    );
  }
}
