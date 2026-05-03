const Map<String, String> kKnownNodeDisplayNames = <String, String>{
  'cam_indoor': 'Indoor Camera',
  'cam_door': 'Door Camera',
  'smoke_node1': 'Smoke Node 1',
  'smoke_node2': 'Smoke Node 2',
  'door_force': 'Door Sensor',
};

String nodeDisplayName(String rawNodeId) {
  final normalized = rawNodeId.trim().toLowerCase();
  if (normalized.isEmpty) {
    return rawNodeId;
  }
  return kKnownNodeDisplayNames[normalized] ?? rawNodeId;
}

String replaceKnownNodeIds(String text) {
  var output = text;
  for (final entry in kKnownNodeDisplayNames.entries) {
    final pattern =
        RegExp(r'\b' + RegExp.escape(entry.key) + r'\b', caseSensitive: false);
    output = output.replaceAllMapped(pattern, (_) => entry.value);
  }
  return output;
}

class NodeStatus {
  NodeStatus({
    required this.nodeId,
    required this.role,
    required this.room,
    required this.status,
  });

  final String nodeId;
  final String role;
  final String room;
  final String status;

  String get displayName => nodeDisplayName(nodeId);

  factory NodeStatus.fromJson(Map<String, dynamic> json) {
    final nodeId = json['node_id']?.toString() ?? json['id']?.toString() ?? '';
    final role = json['role']?.toString() ?? json['type']?.toString() ?? '';
    final room = json['room']?.toString() ?? json['location']?.toString() ?? '';

    return NodeStatus(
      nodeId: nodeId,
      role: role,
      room: room,
      status: json['status']?.toString() ?? 'unknown',
    );
  }
}
