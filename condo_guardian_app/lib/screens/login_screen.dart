import 'package:flutter/material.dart';

import '../core/network/api_client.dart';
import '../core/network/backend_endpoint_resolver.dart';
import '../core/storage/settings_store.dart';
import '../services/backend_service.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({
    super.key,
    required this.settingsStore,
    required this.onAuthenticated,
  });

  final SettingsStore settingsStore;
  final VoidCallback onAuthenticated;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  late final TextEditingController _usernameController;
  late final TextEditingController _passwordController;
  late final TextEditingController _lanBaseUrlController;
  late final TextEditingController _tailscaleBaseUrlController;
  bool _submitting = false;
  bool _testingLan = false;
  bool _testingTailscale = false;
  bool _obscurePassword = true;
  String? _error;
  String? _lanTestMessage;
  String? _tailscaleTestMessage;

  @override
  void initState() {
    super.initState();
    _usernameController = TextEditingController(text: 'admin');
    _passwordController = TextEditingController();
    _lanBaseUrlController = TextEditingController(
      text: widget.settingsStore.lanBaseUrl,
    );
    _tailscaleBaseUrlController = TextEditingController(
      text: widget.settingsStore.tailscaleBaseUrl,
    );
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    _lanBaseUrlController.dispose();
    _tailscaleBaseUrlController.dispose();
    super.dispose();
  }

  Future<void> _saveBackendConfig() async {
    final lan = BackendEndpointResolver.normalizeBaseUrl(
      _lanBaseUrlController.text,
    );
    final tailscale = BackendEndpointResolver.normalizeBaseUrl(
      _tailscaleBaseUrlController.text,
    );
    await widget.settingsStore.setLanBaseUrl(lan);
    await widget.settingsStore.setTailscaleBaseUrl(tailscale);
  }

  Future<void> _testConnection({required bool tailscale}) async {
    final controller = tailscale
        ? _tailscaleBaseUrlController
        : _lanBaseUrlController;
    final normalized = BackendEndpointResolver.normalizeBaseUrl(
      controller.text,
    );

    if (normalized.isEmpty) {
      setState(() {
        if (tailscale) {
          _tailscaleTestMessage = 'Enter a valid URL first.';
        } else {
          _lanTestMessage = 'Enter a valid URL first.';
        }
      });
      return;
    }

    setState(() {
      if (tailscale) {
        _testingTailscale = true;
        _tailscaleTestMessage = null;
      } else {
        _testingLan = true;
        _lanTestMessage = null;
      }
    });

    try {
      final client = ApiClient(
        baseUrl: normalized,
        token: '',
        timeout: BackendEndpointResolver.probeTimeout,
      );
      await client.getJson('health');
      if (!mounted) {
        return;
      }
      setState(() {
        if (tailscale) {
          _tailscaleTestMessage = 'Connection OK';
        } else {
          _lanTestMessage = 'Connection OK';
        }
      });
    } on ApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        final text = 'Failed: ${error.message}';
        if (tailscale) {
          _tailscaleTestMessage = text;
        } else {
          _lanTestMessage = text;
        }
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        if (tailscale) {
          _tailscaleTestMessage = 'Failed: endpoint unreachable';
        } else {
          _lanTestMessage = 'Failed: endpoint unreachable';
        }
      });
    } finally {
      if (mounted) {
        setState(() {
          if (tailscale) {
            _testingTailscale = false;
          } else {
            _testingLan = false;
          }
        });
      }
    }
  }

  Future<void> _submit() async {
    final username = _usernameController.text.trim();
    final password = _passwordController.text;
    await _saveBackendConfig();
    final candidates = BackendEndpointResolver.candidatesFromStore(
      widget.settingsStore,
    );

    if (username.isEmpty || password.isEmpty || candidates.isEmpty) {
      setState(() {
        _error =
            'Enter your username and password and configure one backend URL.';
      });
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });

    try {
      String token = '';
      BackendEndpointResolution? resolved;
      Object? lastError;

      for (final candidate in candidates) {
        try {
          final service = BackendService(
            ApiClient(
              baseUrl: candidate.baseUrl,
              token: '',
              timeout: BackendEndpointResolver.probeTimeout,
            ),
          );
          token = await service.loginAndGetToken(
            username: username,
            password: password,
          );
          resolved = candidate;
          break;
        } catch (error) {
          lastError = error;
        }
      }

      final resolvedEndpoint = resolved;
      if (resolvedEndpoint == null || token.isEmpty) {
        throw ApiException(
          'Unable to sign in to any configured endpoint. Last error: $lastError',
        );
      }

      await widget.settingsStore
          .setActiveBackendBaseUrl(resolvedEndpoint.baseUrl);
      await widget.settingsStore.setAuthToken(token);
      await BackendEndpointResolver.refreshBootstrap(
        widget.settingsStore,
        baseUrl: resolvedEndpoint.baseUrl,
        token: token,
      );

      if (!mounted) {
        return;
      }
      widget.onAuthenticated();
    } on ApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = error.message;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error =
            'Unable to sign in. Check your credentials and backend connection.';
      });
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final lanOk = _lanTestMessage == 'Connection OK';
    final tailscaleOk = _tailscaleTestMessage == 'Connection OK';

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            width: 46,
                            height: 46,
                            decoration: BoxDecoration(
                              color: cs.primary.withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(14),
                            ),
                            clipBehavior: Clip.antiAlias,
                            child: const Image(
                              image: AssetImage('assets/logo.png'),
                              fit: BoxFit.cover,
                            ),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Sign In',
                                  style: Theme.of(context).textTheme.titleLarge,
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  'Authenticate once to unlock the monitoring app.',
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 20),
                      TextField(
                        controller: _lanBaseUrlController,
                        keyboardType: TextInputType.url,
                        textInputAction: TextInputAction.next,
                        decoration: const InputDecoration(
                          labelText: 'Local Backend URL',
                          hintText: 'http://192.168.x.x:8765',
                          prefixIcon:
                              Icon(Icons.router_outlined, size: 20),
                        ),
                      ),
                      const SizedBox(height: 8),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: OutlinedButton.icon(
                          onPressed: _testingLan
                              ? null
                              : () => _testConnection(tailscale: false),
                          icon: _testingLan
                              ? const SizedBox(
                                  width: 14,
                                  height: 14,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Icon(Icons.wifi_tethering_rounded, size: 16),
                          label: Text(_testingLan
                              ? 'Testing...'
                              : 'Test Local Connection'),
                        ),
                      ),
                      if (_lanTestMessage != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Text(
                            _lanTestMessage!,
                            style:
                                Theme.of(context).textTheme.bodySmall?.copyWith(
                                      color: lanOk ? Colors.green[700] : cs.error,
                                      fontWeight: lanOk
                                          ? FontWeight.w600
                                          : FontWeight.w500,
                                    ),
                          ),
                        ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _tailscaleBaseUrlController,
                        keyboardType: TextInputType.url,
                        textInputAction: TextInputAction.next,
                        decoration: const InputDecoration(
                          labelText: 'Tailscale Backend URL',
                          hintText: 'http://100.x.x.x:8765',
                          prefixIcon:
                              Icon(Icons.vpn_lock_outlined, size: 20),
                        ),
                      ),
                      const SizedBox(height: 8),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: OutlinedButton.icon(
                          onPressed: _testingTailscale
                              ? null
                              : () => _testConnection(tailscale: true),
                          icon: _testingTailscale
                              ? const SizedBox(
                                  width: 14,
                                  height: 14,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Icon(Icons.network_check_rounded, size: 16),
                          label: Text(_testingTailscale
                              ? 'Testing...'
                              : 'Test Tailscale Connection'),
                        ),
                      ),
                      if (_tailscaleTestMessage != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Text(
                            _tailscaleTestMessage!,
                            style:
                                Theme.of(context).textTheme.bodySmall?.copyWith(
                                      color: tailscaleOk
                                          ? Colors.green[700]
                                          : cs.error,
                                      fontWeight: tailscaleOk
                                          ? FontWeight.w600
                                          : FontWeight.w500,
                                    ),
                          ),
                        ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _usernameController,
                        textInputAction: TextInputAction.next,
                        decoration: const InputDecoration(
                          labelText: 'Username',
                          prefixIcon:
                              Icon(Icons.person_outline_rounded, size: 20),
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _passwordController,
                        obscureText: _obscurePassword,
                        textInputAction: TextInputAction.done,
                        onSubmitted: (_) => _submitting ? null : _submit(),
                        decoration: InputDecoration(
                          labelText: 'Password',
                          prefixIcon:
                              const Icon(Icons.lock_outline_rounded, size: 20),
                          suffixIcon: IconButton(
                            icon: Icon(
                              _obscurePassword
                                  ? Icons.visibility_outlined
                                  : Icons.visibility_off_outlined,
                              size: 20,
                              color: cs.onSurfaceVariant,
                            ),
                            onPressed: () => setState(
                              () => _obscurePassword = !_obscurePassword,
                            ),
                          ),
                        ),
                      ),
                      if (_error != null) ...[
                        const SizedBox(height: 12),
                        Text(
                          _error!,
                          style:
                              Theme.of(context).textTheme.bodySmall?.copyWith(
                                    color: cs.error,
                                  ),
                        ),
                      ],
                      const SizedBox(height: 18),
                      FilledButton.icon(
                        onPressed: _submitting ? null : _submit,
                        icon: _submitting
                            ? SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: cs.onPrimary,
                                ),
                              )
                            : const Icon(Icons.login_rounded, size: 18),
                        label: Text(_submitting ? 'Signing in...' : 'Sign In'),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
