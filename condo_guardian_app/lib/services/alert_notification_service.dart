import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

class AlertNotificationService {
  AlertNotificationService();

  static const int activeAlertNotificationId = 42001;
  static const AndroidNotificationChannel _activeAlertChannel =
      AndroidNotificationChannel(
    'intruflare_active_alerts',
    'Active Alerts',
    description: 'Persistent safety and security alerts',
    importance: Importance.high,
  );

  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();
  final StreamController<void> _onTapController =
      StreamController<void>.broadcast();

  bool _initialized = false;

  Stream<void> get onAlertNotificationTapped => _onTapController.stream;

  Future<void> initialize() async {
    if (_initialized) {
      return;
    }

    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    const initializationSettings = InitializationSettings(android: androidSettings);

    await _plugin.initialize(
      initializationSettings,
      onDidReceiveNotificationResponse: (_) {
        _onTapController.add(null);
      },
    );

    final launchDetails = await _plugin.getNotificationAppLaunchDetails();
    if (launchDetails?.didNotificationLaunchApp ?? false) {
      _onTapController.add(null);
    }

    final androidImpl = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    await androidImpl?.createNotificationChannel(_activeAlertChannel);
    await androidImpl?.requestNotificationsPermission();

    _initialized = true;
  }

  Future<void> requestPermission() async {
    await initialize();
    final androidImpl = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    await androidImpl?.requestNotificationsPermission();
  }

  Future<void> showPersistentActiveAlert({
    required String title,
    required String body,
    required bool critical,
  }) async {
    await initialize();

    final details = AndroidNotificationDetails(
      _activeAlertChannel.id,
      _activeAlertChannel.name,
      channelDescription: _activeAlertChannel.description,
      importance: Importance.high,
      priority: Priority.high,
      category: AndroidNotificationCategory.alarm,
      ongoing: true,
      autoCancel: false,
      onlyAlertOnce: true,
      styleInformation: BigTextStyleInformation(body),
      color: critical ? const Color(0xFFD32F2F) : const Color(0xFFFFA726),
      ticker: 'IntruFlare active alert',
    );

    await _plugin.show(
      activeAlertNotificationId,
      title,
      body,
      NotificationDetails(android: details),
      payload: 'alerts',
    );
  }

  Future<void> clearActiveAlertNotification() async {
    await _plugin.cancel(activeAlertNotificationId);
  }

  void dispose() {
    _onTapController.close();
  }
}
