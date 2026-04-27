import 'package:flutter/material.dart';

import '../core/storage/settings_store.dart';
import '../models/node_status.dart';
import '../models/sensor_reading.dart';
import '../models/system_snapshot.dart';
import '../services/backend_service.dart';
import '../widgets/status_card.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.backendService,
    required this.settingsStore,
    this.activeAlertCount,
  });

  final BackendService backendService;
  final SettingsStore settingsStore;
  final int? activeAlertCount;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen>
    with SingleTickerProviderStateMixin {
  late Future<SystemSnapshot> _snapshotFuture;
  late final AnimationController _staggerCtrl;

  @override
  void initState() {
    super.initState();
    _staggerCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );
    _snapshotFuture = _fetch();
  }

  @override
  void dispose() {
    _staggerCtrl.dispose();
    super.dispose();
  }

  Future<SystemSnapshot> _fetch() {
    _staggerCtrl.reset();
    final future = widget.backendService.fetchSystemSnapshot();
    future.then((_) => _staggerCtrl.forward(), onError: (_) {});
    return future;
  }

  Future<void> _refresh() async {
    final future = _fetch();
    setState(() => _snapshotFuture = future);
    await future;
  }

  Color _stateColor(String state) {
    switch (state.toLowerCase()) {
      case 'online':
      case 'ok':
      case 'normal':
        return const Color(0xFF26A69A);
      case 'warning':
        return const Color(0xFFFFA726);
      case 'critical':
      case 'error':
        return const Color(0xFFEF5350);
      default:
        return const Color(0xFF1E88E5);
    }
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _refresh,
      color: Theme.of(context).colorScheme.primary,
      backgroundColor: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: FutureBuilder<SystemSnapshot>(
        future: _snapshotFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const _LoadingState();
          }
          if (snapshot.hasError) {
            return _ErrorState(error: '${snapshot.error}', onRetry: _refresh);
          }
          return _DataView(
            data: snapshot.data!,
            backendUrl: widget.settingsStore.backendBaseUrl,
            liveAlertCount: widget.activeAlertCount,
            staggerCtrl: _staggerCtrl,
            stateColor: _stateColor,
          );
        },
      ),
    );
  }
}

class _LoadingState extends StatelessWidget {
  const _LoadingState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: 40,
            height: 40,
            child: CircularProgressIndicator(
              strokeWidth: 2.5,
              color: Theme.of(context).colorScheme.primary,
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'Loading system snapshot…',
            style: Theme.of(context).textTheme.bodyMedium,
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
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        const SizedBox(height: 40),
        Icon(Icons.cloud_off_rounded,
            size: 48, color: cs.error.withValues(alpha: 0.7)),
        const SizedBox(height: 16),
        Text(
          'Unable to load snapshot',
          style: Theme.of(context).textTheme.titleLarge,
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 8),
        Text(
          error,
          style: Theme.of(context).textTheme.bodySmall,
          textAlign: TextAlign.center,
          maxLines: 4,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: 24),
        FilledButton.icon(
          onPressed: onRetry,
          icon: const Icon(Icons.refresh_rounded, size: 18),
          label: const Text('Retry'),
        ),
      ],
    );
  }
}

class _DataView extends StatelessWidget {
  const _DataView({
    required this.data,
    required this.backendUrl,
    required this.liveAlertCount,
    required this.staggerCtrl,
    required this.stateColor,
  });

  final SystemSnapshot data;
  final String backendUrl;
  final int? liveAlertCount;
  final AnimationController staggerCtrl;
  final Color Function(String) stateColor;

  Animation<double> _anim(double start, double end) => CurvedAnimation(
        parent: staggerCtrl,
        curve: Interval(start, end, curve: Curves.easeOut),
      );

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    final screenW = MediaQuery.of(context).size.width;
    final cardWidth = screenW < 380
        ? (screenW - 32)
        : ((screenW - 44) / 2).clamp(160.0, 300.0);
    final onlineNodes = data.nodes
        .where((node) => node.status.toLowerCase() == 'online')
        .length;
    final snapshotAlertCount =
        data.activeAlerts.where((alert) => !alert.acknowledged).length;
    final alertCount = liveAlertCount ?? snapshotAlertCount;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        FadeTransition(
          opacity: _anim(0.0, 0.4),
          child: SlideTransition(
            position:
                Tween<Offset>(begin: const Offset(0, 0.08), end: Offset.zero)
                    .animate(_anim(0.0, 0.4)),
            child: Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                SizedBox(
                  width: cardWidth,
                  child: StatusCard(
                    title: 'System State',
                    value: data.systemState.toUpperCase(),
                    subtitle: backendUrl,
                    icon: Icons.shield_rounded,
                    accentColor: stateColor(data.systemState),
                    statusLabel: data.systemState.toLowerCase() == 'online'
                        ? 'LIVE'
                        : 'CHECK',
                    statusOk: ['online', 'ok', 'normal']
                        .contains(data.systemState.toLowerCase()),
                  ),
                ),
                SizedBox(
                  width: cardWidth,
                  child: StatusCard(
                    title: 'Active Alerts',
                    value: '$alertCount',
                    subtitle: alertCount == 0
                        ? 'No open alerts'
                        : 'Require attention',
                    icon: Icons.warning_amber_rounded,
                    accentColor: alertCount == 0
                        ? const Color(0xFF26A69A)
                        : alertCount > 3
                            ? const Color(0xFFEF5350)
                            : const Color(0xFFFFA726),
                  ),
                ),
                SizedBox(
                  width: cardWidth,
                  child: StatusCard(
                    title: 'Online Nodes',
                    value: '$onlineNodes/${data.nodes.length}',
                    subtitle: 'Node connectivity',
                    icon: Icons.hub_rounded,
                    accentColor: onlineNodes == data.nodes.length
                        ? const Color(0xFF26A69A)
                        : const Color(0xFFFFA726),
                    statusLabel:
                        onlineNodes == data.nodes.length ? 'ALL OK' : 'PARTIAL',
                    statusOk: onlineNodes == data.nodes.length,
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 24),
        if (data.sensorReadings.isNotEmpty) ...[
          FadeTransition(
            opacity: _anim(0.25, 0.65),
            child: const _SectionHeader(
              title: 'Sensor Readings',
              icon: Icons.sensors_rounded,
            ),
          ),
          const SizedBox(height: 10),
          FadeTransition(
            opacity: _anim(0.3, 0.7),
            child: SlideTransition(
              position:
                  Tween<Offset>(begin: const Offset(0, 0.06), end: Offset.zero)
                      .animate(_anim(0.3, 0.7)),
              child: Column(
                children: data.sensorReadings
                    .map(
                      (reading) => Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: _SensorRow(
                            reading: reading, stateColor: stateColor),
                      ),
                    )
                    .toList(),
              ),
            ),
          ),
          const SizedBox(height: 20),
        ],
        if (data.nodes.isNotEmpty) ...[
          FadeTransition(
            opacity: _anim(0.5, 0.9),
            child: const _SectionHeader(
              title: 'Node Overview',
              icon: Icons.hub_rounded,
            ),
          ),
          const SizedBox(height: 10),
          FadeTransition(
            opacity: _anim(0.55, 1.0),
            child: SlideTransition(
              position:
                  Tween<Offset>(begin: const Offset(0, 0.06), end: Offset.zero)
                      .animate(_anim(0.55, 1.0)),
              child: Column(
                children: data.nodes
                    .map(
                      (node) => Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: _NodeRow(node: node, stateColor: stateColor),
                      ),
                    )
                    .toList(),
              ),
            ),
          ),
        ],
        if (data.sensorReadings.isEmpty && data.nodes.isEmpty)
          Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 32),
              child: Text(
                'No sensor or node data available.',
                style: tt.bodyMedium,
              ),
            ),
          ),
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, required this.icon});

  final String title;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Row(
      children: [
        Icon(icon, size: 16, color: cs.primary),
        const SizedBox(width: 8),
        Text(
          title,
          style: Theme.of(context).textTheme.titleLarge?.copyWith(fontSize: 15),
        ),
        const SizedBox(width: 10),
        Expanded(child: Divider(color: cs.outlineVariant)),
      ],
    );
  }
}

class _SensorRow extends StatelessWidget {
  const _SensorRow({required this.reading, required this.stateColor});

  final SensorReading reading;
  final Color Function(String) stateColor;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final statusColor = stateColor(reading.status);
    final displayValue =
        '${reading.value}${reading.unit.isNotEmpty ? ' ${reading.unit}' : ''}'
            .trim();

    return Container(
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: cs.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            Container(
              width: 8,
              height: 8,
              decoration:
                  BoxDecoration(color: statusColor, shape: BoxShape.circle),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                reading.label,
                style: Theme.of(context)
                    .textTheme
                    .bodyLarge
                    ?.copyWith(fontSize: 13),
                overflow: TextOverflow.ellipsis,
                maxLines: 2,
              ),
            ),
            const SizedBox(width: 8),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  displayValue,
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    fontSize: 12,
                    color: cs.onSurface,
                    fontFeatures: [const FontFeature.tabularFigures()],
                  ),
                ),
                Text(
                  reading.status,
                  style: TextStyle(
                    color: statusColor,
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _NodeRow extends StatelessWidget {
  const _NodeRow({required this.node, required this.stateColor});

  final NodeStatus node;
  final Color Function(String) stateColor;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final statusColor = stateColor(node.status);
    final isOnline = node.status.toLowerCase() == 'online';

    return Container(
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: cs.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: statusColor.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(9),
              ),
              child: Icon(
                isOnline ? Icons.memory_rounded : Icons.memory_outlined,
                size: 18,
                color: statusColor,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    node.displayName,
                    style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                        ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '${node.role} · ${node.room}',
                    style: Theme.of(context).textTheme.bodySmall,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: statusColor.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                node.status.toUpperCase(),
                style: TextStyle(
                  color: statusColor,
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.5,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
