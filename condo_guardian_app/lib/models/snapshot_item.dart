import 'node_status.dart';

class FaceOverlay {
  FaceOverlay({
    required this.x,
    required this.y,
    required this.width,
    required this.height,
    required this.classification,
    required this.label,
    this.confidence,
  });

  final int x;
  final int y;
  final int width;
  final int height;
  final String classification;
  final String label;
  final double? confidence;

  bool get isAuthorized => classification.toUpperCase() == 'AUTHORIZED';

  factory FaceOverlay.fromJson(Map<String, dynamic> json) {
    final bbox = json['bbox'];
    final values = bbox is List ? bbox : const <dynamic>[];

    int readAt(int index) {
      if (index < 0 || index >= values.length) {
        return 0;
      }
      final raw = values[index];
      if (raw is num) {
        return raw.round();
      }
      return int.tryParse(raw?.toString() ?? '') ?? 0;
    }

    final classification = json['classification']?.toString() ?? '';
    final confidenceRaw = json['confidence'];
    final confidence = confidenceRaw is num
        ? confidenceRaw.toDouble()
        : double.tryParse(confidenceRaw?.toString() ?? '');

    return FaceOverlay(
      x: readAt(0),
      y: readAt(1),
      width: readAt(2),
      height: readAt(3),
      classification: classification,
      label: json['label']?.toString() ?? classification,
      confidence: confidence,
    );
  }
}

class SnapshotItem {
  SnapshotItem({
    required this.id,
    required this.title,
    required this.message,
    required this.severity,
    required this.snapshotPath,
    required this.capturedAt,
    required this.eventCode,
    required this.faceOverlays,
    required this.recordType,
    this.sourceNode = '',
    this.location = '',
    this.recordId,
    this.linkedEventId,
    this.linkedAlertId,
    this.reviewStatus = 'needs_review',
    this.acknowledged = false,
  });

  final String id;
  final String title;
  final String message;
  final String severity;
  final String snapshotPath;
  final DateTime capturedAt;
  final String eventCode;
  final List<FaceOverlay> faceOverlays;
  final String recordType;
  final String sourceNode;
  final String location;
  final int? recordId;
  final int? linkedEventId;
  final int? linkedAlertId;
  final String reviewStatus;
  final bool acknowledged;

  String get sourceNodeLabel => nodeDisplayName(sourceNode);

  bool get isAlertRecord => recordType == 'alert';

  int? get actionableAlertId => isAlertRecord ? recordId : linkedAlertId;

  String get recordLabel {
    final fallbackId = id.isEmpty ? 'unknown' : id;
    final displayId = recordId?.toString() ?? fallbackId;
    return '${isAlertRecord ? 'Alert' : 'Event'} #$displayId';
  }

  String get linkedRecordLabel {
    if (isAlertRecord && linkedEventId != null) {
      return 'Linked Event #$linkedEventId';
    }
    if (!isAlertRecord && linkedAlertId != null) {
      return 'Linked Alert #$linkedAlertId';
    }
    return '';
  }

  bool get isTerminalReviewStatus {
    switch (reviewStatus.toLowerCase()) {
      case 'false_positive':
      case 'resolved':
      case 'archived':
        return true;
      default:
        return false;
    }
  }

  bool get isPersonSnapshot {
    final normalizedEventCode = eventCode.toUpperCase();
    if (faceOverlays.isNotEmpty || normalizedEventCode == 'AUTHORIZED_ENTRY') {
      return true;
    }

    final loweredTitle = title.toLowerCase();
    return loweredTitle.contains('authorized') ||
        loweredTitle.contains('non-authorized');
  }

  static int? _optionalInt(dynamic value) {
    if (value == null || value.toString().trim().isEmpty) {
      return null;
    }
    if (value is int) {
      return value;
    }
    return int.tryParse(value.toString());
  }

  factory SnapshotItem.fromJson(
    Map<String, dynamic> json, {
    String recordType = 'alert',
  }) {
    final timestampRaw =
        json['timestamp']?.toString() ?? json['created_at']?.toString() ?? '';
    final message = json['message']?.toString();
    final description = json['description']?.toString();
    final normalizedRecordType = recordType == 'event' ? 'event' : 'alert';
    final overlaysRaw = json['face_overlays'];
    final overlays = overlaysRaw is List
        ? overlaysRaw
            .whereType<Map<String, dynamic>>()
            .map(FaceOverlay.fromJson)
            .where((overlay) => overlay.width > 0 && overlay.height > 0)
            .toList()
        : <FaceOverlay>[];

    return SnapshotItem(
      id: json['id']?.toString() ?? '',
      title: replaceKnownNodeIds(json['title']?.toString() ?? 'Snapshot'),
      message: replaceKnownNodeIds(
        (message != null && message.isNotEmpty) ? message : (description ?? ''),
      ),
      severity: json['severity']?.toString() ?? 'info',
      snapshotPath: json['snapshot_path']?.toString() ?? '',
      capturedAt: DateTime.tryParse(timestampRaw) ?? DateTime.now(),
      eventCode: json['event_code']?.toString() ?? '',
      faceOverlays: overlays,
      recordType: normalizedRecordType,
      sourceNode: replaceKnownNodeIds(json['source_node']?.toString() ?? ''),
      location: json['location']?.toString() ?? '',
      recordId: _optionalInt(json['id']),
      linkedEventId: _optionalInt(json['event_id'] ?? json['eventId']),
      linkedAlertId:
          _optionalInt(json['related_alert_id'] ?? json['relatedAlertId']),
      reviewStatus: json['review_status']?.toString() ?? 'needs_review',
      acknowledged: json['acknowledged'] == true,
    );
  }
}
