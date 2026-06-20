import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// FloodGuard Design System tokens (from approved UI mockup)
class AppColors {
  AppColors._();

  // Brand
  static const navyDark = Color(0xFF0B2545);    // brand/navy-900
  static const navyMid = Color(0xFF13315C);     // brand/navy-700
  static const blue600 = Color(0xFF2563EB);     // primary buttons, active nav

  // Risk levels
  static const riskLow = Color(0xFF22C55E);
  static const riskModerate = Color(0xFFFACC15);
  static const riskHigh = Color(0xFFF97316);
  static const riskSevere = Color(0xFFEF4444);

  // Surfaces
  static const white = Color(0xFFFFFFFF);
  static const glass = Color(0xD9FFFFFF); // rgba(255,255,255,0.85)

  // Text
  static const textPrimary = Color(0xFF0F172A);
  static const textMuted = Color(0xFF64748B);

  // Alert
  static const severeBg = Color(0xFFFEF2F2);
}

class AppTheme {
  AppTheme._();

  static ThemeData get light => ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: AppColors.blue600,
          primary: AppColors.blue600,
          onPrimary: Colors.white,
          secondary: AppColors.navyMid,
          onSecondary: Colors.white,
          surface: AppColors.white,
          onSurface: AppColors.textPrimary,
          surfaceContainerHighest: const Color(0xFFF1F5F9),
          onSurfaceVariant: AppColors.textMuted,
          error: AppColors.riskSevere,
          brightness: Brightness.light,
        ),
        textTheme: GoogleFonts.interTextTheme().copyWith(
          displayLarge: GoogleFonts.inter(fontSize: 22, fontWeight: FontWeight.w700, color: AppColors.textPrimary),
          headlineMedium: GoogleFonts.inter(fontSize: 17, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
          bodyLarge: GoogleFonts.inter(fontSize: 15, fontWeight: FontWeight.w400, color: AppColors.textPrimary),
          labelSmall: GoogleFonts.inter(fontSize: 12, fontWeight: FontWeight.w500, color: AppColors.textMuted),
        ),
        appBarTheme: AppBarTheme(
          backgroundColor: AppColors.navyDark,
          foregroundColor: Colors.white,
          elevation: 0,
          centerTitle: false,
          titleTextStyle: GoogleFonts.inter(
            fontSize: 17,
            fontWeight: FontWeight.w600,
            color: Colors.white,
          ),
        ),
        navigationBarTheme: NavigationBarThemeData(
          backgroundColor: AppColors.white,
          indicatorColor: AppColors.blue600.withOpacity(0.12),
          iconTheme: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.selected)) {
              return const IconThemeData(color: AppColors.blue600);
            }
            return const IconThemeData(color: AppColors.textMuted);
          }),
          labelTextStyle: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.selected)) {
              return GoogleFonts.inter(
                fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.blue600,
              );
            }
            return GoogleFonts.inter(
              fontSize: 12, fontWeight: FontWeight.w500, color: AppColors.textMuted,
            );
          }),
          elevation: 8,
          shadowColor: AppColors.textPrimary.withOpacity(0.08),
        ),
        cardTheme: const CardThemeData(
          color: AppColors.white,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(16)),
          ),
          margin: EdgeInsets.zero,
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            backgroundColor: AppColors.blue600,
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            textStyle: GoogleFonts.inter(fontSize: 15, fontWeight: FontWeight.w600),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        ),
        dividerTheme: const DividerThemeData(color: Color(0xFFE2E8F0)),
      );

  static ThemeData get dark => light.copyWith(
        colorScheme: ColorScheme.fromSeed(
          seedColor: AppColors.blue600,
          brightness: Brightness.dark,
          primary: AppColors.blue600,
          surface: const Color(0xFF1E293B),
          onSurface: const Color(0xFFE2E8F0),
        ),
      );
}

/// Design tokens for inline use
extension BuildContextThemeX on BuildContext {
  ThemeData get theme => Theme.of(this);
  ColorScheme get colors => Theme.of(this).colorScheme;
  TextTheme get texts => Theme.of(this).textTheme;
}
