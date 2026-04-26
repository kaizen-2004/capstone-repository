import '../core/network/api_client.dart';

class ProvisioningService {
  ProvisioningService(this.apiClient);

  final ApiClient apiClient;

  Future<String> sendNodeConfiguration({
    required String wifiSsid,
    required String wifiPassword,
    required String backendHost,
    required int backendPort,
    required String nodeId,
    required String nodeRole,
    required String roomName,
  }) async {
    final json = await apiClient.postJson('configure', <String, dynamic>{
      'wifi_ssid': wifiSsid,
      'wifi_password': wifiPassword,
      'backend_host': backendHost,
      'backend_port': backendPort,
      'node_id': nodeId,
      'node_role': nodeRole,
      'room_name': roomName,
    });

    return json['message']?.toString() ??
        json['detail']?.toString() ??
        'Configuration submitted.';
  }
}
