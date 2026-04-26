import 'package:flutter/material.dart';

import 'app.dart';
import 'core/storage/settings_store.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final settingsStore = await SettingsStore.create();
  runApp(CondoGuardianApp(settingsStore: settingsStore));
}
