import 'dart:async';

import 'package:flutter/material.dart';

import '../core/storage/settings_store.dart';
import '../models/alert_item.dart';
import '../models/snapshot_item.dart';
import '../services/backend_service.dart';
import '../widgets/snapshot_image_with_overlay.dart';

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
  Timer? _timer;
  bool _refreshing = false;
  bool _bulkFalseAlarmMode = false;
  bool _bulkFeedbackPending = false;
  bool _groupTraining = false;
  bool _loadingFeedbackProfiles = false;
  String _bulkFeedbackProfileName = '';
  String _searchQuery = '';
  String? _bulkFeedbackMessage;
  String? _groupTrainMessage;
  final Set<String> _bulkFalseAlarmIds = <String>{};
  List<FaceProfile> _feedbackProfiles = const <FaceProfile>[];
  late final TextEditingController _searchController;

  @override
  void initState() {
    super.initState();
    _searchController = TextEditingController();
    if (widget.initialDate != null) {
      _selectedDate = DateTime(
        widget.initialDate!.year,
        widget.initialDate!.month,
        widget.initialDate!.day,
      );
    }
    _loadEvents();
    _timer = Timer.periodic(
      Duration(seconds: _pollingSeconds),
      (_) {
        if (_busyAlertId == null) {
          unawaited(_loadEvents(silent: true));
        }
      },
    );
  }

  @override
  void dispose() {
    _timer?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  int get _pollingSeconds {
    final seconds = widget.settingsStore.pollingSeconds;
    return seconds < 1 ? 10 : seconds;
  }

  Future<void> _loadEvents({bool silent = false}) async {
    if (_refreshing) {
      return;
    }
    _refreshing = true;
    if (!silent) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }

    try {
      final events =
          await widget.backendService.fetchEvents(localDate: _selectedDate);
      if (!mounted) {
        return;
      }
      setState(() {
        _events = events;
        _loading = false;
        _error = null;
      });
    } catch (error) {
      if (!mounted || silent) {
        return;
      }
      setState(() {
        _loading = false;
        _error = '$error';
      });
    } finally {
      _refreshing = false;
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
    final baseUrl = widget.backendService.apiClient.baseUrl;
    final normalizedBase = baseUrl.endsWith('/') ? baseUrl : '$baseUrl/';
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
      await _loadEvents(silent: true);
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

  bool _isBulkEligibleEvent(AlertItem event) {
    return event.relatedAlertId != null &&
        event.hasSnapshot &&
        event.supportsIntruderFeedback &&
        !event.hasFeedbackReview;
  }

  List<AlertItem> _filteredEvents() {
    final query = _searchQuery.toLowerCase().trim();
    if (query.isEmpty) {
      return _events;
    }
    return _events.where((event) {
      return event.title.toLowerCase().contains(query) ||
          event.message.toLowerCase().contains(query) ||
          event.eventCode.toLowerCase().contains(query) ||
          event.sourceNodeLabel.toLowerCase().contains(query) ||
          event.location.toLowerCase().contains(query);
    }).toList();
  }

  Widget _buildSearchCard(int visibleCount) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: cs.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '$visibleCount event${visibleCount == 1 ? '' : 's'} shown',
            style: Theme.of(context).textTheme.labelLarge,
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _searchController,
            onChanged: (value) => setState(() => _searchQuery = value),
            decoration: const InputDecoration(
              labelText: 'Search events',
              hintText: 'Title, code, location, source node',
              prefixIcon: Icon(Icons.search_rounded, size: 20),
            ),
          ),
          if (_searchQuery.trim().isNotEmpty) ...[
            const SizedBox(height: 8),
            TextButton.icon(
              onPressed: () {
                _searchController.clear();
                setState(() => _searchQuery = '');
              },
              icon: const Icon(Icons.clear_rounded, size: 18),
              label: const Text('Clear search'),
            ),
          ],
        ],
      ),
    );
  }

  List<_EventBulkFalseAlarmTarget> _bulkTargets() {
    final targets = <_EventBulkFalseAlarmTarget>[];
    final seenAlertIds = <int>{};
    for (final event in _events) {
      if (!_isBulkEligibleEvent(event)) {
        continue;
      }
      final alertId = event.relatedAlertId;
      if (alertId == null || !seenAlertIds.add(alertId)) {
        continue;
      }
      targets.add(
        _EventBulkFalseAlarmTarget(
          key: event.id,
          alertId: alertId,
          title: event.title,
        ),
      );
    }
    return targets;
  }

  Future<void> _ensureFeedbackProfiles() async {
    if (_feedbackProfiles.isNotEmpty || _loadingFeedbackProfiles) {
      return;
    }
    setState(() {
      _loadingFeedbackProfiles = true;
      _bulkFeedbackMessage = null;
    });
    try {
      final profiles = await widget.backendService.fetchFaceProfiles();
      if (!mounted) {
        return;
      }
      setState(() {
        _feedbackProfiles = profiles;
        _bulkFeedbackProfileName = profiles.isEmpty ? '' : profiles.first.name;
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _bulkFeedbackMessage = 'Could not load authorized profiles: $error';
      });
    } finally {
      if (mounted) {
        setState(() => _loadingFeedbackProfiles = false);
      }
    }
  }

  void _toggleBulkMode() {
    setState(() {
      _bulkFalseAlarmMode = !_bulkFalseAlarmMode;
      _bulkFeedbackMessage = null;
      if (!_bulkFalseAlarmMode) {
        _bulkFalseAlarmIds.clear();
      }
    });
    if (_bulkFalseAlarmMode) {
      unawaited(_ensureFeedbackProfiles());
    }
  }

  void _toggleBulkSelection(AlertItem event) {
    if (!_isBulkEligibleEvent(event)) {
      setState(() {
        _bulkFeedbackMessage =
            'This event is not eligible for intruder false-alarm retraining.';
      });
      return;
    }
    setState(() {
      _bulkFeedbackMessage = null;
      if (_bulkFalseAlarmIds.contains(event.id)) {
        _bulkFalseAlarmIds.remove(event.id);
      } else {
        _bulkFalseAlarmIds.add(event.id);
      }
    });
  }

  Future<void> _submitBulkFalseAlarms(
    List<_EventBulkFalseAlarmTarget> selectedTargets,
  ) async {
    if (_bulkFeedbackPending) {
      return;
    }
    if (selectedTargets.isEmpty) {
      setState(() {
        _bulkFeedbackMessage = 'Select at least one eligible intruder event.';
      });
      return;
    }
    final faceName = _bulkFeedbackProfileName.trim();
    if (faceName.isEmpty) {
      setState(() {
        _bulkFeedbackMessage =
            'Select the authorized person before marking false alarms.';
      });
      return;
    }

    final confirmed = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Mark selected events as false alarms?'),
            content: Text(
              'This will import ${selectedTargets.length} linked alert snapshot(s) into $faceName for group face retraining.',
            ),
            actions: <Widget>[
              TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text('Save False Alarms'),
              ),
            ],
          ),
        ) ??
        false;
    if (!confirmed) {
      return;
    }

    setState(() {
      _bulkFeedbackPending = true;
      _bulkFeedbackMessage =
          'Saving ${selectedTargets.length} false alarm(s) for group retraining...';
    });

    var savedCount = 0;
    String? failure;
    final savedKeys = <String>{};
    for (final target in selectedTargets) {
      try {
        await widget.backendService.submitSnapshotFeedback(
          '${target.alertId}',
          verdict: 'false_positive',
          faceName: faceName,
        );
        savedCount += 1;
        savedKeys.add(target.key);
      } catch (error) {
        failure = '$error';
        break;
      }
    }

    if (!mounted) {
      return;
    }
    setState(() {
      _bulkFeedbackPending = false;
      _bulkFalseAlarmIds.removeAll(savedKeys);
      _bulkFeedbackMessage = failure == null
          ? '$savedCount false alarm${savedCount == 1 ? '' : 's'} saved for $faceName. Retrain once after reviewing all false alarms.'
          : savedCount > 0
              ? '$savedCount false alarm${savedCount == 1 ? '' : 's'} saved before an error: $failure'
              : 'Could not save selected false alarms: $failure';
    });
    await _loadEvents(silent: true);
    widget.onAlertResolved?.call();
  }

  Future<void> _runGroupRetrain() async {
    if (_groupTraining) {
      return;
    }
    setState(() {
      _groupTraining = true;
      _groupTrainMessage = 'Retraining face model from saved samples...';
    });
    try {
      final result = await widget.backendService.trainFaceModel();
      if (!mounted) {
        return;
      }
      setState(() {
        _groupTrainMessage = result.ok
            ? 'Group retrain complete. ${result.message}'.trim()
            : 'Group retrain failed. ${result.message}'.trim();
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() => _groupTrainMessage = 'Group retrain failed: $error');
    } finally {
      if (mounted) {
        setState(() => _groupTraining = false);
      }
    }
  }

  Widget _buildFalseAlarmReviewPanel({
    required List<_EventBulkFalseAlarmTarget> eligibleTargets,
    required List<_EventBulkFalseAlarmTarget> selectedTargets,
  }) {
    final cs = Theme.of(context).colorScheme;
    final selectedProfileName = _feedbackProfiles
            .any((profile) => profile.name == _bulkFeedbackProfileName)
        ? _bulkFeedbackProfileName
        : (_feedbackProfiles.isEmpty ? '' : _feedbackProfiles.first.name);

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFFFA726).withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(16),
        border:
            Border.all(color: const Color(0xFFFFA726).withValues(alpha: 0.28)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Intruder False Alarm Review',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: const Color(0xFFFFA726),
                  fontWeight: FontWeight.w800,
                ),
          ),
          const SizedBox(height: 4),
          Text(
            '${selectedTargets.length} selected of ${eligibleTargets.length} eligible linked intruder event${eligibleTargets.length == 1 ? '' : 's'}.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          if (_bulkFalseAlarmMode) ...[
            const SizedBox(height: 12),
            if (_loadingFeedbackProfiles)
              const LinearProgressIndicator(minHeight: 2)
            else if (_feedbackProfiles.isEmpty)
              Text(
                'No authorized profiles loaded.',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: cs.error,
                    ),
              )
            else
              DropdownButtonFormField<String>(
                key: ValueKey<String>(selectedProfileName),
                initialValue: selectedProfileName,
                decoration: const InputDecoration(
                  labelText: 'Authorized person',
                  prefixIcon: Icon(Icons.person_search_outlined, size: 20),
                ),
                items: _feedbackProfiles
                    .map(
                      (profile) => DropdownMenuItem<String>(
                        value: profile.name,
                        child: Text(profile.displayLabel),
                      ),
                    )
                    .toList(),
                onChanged: _bulkFeedbackPending
                    ? null
                    : (value) => setState(
                          () => _bulkFeedbackProfileName = value ?? '',
                        ),
              ),
          ],
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              OutlinedButton.icon(
                onPressed: _bulkFeedbackPending ? null : _toggleBulkMode,
                icon: Icon(
                  _bulkFalseAlarmMode
                      ? Icons.close_rounded
                      : Icons.checklist_rounded,
                  size: 18,
                ),
                label: Text(
                  _bulkFalseAlarmMode
                      ? 'Stop Selecting'
                      : 'Select Intruder Events',
                ),
              ),
              if (_bulkFalseAlarmMode)
                FilledButton.icon(
                  onPressed: _bulkFeedbackPending || selectedTargets.isEmpty
                      ? null
                      : () => _submitBulkFalseAlarms(selectedTargets),
                  icon:
                      const Icon(Icons.report_gmailerrorred_rounded, size: 18),
                  label: Text(
                    _bulkFeedbackPending
                        ? 'Saving...'
                        : 'Mark Selected False Alarm',
                  ),
                ),
              OutlinedButton.icon(
                onPressed: _groupTraining ? null : _runGroupRetrain,
                icon: const Icon(Icons.psychology_alt_outlined, size: 18),
                label: Text(
                  _groupTraining ? 'Retraining...' : 'Group Retrain Face Model',
                ),
              ),
            ],
          ),
          if (_bulkFeedbackMessage != null) ...[
            const SizedBox(height: 10),
            Text(
              _bulkFeedbackMessage!,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: const Color(0xFF9A5A00),
                    fontWeight: FontWeight.w700,
                  ),
            ),
          ],
          if (_groupTrainMessage != null) ...[
            const SizedBox(height: 8),
            Text(
              _groupTrainMessage!,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: cs.primary,
                    fontWeight: FontWeight.w700,
                  ),
            ),
          ],
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final visibleEvents = _filteredEvents();
    final bulkTargets = _bulkTargets();
    final selectedBulkTargets = bulkTargets
        .where((target) => _bulkFalseAlarmIds.contains(target.key))
        .toList();

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
                      child: ListView(
                        padding: const EdgeInsets.all(16),
                        children: [
                          _buildSearchCard(visibleEvents.length),
                          const SizedBox(height: 12),
                          _buildFalseAlarmReviewPanel(
                            eligibleTargets: bulkTargets,
                            selectedTargets: selectedBulkTargets,
                          ),
                          const SizedBox(height: 12),
                          if (visibleEvents.isEmpty)
                            const _NoMatchingEventsCard()
                          else
                            ...visibleEvents.map((event) {
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
                                  onResolveLinkedAlert:
                                      event.relatedAlertId == null
                                          ? null
                                          : () => _resolveLinkedAlert(event),
                                  selectable: _bulkFalseAlarmMode,
                                  selected:
                                      _bulkFalseAlarmIds.contains(event.id),
                                  bulkEligible: _isBulkEligibleEvent(event),
                                  onToggleSelected: () =>
                                      _toggleBulkSelection(event),
                                ),
                              );
                            }),
                        ],
                      ),
                    ),
    );
  }
}

class _EventBulkFalseAlarmTarget {
  const _EventBulkFalseAlarmTarget({
    required this.key,
    required this.alertId,
    required this.title,
  });

  final String key;
  final int alertId;
  final String title;
}

class _NoMatchingEventsCard extends StatelessWidget {
  const _NoMatchingEventsCard();

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: cs.outlineVariant),
      ),
      child: const Row(
        children: [
          Icon(Icons.search_off_rounded),
          SizedBox(width: 10),
          Expanded(child: Text('No events match the current search.')),
        ],
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
    this.selectable = false,
    this.selected = false,
    this.bulkEligible = false,
    this.onToggleSelected,
    this.snapshotUrl,
    this.imageHeaders,
  });

  final AlertItem event;
  final Color severityColor;
  final String timeLabel;
  final bool busy;
  final VoidCallback? onResolveLinkedAlert;
  final bool selectable;
  final bool selected;
  final bool bulkEligible;
  final VoidCallback? onToggleSelected;
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
              overlays: event.faceOverlays,
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
                    if (selectable)
                      _EventPill(
                        label: bulkEligible
                            ? (selected ? 'Selected' : 'Selectable')
                            : 'Not Eligible',
                        color: bulkEligible
                            ? const Color(0xFFFFA726)
                            : cs.onSurfaceVariant,
                        filled: selected,
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
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      if (selectable)
                        OutlinedButton.icon(
                          onPressed: bulkEligible ? onToggleSelected : null,
                          icon: Icon(
                            selected
                                ? Icons.check_box_rounded
                                : Icons.check_box_outline_blank_rounded,
                            size: 17,
                          ),
                          label: Text(selected ? 'Selected' : 'Select'),
                        ),
                      FilledButton.tonalIcon(
                        onPressed: busy ? null : onResolveLinkedAlert,
                        icon: const Icon(Icons.task_alt_rounded, size: 17),
                        label: const Text('Resolve linked alert'),
                      ),
                    ],
                  ),
                ] else if (selectable) ...[
                  const SizedBox(height: 12),
                  OutlinedButton.icon(
                    onPressed: bulkEligible ? onToggleSelected : null,
                    icon: Icon(
                      selected
                          ? Icons.check_box_rounded
                          : Icons.check_box_outline_blank_rounded,
                      size: 17,
                    ),
                    label: Text(selected ? 'Selected' : 'Select'),
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
    required this.overlays,
    required this.severityColor,
  });

  final String imageUrl;
  final Map<String, String>? headers;
  final List<FaceOverlay> overlays;
  final Color severityColor;

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: 16 / 9,
      child: Stack(
        fit: StackFit.expand,
        children: [
          SnapshotImageWithOverlay(
            imageUrl: imageUrl,
            headers: headers,
            overlays: overlays,
            borderRadius: BorderRadius.zero,
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
