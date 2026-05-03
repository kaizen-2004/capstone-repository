import 'alert_item.dart';
import 'node_status.dart';
import 'sensor_reading.dart';

class SystemSnapshot {
  SystemSnapshot({
    required this.systemState,
    required this.sensorReadings,
    required this.nodes,
    required this.activeAlerts,
  });

  final String systemState;
  final List<SensorReading> sensorReadings;
  final List<NodeStatus> nodes;
  final List<AlertItem> activeAlerts;

  factory SystemSnapshot.fromJson(Map<String, dynamic> json) {
    final sensorList =
        (json['sensor_readings'] as List<dynamic>? ?? <dynamic>[])
            .map((item) => SensorReading.fromJson(item as Map<String, dynamic>))
            .toList();
    final nodeList = (json['nodes'] as List<dynamic>? ?? <dynamic>[])
        .map((item) => NodeStatus.fromJson(item as Map<String, dynamic>))
        .toList();
    final alertList = (json['active_alerts'] as List<dynamic>? ?? <dynamic>[])
        .map((item) => AlertItem.fromJson(item as Map<String, dynamic>))
        .toList();

    return SystemSnapshot(
      systemState: json['system_state']?.toString() ?? 'Unknown',
      sensorReadings: sensorList,
      nodes: nodeList,
      activeAlerts: alertList,
    );
  }
}
