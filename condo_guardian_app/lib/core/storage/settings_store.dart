import 'package:shared_preferences/shared_preferences.dart';

class SettingsStore {
  SettingsStore._(this._prefs);

  static const _backendBaseUrlKey = 'backend_base_url';
  static const _dashboardUrlKey = 'dashboard_url';
  static const _lanBaseUrlKey = 'lan_base_url';
  static const _tailscaleBaseUrlKey = 'tailscale_base_url';
  static const _activeBackendBaseUrlKey = 'active_backend_base_url';
  static const _authTokenKey = 'auth_token';
  static const _usernameKey = 'username';
  static const _pollingSecondsKey = 'polling_seconds';

  final SharedPreferences _prefs;

  static Future<SettingsStore> create() async {
    final prefs = await SharedPreferences.getInstance();
    return SettingsStore._(prefs);
  }

  String get backendBaseUrl => activeBackendBaseUrl;

  String get activeBackendBaseUrl {
    final active = (_prefs.getString(_activeBackendBaseUrlKey) ??
            _prefs.getString(_backendBaseUrlKey) ??
            '')
        .trim();
    final lan = lanBaseUrl;
    final tailscale = tailscaleBaseUrl;
    final savedProfiles = <String>{
      if (lan.isNotEmpty) lan,
      if (tailscale.isNotEmpty) tailscale,
    };

    if (active.isNotEmpty &&
        !_isLocalHostname(active) &&
        (savedProfiles.isEmpty || savedProfiles.contains(active))) {
      return active;
    }

    if (lan.isNotEmpty) {
      return lan;
    }

    if (tailscale.isNotEmpty) {
      return tailscale;
    }

    return '';
  }

  bool _isLocalHostname(String value) {
    final uri = Uri.tryParse(value);
    final host = uri?.host.toLowerCase() ?? '';
    return host.endsWith('.local');
  }

  Future<void> setBackendBaseUrl(String value) async {
    await setActiveBackendBaseUrl(value);
    await _prefs.setString(_backendBaseUrlKey, value);
  }

  Future<void> setActiveBackendBaseUrl(String value) async {
    await _prefs.setString(_activeBackendBaseUrlKey, value.trim());
  }

  String get lanBaseUrl => _prefs.getString(_lanBaseUrlKey) ?? '';

  Future<void> setLanBaseUrl(String value) async {
    await _prefs.setString(_lanBaseUrlKey, value.trim());
  }

  String get tailscaleBaseUrl => _prefs.getString(_tailscaleBaseUrlKey) ?? '';

  Future<void> setTailscaleBaseUrl(String value) async {
    await _prefs.setString(_tailscaleBaseUrlKey, value.trim());
  }

  Future<void> setConnectionProfiles({
    required String lanBaseUrl,
    required String tailscaleBaseUrl,
  }) async {
    await setLanBaseUrl(lanBaseUrl);
    await setTailscaleBaseUrl(tailscaleBaseUrl);
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

  String get username => _prefs.getString(_usernameKey) ?? 'admin';

  Future<void> setUsername(String value) async {
    await _prefs.setString(_usernameKey, value.trim());
  }

  int get pollingSeconds => _prefs.getInt(_pollingSecondsKey) ?? 10;

  Future<void> setPollingSeconds(int value) async {
    await _prefs.setInt(_pollingSecondsKey, value);
  }
}
