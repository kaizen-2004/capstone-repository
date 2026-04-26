import 'package:flutter/material.dart';

import '../core/network/api_client.dart';
import '../core/storage/settings_store.dart';
import '../services/backend_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({
    super.key,
    required this.settingsStore,
    this.onSaved,
  });

  final SettingsStore settingsStore;
  final VoidCallback? onSaved;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _backendBaseUrlController;
  late final TextEditingController _usernameController;
  late final TextEditingController _passwordController;
  late final TextEditingController _tokenController;
  late final TextEditingController _pollingController;
  String? _message;
  bool _isSuccess = false;
  bool _isFetchingToken = false;
  bool _obscurePassword = true;
  bool _obscureToken = true;

  @override
  void initState() {
    super.initState();
    _backendBaseUrlController =
        TextEditingController(text: widget.settingsStore.backendBaseUrl);
    _usernameController =
        TextEditingController(text: widget.settingsStore.authUsername);
    _passwordController =
        TextEditingController(text: widget.settingsStore.authPassword);
    _tokenController =
        TextEditingController(text: widget.settingsStore.authToken);
    _pollingController =
        TextEditingController(text: '${widget.settingsStore.pollingSeconds}');
  }

  @override
  void dispose() {
    _backendBaseUrlController.dispose();
    _usernameController.dispose();
    _passwordController.dispose();
    _tokenController.dispose();
    _pollingController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    await widget.settingsStore
        .setBackendBaseUrl(_backendBaseUrlController.text.trim());
    await widget.settingsStore.setAuthUsername(_usernameController.text.trim());
    await widget.settingsStore.setAuthPassword(_passwordController.text);
    await widget.settingsStore.setAuthToken(_tokenController.text.trim());
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

  Future<void> _fetchTokenFromCredentials() async {
    final backendBaseUrl = _backendBaseUrlController.text.trim();
    final username = _usernameController.text.trim();
    final password = _passwordController.text;

    if (backendBaseUrl.isEmpty || username.isEmpty || password.isEmpty) {
      setState(() {
        _message = 'Enter backend URL, username, and password first.';
        _isSuccess = false;
      });
      return;
    }

    setState(() {
      _isFetchingToken = true;
      _message = null;
    });

    try {
      final service = BackendService(
        ApiClient(baseUrl: backendBaseUrl, token: ''),
      );
      final token = await service.loginAndGetToken(
        username: username,
        password: password,
      );

      _tokenController.text = token;

      await widget.settingsStore.setBackendBaseUrl(backendBaseUrl);
      await widget.settingsStore.setAuthUsername(username);
      await widget.settingsStore.setAuthPassword(password);
      await widget.settingsStore.setAuthToken(token);

      widget.onSaved?.call();

      if (!mounted) {
        return;
      }
      setState(() {
        _message = 'Signed in. Bearer token refreshed.';
        _isSuccess = true;
      });
    } on ApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _message = error.message;
        _isSuccess = false;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _message = 'Unable to fetch token. Check connection and credentials.';
        _isSuccess = false;
      });
    } finally {
      if (mounted) {
        setState(() => _isFetchingToken = false);
      }
    }
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
        TextField(
          controller: _backendBaseUrlController,
          textInputAction: TextInputAction.next,
          decoration: const InputDecoration(
            labelText: 'Backend base URL',
            hintText: 'http://100.123.42.91:8765',
            prefixIcon: Icon(Icons.dns_outlined, size: 20),
          ),
        ),
        const SizedBox(height: 10),
        Text(
          'Monitor URL is automatic: <Backend base URL>/dashboard/remote/mobile',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        _sectionHeader('AUTHENTICATION', icon: Icons.key_outlined),
        TextField(
          controller: _usernameController,
          textInputAction: TextInputAction.next,
          decoration: const InputDecoration(
            labelText: 'Username',
            prefixIcon: Icon(Icons.person_outline_rounded, size: 20),
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _passwordController,
          obscureText: _obscurePassword,
          textInputAction: TextInputAction.next,
          decoration: InputDecoration(
            labelText: 'Password',
            prefixIcon: const Icon(Icons.password_rounded, size: 20),
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
        ),
        const SizedBox(height: 12),
        FilledButton.tonalIcon(
          onPressed: _isFetchingToken ? null : _fetchTokenFromCredentials,
          icon: _isFetchingToken
              ? SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: cs.onSecondaryContainer,
                  ),
                )
              : const Icon(Icons.login_rounded, size: 18),
          label: Text(
            _isFetchingToken ? 'Signing in...' : 'Sign in and Refresh Token',
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'You can still paste a token manually below if needed.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _tokenController,
          obscureText: _obscureToken,
          decoration: InputDecoration(
            labelText: 'Bearer token',
            prefixIcon: const Icon(Icons.lock_outline_rounded, size: 20),
            suffixIcon: IconButton(
              icon: Icon(
                _obscureToken
                    ? Icons.visibility_outlined
                    : Icons.visibility_off_outlined,
                size: 20,
                color: cs.onSurfaceVariant,
              ),
              onPressed: () => setState(() => _obscureToken = !_obscureToken),
            ),
          ),
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
