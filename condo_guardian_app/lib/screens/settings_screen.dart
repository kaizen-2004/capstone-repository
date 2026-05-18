import 'dart:async';

import 'package:flutter/material.dart';

import '../core/network/api_client.dart';
import '../core/network/backend_endpoint_resolver.dart';
import '../core/storage/settings_store.dart';
import '../services/backend_service.dart';
import '../services/alert_notification_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({
    super.key,
    required this.settingsStore,
    required this.backendService,
    required this.activeBackendBaseUrl,
    required this.activeConnectionLabel,
    this.onSaved,
    this.onSignedOut,
  });

  final SettingsStore settingsStore;
  final BackendService backendService;
  final String activeBackendBaseUrl;
  final String activeConnectionLabel;
  final VoidCallback? onSaved;
  final Future<void> Function()? onSignedOut;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  static const _guestModePresets = <int>[1, 2, 4, 8, 12, 24];
  static const _pollingPresets = <int>[5, 10, 30, 60];

  late final TextEditingController _lanBaseUrlController;
  late final TextEditingController _tailscaleBaseUrlController;
  late final TextEditingController _pollingController;
  final AlertNotificationService _notificationService =
      AlertNotificationService();
  GuestModeStatus? _guestModeStatus;
  Timer? _guestModeTimer;
  int _guestModePresetIndex = 1;
  bool _guestModeBusy = false;
  String? _guestModeMessage;
  String? _connectionMessage;
  String? _notificationMessage;
  String? _message;
  bool _isSuccess = false;
  bool _checkingConnection = false;
  bool _notificationBusy = false;

  @override
  void initState() {
    super.initState();
    _lanBaseUrlController =
        TextEditingController(text: widget.settingsStore.lanBaseUrl);
    _tailscaleBaseUrlController =
        TextEditingController(text: widget.settingsStore.tailscaleBaseUrl);
    _pollingController =
        TextEditingController(text: '${widget.settingsStore.pollingSeconds}');
    unawaited(_loadGuestModeStatus());
  }

  @override
  void dispose() {
    _lanBaseUrlController.dispose();
    _tailscaleBaseUrlController.dispose();
    _pollingController.dispose();
    _guestModeTimer?.cancel();
    _notificationService.dispose();
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant SettingsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.backendService.apiClient.baseUrl !=
            widget.backendService.apiClient.baseUrl ||
        oldWidget.backendService.apiClient.token !=
            widget.backendService.apiClient.token) {
      unawaited(_loadGuestModeStatus());
    }
  }

  Future<void> _loadGuestModeStatus() async {
    try {
      final service = await _resolveGuestModeBackendService();
      final status = await service.fetchGuestModeStatus();
      if (!mounted) {
        return;
      }
      setState(() => _guestModeStatus = status);
      _syncGuestModeTimer();
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() => _guestModeMessage = 'Guest Mode unavailable: $error');
    }
  }

  Future<BackendService> _resolveGuestModeBackendService() async {
    final token = widget.settingsStore.authToken;
    final activeBaseUrl = BackendEndpointResolver.normalizeBaseUrl(
      widget.activeBackendBaseUrl,
    );
    if (activeBaseUrl.isNotEmpty) {
      return BackendService(
        ApiClient(
          baseUrl: activeBaseUrl,
          token: token,
        ),
      );
    }

    try {
      final resolved = await BackendEndpointResolver.resolve(
        widget.settingsStore,
        token: token,
      );
      return BackendService(
        ApiClient(
          baseUrl: resolved.baseUrl,
          token: token,
        ),
      );
    } catch (_) {
      return widget.backendService;
    }
  }

  void _syncGuestModeTimer() {
    _guestModeTimer?.cancel();
    if (!(_guestModeStatus?.active ?? false)) {
      return;
    }
    _guestModeTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) {
        setState(() {});
      }
    });
  }

  int get _guestModeHours => _guestModePresets[_guestModePresetIndex];

  int get _guestModeRemainingSeconds {
    final status = _guestModeStatus;
    if (status == null || !status.active || status.untilTs.isEmpty) {
      return status?.remainingSeconds ?? 0;
    }
    final until = DateTime.tryParse(status.untilTs)?.toLocal();
    if (until == null) {
      return status.remainingSeconds;
    }
    return until.difference(DateTime.now()).inSeconds.clamp(0, 1 << 31).toInt();
  }

  bool get _guestModeActive =>
      (_guestModeStatus?.active ?? false) &&
      (_guestModeRemainingSeconds > 0 ||
          (_guestModeStatus?.untilTs ?? '').isEmpty);

  String _formatGuestModeRemaining(int seconds) {
    final safeSeconds = seconds < 0 ? 0 : seconds;
    final hours = safeSeconds ~/ 3600;
    final minutes = (safeSeconds % 3600) ~/ 60;
    if (hours <= 0) {
      return '${minutes < 1 ? 1 : minutes}m remaining';
    }
    return minutes > 0
        ? '${hours}h ${minutes}m remaining'
        : '${hours}h remaining';
  }

  String _formatGuestModeUntil(String untilTs) {
    final until = DateTime.tryParse(untilTs)?.toLocal();
    if (until == null) {
      return '';
    }
    final hour = until.hour % 12 == 0 ? 12 : until.hour % 12;
    final minute = until.minute.toString().padLeft(2, '0');
    final meridiem = until.hour >= 12 ? 'PM' : 'AM';
    return '$hour:$minute $meridiem';
  }

  Future<void> _startGuestMode() async {
    if (_guestModeBusy) {
      return;
    }
    setState(() {
      _guestModeBusy = true;
      _guestModeMessage = null;
    });
    try {
      final service = await _resolveGuestModeBackendService();
      final status = await service.updateGuestMode(_guestModeHours);
      if (!mounted) {
        return;
      }
      setState(() {
        _guestModeStatus = status;
        _guestModeMessage = status.active
            ? 'Guest Mode is active for $_guestModeHours hour${_guestModeHours == 1 ? '' : 's'}.'
            : 'Guest Mode update was sent, but the backend still reports inactive.';
      });
      widget.onSaved?.call();
      _syncGuestModeTimer();
      unawaited(_loadGuestModeStatus());
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() => _guestModeMessage = 'Unable to start Guest Mode: $error');
    } finally {
      if (mounted) {
        setState(() => _guestModeBusy = false);
      }
    }
  }

  Future<void> _endGuestMode() async {
    if (_guestModeBusy) {
      return;
    }
    setState(() {
      _guestModeBusy = true;
      _guestModeMessage = null;
    });
    try {
      final service = await _resolveGuestModeBackendService();
      final status = await service.updateGuestMode(0);
      if (!mounted) {
        return;
      }
      setState(() {
        _guestModeStatus = status;
        _guestModeMessage =
            'Guest Mode ended. Unknown visitors will be treated normally again.';
      });
      widget.onSaved?.call();
      _syncGuestModeTimer();
      unawaited(_loadGuestModeStatus());
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() => _guestModeMessage = 'Unable to end Guest Mode: $error');
    } finally {
      if (mounted) {
        setState(() => _guestModeBusy = false);
      }
    }
  }

  Future<void> _save() async {
    await widget.settingsStore.setConnectionProfiles(
      lanBaseUrl: BackendEndpointResolver.normalizeBaseUrl(
        _lanBaseUrlController.text,
      ),
      tailscaleBaseUrl: BackendEndpointResolver.normalizeBaseUrl(
        _tailscaleBaseUrlController.text,
      ),
    );
    await widget.settingsStore
        .setPollingSeconds(int.tryParse(_pollingController.text.trim()) ?? 10);
    _pollingController.text = '${widget.settingsStore.pollingSeconds}';
    widget.onSaved?.call();
    if (!mounted) {
      return;
    }
    setState(() {
      _message = 'Settings saved. Connections refreshed.';
      _isSuccess = true;
    });
  }

  Future<void> _testConnection() async {
    if (_checkingConnection) {
      return;
    }
    setState(() {
      _checkingConnection = true;
      _connectionMessage = null;
    });
    await widget.settingsStore.setConnectionProfiles(
      lanBaseUrl: BackendEndpointResolver.normalizeBaseUrl(
        _lanBaseUrlController.text,
      ),
      tailscaleBaseUrl: BackendEndpointResolver.normalizeBaseUrl(
        _tailscaleBaseUrlController.text,
      ),
    );
    try {
      final resolved = await BackendEndpointResolver.resolve(
        widget.settingsStore,
        token: widget.settingsStore.authToken,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _connectionMessage = 'Connection OK via ${resolved.label}.';
      });
      widget.onSaved?.call();
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _connectionMessage =
            'Backend unreachable. Check Wi-Fi, Tailscale, and backend status. $error';
      });
    } finally {
      if (mounted) {
        setState(() => _checkingConnection = false);
      }
    }
  }

  Future<void> _requestNotifications() async {
    if (_notificationBusy) {
      return;
    }
    setState(() {
      _notificationBusy = true;
      _notificationMessage = null;
    });
    try {
      await _notificationService.requestPermission();
      if (!mounted) {
        return;
      }
      setState(() {
        _notificationMessage =
            'Notification permission requested. Active alerts stay visible until acknowledged.';
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _notificationMessage = 'Could not request notifications: $error';
      });
    } finally {
      if (mounted) {
        setState(() => _notificationBusy = false);
      }
    }
  }

  Future<void> _signOut() async {
    final confirmed = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Sign out?'),
            content: const Text(
              'You will need to sign in again before viewing alerts and monitor data.',
            ),
            actions: <Widget>[
              TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text('Sign Out'),
              ),
            ],
          ),
        ) ??
        false;
    if (!confirmed) {
      return;
    }
    await widget.settingsStore.setAuthToken('');
    await widget.onSignedOut?.call();
  }

  Widget _sectionHeader(String label, {IconData? icon}) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(top: 28, bottom: 10),
      child: Row(
        children: [
          if (icon != null) ...[
            Icon(icon, size: 14, color: cs.primary),
            const SizedBox(width: 7),
          ],
          Text(
            label,
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w700,
              color: cs.onSurfaceVariant,
              letterSpacing: 1.3,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(child: Divider(color: cs.outlineVariant)),
        ],
      ),
    );
  }

  Widget _buildGuestModeCard() {
    final cs = Theme.of(context).colorScheme;
    final remainingSeconds = _guestModeRemainingSeconds;
    final untilLabel = _formatGuestModeUntil(_guestModeStatus?.untilTs ?? '');
    final statusLabel = _guestModeActive ? 'Active' : 'Inactive';
    final durationLabel =
        '$_guestModeHours hour${_guestModeHours == 1 ? '' : 's'}';

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: _guestModeActive
            ? const Color(0xFF26A69A).withValues(alpha: 0.12)
            : cs.primary.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: _guestModeActive
              ? const Color(0xFF26A69A).withValues(alpha: 0.35)
              : cs.primary.withValues(alpha: 0.24),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color:
                      (_guestModeActive ? const Color(0xFF26A69A) : cs.primary)
                          .withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  Icons.group_outlined,
                  color:
                      _guestModeActive ? const Color(0xFF26A69A) : cs.primary,
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            'Guest Mode',
                            style: Theme.of(context)
                                .textTheme
                                .titleMedium
                                ?.copyWith(fontWeight: FontWeight.w800),
                          ),
                        ),
                        Chip(
                          visualDensity: VisualDensity.compact,
                          label: Text(statusLabel),
                          backgroundColor: _guestModeActive
                              ? const Color(0xFF26A69A).withValues(alpha: 0.16)
                              : cs.surfaceContainerHighest,
                        ),
                      ],
                    ),
                    Text(
                      'Allow guests temporarily without creating unknown-person intruder alerts.',
                      style: Theme.of(context)
                          .textTheme
                          .bodySmall
                          ?.copyWith(height: 1.35),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Slider(
            value: _guestModePresetIndex.toDouble(),
            min: 0,
            max: (_guestModePresets.length - 1).toDouble(),
            divisions: _guestModePresets.length - 1,
            label: durationLabel,
            onChanged: _guestModeBusy
                ? null
                : (value) {
                    setState(() => _guestModePresetIndex = value.round());
                  },
          ),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: _guestModePresets
                .map(
                  (hours) => Text(
                    '${hours}h',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: cs.onSurfaceVariant,
                          fontWeight: hours == _guestModeHours
                              ? FontWeight.w800
                              : FontWeight.w500,
                        ),
                  ),
                )
                .toList(),
          ),
          const SizedBox(height: 10),
          Text(
            _guestModeActive
                ? 'Ends at ${untilLabel.isEmpty ? 'scheduled time' : untilLabel} • ${_formatGuestModeRemaining(remainingSeconds)}'
                : 'Selected duration: $durationLabel',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color:
                      _guestModeActive ? const Color(0xFF00796B) : cs.primary,
                  fontWeight: FontWeight.w700,
                ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: FilledButton.icon(
                  onPressed: _guestModeBusy ? null : _startGuestMode,
                  icon: Icon(
                    _guestModeActive
                        ? Icons.more_time_rounded
                        : Icons.play_circle_outline_rounded,
                    size: 18,
                  ),
                  label: Text(
                    _guestModeBusy
                        ? 'Updating...'
                        : _guestModeActive
                            ? 'Extend'
                            : 'Start',
                  ),
                ),
              ),
              if (_guestModeActive) ...[
                const SizedBox(width: 10),
                OutlinedButton(
                  onPressed: _guestModeBusy ? null : _endGuestMode,
                  child: const Text('End now'),
                ),
              ],
            ],
          ),
          if (_guestModeMessage != null) ...[
            const SizedBox(height: 10),
            Text(
              _guestModeMessage!,
              style:
                  Theme.of(context).textTheme.bodySmall?.copyWith(height: 1.35),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
      children: [
        _buildGuestModeCard(),
        _sectionHeader('CONNECTION', icon: Icons.cloud_outlined),
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: cs.primary.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: cs.primary.withValues(alpha: 0.24)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Active: ${widget.activeConnectionLabel}',
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      color: cs.primary,
                      fontWeight: FontWeight.w700,
                    ),
              ),
              const SizedBox(height: 4),
              Text(
                widget.activeBackendBaseUrl,
                style: Theme.of(context).textTheme.bodySmall,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _lanBaseUrlController,
          textInputAction: TextInputAction.next,
          decoration: const InputDecoration(
            labelText: 'Home LAN URL',
            hintText: 'http://192.168.1.50:8765',
            prefixIcon: Icon(Icons.router_outlined, size: 20),
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _tailscaleBaseUrlController,
          textInputAction: TextInputAction.next,
          decoration: const InputDecoration(
            labelText: 'Away Tailscale URL',
            hintText: 'http://100.x.x.x:8765',
            prefixIcon: Icon(Icons.vpn_lock_outlined, size: 20),
          ),
        ),
        const SizedBox(height: 10),
        Text(
          'The app always tries LAN first and switches to Tailscale only when LAN is unreachable.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const SizedBox(height: 10),
        OutlinedButton.icon(
          onPressed: _checkingConnection ? null : _testConnection,
          icon: _checkingConnection
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.network_check_rounded, size: 18),
          label: Text(_checkingConnection ? 'Testing...' : 'Test Connection'),
        ),
        if (_connectionMessage != null) ...[
          const SizedBox(height: 8),
          Text(
            _connectionMessage!,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: _connectionMessage!.startsWith('Connection OK')
                      ? const Color(0xFF26A69A)
                      : cs.error,
                  fontWeight: FontWeight.w700,
                ),
          ),
        ],
        _sectionHeader('POLLING', icon: Icons.timer_outlined),
        TextField(
          controller: _pollingController,
          keyboardType: TextInputType.number,
          textInputAction: TextInputAction.done,
          decoration: const InputDecoration(
            labelText: 'Alert polling interval (seconds)',
            prefixIcon: Icon(Icons.update_rounded, size: 20),
            suffixText: 'sec',
          ),
        ),
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: _pollingPresets
              .map(
                (seconds) => ChoiceChip(
                  label: Text('${seconds}s'),
                  selected: _pollingController.text.trim() == '$seconds',
                  onSelected: (_) => setState(
                    () => _pollingController.text = '$seconds',
                  ),
                ),
              )
              .toList(),
        ),
        const SizedBox(height: 8),
        Text(
          'Allowed range: ${SettingsStore.minPollingSeconds}-${SettingsStore.maxPollingSeconds} seconds.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        _sectionHeader('NOTIFICATIONS', icon: Icons.notifications_outlined),
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: cs.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: cs.outlineVariant),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Persistent alert notifications',
                style: Theme.of(context)
                    .textTheme
                    .labelLarge
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 4),
              Text(
                'Critical alerts remain visible until you acknowledge or resolve them.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 10),
              OutlinedButton.icon(
                onPressed: _notificationBusy ? null : _requestNotifications,
                icon: const Icon(Icons.notifications_active_outlined, size: 18),
                label: Text(
                  _notificationBusy ? 'Requesting...' : 'Enable Notifications',
                ),
              ),
              if (_notificationMessage != null) ...[
                const SizedBox(height: 8),
                Text(
                  _notificationMessage!,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 28),
        FilledButton.icon(
          onPressed: _save,
          icon: const Icon(Icons.save_alt_rounded, size: 18),
          label: const Text('Save Settings'),
        ),
        if (_message != null) ...[
          const SizedBox(height: 16),
          AnimatedContainer(
            duration: const Duration(milliseconds: 250),
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: _isSuccess
                  ? const Color(0xFF26A69A).withValues(alpha: 0.10)
                  : cs.error.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: _isSuccess
                    ? const Color(0xFF26A69A).withValues(alpha: 0.4)
                    : cs.error.withValues(alpha: 0.4),
              ),
            ),
            child: Row(
              children: [
                Icon(
                  _isSuccess
                      ? Icons.check_circle_outline_rounded
                      : Icons.error_outline_rounded,
                  size: 18,
                  color: _isSuccess ? const Color(0xFF26A69A) : cs.error,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    _message!,
                    style: Theme.of(context)
                        .textTheme
                        .bodySmall
                        ?.copyWith(height: 1.5),
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ),
        ],
        const SizedBox(height: 20),
        OutlinedButton.icon(
          onPressed: _signOut,
          icon: const Icon(Icons.logout_rounded, size: 18),
          label: const Text('Sign Out'),
        ),
        const SizedBox(height: 32),
        Center(
          child: Column(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: cs.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                clipBehavior: Clip.antiAlias,
                child: const Image(
                  image: AssetImage('assets/logo.png'),
                  fit: BoxFit.cover,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'IntruFlare',
                style: Theme.of(context)
                    .textTheme
                    .titleMedium
                    ?.copyWith(fontSize: 14),
              ),
              const SizedBox(height: 2),
              Text(
                'Security monitoring system',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
      ],
    );
  }
}
