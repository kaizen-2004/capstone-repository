import 'package:shared_preferences/shared_preferences.dart';

class SettingsStore {
  SettingsStore._(this._prefs);

  static const _backendBaseUrlKey = 'backend_base_url';
  static const _dashboardUrlKey = 'dashboard_url';
  static const _mdnsBaseUrlKey = 'mdns_base_url';
  static const _lanBaseUrlKey = 'lan_base_url';
  static const _tailscaleBaseUrlKey = 'tailscale_base_url';
  static const _activeBackendBaseUrlKey = 'active_backend_base_url';
  static const _networkModeKey = 'network_mode';
  static const _authTokenKey = 'auth_token';
  static const _pollingSecondsKey = 'polling_seconds';
  static const defaultMdnsBaseUrl = 'http://thesis-monitor.local:8765';

  final SharedPreferences _prefs;

  static Future<SettingsStore> create() async {
    final prefs = await SharedPreferences.getInstance();
    return SettingsStore._(prefs);
  }

  String get backendBaseUrl => activeBackendBaseUrl;

  String get activeBackendBaseUrl =>
      _prefs.getString(_activeBackendBaseUrlKey) ??
      _prefs.getString(_backendBaseUrlKey) ??
      mdnsBaseUrl;

  Future<void> setBackendBaseUrl(String value) async {
    await setActiveBackendBaseUrl(value);
    await _prefs.setString(_backendBaseUrlKey, value);
  }

  Future<void> setActiveBackendBaseUrl(String value) async {
    await _prefs.setString(_activeBackendBaseUrlKey, value.trim());
  }

  String get mdnsBaseUrl =>
      _prefs.getString(_mdnsBaseUrlKey) ?? defaultMdnsBaseUrl;

  Future<void> setMdnsBaseUrl(String value) async {
    await _prefs.setString(_mdnsBaseUrlKey, value.trim());
  }

  String get lanBaseUrl => _prefs.getString(_lanBaseUrlKey) ?? '';

  Future<void> setLanBaseUrl(String value) async {
    await _prefs.setString(_lanBaseUrlKey, value.trim());
  }

  String get tailscaleBaseUrl => _prefs.getString(_tailscaleBaseUrlKey) ?? '';

  Future<void> setTailscaleBaseUrl(String value) async {
    await _prefs.setString(_tailscaleBaseUrlKey, value.trim());
  }

  String get networkMode {
    final value =
        (_prefs.getString(_networkModeKey) ?? 'auto').trim().toLowerCase();
    return value == 'home' || value == 'away' ? value : 'auto';
  }

  Future<void> setNetworkMode(String value) async {
    final normalized = value.trim().toLowerCase();
    await _prefs.setString(
      _networkModeKey,
      normalized == 'home' || normalized == 'away' ? normalized : 'auto',
    );
  }

  Future<void> setConnectionProfiles({
    required String mdnsBaseUrl,
    required String lanBaseUrl,
    required String tailscaleBaseUrl,
    required String networkMode,
  }) async {
    await setMdnsBaseUrl(mdnsBaseUrl);
    await setLanBaseUrl(lanBaseUrl);
    await setTailscaleBaseUrl(tailscaleBaseUrl);
    await setNetworkMode(networkMode);
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

  int get pollingSeconds => _prefs.getInt(_pollingSecondsKey) ?? 10;

  Future<void> setPollingSeconds(int value) async {
    await _prefs.setInt(_pollingSecondsKey, value);
  }
}
