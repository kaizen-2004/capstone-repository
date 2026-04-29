import 'package:flutter/material.dart';

import '../core/storage/settings_store.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({
    super.key,
    required this.settingsStore,
    required this.activeBackendBaseUrl,
    required this.activeConnectionLabel,
    this.onSaved,
  });

  final SettingsStore settingsStore;
  final String activeBackendBaseUrl;
  final String activeConnectionLabel;
  final VoidCallback? onSaved;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _mdnsBaseUrlController;
  late final TextEditingController _lanBaseUrlController;
  late final TextEditingController _tailscaleBaseUrlController;
  late final TextEditingController _pollingController;
  String? _message;
  bool _isSuccess = false;
  late String _networkMode;

  @override
  void initState() {
    super.initState();
    _mdnsBaseUrlController =
        TextEditingController(text: widget.settingsStore.mdnsBaseUrl);
    _lanBaseUrlController =
        TextEditingController(text: widget.settingsStore.lanBaseUrl);
    _tailscaleBaseUrlController =
        TextEditingController(text: widget.settingsStore.tailscaleBaseUrl);
    _pollingController =
        TextEditingController(text: '${widget.settingsStore.pollingSeconds}');
    _networkMode = widget.settingsStore.networkMode;
  }

  @override
  void dispose() {
    _mdnsBaseUrlController.dispose();
    _lanBaseUrlController.dispose();
    _tailscaleBaseUrlController.dispose();
    _pollingController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    await widget.settingsStore.setConnectionProfiles(
      mdnsBaseUrl: _mdnsBaseUrlController.text.trim(),
      lanBaseUrl: _lanBaseUrlController.text.trim(),
      tailscaleBaseUrl: _tailscaleBaseUrlController.text.trim(),
      networkMode: _networkMode,
    );
    await widget.settingsStore
        .setPollingSeconds(int.tryParse(_pollingController.text.trim()) ?? 10);
    widget.onSaved?.call();
    if (!mounted) {
      return;
    }
    setState(() {
      _message = 'Settings saved. Connections refreshed.';
      _isSuccess = true;
    });
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

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
      children: [
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
        DropdownButtonFormField<String>(
          initialValue: _networkMode,
          decoration: const InputDecoration(
            labelText: 'Connection mode',
            prefixIcon: Icon(Icons.hub_outlined, size: 20),
          ),
          items: const [
            DropdownMenuItem(
                value: 'auto', child: Text('Auto: mDNS → LAN → Tailscale')),
            DropdownMenuItem(
                value: 'home', child: Text('Home only: mDNS → LAN')),
            DropdownMenuItem(
                value: 'away', child: Text('Away only: Tailscale')),
          ],
          onChanged: (value) {
            if (value == null) {
              return;
            }
            setState(() => _networkMode = value);
          },
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _mdnsBaseUrlController,
          textInputAction: TextInputAction.next,
          decoration: const InputDecoration(
            labelText: 'Home mDNS URL',
            hintText: 'http://thesis-monitor.local:8765',
            prefixIcon: Icon(Icons.dns_outlined, size: 20),
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
          'Auto mode uses mDNS or LAN at home and Tailscale outside the house.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
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
