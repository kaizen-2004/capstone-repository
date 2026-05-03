import 'node_status.dart';

class AlertItem {
  AlertItem({
    required this.id,
    required this.title,
    required this.message,
    required this.severity,
    required this.createdAt,
    this.acknowledged = false,
    this.eventId,
    this.relatedAlertId,
    this.eventCode = '',
    this.sourceNode = '',
    this.location = '',
    this.snapshotPath = '',
    this.reviewStatus = 'needs_review',
    this.reviewNote = '',
    this.reviewedBy = '',
    this.reviewedAt,
  });

  final String id;
  final String title;
  final String message;
  final String severity;
  final DateTime createdAt;
  final bool acknowledged;
  final int? eventId;
  final int? relatedAlertId;
  final String eventCode;
  final String sourceNode;
  final String location;
  final String snapshotPath;
  final String reviewStatus;
  final String reviewNote;
  final String reviewedBy;
  final DateTime? reviewedAt;

  String get sourceNodeLabel => nodeDisplayName(sourceNode);

  bool get hasSnapshot => snapshotPath.trim().isNotEmpty;

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

  static int? _optionalInt(dynamic value) {
    if (value == null || value.toString().trim().isEmpty) {
      return null;
    }
    if (value is int) {
      return value;
    }
    return int.tryParse(value.toString());
  }

  factory AlertItem.fromJson(Map<String, dynamic> json) {
    final message = json['message']?.toString();
    final description = json['description']?.toString();
    final createdAtRaw =
        json['created_at']?.toString() ?? json['timestamp']?.toString() ?? '';
    final reviewedAtRaw = json['reviewed_at']?.toString() ??
        json['reviewed_ts']?.toString() ??
        '';

    final rawTitle = json['title']?.toString() ?? 'Alert';
    final resolvedMessage =
        (message != null && message.isNotEmpty) ? message : (description ?? '');

    return AlertItem(
      id: json['id']?.toString() ?? '',
      title: replaceKnownNodeIds(rawTitle),
      message: replaceKnownNodeIds(resolvedMessage),
      severity: json['severity']?.toString() ?? 'info',
      createdAt: DateTime.tryParse(createdAtRaw) ?? DateTime.now(),
      acknowledged: json['acknowledged'] == true,
      eventId: _optionalInt(json['event_id'] ?? json['eventId']),
      relatedAlertId:
          _optionalInt(json['related_alert_id'] ?? json['relatedAlertId']),
      eventCode:
          json['event_code']?.toString() ?? json['type']?.toString() ?? '',
      sourceNode: replaceKnownNodeIds(json['source_node']?.toString() ?? ''),
      location: replaceKnownNodeIds(json['location']?.toString() ?? ''),
      snapshotPath: json['snapshot_path']?.toString() ?? '',
      reviewStatus: json['review_status']?.toString() ?? 'needs_review',
      reviewNote: json['review_note']?.toString() ?? '',
      reviewedBy: json['reviewed_by']?.toString() ?? '',
      reviewedAt: DateTime.tryParse(reviewedAtRaw),
    );
  }
}
