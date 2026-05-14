import 'dart:async';

import '../core/network/api_client.dart';
import '../core/storage/settings_store.dart';
import '../models/alert_item.dart';
import 'alert_notification_service.dart';
import 'backend_service.dart';

class AlertNotificationCoordinator {
  AlertNotificationCoordinator({
    required SettingsStore settingsStore,
    required BackendService Function() backendServiceFactory,
    Future<void> Function()? onAuthenticationExpired,
    AlertNotificationService? notificationService,
  })  : _settingsStore = settingsStore,
        _backendServiceFactory = backendServiceFactory,
        _onAuthenticationExpired = onAuthenticationExpired,
        _notificationService =
            notificationService ?? AlertNotificationService();

  final SettingsStore _settingsStore;
  final BackendService Function() _backendServiceFactory;
  final Future<void> Function()? _onAuthenticationExpired;
  final AlertNotificationService _notificationService;

  Timer? _timer;
  bool _started = false;
  bool _syncInProgress = false;
  final StreamController<int> _activeAlertCountController =
      StreamController<int>.broadcast();
  final Set<String> _notifiedNormalEventIds = <String>{};
  int _activeAlertCount = 0;
  bool _activeAlertCountPublished = false;

  Stream<void> get onAlertNotificationTapped =>
      _notificationService.onAlertNotificationTapped;

  Stream<int> get activeAlertCountStream => _activeAlertCountController.stream;

  int get activeAlertCount => _activeAlertCount;

  Future<void> start() async {
    if (_started) {
      return;
    }
    _started = true;

    await _notificationService.initialize();
    await refreshNow();
    _timer = Timer.periodic(
      Duration(seconds: _settingsStore.pollingSeconds),
      (_) {
        unawaited(refreshNow());
      },
    );
  }

  Future<void> restart() async {
    stop();
    await start();
  }

  void stop() {
    _timer?.cancel();
    _timer = null;
    _started = false;
  }

  Future<void> refreshNow() async {
    if (_syncInProgress) {
      return;
    }
    _syncInProgress = true;
    try {
      final backendService = _backendServiceFactory();
      final alerts = await backendService.fetchAlerts();
      final active = alerts.where((item) => !item.acknowledged).toList();
      final activeCount = active.length;
      _publishActiveAlertCount(activeCount);
      await _notifyLatestDoorStateEvent(backendService);

      if (active.isEmpty) {
        await _notificationService.clearActiveAlertNotification();
        return;
      }

      final primary = _pickPrimaryAlert(active);
      final title = activeCount == 1
          ? primary.title
          : '$activeCount active alerts need acknowledgment';

      final text = primary.message.trim().isNotEmpty
          ? primary.message.trim()
          : 'Open Alerts and acknowledge this event.';

      final body = activeCount == 1 ? text : '${primary.title}: $text';

      await _notificationService.showPersistentActiveAlert(
        title: title,
        body: body,
        critical: _severityRank(primary.severity) >= _severityRank('critical'),
      );
    } on ApiException catch (error) {
      if (error.statusCode == 401) {
        await _onAuthenticationExpired?.call();
      }
    } catch (_) {
      // Keep app stable if backend is temporarily unreachable.
    } finally {
      _syncInProgress = false;
    }
  }

  AlertItem _pickPrimaryAlert(List<AlertItem> alerts) {
    final sorted = List<AlertItem>.from(alerts)
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return sorted.first;
  }

  Future<void> _notifyLatestDoorStateEvent(
      BackendService backendService) async {
    try {
      final events = await backendService.fetchEvents();
      final doorEvents = events.where((event) {
        final eventCode = event.eventCode.toUpperCase();
        return eventCode == 'DOOR_OPEN' || eventCode == 'DOOR_CLOSED';
      }).toList()
        ..sort((a, b) => b.createdAt.compareTo(a.createdAt));

      if (doorEvents.isEmpty) {
        return;
      }

      final latest = doorEvents.first;
      if (_notifiedNormalEventIds.contains(latest.id)) {
        return;
      }

      final maxAgeSeconds = _settingsStore.pollingSeconds * 2 < 30
          ? 30
          : _settingsStore.pollingSeconds * 2;
      if (DateTime.now().difference(latest.createdAt).inSeconds >
          maxAgeSeconds) {
        return;
      }

      final body = latest.message.trim().isNotEmpty
          ? latest.message.trim()
          : 'Door state changed at ${latest.location}.';
      await _notificationService.showNormalEventNotification(
        notificationKey: latest.id,
        title: latest.title,
        body: body,
      );
      _notifiedNormalEventIds.add(latest.id);
    } catch (_) {
      // Normal event notifications should not block active alert refresh.
    }
  }

  int _severityRank(String severityRaw) {
    switch (severityRaw.toLowerCase()) {
      case 'critical':
        return 3;
      case 'warning':
        return 2;
      case 'normal':
      case 'info':
        return 1;
      default:
        return 0;
    }
  }

  void _publishActiveAlertCount(int count) {
    final nextCount = count < 0 ? 0 : count;
    if (_activeAlertCountPublished && nextCount == _activeAlertCount) {
      return;
    }
    _activeAlertCount = nextCount;
    _activeAlertCountPublished = true;
    if (!_activeAlertCountController.isClosed) {
      _activeAlertCountController.add(_activeAlertCount);
    }
  }

  void dispose() {
    stop();
    _activeAlertCountController.close();
    _notificationService.dispose();
  }
}
