import 'dart:async';

import 'package:flutter/material.dart';

import '../core/network/backend_endpoint_resolver.dart';
import '../core/network/api_client.dart';
import '../core/storage/settings_store.dart';
import '../services/alert_notification_coordinator.dart';
import '../services/backend_service.dart';
import 'alerts_screen.dart';
import 'assistant_screen.dart';
import 'enrollment_screen.dart';
import 'home_screen.dart';
import 'monitor_screen.dart';
import 'provisioning_screen.dart';
import 'settings_screen.dart';

class ShellScreen extends StatefulWidget {
  const ShellScreen({
    super.key,
    required this.settingsStore,
    this.onSessionInvalidated,
  });

  final SettingsStore settingsStore;
  final VoidCallback? onSessionInvalidated;

  @override
  State<ShellScreen> createState() => _ShellScreenState();
}

class _ShellScreenState extends State<ShellScreen>
    with TickerProviderStateMixin {
  int _selectedIndex = 0;
  int? _activeAlertCount;
  late String _activeBackendBaseUrl;
  String _activeConnectionLabel = 'Resolving connection';
  late final AnimationController _fadeController;
  late final AlertNotificationCoordinator _alertNotificationCoordinator;
  StreamSubscription<void>? _alertTapSubscription;
  StreamSubscription<int>? _activeAlertCountSubscription;

  static const _navItems =
      <({String label, IconData icon, IconData activeIcon})>[
    (
      label: 'Home',
      icon: Icons.home_outlined,
      activeIcon: Icons.home_rounded,
    ),
    (
      label: 'Monitor',
      icon: Icons.videocam_outlined,
      activeIcon: Icons.videocam_rounded,
    ),
    (
      label: 'Alerts',
      icon: Icons.notifications_outlined,
      activeIcon: Icons.notifications_rounded,
    ),
    (
      label: 'Enroll',
      icon: Icons.face_outlined,
      activeIcon: Icons.face_rounded,
    ),
    (
      label: 'AI',
      icon: Icons.smart_toy_outlined,
      activeIcon: Icons.smart_toy_rounded,
    ),
    (
      label: 'Settings',
      icon: Icons.settings_outlined,
      activeIcon: Icons.settings_rounded,
    ),
  ];

  static const _pageTitles = <String>[
    'Dashboard',
    'Live Monitor',
    'Alerts',
    'Enrollment',
    'AI Assistant',
    'Settings',
  ];

  BackendService _buildBackendService() => BackendService(
        ApiClient(
          baseUrl: _activeBackendBaseUrl,
          token: widget.settingsStore.authToken,
        ),
      );

  BackendService get _backendService => _buildBackendService();

  @override
  void initState() {
    super.initState();
    _fadeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 180),
      value: 1,
    );
    _activeBackendBaseUrl = widget.settingsStore.activeBackendBaseUrl;

    _alertNotificationCoordinator = AlertNotificationCoordinator(
      settingsStore: widget.settingsStore,
      backendServiceFactory: _buildBackendService,
    );
    _activeAlertCountSubscription =
        _alertNotificationCoordinator.activeAlertCountStream.listen((count) {
      if (!mounted || _activeAlertCount == count) {
        return;
      }
      setState(() => _activeAlertCount = count);
    });
    unawaited(_initializeConnectionAndNotifications());

    _alertTapSubscription =
        _alertNotificationCoordinator.onAlertNotificationTapped.listen((_) {
      if (!mounted) {
        return;
      }
      unawaited(_onDestinationSelected(2));
    });
  }

  @override
  void dispose() {
    _activeAlertCountSubscription?.cancel();
    _alertTapSubscription?.cancel();
    _alertNotificationCoordinator.dispose();
    _fadeController.dispose();
    super.dispose();
  }

  Future<void> _initializeConnectionAndNotifications() async {
    await _refreshActiveBackendUrl();
    if (!mounted) {
      return;
    }
    await _alertNotificationCoordinator.start();
  }

  Future<void> _refreshActiveBackendUrl() async {
    try {
      final resolved = await BackendEndpointResolver.resolve(
        widget.settingsStore,
        token: widget.settingsStore.authToken,
      );
      await BackendEndpointResolver.refreshBootstrap(
        widget.settingsStore,
        baseUrl: resolved.baseUrl,
        token: widget.settingsStore.authToken,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _activeBackendBaseUrl = resolved.baseUrl;
        _activeConnectionLabel = resolved.label;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _activeBackendBaseUrl = widget.settingsStore.activeBackendBaseUrl;
        _activeConnectionLabel = 'Saved endpoint';
      });
      final token = widget.settingsStore.authToken.trim();
      if (token.isEmpty) {
        widget.onSessionInvalidated?.call();
      }
    }
  }

  void _handleSettingsSaved() {
    unawaited(() async {
      await _refreshActiveBackendUrl();
      await _alertNotificationCoordinator.restart();
    }());
  }

  Future<void> _onDestinationSelected(int index) async {
    if (index == _selectedIndex) return;
    await _fadeController.animateTo(0, curve: Curves.easeOut);
    setState(() => _selectedIndex = index);
    await _fadeController.animateTo(1, curve: Curves.easeIn);
  }

  List<Widget> get _pages => <Widget>[
        HomeScreen(
          backendService: _backendService,
          settingsStore: widget.settingsStore,
          activeAlertCount: _activeAlertCount,
          activeBackendBaseUrl: _activeBackendBaseUrl,
          activeConnectionLabel: _activeConnectionLabel,
        ),
        MonitorScreen(
          backendBaseUrl: _activeBackendBaseUrl,
          authToken: widget.settingsStore.authToken,
        ),
        AlertsScreen(
          backendService: _backendService,
          pollingSeconds: widget.settingsStore.pollingSeconds,
          settingsStore: widget.settingsStore,
          onAlertAcknowledged: () {
            unawaited(_alertNotificationCoordinator.refreshNow());
          },
        ),
        EnrollmentScreen(backendService: _backendService),
        AssistantScreen(backendService: _backendService),
        SettingsScreen(
          settingsStore: widget.settingsStore,
          activeBackendBaseUrl: _activeBackendBaseUrl,
          activeConnectionLabel: _activeConnectionLabel,
          onSaved: _handleSettingsSaved,
        ),
      ];

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 28,
              height: 28,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(8),
              ),
              clipBehavior: Clip.antiAlias,
              child: const Image(
                image: AssetImage('assets/logo.png'),
                fit: BoxFit.cover,
              ),
            ),
            const SizedBox(width: 10),
            Text(_pageTitles[_selectedIndex]),
          ],
        ),
        actions: [
          Tooltip(
            message: 'Provision node',
            child: InkWell(
              borderRadius: BorderRadius.circular(10),
              onTap: () async {
                await Navigator.of(context).push(
                  PageRouteBuilder<void>(
                    pageBuilder: (_, animation, __) => FadeTransition(
                        opacity: animation, child: const ProvisioningScreen()),
                    transitionDuration: const Duration(milliseconds: 220),
                  ),
                );
              },
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  border: Border.all(color: cs.outline),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.router_outlined,
                        size: 16, color: cs.onSurfaceVariant),
                    const SizedBox(width: 5),
                    Text(
                      'Provision',
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            color: cs.onSurfaceVariant,
                            fontSize: 12,
                          ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
      body: FadeTransition(
        opacity: _fadeController,
        child: IndexedStack(index: _selectedIndex, children: _pages),
      ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          border: Border(
            top: BorderSide(color: cs.outlineVariant, width: 1),
          ),
        ),
        child: NavigationBar(
          labelBehavior: NavigationDestinationLabelBehavior.onlyShowSelected,
          selectedIndex: _selectedIndex,
          onDestinationSelected: _onDestinationSelected,
          destinations: _navItems
              .map(
                (item) => NavigationDestination(
                  icon: _buildDestinationIcon(
                    icon: item.icon,
                    itemLabel: item.label,
                  ),
                  selectedIcon: _buildDestinationIcon(
                    icon: item.activeIcon,
                    itemLabel: item.label,
                  ),
                  label: item.label,
                ),
              )
              .toList(),
        ),
      ),
    );
  }

  Widget _buildDestinationIcon({
    required IconData icon,
    required String itemLabel,
  }) {
    if (itemLabel.toLowerCase() != 'alerts') {
      return Icon(icon);
    }
    return _NotificationCountIcon(
      icon: icon,
      count: _activeAlertCount ?? 0,
    );
  }
}

class _NotificationCountIcon extends StatelessWidget {
  const _NotificationCountIcon({
    required this.icon,
    required this.count,
  });

  final IconData icon;
  final int count;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final badgeText = count > 99 ? '99+' : '$count';

    return Stack(
      clipBehavior: Clip.none,
      children: [
        Icon(icon),
        if (count > 0)
          Positioned(
            right: -10,
            top: -6,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
              constraints: const BoxConstraints(minWidth: 16, minHeight: 16),
              decoration: BoxDecoration(
                color: cs.error,
                borderRadius: BorderRadius.circular(999),
              ),
              alignment: Alignment.center,
              child: Text(
                badgeText,
                style: TextStyle(
                  color: cs.onError,
                  fontSize: 9,
                  fontWeight: FontWeight.w700,
                ),
                textAlign: TextAlign.center,
              ),
            ),
          ),
      ],
    );
  }
}
