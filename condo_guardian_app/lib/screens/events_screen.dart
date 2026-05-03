import 'package:flutter/material.dart';

import '../core/storage/settings_store.dart';
import '../models/alert_item.dart';
import '../services/backend_service.dart';

class EventsScreen extends StatefulWidget {
  const EventsScreen({
    super.key,
    required this.backendService,
    required this.settingsStore,
    this.initialDate,
    this.onAlertResolved,
  });

  final BackendService backendService;
  final SettingsStore settingsStore;
  final DateTime? initialDate;
  final VoidCallback? onAlertResolved;

  @override
  State<EventsScreen> createState() => _EventsScreenState();
}

class _EventsScreenState extends State<EventsScreen> {
  bool _loading = true;
  String? _error;
  List<AlertItem> _events = <AlertItem>[];
  DateTime? _selectedDate;
  String? _busyAlertId;

  @override
  void initState() {
    super.initState();
    if (widget.initialDate != null) {
      _selectedDate = DateTime(
        widget.initialDate!.year,
        widget.initialDate!.month,
        widget.initialDate!.day,
      );
    }
    _loadEvents();
  }

  Future<void> _loadEvents() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final events =
          await widget.backendService.fetchEvents(localDate: _selectedDate);
      if (!mounted) {
        return;
      }
      setState(() {
        _events = events;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loading = false;
        _error = '$error';
      });
    }
  }

  Color _severityColor(String severity) {
    switch (severity.toLowerCase()) {
      case 'critical':
        return Colors.red;
      case 'warning':
        return Colors.orange;
      default:
        return Colors.blue;
    }
  }

  String _absoluteSnapshotUrl(String snapshotPath) {
    final normalizedBase = widget.settingsStore.backendBaseUrl.endsWith('/')
        ? widget.settingsStore.backendBaseUrl
        : '${widget.settingsStore.backendBaseUrl}/';
    return Uri.parse(normalizedBase).resolve(snapshotPath).toString();
  }

  Map<String, String>? get _imageHeaders {
    final token = widget.settingsStore.authToken.trim();
    if (token.isEmpty) {
      return null;
    }
    return <String, String>{'Authorization': 'Bearer $token'};
  }

  String _formatDate(DateTime dt) {
    final local = dt.toLocal();
    final date =
        '${local.year}-${local.month.toString().padLeft(2, '0')}-${local.day.toString().padLeft(2, '0')}';
    final time =
        '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
    return '$date $time';
  }

  Future<void> _resolveLinkedAlert(AlertItem event) async {
    final alertId = event.relatedAlertId;
    if (alertId == null) {
      return;
    }

    setState(() => _busyAlertId = '$alertId');
    try {
      await widget.backendService.updateAlertReview(
        '$alertId',
        reviewStatus: 'resolved',
        reviewNote: 'Resolved from mobile event history.',
      );
      await _loadEvents();
      widget.onAlertResolved?.call();
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Alert #$alertId marked resolved.')),
      );
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Resolve failed: $error')),
      );
    } finally {
      if (mounted) {
        setState(() => _busyAlertId = null);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Events')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        Text(
                          'Could not load events.',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 8),
                        Text(_error!),
                        const SizedBox(height: 12),
                        FilledButton(
                          onPressed: _loadEvents,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : _events.isEmpty
                  ? const Center(child: Text('No events at the moment.'))
                  : RefreshIndicator(
                      onRefresh: _loadEvents,
                      child: ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: _events.length,
                        itemBuilder: (context, index) {
                          final event = _events[index];
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 12),
                            child: _EventCard(
                              event: event,
                              severityColor: _severityColor(event.severity),
                              timeLabel: _formatDate(event.createdAt),
                              snapshotUrl: event.hasSnapshot
                                  ? _absoluteSnapshotUrl(event.snapshotPath)
                                  : null,
                              imageHeaders: _imageHeaders,
                              busy: event.relatedAlertId != null &&
                                  _busyAlertId == '${event.relatedAlertId}',
                              onResolveLinkedAlert: event.relatedAlertId == null
                                  ? null
                                  : () => _resolveLinkedAlert(event),
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}

class _EventCard extends StatelessWidget {
  const _EventCard({
    required this.event,
    required this.severityColor,
    required this.timeLabel,
    required this.busy,
    required this.onResolveLinkedAlert,
    this.snapshotUrl,
    this.imageHeaders,
  });

  final AlertItem event;
  final Color severityColor;
  final String timeLabel;
  final bool busy;
  final VoidCallback? onResolveLinkedAlert;
  final String? snapshotUrl;
  final Map<String, String>? imageHeaders;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;

    return Card(
      elevation: 0,
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(color: cs.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (snapshotUrl != null)
            _EventSnapshotPreview(
              imageUrl: snapshotUrl!,
              headers: imageHeaders,
              severityColor: severityColor,
            ),
          Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    _EventPill(label: 'Event #${event.id}', color: cs.primary),
                    _EventPill(
                      label: event.severity.toUpperCase(),
                      color: severityColor,
                      filled: true,
                    ),
                    if (event.relatedAlertId != null)
                      _EventPill(
                        label: 'Linked Alert #${event.relatedAlertId}',
                        color: const Color(0xFF7E57C2),
                      ),
                    if (event.hasSnapshot)
                      _EventPill(
                        label: 'Snapshot',
                        color: const Color(0xFF1E88E5),
                      ),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  event.title,
                  style: tt.titleSmall?.copyWith(fontWeight: FontWeight.w700),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                if (event.message.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(
                    event.message,
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                    style: tt.bodySmall?.copyWith(
                      color: cs.onSurfaceVariant,
                      height: 1.45,
                    ),
                  ),
                ],
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    if (event.eventCode.isNotEmpty)
                      _EventMetadataChip(
                        icon: Icons.confirmation_number_outlined,
                        label: event.eventCode,
                      ),
                    if (event.sourceNodeLabel.isNotEmpty)
                      _EventMetadataChip(
                        icon: Icons.memory_rounded,
                        label: event.sourceNodeLabel,
                      ),
                    if (event.location.isNotEmpty)
                      _EventMetadataChip(
                        icon: Icons.place_outlined,
                        label: event.location,
                      ),
                    _EventMetadataChip(
                      icon: Icons.access_time_rounded,
                      label: timeLabel,
                    ),
                  ],
                ),
                if (onResolveLinkedAlert != null) ...[
                  const SizedBox(height: 12),
                  FilledButton.tonalIcon(
                    onPressed: busy ? null : onResolveLinkedAlert,
                    icon: const Icon(Icons.task_alt_rounded, size: 17),
                    label: const Text('Resolve linked alert'),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _EventSnapshotPreview extends StatelessWidget {
  const _EventSnapshotPreview({
    required this.imageUrl,
    required this.headers,
    required this.severityColor,
  });

  final String imageUrl;
  final Map<String, String>? headers;
  final Color severityColor;

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: 16 / 9,
      child: Stack(
        fit: StackFit.expand,
        children: [
          Image.network(
            imageUrl,
            headers: headers,
            fit: BoxFit.cover,
            errorBuilder: (_, __, ___) => Container(
              color: Colors.black12,
              alignment: Alignment.center,
              child: const Text('Snapshot unavailable'),
            ),
          ),
          Positioned(
            left: 12,
            top: 12,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.black.withValues(alpha: 0.68),
                borderRadius: BorderRadius.circular(999),
                border: Border.all(color: severityColor.withValues(alpha: 0.8)),
              ),
              child: const Text(
                'Event Snapshot',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _EventPill extends StatelessWidget {
  const _EventPill({
    required this.label,
    required this.color,
    this.filled = false,
  });

  final String label;
  final Color color;
  final bool filled;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: filled ? color : color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: filled ? Colors.white : color,
          fontSize: 10,
          fontWeight: FontWeight.w800,
          letterSpacing: 0.2,
        ),
      ),
    );
  }
}

class _EventMetadataChip extends StatelessWidget {
  const _EventMetadataChip({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest.withValues(alpha: 0.58),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: cs.outlineVariant),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: cs.onSurfaceVariant),
          const SizedBox(width: 5),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 180),
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: cs.onSurfaceVariant,
                fontSize: 11,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
