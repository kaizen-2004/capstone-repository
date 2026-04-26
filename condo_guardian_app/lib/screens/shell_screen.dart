import 'dart:async';

import 'package:flutter/material.dart';

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
  const ShellScreen({super.key, required this.settingsStore});

  final SettingsStore settingsStore;

  @override
  State<ShellScreen> createState() => _ShellScreenState();
}

class _ShellScreenState extends State<ShellScreen>
    with TickerProviderStateMixin {
  int _selectedIndex = 0;
  late final AnimationController _fadeController;
  late final AlertNotificationCoordinator _alertNotificationCoordinator;
  StreamSubscription<void>? _alertTapSubscription;

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
          baseUrl: widget.settingsStore.backendBaseUrl,
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

    _alertNotificationCoordinator = AlertNotificationCoordinator(
      settingsStore: widget.settingsStore,
      backendServiceFactory: _buildBackendService,
    );
    unawaited(_alertNotificationCoordinator.start());

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
    _alertTapSubscription?.cancel();
    _alertNotificationCoordinator.dispose();
    _fadeController.dispose();
    super.dispose();
  }

  void _handleSettingsSaved() {
    setState(() {});
    unawaited(_alertNotificationCoordinator.restart());
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
        ),
        MonitorScreen(settingsStore: widget.settingsStore),
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
                  icon: Icon(item.icon),
                  selectedIcon: Icon(item.activeIcon),
                  label: item.label,
                ),
              )
              .toList(),
        ),
      ),
    );
  }
}
