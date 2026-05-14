import 'dart:async';

import 'package:flutter/material.dart';

import '../core/storage/settings_store.dart';
import '../models/alert_item.dart';
import '../models/snapshot_item.dart';
import '../services/backend_service.dart';
import '../widgets/snapshot_image_with_overlay.dart';

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({
    super.key,
    required this.backendService,
    required this.pollingSeconds,
    required this.settingsStore,
    this.onAlertAcknowledged,
  });

  final BackendService backendService;
  final int pollingSeconds;
  final SettingsStore settingsStore;
  final VoidCallback? onAlertAcknowledged;

  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  List<AlertItem> _alerts = [];
  List<SnapshotItem> _snapshots = [];
  bool _loading = true;
  String? _error;
  Timer? _timer;
  DateTime? _selectedDate;
  String? _busyAlertId;
  DateTime? _lastUpdated;
  bool _refreshing = false;
  bool _historyFiltersOpen = false;
  String _historySearchQuery = '';
  String _selectedSeverity = 'all';
  String _selectedType = 'all';
  late final TextEditingController _historySearchController;

  @override
  void initState() {
    super.initState();
    _historySearchController = TextEditingController();
    _loadAlerts();
    _startPolling();
  }

  @override
  void didUpdateWidget(covariant AlertsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.pollingSeconds != widget.pollingSeconds) {
      _startPolling();
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _historySearchController.dispose();
    super.dispose();
  }

  int get _pollingSeconds =>
      widget.pollingSeconds < 1 ? 10 : widget.pollingSeconds;

  void _startPolling() {
    _timer?.cancel();
    _timer = Timer.periodic(
      Duration(seconds: _pollingSeconds),
      (_) => _loadAlerts(silent: true),
    );
  }

  Future<void> _loadAlerts({bool silent = false}) async {
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
      final alertsFuture = widget.backendService.fetchAlerts();
      final snapshotsFuture =
          widget.backendService.fetchSnapshots(localDate: _selectedDate);
      final alerts = await alertsFuture;
      final snapshots = await snapshotsFuture;
      if (mounted) {
        setState(() {
          _alerts = alerts;
          _snapshots = snapshots;
          _loading = false;
          _error = null;
          _lastUpdated = DateTime.now();
        });
      }
    } catch (error) {
      if (mounted && !silent) {
        setState(() {
          _loading = false;
          _error = '$error';
        });
      }
    } finally {
      _refreshing = false;
    }
  }

  Future<void> _acknowledge(String alertId) async {
    setState(() => _busyAlertId = alertId);
    try {
      await widget.backendService.acknowledgeAlert(alertId);
      await _loadAlerts(silent: true);
      widget.onAlertAcknowledged?.call();
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Acknowledge failed: $error')),
      );
    } finally {
      if (mounted) {
        setState(() => _busyAlertId = null);
      }
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

  DateTime _normalizeDate(DateTime value) {
    return DateTime(value.year, value.month, value.day);
  }

  bool _isSameDate(DateTime a, DateTime b) {
    return a.year == b.year && a.month == b.month && a.day == b.day;
  }

  String _calendarLabel(DateTime date) {
    const months = <String>[
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    final month = months[date.month - 1];
    return '$month ${date.day}, ${date.year}';
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate ?? now,
      firstDate: DateTime(now.year - 5, 1, 1),
      lastDate: DateTime(now.year + 1, 12, 31),
      helpText: 'Filter snapshot history by date',
      confirmText: 'Apply',
    );
    if (picked == null) {
      return;
    }

    final nextDate = _normalizeDate(picked);
    if (_selectedDate != null && _isSameDate(_selectedDate!, nextDate)) {
      return;
    }

    setState(() => _selectedDate = nextDate);
    await _loadAlerts();
  }

  Future<void> _clearDateFilter() async {
    if (_selectedDate == null) {
      return;
    }
    setState(() => _selectedDate = null);
    await _loadAlerts();
  }

  Widget _buildHistoryControls() {
    final cs = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: cs.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: cs.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextField(
            controller: _historySearchController,
            onChanged: (value) => setState(() => _historySearchQuery = value),
            textInputAction: TextInputAction.search,
            decoration: const InputDecoration(
              prefixIcon: Icon(Icons.search_rounded),
              labelText: 'Search snapshot history',
              hintText: 'Code, title, location, source node',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              _DateFilterBar(
                selectedDate: _selectedDate,
                onPickDate: _pickDate,
                onClearDate: _clearDateFilter,
                dateLabelBuilder: _calendarLabel,
              ),
              OutlinedButton.icon(
                onPressed: () => setState(
                  () => _historyFiltersOpen = !_historyFiltersOpen,
                ),
                icon: const Icon(Icons.filter_list_rounded, size: 18),
                label: Text(
                  _historyFiltersOpen ? 'Hide filters' : 'More filters',
                ),
              ),
              if (_hasHistoryFilters)
                TextButton(
                  onPressed: _clearHistoryFilters,
                  child: const Text('Clear filters'),
                ),
            ],
          ),
          if (_historyFiltersOpen) ...[
            const SizedBox(height: 10),
            Column(
              children: [
                _FilterDropdown(
                  label: 'Severity',
                  value: _selectedSeverity,
                  items: const <String, String>{
                    'all': 'All severities',
                    'critical': 'Critical',
                    'warning': 'Warning',
                    'normal': 'Normal',
                    'info': 'Info',
                  },
                  onChanged: (value) => setState(
                    () => _selectedSeverity = value,
                  ),
                ),
                const SizedBox(height: 10),
                _FilterDropdown(
                  label: 'Type',
                  value: _selectedType,
                  items: const <String, String>{
                    'all': 'All types',
                    'intruder': 'Intruder',
                    'fire': 'Fire',
                    'sensor': 'Sensor',
                    'authorized': 'Authorized',
                    'system': 'System',
                  },
                  onChanged: (value) => setState(() => _selectedType = value),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  ({Color bg, Color border, Color text, IconData icon}) _severityStyle(
    String severity,
  ) {
    switch (severity.toLowerCase()) {
      case 'critical':
        return (
          bg: const Color(0xFFEF5350).withValues(alpha: 0.10),
          border: const Color(0xFFEF5350).withValues(alpha: 0.35),
          text: const Color(0xFFEF5350),
          icon: Icons.error_rounded,
        );
      case 'warning':
        return (
          bg: const Color(0xFFFFA726).withValues(alpha: 0.10),
          border: const Color(0xFFFFA726).withValues(alpha: 0.35),
          text: const Color(0xFFFFA726),
          icon: Icons.warning_rounded,
        );
      default:
        return (
          bg: const Color(0xFF1E88E5).withValues(alpha: 0.10),
          border: const Color(0xFF1E88E5).withValues(alpha: 0.35),
          text: const Color(0xFF1E88E5),
          icon: Icons.info_rounded,
        );
    }
  }

  String _formatDate(DateTime dt) {
    final now = DateTime.now();
    final diff = now.difference(dt);
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inHours < 1) return '${diff.inMinutes}m ago';
    if (diff.inDays < 1) return '${diff.inHours}h ago';
    return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')}';
  }

  String _formatClock(DateTime value) {
    final local = value.toLocal();
    return '${local.hour.toString().padLeft(2, '0')}:'
        '${local.minute.toString().padLeft(2, '0')}:'
        '${local.second.toString().padLeft(2, '0')}';
  }

  Widget _buildAutoRefreshStatus() {
    final suffix =
        _lastUpdated == null ? '' : ' • updated ${_formatClock(_lastUpdated!)}';
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 0, 4, 8),
      child: Text(
        'Auto-refreshing every $_pollingSeconds sec$suffix',
        style: Theme.of(context).textTheme.bodySmall,
      ),
    );
  }

  bool get _hasHistoryFilters =>
      _historySearchQuery.trim().isNotEmpty ||
      _selectedDate != null ||
      _selectedSeverity != 'all' ||
      _selectedType != 'all';

  void _clearHistoryFilters() {
    _historySearchController.clear();
    setState(() {
      _historySearchQuery = '';
      _selectedDate = null;
      _selectedSeverity = 'all';
      _selectedType = 'all';
    });
    unawaited(_loadAlerts());
  }

  String _snapshotType(SnapshotItem snapshot) {
    final eventCode = snapshot.eventCode.toUpperCase();
    final text = '${snapshot.title} ${snapshot.message}'.toLowerCase();
    if (eventCode.contains('FIRE') ||
        eventCode.contains('SMOKE') ||
        text.contains('fire') ||
        text.contains('smoke')) {
      return 'fire';
    }
    if (eventCode.contains('AUTHORIZED')) {
      return 'authorized';
    }
    if (eventCode.contains('INTRUDER') ||
        eventCode.contains('UNKNOWN') ||
        text.contains('intruder') ||
        text.contains('non-authorized')) {
      return 'intruder';
    }
    if (eventCode.contains('SENSOR') ||
        eventCode.contains('CAMERA') ||
        text.contains('sensor') ||
        text.contains('camera')) {
      return 'sensor';
    }
    return 'system';
  }

  String _displaySnapshotTitle(SnapshotItem snapshot) {
    return snapshot.isPersonSnapshot ? 'Person Detected' : snapshot.title;
  }

  List<AlertItem> get _activeAlerts {
    final active = _alerts.where((alert) => !alert.acknowledged).toList()
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return active;
  }

  List<SnapshotItem> _snapshotHistory(List<AlertItem> activeAlerts) {
    final activeSnapshotPaths = activeAlerts
        .map((alert) => alert.snapshotPath.trim())
        .where((path) => path.isNotEmpty)
        .toSet();
    final query = _historySearchQuery.toLowerCase().trim();

    return _snapshots.where((snapshot) {
      final snapshotPath = snapshot.snapshotPath.trim();
      if (snapshotPath.isEmpty || activeSnapshotPaths.contains(snapshotPath)) {
        return false;
      }
      final matchesSearch = query.isEmpty ||
          snapshot.title.toLowerCase().contains(query) ||
          snapshot.message.toLowerCase().contains(query) ||
          snapshot.eventCode.toLowerCase().contains(query) ||
          snapshot.sourceNodeLabel.toLowerCase().contains(query) ||
          snapshot.location.toLowerCase().contains(query) ||
          snapshot.recordLabel.toLowerCase().contains(query);
      final matchesSeverity = _selectedSeverity == 'all' ||
          snapshot.severity.toLowerCase() == _selectedSeverity;
      final matchesType =
          _selectedType == 'all' || _snapshotType(snapshot) == _selectedType;
      return matchesSearch && matchesSeverity && matchesType;
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return _ErrorState(error: _error!, onRetry: () => _loadAlerts());
    }

    final active = _activeAlerts;
    final history = _snapshotHistory(active);

    if (active.isEmpty && history.isEmpty && !_hasHistoryFilters) {
      return RefreshIndicator(
        onRefresh: _loadAlerts,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 24, 16, 24),
          children: [
            _buildAutoRefreshStatus(),
            const SizedBox(height: 96),
            const _EmptyState(),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadAlerts,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        children: [
          _buildAutoRefreshStatus(),
          const SizedBox(height: 8),
          _SectionLabel(
              label: 'Active Alerts', count: active.length, isActive: true),
          const SizedBox(height: 8),
          if (active.isEmpty)
            const _NoActiveAlertsCard()
          else
            ...active.map(
              (alert) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _ActiveAlertCard(
                  alert: alert,
                  style: _severityStyle(alert.severity),
                  timeLabel: _formatDate(alert.createdAt),
                  snapshotUrl: alert.hasSnapshot
                      ? _absoluteSnapshotUrl(alert.snapshotPath)
                      : null,
                  imageHeaders: _imageHeaders,
                  busy: _busyAlertId == alert.id,
                  onAcknowledge: () => _acknowledge(alert.id),
                ),
              ),
            ),
          const SizedBox(height: 20),
          _SectionLabel(
            label: 'Snapshot History',
            count: history.length,
            isActive: false,
          ),
          const SizedBox(height: 8),
          _buildHistoryControls(),
          const SizedBox(height: 12),
          if (history.isEmpty)
            const _NoSnapshotHistoryCard()
          else
            ...history.map(
              (snapshot) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _SnapshotHistoryCard(
                  snapshot: snapshot,
                  title: _displaySnapshotTitle(snapshot),
                  severityColor: _severityStyle(snapshot.severity).text,
                  timeLabel: _formatDate(snapshot.capturedAt),
                  snapshotUrl: _absoluteSnapshotUrl(snapshot.snapshotPath),
                  imageHeaders: _imageHeaders,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _DateFilterBar extends StatelessWidget {
  const _DateFilterBar({
    required this.selectedDate,
    required this.onPickDate,
    required this.onClearDate,
    required this.dateLabelBuilder,
  });

  final DateTime? selectedDate;
  final VoidCallback onPickDate;
  final VoidCallback onClearDate;
  final String Function(DateTime date) dateLabelBuilder;

  @override
  Widget build(BuildContext context) {
    final hasFilter = selectedDate != null;
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        OutlinedButton.icon(
          onPressed: onPickDate,
          icon: const Icon(Icons.calendar_month_outlined, size: 18),
          label: Text(
            hasFilter
                ? 'Date: ${dateLabelBuilder(selectedDate!)}'
                : 'Filter history by date',
          ),
        ),
        if (hasFilter)
          TextButton(
            onPressed: onClearDate,
            child: const Text('Clear'),
          ),
      ],
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel({
    required this.label,
    required this.count,
    required this.isActive,
  });

  final String label;
  final int count;
  final bool isActive;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final color = isActive ? const Color(0xFFFFA726) : cs.primary;
    return Row(
      children: [
        Text(
          label.toUpperCase(),
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w700,
            color: color,
            letterSpacing: 1.2,
          ),
        ),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 1),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.14),
            borderRadius: BorderRadius.circular(20),
          ),
          child: Text(
            '$count',
            style: TextStyle(
                color: color, fontSize: 11, fontWeight: FontWeight.w700),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(child: Divider(color: cs.outlineVariant)),
      ],
    );
  }
}

class _FilterDropdown extends StatelessWidget {
  const _FilterDropdown({
    required this.label,
    required this.value,
    required this.items,
    required this.onChanged,
  });

  final String label;
  final String value;
  final Map<String, String> items;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return DropdownButtonFormField<String>(
      initialValue: value,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
      items: items.entries
          .map(
            (entry) => DropdownMenuItem<String>(
              value: entry.key,
              child: Text(entry.value),
            ),
          )
          .toList(),
      onChanged: (value) {
        if (value != null) {
          onChanged(value);
        }
      },
    );
  }
}

class _NoActiveAlertsCard extends StatelessWidget {
  const _NoActiveAlertsCard();

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF26A69A).withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(18),
        border:
            Border.all(color: const Color(0xFF26A69A).withValues(alpha: 0.28)),
      ),
      child: Row(
        children: [
          const Icon(Icons.check_circle_outline_rounded,
              color: Color(0xFF26A69A)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'No active alerts need acknowledgement right now.',
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(color: cs.onSurface),
            ),
          ),
        ],
      ),
    );
  }
}

class _NoSnapshotHistoryCard extends StatelessWidget {
  const _NoSnapshotHistoryCard();

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: cs.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: cs.outlineVariant),
      ),
      child: const Row(
        children: [
          Icon(Icons.photo_library_outlined),
          SizedBox(width: 10),
          Expanded(child: Text('No snapshots match the current filters.')),
        ],
      ),
    );
  }
}

class _SnapshotHistoryCard extends StatelessWidget {
  const _SnapshotHistoryCard({
    required this.snapshot,
    required this.title,
    required this.severityColor,
    required this.timeLabel,
    required this.snapshotUrl,
    required this.imageHeaders,
  });

  final SnapshotItem snapshot;
  final String title;
  final Color severityColor;
  final String timeLabel;
  final String snapshotUrl;
  final Map<String, String>? imageHeaders;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;
    return Container(
      decoration: BoxDecoration(
        color: cs.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: cs.outlineVariant),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _AlertSnapshotPreview(
            imageUrl: snapshotUrl,
            headers: imageHeaders,
            overlays: snapshot.faceOverlays,
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
                    _StatusPill(label: snapshot.recordLabel, color: cs.primary),
                    _StatusPill(
                      label: snapshot.severity.toUpperCase(),
                      color: severityColor,
                      filled: true,
                    ),
                    _StatusPill(
                      label: snapshot.isAlertRecord
                          ? 'Acknowledged Alert'
                          : 'Event Snapshot',
                      color: const Color(0xFF1E88E5),
                    ),
                    if (snapshot.linkedRecordLabel.isNotEmpty)
                      _StatusPill(
                        label: snapshot.linkedRecordLabel,
                        color: const Color(0xFF7E57C2),
                      ),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  title,
                  style: tt.titleSmall?.copyWith(fontWeight: FontWeight.w700),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                if (snapshot.message.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(
                    snapshot.message,
                    style: tt.bodySmall?.copyWith(
                      color: cs.onSurfaceVariant,
                      height: 1.45,
                    ),
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    if (snapshot.eventCode.isNotEmpty)
                      _MetadataChip(
                        icon: Icons.confirmation_number_outlined,
                        label: snapshot.eventCode,
                      ),
                    if (snapshot.sourceNodeLabel.isNotEmpty)
                      _MetadataChip(
                        icon: Icons.memory_rounded,
                        label: snapshot.sourceNodeLabel,
                      ),
                    if (snapshot.location.isNotEmpty)
                      _MetadataChip(
                        icon: Icons.place_outlined,
                        label: snapshot.location,
                      ),
                    _MetadataChip(
                      icon: Icons.access_time_rounded,
                      label: timeLabel,
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ActiveAlertCard extends StatelessWidget {
  const _ActiveAlertCard({
    required this.alert,
    required this.style,
    required this.timeLabel,
    required this.busy,
    required this.onAcknowledge,
    this.snapshotUrl,
    this.imageHeaders,
  });

  final AlertItem alert;
  final ({Color bg, Color border, Color text, IconData icon}) style;
  final String timeLabel;
  final bool busy;
  final VoidCallback onAcknowledge;
  final String? snapshotUrl;
  final Map<String, String>? imageHeaders;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;

    return Container(
      decoration: BoxDecoration(
        color: cs.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: style.border, width: 1.4),
        boxShadow: [
          BoxShadow(
            color: cs.shadow.withValues(alpha: 0.06),
            blurRadius: 16,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (snapshotUrl != null)
            _AlertSnapshotPreview(
              imageUrl: snapshotUrl!,
              headers: imageHeaders,
              overlays: alert.faceOverlays,
              severityColor: style.text,
            )
          else
            _SnapshotFallbackPreview(severityColor: style.text),
          Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    _StatusPill(label: 'Alert #${alert.id}', color: cs.primary),
                    _StatusPill(
                      label: alert.severity.toUpperCase(),
                      color: style.text,
                      filled: true,
                    ),
                    if (alert.eventId != null)
                      _StatusPill(
                        label: 'Linked Event #${alert.eventId}',
                        color: const Color(0xFF7E57C2),
                      ),
                  ],
                ),
                const SizedBox(height: 10),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(style.icon, size: 18, color: style.text),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        alert.title,
                        style: tt.titleSmall?.copyWith(
                          fontWeight: FontWeight.w700,
                          color: cs.onSurface,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
                if (alert.message.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    alert.message,
                    style: tt.bodySmall?.copyWith(
                      height: 1.45,
                      color: cs.onSurfaceVariant,
                    ),
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    if (alert.eventCode.isNotEmpty)
                      _MetadataChip(
                        icon: Icons.confirmation_number_outlined,
                        label: alert.eventCode,
                      ),
                    if (alert.sourceNodeLabel.isNotEmpty)
                      _MetadataChip(
                        icon: Icons.memory_rounded,
                        label: alert.sourceNodeLabel,
                      ),
                    if (alert.location.isNotEmpty)
                      _MetadataChip(
                        icon: Icons.place_outlined,
                        label: alert.location,
                      ),
                    _MetadataChip(
                      icon: Icons.access_time_rounded,
                      label: timeLabel,
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: busy ? null : onAcknowledge,
                  icon: const Icon(Icons.done_rounded, size: 17),
                  label: Text(busy ? 'Acknowledging...' : 'Acknowledge'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SnapshotFallbackPreview extends StatelessWidget {
  const _SnapshotFallbackPreview({required this.severityColor});

  final Color severityColor;

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: 16 / 9,
      child: Container(
        color: Colors.black12,
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.image_not_supported_outlined,
                  size: 42, color: severityColor),
              const SizedBox(height: 8),
              const Text('Snapshot unavailable'),
            ],
          ),
        ),
      ),
    );
  }
}

class _AlertSnapshotPreview extends StatelessWidget {
  const _AlertSnapshotPreview({
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
                border: Border.all(
                  color: severityColor.withValues(alpha: 0.8),
                ),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.photo_camera_outlined,
                      color: Colors.white, size: 14),
                  SizedBox(width: 5),
                  Text(
                    'Snapshot',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({
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

class _MetadataChip extends StatelessWidget {
  const _MetadataChip({required this.icon, required this.label});

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

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.error, required this.onRetry});

  final String error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.wifi_off_rounded,
                size: 48, color: cs.error.withValues(alpha: 0.7)),
            const SizedBox(height: 16),
            Text(
              'Could not load alerts',
              style: Theme.of(context).textTheme.titleLarge,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              error,
              style: Theme.of(context).textTheme.bodySmall,
              textAlign: TextAlign.center,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh_rounded, size: 18),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              color: const Color(0xFF26A69A).withValues(alpha: 0.12),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.check_circle_outline_rounded,
              size: 32,
              color: Color(0xFF26A69A),
            ),
          ),
          const SizedBox(height: 16),
          Text('All clear', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 6),
          Text(
            'No alerts at this time.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ],
      ),
    );
  }
}
