import 'api_client.dart';
import '../storage/settings_store.dart';

class BackendEndpointResolution {
  const BackendEndpointResolution({
    required this.baseUrl,
    required this.label,
  });

  final String baseUrl;
  final String label;
}

class BackendEndpointResolver {
  static const probeTimeout = Duration(seconds: 3);

  static String normalizeBaseUrl(String raw) {
    var value = raw.trim();
    if (value.isEmpty) {
      return '';
    }
    if (!value.contains('://')) {
      value = 'http://$value';
    }
    final parsed = Uri.tryParse(value);
    if (parsed == null || parsed.host.isEmpty) {
      return '';
    }
    return parsed
        .replace(path: parsed.path.replaceAll(RegExp(r'/+$'), ''))
        .toString()
        .replaceAll(RegExp(r'/+$'), '');
  }

  static List<BackendEndpointResolution> candidates({
    required String lanBaseUrl,
    required String tailscaleBaseUrl,
  }) {
    final selected = <BackendEndpointResolution>[];

    void add(String label, String rawUrl) {
      final url = normalizeBaseUrl(rawUrl);
      if (url.isEmpty || selected.any((item) => item.baseUrl == url)) {
        return;
      }
      selected.add(BackendEndpointResolution(baseUrl: url, label: label));
    }

    add('LAN', lanBaseUrl);
    add('Tailscale', tailscaleBaseUrl);

    return selected;
  }

  static List<BackendEndpointResolution> candidatesFromStore(
      SettingsStore store) {
    return candidates(
      lanBaseUrl: store.lanBaseUrl,
      tailscaleBaseUrl: store.tailscaleBaseUrl,
    );
  }

  static Future<BackendEndpointResolution> resolve(
    SettingsStore store, {
    required String token,
  }) async {
    final candidates = candidatesFromStore(store);
    if (candidates.isEmpty) {
      throw ApiException('No backend connection profile is configured.');
    }

    Object? lastError;
    for (final candidate in candidates) {
      try {
        final client = ApiClient(
          baseUrl: candidate.baseUrl,
          token: token,
          timeout: probeTimeout,
        );
        await client.getJson('api/status');
        await store.setActiveBackendBaseUrl(candidate.baseUrl);
        return candidate;
      } catch (error) {
        lastError = error;
      }
    }

    throw ApiException(
        'No configured backend endpoint is reachable. Last error: $lastError');
  }

  static Future<void> refreshBootstrap(
    SettingsStore store, {
    required String baseUrl,
    required String token,
  }) async {
    if (token.trim().isEmpty) {
      return;
    }
    try {
      final client = ApiClient(
        baseUrl: baseUrl,
        token: token,
        timeout: probeTimeout,
      );
      final payload = await client.getJson('api/mobile/bootstrap');
      final lan = normalizeBaseUrl(payload['lan_base_url']?.toString() ?? '');
      final tailscale =
          normalizeBaseUrl(payload['tailscale_base_url']?.toString() ?? '');
      if (lan.isNotEmpty && normalizeBaseUrl(store.lanBaseUrl).isEmpty) {
        await store.setLanBaseUrl(lan);
      }
      if (tailscale.isNotEmpty &&
          normalizeBaseUrl(store.tailscaleBaseUrl).isEmpty) {
        await store.setTailscaleBaseUrl(tailscale);
      }
    } catch (_) {
      // Bootstrap only improves future switching; keep current connection if it fails.
    }
  }
}
