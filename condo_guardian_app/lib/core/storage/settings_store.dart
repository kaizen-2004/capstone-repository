import 'package:shared_preferences/shared_preferences.dart';

class SettingsStore {
  SettingsStore._(this._prefs);

  static const _backendBaseUrlKey = 'backend_base_url';
  static const _dashboardUrlKey = 'dashboard_url';
  static const _authTokenKey = 'auth_token';
  static const _authUsernameKey = 'auth_username';
  static const _authPasswordKey = 'auth_password';
  static const _pollingSecondsKey = 'polling_seconds';

  final SharedPreferences _prefs;

  static Future<SettingsStore> create() async {
    final prefs = await SharedPreferences.getInstance();
    return SettingsStore._(prefs);
  }

  String get backendBaseUrl =>
      _prefs.getString(_backendBaseUrlKey) ?? 'http://127.0.0.1:8765';

  Future<void> setBackendBaseUrl(String value) async {
    await _prefs.setString(_backendBaseUrlKey, value);
  }

  String get dashboardUrl =>
      _prefs.getString(_dashboardUrlKey) ?? 'http://127.0.0.1:8765/dashboard';

  Future<void> setDashboardUrl(String value) async {
    await _prefs.setString(_dashboardUrlKey, value);
  }

  String get authToken => _prefs.getString(_authTokenKey) ?? '';

  Future<void> setAuthToken(String value) async {
    await _prefs.setString(_authTokenKey, value);
  }

  String get authUsername => _prefs.getString(_authUsernameKey) ?? 'admin';

  Future<void> setAuthUsername(String value) async {
    await _prefs.setString(_authUsernameKey, value);
  }

  String get authPassword => _prefs.getString(_authPasswordKey) ?? '';

  Future<void> setAuthPassword(String value) async {
    await _prefs.setString(_authPasswordKey, value);
  }

  int get pollingSeconds => _prefs.getInt(_pollingSecondsKey) ?? 10;

  Future<void> setPollingSeconds(int value) async {
    await _prefs.setInt(_pollingSecondsKey, value);
  }
}
