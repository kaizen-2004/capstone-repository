import 'dart:async';

import 'package:flutter/material.dart';

import '../core/storage/settings_store.dart';
import '../models/alert_item.dart';
import '../services/backend_service.dart';
import 'events_screen.dart';
import 'snapshots_screen.dart';

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
  bool _loading = true;
  String? _error;
  Timer? _timer;
  DateTime? _selectedDate;
  String? _busyAlertId;

  @override
  void initState() {
    super.initState();
    _loadAlerts();
    _timer = Timer.periodic(
      Duration(seconds: widget.pollingSeconds),
      (_) => _loadAlerts(silent: true),
    );
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _loadAlerts({bool silent = false}) async {
    if (!silent) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final alerts =
          await widget.backendService.fetchAlerts(localDate: _selectedDate);
      if (mounted) {
        setState(() {
          _alerts = alerts;
          _loading = false;
          _error = null;
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = '$error';
        });
      }
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

  Future<void> _resolveAlert(String alertId) async {
    setState(() => _busyAlertId = alertId);
    try {
      await widget.backendService.updateAlertReview(
        alertId,
        reviewStatus: 'resolved',
        reviewNote: 'Resolved from mobile app.',
      );
      await _loadAlerts(silent: true);
      widget.onAlertAcknowledged?.call();
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Alert marked resolved.')),
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

  Future<void> _openEvents() async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => EventsScreen(
          backendService: widget.backendService,
          settingsStore: widget.settingsStore,
          initialDate: _selectedDate,
          onAlertResolved: widget.onAlertAcknowledged,
        ),
      ),
    );
  }

  Future<void> _openSnapshots() async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => SnapshotsScreen(
          backendService: widget.backendService,
          settingsStore: widget.settingsStore,
          initialDate: _selectedDate,
          onAlertResolved: widget.onAlertAcknowledged,
        ),
      ),
    );
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
      helpText: 'Filter alerts by date',
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

  Widget _buildTopControls() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _IncidentSwitcher(
          onOpenEvents: _openEvents,
          onOpenSnapshots: _openSnapshots,
        ),
        _DateFilterBar(
          selectedDate: _selectedDate,
          onPickDate: _pickDate,
          onClearDate: _clearDateFilter,
          dateLabelBuilder: _calendarLabel,
        ),
      ],
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

  String _formatReviewStatusLabel(String value) {
    final words = value.replaceAll('_', ' ').trim().split(RegExp(r'\s+'));
    return words
        .where((word) => word.isNotEmpty)
        .map((word) => '${word[0].toUpperCase()}${word.substring(1)}')
        .join(' ');
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Column(
        children: [
          _buildTopControls(),
          const Expanded(child: Center(child: CircularProgressIndicator())),
        ],
      );
    }

    if (_error != null) {
      return Column(
        children: [
          _buildTopControls(),
          Expanded(
            child: _ErrorState(error: _error!, onRetry: () => _loadAlerts()),
          ),
        ],
      );
    }

    if (_alerts.isEmpty) {
      return Column(
        children: [
          _buildTopControls(),
          const Expanded(child: _EmptyState()),
        ],
      );
    }

    final active = _alerts
        .where((alert) => !alert.acknowledged && !alert.isTerminalReviewStatus)
        .toList();
    final acked = _alerts
        .where((alert) => alert.acknowledged || alert.isTerminalReviewStatus)
        .toList();

    return RefreshIndicator(
      onRefresh: _loadAlerts,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        children: [
          _buildTopControls(),
          const SizedBox(height: 8),
          if (active.isNotEmpty) ...[
            _SectionLabel(
                label: 'Review Queue', count: active.length, isActive: true),
            const SizedBox(height: 8),
            ...active.map(
              (alert) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _AlertCard(
                  alert: alert,
                  style: _severityStyle(alert.severity),
                  timeLabel: _formatDate(alert.createdAt),
                  reviewStatusLabel:
                      _formatReviewStatusLabel(alert.reviewStatus),
                  snapshotUrl: alert.hasSnapshot
                      ? _absoluteSnapshotUrl(alert.snapshotPath)
                      : null,
                  imageHeaders: _imageHeaders,
                  busy: _busyAlertId == alert.id,
                  onAcknowledge: () => _acknowledge(alert.id),
                  onResolve: () => _resolveAlert(alert.id),
                ),
              ),
            ),
            const SizedBox(height: 8),
          ],
          if (acked.isNotEmpty) ...[
            _SectionLabel(
              label: 'Reviewed / Acknowledged',
              count: acked.length,
              isActive: false,
            ),
            const SizedBox(height: 8),
            ...acked.map(
              (alert) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: _AlertCard(
                  alert: alert,
                  style: _severityStyle(alert.severity),
                  timeLabel: _formatDate(alert.createdAt),
                  reviewStatusLabel:
                      _formatReviewStatusLabel(alert.reviewStatus),
                  snapshotUrl: alert.hasSnapshot
                      ? _absoluteSnapshotUrl(alert.snapshotPath)
                      : null,
                  imageHeaders: _imageHeaders,
                  busy: _busyAlertId == alert.id,
                  onAcknowledge: null,
                  onResolve: null,
                  dimmed: true,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _IncidentSwitcher extends StatelessWidget {
  const _IncidentSwitcher({
    required this.onOpenEvents,
    required this.onOpenSnapshots,
  });

  final VoidCallback onOpenEvents;
  final VoidCallback onOpenSnapshots;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(0, 8, 0, 8),
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          const FilledButton.tonal(onPressed: null, child: Text('Alerts')),
          OutlinedButton(onPressed: onOpenEvents, child: const Text('Events')),
          OutlinedButton(
            onPressed: onOpenSnapshots,
            child: const Text('Snapshots'),
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
    return Padding(
      padding: const EdgeInsets.fromLTRB(0, 0, 0, 8),
      child: Wrap(
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
                  : 'Filter by date',
            ),
          ),
          if (hasFilter)
            TextButton(
              onPressed: onClearDate,
              child: const Text('Clear'),
            ),
        ],
      ),
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

class _AlertCard extends StatelessWidget {
  const _AlertCard({
    required this.alert,
    required this.style,
    required this.timeLabel,
    required this.reviewStatusLabel,
    required this.busy,
    required this.onAcknowledge,
    required this.onResolve,
    this.snapshotUrl,
    this.imageHeaders,
    this.dimmed = false,
  });

  final AlertItem alert;
  final ({Color bg, Color border, Color text, IconData icon}) style;
  final String timeLabel;
  final String reviewStatusLabel;
  final bool busy;
  final VoidCallback? onAcknowledge;
  final VoidCallback? onResolve;
  final String? snapshotUrl;
  final Map<String, String>? imageHeaders;
  final bool dimmed;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;

    return Opacity(
      opacity: dimmed ? 0.55 : 1.0,
      child: Container(
        decoration: BoxDecoration(
          color: cs.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(
            color: dimmed ? cs.outlineVariant : style.border,
            width: dimmed ? 1 : 1.4,
          ),
          boxShadow: [
            BoxShadow(
              color: cs.shadow.withValues(alpha: dimmed ? 0.02 : 0.06),
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
                severityColor: style.text,
              ),
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
                      _StatusPill(
                        label: 'Alert #${alert.id}',
                        color: cs.primary,
                      ),
                      _StatusPill(
                        label: alert.severity.toUpperCase(),
                        color: style.text,
                        filled: true,
                      ),
                      _StatusPill(
                        label: reviewStatusLabel.isEmpty
                            ? 'Needs Review'
                            : reviewStatusLabel,
                        color: const Color(0xFF1E88E5),
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
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      if (onAcknowledge != null)
                        OutlinedButton.icon(
                          onPressed: busy ? null : onAcknowledge,
                          icon: const Icon(Icons.done_rounded, size: 17),
                          label: const Text('Acknowledge'),
                        ),
                      if (onResolve != null)
                        FilledButton.tonalIcon(
                          onPressed: busy ? null : onResolve,
                          icon: const Icon(Icons.task_alt_rounded, size: 17),
                          label: const Text('Resolve'),
                        ),
                      if (onAcknowledge == null && onResolve == null)
                        const _ReviewedIndicator(),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _AlertSnapshotPreview extends StatelessWidget {
  const _AlertSnapshotPreview({
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

class _ReviewedIndicator extends StatelessWidget {
  const _ReviewedIndicator();

  @override
  Widget build(BuildContext context) {
    return const Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          Icons.check_circle_rounded,
          size: 16,
          color: Color(0xFF26A69A),
        ),
        SizedBox(width: 5),
        Text(
          'Reviewed',
          style: TextStyle(
            color: Color(0xFF26A69A),
            fontSize: 12,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
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
