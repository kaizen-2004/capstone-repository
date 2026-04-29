import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'core/storage/settings_store.dart';
import 'screens/login_screen.dart';
import 'screens/shell_screen.dart';

class CondoGuardianApp extends StatefulWidget {
  const CondoGuardianApp({super.key, required this.settingsStore});

  final SettingsStore settingsStore;

  @override
  State<CondoGuardianApp> createState() => _CondoGuardianAppState();
}

class _CondoGuardianAppState extends State<CondoGuardianApp> {
  late bool _authenticated;

  @override
  void initState() {
    super.initState();
    _authenticated = widget.settingsStore.authToken.trim().isNotEmpty;
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
      DeviceOrientation.portraitDown,
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final isDark = MediaQuery.platformBrightnessOf(context) == Brightness.dark;

    SystemChrome.setSystemUIOverlayStyle(
      isDark
          ? const SystemUiOverlayStyle(
              statusBarColor: Colors.transparent,
              statusBarIconBrightness: Brightness.light,
              statusBarBrightness: Brightness.dark,
            )
          : const SystemUiOverlayStyle(
              statusBarColor: Colors.transparent,
              statusBarIconBrightness: Brightness.dark,
              statusBarBrightness: Brightness.light,
            ),
    );

    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'IntruFlare',
      themeMode: ThemeMode.system,
      theme: _buildLightTheme(),
      darkTheme: _buildDarkTheme(),
      home: _authenticated
          ? ShellScreen(
              settingsStore: widget.settingsStore,
              onSessionInvalidated: _handleSessionInvalidated,
            )
          : LoginScreen(
              settingsStore: widget.settingsStore,
              onAuthenticated: _handleAuthenticated,
            ),
    );
  }

  void _handleAuthenticated() {
    if (!mounted) {
      return;
    }
    setState(() => _authenticated = true);
  }

  void _handleSessionInvalidated() {
    if (!mounted) {
      return;
    }
    setState(() => _authenticated = false);
  }

  static ThemeData _buildDarkTheme() {
    const primary = Color(0xFF1E88E5);
    const surface = Color(0xFF0D1B2A);
    const surfaceContainer = Color(0xFF162032);
    const onSurface = Color(0xFFE8EFF7);

    final cs = const ColorScheme(
      brightness: Brightness.dark,
      primary: primary,
      onPrimary: Colors.white,
      secondary: Color(0xFF00BCD4),
      onSecondary: Colors.black,
      error: Color(0xFFEF5350),
      onError: Colors.white,
      surface: surface,
      onSurface: onSurface,
      surfaceContainerHighest: surfaceContainer,
      outline: Color(0xFF2C4A6E),
      outlineVariant: Color(0xFF1A3A5C),
      tertiary: Color(0xFF26A69A),
      onTertiary: Colors.white,
      primaryContainer: Color(0xFF1565C0),
      onPrimaryContainer: Colors.white,
      secondaryContainer: Color(0xFF1A3A5C),
      onSecondaryContainer: onSurface,
      shadow: Colors.black,
      scrim: Colors.black87,
      inverseSurface: onSurface,
      onInverseSurface: surface,
      inversePrimary: Color(0xFF1565C0),
      surfaceTint: primary,
    );

    return _buildThemeData(cs, isDark: true);
  }

  static ThemeData _buildLightTheme() {
    const primary = Color(0xFF1565C0);
    const surface = Color(0xFFF4F7FB);
    const surfaceContainer = Color(0xFFFFFFFF);
    const onSurface = Color(0xFF0D1B2A);

    final cs = const ColorScheme(
      brightness: Brightness.light,
      primary: primary,
      onPrimary: Colors.white,
      secondary: Color(0xFF0097A7),
      onSecondary: Colors.white,
      error: Color(0xFFD32F2F),
      onError: Colors.white,
      surface: surface,
      onSurface: onSurface,
      surfaceContainerHighest: surfaceContainer,
      outline: Color(0xFFB0C4DE),
      outlineVariant: Color(0xFFD6E4F0),
      tertiary: Color(0xFF00796B),
      onTertiary: Colors.white,
      primaryContainer: Color(0xFFDCEEFF),
      onPrimaryContainer: Color(0xFF0A2540),
      secondaryContainer: Color(0xFFE0F4F8),
      onSecondaryContainer: Color(0xFF003A40),
      shadow: Color(0x1A000000),
      scrim: Colors.black54,
      inverseSurface: Color(0xFF0D1B2A),
      onInverseSurface: Color(0xFFE8EFF7),
      inversePrimary: Color(0xFF90CAF9),
      surfaceTint: primary,
    );

    return _buildThemeData(cs, isDark: false);
  }

  static ThemeData _buildThemeData(ColorScheme cs, {required bool isDark}) {
    final secondaryText =
        isDark ? const Color(0xFF8BA7C4) : const Color(0xFF4A6080);
    final dimText = isDark ? const Color(0xFF5D7A96) : const Color(0xFF7A97B4);
    final inputFill =
        isDark ? const Color(0xFF0F2032) : const Color(0xFFF0F5FB);
    final cardBorder =
        isDark ? const Color(0xFF1E3A55) : const Color(0xFFD6E4F0);
    final dividerColor =
        isDark ? const Color(0xFF1E3A55) : const Color(0xFFD6E4F0);
    final navBg = isDark ? const Color(0xFF162032) : Colors.white;

    return ThemeData(
      useMaterial3: true,
      colorScheme: cs,
      brightness: cs.brightness,
      scaffoldBackgroundColor: cs.surface,
      appBarTheme: AppBarTheme(
        backgroundColor: cs.surfaceContainerHighest,
        foregroundColor: cs.onSurface,
        elevation: 0,
        centerTitle: false,
        scrolledUnderElevation: 2,
        shadowColor: isDark ? Colors.black45 : const Color(0x14000000),
        titleTextStyle: TextStyle(
          color: cs.onSurface,
          fontSize: 18,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.3,
        ),
        iconTheme: IconThemeData(color: secondaryText),
        actionsIconTheme: IconThemeData(color: secondaryText),
      ),
      cardTheme: CardThemeData(
        color: cs.surfaceContainerHighest,
        elevation: isDark ? 0 : 1,
        shadowColor: isDark ? Colors.transparent : const Color(0x14000000),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: cardBorder, width: 1),
        ),
        margin: EdgeInsets.zero,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: inputFill,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: cs.outline),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: cs.outline),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: cs.primary, width: 1.5),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: cs.error),
        ),
        labelStyle: TextStyle(color: secondaryText, fontSize: 14),
        hintStyle: TextStyle(
            color: secondaryText.withValues(alpha: 0.6), fontSize: 14),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: cs.primary,
          foregroundColor: cs.onPrimary,
          minimumSize: const Size(double.infinity, 48),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: cs.primary,
          textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: navBg,
        indicatorColor: cs.primary.withValues(alpha: 0.14),
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return TextStyle(
            fontSize: 11,
            fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
            color: selected ? cs.primary : secondaryText,
          );
        }),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return IconThemeData(
            color: selected ? cs.primary : secondaryText,
            size: 22,
          );
        }),
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        elevation: 0,
        height: 64,
      ),
      listTileTheme: ListTileThemeData(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        iconColor: secondaryText,
        textColor: cs.onSurface,
      ),
      dividerTheme: DividerThemeData(
        color: dividerColor,
        thickness: 1,
        space: 1,
      ),
      textTheme: TextTheme(
        displayLarge:
            TextStyle(color: cs.onSurface, fontWeight: FontWeight.w700),
        displayMedium:
            TextStyle(color: cs.onSurface, fontWeight: FontWeight.w700),
        headlineLarge:
            TextStyle(color: cs.onSurface, fontWeight: FontWeight.w700),
        headlineMedium:
            TextStyle(color: cs.onSurface, fontWeight: FontWeight.w600),
        headlineSmall:
            TextStyle(color: cs.onSurface, fontWeight: FontWeight.w600),
        titleLarge: TextStyle(
            color: cs.onSurface, fontWeight: FontWeight.w600, fontSize: 17),
        titleMedium: TextStyle(
            color: secondaryText, fontWeight: FontWeight.w500, fontSize: 13),
        titleSmall: TextStyle(
            color: secondaryText, fontWeight: FontWeight.w500, fontSize: 12),
        bodyLarge: TextStyle(color: cs.onSurface, fontSize: 15),
        bodyMedium: TextStyle(color: secondaryText, fontSize: 13, height: 1.5),
        bodySmall: TextStyle(color: dimText, fontSize: 11, height: 1.4),
        labelLarge: TextStyle(
            color: cs.onSurface, fontWeight: FontWeight.w600, fontSize: 14),
        labelMedium: TextStyle(color: secondaryText, fontSize: 12),
        labelSmall: TextStyle(color: dimText, fontSize: 11),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: cs.surfaceContainerHighest,
        selectedColor: cs.primary.withValues(alpha: 0.2),
        labelStyle: TextStyle(color: cs.onSurface, fontSize: 12),
        side: BorderSide(color: cs.outline),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
      progressIndicatorTheme: ProgressIndicatorThemeData(
        color: cs.primary,
        linearTrackColor: cs.outline.withValues(alpha: 0.4),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: cs.surfaceContainerHighest,
        contentTextStyle: TextStyle(color: cs.onSurface),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
}
