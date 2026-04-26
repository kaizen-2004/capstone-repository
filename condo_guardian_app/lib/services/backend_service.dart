import '../core/network/api_client.dart';
import '../models/alert_item.dart';
import '../models/snapshot_item.dart';
import '../models/system_snapshot.dart';

class FaceProfile {
  FaceProfile({
    required this.profileId,
    required this.name,
    required this.sampleCount,
  });

  final String profileId;
  final String name;
  final int sampleCount;

  String get displayLabel => '$profileId - $name ($sampleCount samples)';

  factory FaceProfile.fromJson(Map<String, dynamic> json) {
    return FaceProfile(
      profileId: json['id']?.toString() ?? '',
      name: json['label']?.toString() ?? '',
      sampleCount: int.tryParse(json['sample_count']?.toString() ?? '') ?? 0,
    );
  }
}

class EnrollmentStatus {
  EnrollmentStatus({
    required this.count,
    required this.minRequired,
    required this.target,
    required this.remaining,
    required this.ready,
    required this.targetReached,
  });

  final int count;
  final int minRequired;
  final int target;
  final int remaining;
  final bool ready;
  final bool targetReached;

  factory EnrollmentStatus.fromJson(Map<String, dynamic> json) {
    return EnrollmentStatus(
      count: int.tryParse(json['count']?.toString() ?? '') ?? 0,
      minRequired: int.tryParse(json['min_required']?.toString() ?? '') ?? 0,
      target: int.tryParse(json['target']?.toString() ?? '') ?? 0,
      remaining: int.tryParse(json['remaining']?.toString() ?? '') ?? 0,
      ready: json['ready'] == true,
      targetReached: json['target_reached'] == true,
    );
  }

  factory EnrollmentStatus.fromResponse(Map<String, dynamic> json) {
    final nestedStatus = json['status'];
    if (nestedStatus is Map<String, dynamic>) {
      return EnrollmentStatus.fromJson(nestedStatus);
    }
    if (nestedStatus is Map) {
      return EnrollmentStatus.fromJson(
        Map<String, dynamic>.from(nestedStatus),
      );
    }
    return EnrollmentStatus.fromJson(json);
  }
}

class BackendService {
  BackendService(this.apiClient);

  final ApiClient apiClient;

  Future<String> loginAndGetToken({
    required String username,
    required String password,
  }) async {
    final loginClient = ApiClient(baseUrl: apiClient.baseUrl, token: '');
    final json = await loginClient.postJson(
      'api/auth/login',
      <String, dynamic>{
        'username': username,
        'password': password,
      },
    );

    final token = json['token']?.toString() ?? '';
    if (token.isEmpty) {
      throw ApiException('Login succeeded but no token was returned.');
    }
    return token;
  }

  Future<SystemSnapshot> fetchSystemSnapshot() async {
    final statusFuture = apiClient.getJson('api/status');
    final nodesFuture = apiClient.getJson('api/nodes');
    final sensorsFuture = apiClient.getJson('api/sensors');
    final alertsFuture = apiClient.getJson(
      'api/alerts',
      query: <String, dynamic>{'limit': 20},
    );

    final status = await statusFuture;
    final nodes = await nodesFuture;
    final sensors = await sensorsFuture;
    final alerts = await alertsFuture;

    final merged = <String, dynamic>{
      'system_state': status['backend']?.toString() ?? 'online',
      'sensor_readings': sensors['sensors'] ?? <dynamic>[],
      'nodes': nodes['nodes'] ?? <dynamic>[],
      'active_alerts': alerts['alerts'] ?? <dynamic>[],
    };

    return SystemSnapshot.fromJson(merged);
  }

  Future<List<AlertItem>> fetchAlerts() async {
    final json = await apiClient.getJson('api/alerts');
    final items = (json['alerts'] as List<dynamic>? ?? <dynamic>[])
        .map((item) => AlertItem.fromJson(item as Map<String, dynamic>))
        .toList();
    return items;
  }

  Future<List<AlertItem>> fetchEvents() async {
    final json = await apiClient.getJson(
      'api/events',
      query: <String, dynamic>{'limit': 100},
    );
    final items = (json['events'] as List<dynamic>? ?? <dynamic>[])
        .map((item) => AlertItem.fromJson(item as Map<String, dynamic>))
        .toList();
    return items;
  }

  Future<List<SnapshotItem>> fetchSnapshots() async {
    final json = await apiClient.getJson(
      'api/alerts',
      query: <String, dynamic>{'limit': 200},
    );
    final items = (json['alerts'] as List<dynamic>? ?? <dynamic>[])
        .map((item) => SnapshotItem.fromJson(item as Map<String, dynamic>))
        .where((item) => item.snapshotPath.isNotEmpty)
        .toList();
    return items;
  }

  Future<void> deleteSnapshot(String alertId) async {
    await apiClient.postJson(
      'api/alerts/$alertId/snapshot/delete',
      <String, dynamic>{},
    );
  }

  Future<List<FaceProfile>> fetchFaceProfiles() async {
    final json = await apiClient.getJson('api/faces');
    final items = (json['faces'] as List<dynamic>? ?? <dynamic>[])
        .whereType<Map<String, dynamic>>()
        .map(FaceProfile.fromJson)
        .where((item) => item.profileId.isNotEmpty && item.name.isNotEmpty)
        .toList();
    items.sort((a, b) => a.profileId.compareTo(b.profileId));
    return items;
  }

  Future<void> acknowledgeAlert(String alertId) async {
    await apiClient.postJson(
      'api/alerts/$alertId/acknowledge',
      <String, dynamic>{},
    );
  }

  Future<String> queryAssistant(String questionId) async {
    final json = await apiClient.postJson(
      'api/assistant/query',
      <String, dynamic>{'question_id': questionId},
    );
    return json['answer']?.toString() ?? 'No response received.';
  }

  Future<EnrollmentStatus> submitEnrollmentStart({
    required String fullName,
    required String userCode,
  }) async {
    final json = await apiClient.postJson('api/enroll/start', <String, dynamic>{
      'full_name': fullName,
      'user_code': userCode,
    });
    return EnrollmentStatus.fromResponse(json);
  }

  Future<EnrollmentStatus> uploadEnrollmentImage({
    required String userCode,
    required String filePath,
    required int sampleIndex,
  }) async {
    final json = await apiClient.multipartPost(
      'api/enroll/upload',
      fields: <String, String>{
        'user_code': userCode,
        'capture_source': 'mobile_app',
        'sample_index': '$sampleIndex',
      },
      fileField: 'image',
      filePath: filePath,
      fileName: 'mobile_enroll_$sampleIndex.jpg',
    );
    return EnrollmentStatus.fromResponse(json);
  }

  Future<EnrollmentStatus> completeEnrollment(
      {required String userCode}) async {
    final json =
        await apiClient.postJson('api/enroll/complete', <String, dynamic>{
      'user_code': userCode,
    });
    return EnrollmentStatus.fromResponse(json);
  }
}
