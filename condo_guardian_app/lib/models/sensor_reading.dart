class SensorReading {
  SensorReading({
    required this.label,
    required this.value,
    required this.unit,
    required this.status,
  });

  final String label;
  final String value;
  final String unit;
  final String status;

  factory SensorReading.fromJson(Map<String, dynamic> json) {
    final label = json['label']?.toString() ??
        json['name']?.toString() ??
        'Unknown Sensor';
    final value = json['value']?.toString() ?? json['note']?.toString() ?? '--';
    final unit = json['unit']?.toString() ?? '';

    return SensorReading(
      label: label,
      value: value,
      unit: unit,
      status: json['status']?.toString() ?? 'unknown',
    );
  }
}
