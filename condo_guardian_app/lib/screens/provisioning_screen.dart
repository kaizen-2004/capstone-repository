import 'package:flutter/material.dart';

import '../core/network/api_client.dart';
import '../services/provisioning_service.dart';

class ProvisioningScreen extends StatefulWidget {
  const ProvisioningScreen({super.key});

  @override
  State<ProvisioningScreen> createState() => _ProvisioningScreenState();
}

class _ProvisioningScreenState extends State<ProvisioningScreen> {
  final _formKey = GlobalKey<FormState>();
  final _setupBaseUrlController =
      TextEditingController(text: 'http://192.168.4.1');
  final _wifiSsidController = TextEditingController();
  final _wifiPasswordController = TextEditingController();
  final _backendHostController = TextEditingController();
  final _backendPortController = TextEditingController(text: '8765');
  final _nodeIdController = TextEditingController(text: 'smoke_node1');
  String _nodeRole = 'smoke_node1';
  String _roomName = 'Living Room';
  String? _result;
  bool _submitting = false;
  bool _obscurePassword = true;
  bool _isSuccess = false;

  static const _nodeRoleOptions = [
    'smoke_node1',
    'smoke_node2',
    'door_force',
    'cam_door',
  ];
  static const _roomOptions = ['Living Room', 'Door Entrance Area'];

  @override
  void dispose() {
    _setupBaseUrlController.dispose();
    _wifiSsidController.dispose();
    _wifiPasswordController.dispose();
    _backendHostController.dispose();
    _backendPortController.dispose();
    _nodeIdController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _submitting = true;
      _result = null;
    });
    try {
      final service = ProvisioningService(
        ApiClient(baseUrl: _setupBaseUrlController.text.trim(), token: ''),
      );
      final message = await service.sendNodeConfiguration(
        wifiSsid: _wifiSsidController.text.trim(),
        wifiPassword: _wifiPasswordController.text.trim(),
        backendHost: _backendHostController.text.trim(),
        backendPort: int.parse(_backendPortController.text.trim()),
        nodeId: _nodeIdController.text.trim(),
        nodeRole: _nodeRole,
        roomName: _roomName,
      );
      setState(() {
        _result = message;
        _isSuccess = true;
      });
    } catch (error) {
      setState(() {
        _result = '$error';
        _isSuccess = false;
      });
    } finally {
      setState(() => _submitting = false);
    }
  }

  Widget _sectionHeader(String label) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(top: 24, bottom: 10),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          color: cs.onSurfaceVariant,
          letterSpacing: 1.3,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.router_rounded, size: 18, color: cs.primary),
            const SizedBox(width: 8),
            const Text('Provision Node'),
          ],
        ),
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          children: [
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: cs.primary.withValues(alpha: 0.07),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: cs.primary.withValues(alpha: 0.2)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.wifi_find_rounded, size: 18, color: cs.primary),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Connect your phone to the node\'s setup AP first, then submit the configuration.',
                      style: Theme.of(context)
                          .textTheme
                          .bodySmall
                          ?.copyWith(height: 1.55),
                    ),
                  ),
                ],
              ),
            ),
            _sectionHeader('NODE ENDPOINT'),
            _field(
              controller: _setupBaseUrlController,
              label: 'Node setup base URL',
              hint: 'http://192.168.4.1',
              icon: Icons.link_rounded,
              action: TextInputAction.next,
              validator: (value) =>
                  (value == null || value.isEmpty) ? 'Required' : null,
            ),
            _sectionHeader('WI-FI CREDENTIALS'),
            _field(
              controller: _wifiSsidController,
              label: 'Wi-Fi SSID',
              icon: Icons.wifi_rounded,
              action: TextInputAction.next,
              validator: (value) =>
                  (value == null || value.isEmpty) ? 'Required' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _wifiPasswordController,
              obscureText: _obscurePassword,
              textInputAction: TextInputAction.next,
              decoration: InputDecoration(
                labelText: 'Wi-Fi password',
                prefixIcon: const Icon(Icons.lock_outline_rounded, size: 20),
                suffixIcon: IconButton(
                  icon: Icon(
                    _obscurePassword
                        ? Icons.visibility_outlined
                        : Icons.visibility_off_outlined,
                    size: 20,
                    color: cs.onSurfaceVariant,
                  ),
                  onPressed: () =>
                      setState(() => _obscurePassword = !_obscurePassword),
                ),
              ),
              validator: (value) =>
                  (value == null || value.isEmpty) ? 'Required' : null,
            ),
            _sectionHeader('BACKEND TARGET'),
            _field(
              controller: _backendHostController,
              label: 'Backend host / IP',
              icon: Icons.dns_outlined,
              action: TextInputAction.next,
              validator: (value) =>
                  (value == null || value.isEmpty) ? 'Required' : null,
            ),
            const SizedBox(height: 12),
            _field(
              controller: _backendPortController,
              label: 'Backend port',
              icon: Icons.numbers_rounded,
              action: TextInputAction.next,
              keyboardType: TextInputType.number,
              validator: (value) =>
                  (value == null || int.tryParse(value) == null)
                      ? 'Valid port required'
                      : null,
            ),
            _sectionHeader('NODE CONFIGURATION'),
            DropdownButtonFormField<String>(
              initialValue: _nodeRole,
              decoration: const InputDecoration(
                labelText: 'Node role',
                prefixIcon: Icon(Icons.category_outlined, size: 20),
              ),
              items: _nodeRoleOptions
                  .map((role) =>
                      DropdownMenuItem(value: role, child: Text(role)))
                  .toList(),
              onChanged: (value) {
                final role = value ?? 'smoke_node1';
                final previousRole = _nodeRole;
                setState(() {
                  _nodeRole = role;
                  if (_nodeIdController.text.trim().isEmpty ||
                      _nodeIdController.text.trim() == previousRole) {
                    _nodeIdController.text = role;
                  }
                });
              },
            ),
            const SizedBox(height: 12),
            _field(
              controller: _nodeIdController,
              label: 'Node ID',
              icon: Icons.fingerprint_rounded,
              action: TextInputAction.done,
              validator: (value) =>
                  (value == null || value.isEmpty) ? 'Required' : null,
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _roomName,
              decoration: const InputDecoration(
                labelText: 'Room / location',
                prefixIcon: Icon(Icons.room_outlined, size: 20),
              ),
              items: _roomOptions
                  .map((room) =>
                      DropdownMenuItem(value: room, child: Text(room)))
                  .toList(),
              onChanged: (value) =>
                  setState(() => _roomName = value ?? 'Living Room'),
            ),
            const SizedBox(height: 28),
            FilledButton.icon(
              onPressed: _submitting ? null : _submit,
              icon: _submitting
                  ? const SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white),
                    )
                  : const Icon(Icons.send_rounded, size: 18),
              label: Text(_submitting ? 'Sending…' : 'Send Configuration'),
            ),
            const SizedBox(height: 16),
            Text(
              'Note: firmware currently supports roles door_force, smoke_node1, and smoke_node2. cam_door onboarding is planned in a follow-up firmware pass.',
              style: Theme.of(context).textTheme.bodySmall,
              textAlign: TextAlign.center,
            ),
            if (_result != null) ...[
              const SizedBox(height: 20),
              Container(
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
                  crossAxisAlignment: CrossAxisAlignment.start,
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
                        _result!,
                        style: Theme.of(context)
                            .textTheme
                            .bodySmall
                            ?.copyWith(height: 1.5),
                        maxLines: 6,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _field({
    required TextEditingController controller,
    required String label,
    String? hint,
    required IconData icon,
    required TextInputAction action,
    TextInputType? keyboardType,
    required String? Function(String?) validator,
  }) {
    return TextFormField(
      controller: controller,
      textInputAction: action,
      keyboardType: keyboardType,
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        prefixIcon: Icon(icon, size: 20),
      ),
      validator: validator,
    );
  }
}
