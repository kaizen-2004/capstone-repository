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
      final alerts = await widget.backendService.fetchAlerts();
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
    await widget.backendService.acknowledgeAlert(alertId);
    await _loadAlerts(silent: true);
    widget.onAlertAcknowledged?.call();
  }

  Future<void> _openEvents() async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => EventsScreen(backendService: widget.backendService),
      ),
    );
  }

  Future<void> _openSnapshots() async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => SnapshotsScreen(
          backendService: widget.backendService,
          settingsStore: widget.settingsStore,
        ),
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

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Column(
        children: [
          _IncidentSwitcher(
            onOpenEvents: _openEvents,
            onOpenSnapshots: _openSnapshots,
          ),
          const Expanded(child: Center(child: CircularProgressIndicator())),
        ],
      );
    }

    if (_error != null) {
      return Column(
        children: [
          _IncidentSwitcher(
            onOpenEvents: _openEvents,
            onOpenSnapshots: _openSnapshots,
          ),
          Expanded(
            child: _ErrorState(error: _error!, onRetry: () => _loadAlerts()),
          ),
        ],
      );
    }

    if (_alerts.isEmpty) {
      return Column(
        children: [
          _IncidentSwitcher(
            onOpenEvents: _openEvents,
            onOpenSnapshots: _openSnapshots,
          ),
          const Expanded(child: _EmptyState()),
        ],
      );
    }

    final active = _alerts.where((alert) => !alert.acknowledged).toList();
    final acked = _alerts.where((alert) => alert.acknowledged).toList();

    return RefreshIndicator(
      onRefresh: _loadAlerts,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        children: [
          _IncidentSwitcher(
            onOpenEvents: _openEvents,
            onOpenSnapshots: _openSnapshots,
          ),
          const SizedBox(height: 8),
          if (active.isNotEmpty) ...[
            _SectionLabel(
                label: 'Active', count: active.length, isActive: true),
            const SizedBox(height: 8),
            ...active.map(
              (alert) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _AlertCard(
                  alert: alert,
                  style: _severityStyle(alert.severity),
                  timeLabel: _formatDate(alert.createdAt),
                  onAcknowledge: () => _acknowledge(alert.id),
                ),
              ),
            ),
            const SizedBox(height: 8),
          ],
          if (acked.isNotEmpty) ...[
            _SectionLabel(
              label: 'Acknowledged',
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
                  onAcknowledge: null,
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
    required this.onAcknowledge,
    this.dimmed = false,
  });

  final AlertItem alert;
  final ({Color bg, Color border, Color text, IconData icon}) style;
  final String timeLabel;
  final VoidCallback? onAcknowledge;
  final bool dimmed;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;

    return Opacity(
      opacity: dimmed ? 0.55 : 1.0,
      child: Container(
        decoration: BoxDecoration(
          color: dimmed ? cs.surfaceContainerHighest : style.bg,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: dimmed ? cs.outlineVariant : style.border,
            width: dimmed ? 1 : 1.5,
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(style.icon, size: 18, color: style.text),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      alert.title,
                      style: tt.bodyLarge?.copyWith(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: cs.onSurface,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                    decoration: BoxDecoration(
                      color: style.text.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      alert.severity.toUpperCase(),
                      style: TextStyle(
                        color: style.text,
                        fontSize: 9,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ),
                ],
              ),
              if (alert.message.isNotEmpty) ...[
                const SizedBox(height: 8),
                Padding(
                  padding: const EdgeInsets.only(left: 28),
                  child: Text(
                    alert.message,
                    style: tt.bodySmall?.copyWith(height: 1.5),
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
              const SizedBox(height: 10),
              Row(
                children: [
                  const SizedBox(width: 28),
                  Icon(Icons.access_time_rounded,
                      size: 12, color: cs.onSurfaceVariant),
                  const SizedBox(width: 4),
                  Text(timeLabel, style: tt.bodySmall?.copyWith(fontSize: 11)),
                  const Spacer(),
                  if (onAcknowledge != null)
                    TextButton(
                      onPressed: onAcknowledge,
                      style: TextButton.styleFrom(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 4),
                        minimumSize: Size.zero,
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      ),
                      child: const Text('Acknowledge',
                          style: TextStyle(fontSize: 12)),
                    )
                  else
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(
                          Icons.check_circle_rounded,
                          size: 14,
                          color: Color(0xFF26A69A),
                        ),
                        const SizedBox(width: 4),
                        const Text(
                          'Acknowledged',
                          style: TextStyle(
                            color: Color(0xFF26A69A),
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                ],
              ),
            ],
          ),
        ),
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
