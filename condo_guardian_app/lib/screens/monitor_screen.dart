import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

class MonitorScreen extends StatefulWidget {
  const MonitorScreen({
    super.key,
    required this.backendBaseUrl,
    required this.authToken,
    required this.activeConnectionLabel,
    this.onOpenSettings,
  });

  final String backendBaseUrl;
  final String authToken;
  final String activeConnectionLabel;
  final VoidCallback? onOpenSettings;

  @override
  State<MonitorScreen> createState() => _MonitorScreenState();
}

class _MonitorScreenState extends State<MonitorScreen> {
  late WebViewController _controller;
  bool _loading = true;
  bool _hasError = false;
  int _loadingProgress = 0;
  String _lastError = '';
  DateTime _lastReloaded = DateTime.now();

  static const _embeddedDashboardPath = '/dashboard/remote/mobile?embedded=1';

  String get _mobileDashboardUrl {
    final normalizedBase = widget.backendBaseUrl.endsWith('/')
        ? widget.backendBaseUrl
        : '${widget.backendBaseUrl}/';
    final bootstrap =
        Uri.parse(normalizedBase).resolve('api/auth/mobile/webview-session');
    return bootstrap.replace(queryParameters: <String, String>{
      'token': widget.authToken.trim(),
      'next': _embeddedDashboardPath,
    }).toString();
  }

  String get _displayDashboardUrl {
    final normalizedBase = widget.backendBaseUrl.endsWith('/')
        ? widget.backendBaseUrl
        : '${widget.backendBaseUrl}/';
    return Uri.parse(normalizedBase)
        .resolve('dashboard/remote/mobile')
        .toString();
  }

  String get _friendlyError {
    final message = _lastError.trim();
    if (message.isEmpty) {
      return 'Could not reach the mobile dashboard. Check that the backend is running and this phone is on LAN or Tailscale.';
    }
    final lower = message.toLowerCase();
    if (lower.contains('host') || lower.contains('resolve')) {
      return 'Dashboard host could not be reached. Check the saved backend URL or Tailscale connection.';
    }
    if (lower.contains('timeout') || lower.contains('timed out')) {
      return 'Dashboard connection timed out. Check Wi-Fi, Tailscale, or backend availability.';
    }
    if (lower.contains('401') || lower.contains('unauthorized')) {
      return 'Your session expired. Sign out and sign in again.';
    }
    return message;
  }

  @override
  void initState() {
    super.initState();
    _initController();
  }

  @override
  void didUpdateWidget(covariant MonitorScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.backendBaseUrl != widget.backendBaseUrl ||
        oldWidget.authToken != widget.authToken) {
      _initController();
    }
  }

  void _initController() {
    final url = _mobileDashboardUrl;
    _lastReloaded = DateTime.now();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageStarted: (_) => setState(() {
            _loading = true;
            _hasError = false;
            _loadingProgress = 0;
            _lastError = '';
          }),
          onPageFinished: (_) => setState(() {
            _loading = false;
          }),
          onProgress: (progress) => setState(() => _loadingProgress = progress),
          onWebResourceError: (error) => setState(() {
            _hasError = true;
            _loading = false;
            _lastError = error.description;
          }),
        ),
      )
      ..loadRequest(Uri.parse(url));
  }

  void _reload() {
    setState(() {
      _loading = true;
      _hasError = false;
      _loadingProgress = 0;
      _lastError = '';
      _lastReloaded = DateTime.now();
    });
    _controller.loadRequest(Uri.parse(_mobileDashboardUrl));
  }

  String _formatClock(DateTime value) {
    final local = value.toLocal();
    final hour = local.hour % 12 == 0 ? 12 : local.hour % 12;
    final minute = local.minute.toString().padLeft(2, '0');
    final meridiem = local.hour >= 12 ? 'PM' : 'AM';
    return '$hour:$minute $meridiem';
  }

  Widget _statusPill({
    required IconData icon,
    required String label,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.32)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: color),
          const SizedBox(width: 5),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 11,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.2,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    const liveColor = Color(0xFF42A5F5);
    const okColor = Color(0xFF26A69A);

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 16, 16, 10),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF06111F), Color(0xFF0C2742)],
        ),
        border: Border.all(color: const Color(0xFF1B4A73)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x33000000),
            blurRadius: 18,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: liveColor.withValues(alpha: 0.16),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: liveColor.withValues(alpha: 0.3)),
                ),
                child: const Icon(
                  Icons.videocam_rounded,
                  color: liveColor,
                  size: 22,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Live Monitor',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.2,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Camera streams run inside the secured mobile view.',
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.68),
                        fontSize: 12,
                        height: 1.4,
                      ),
                    ),
                  ],
                ),
              ),
              IconButton.filledTonal(
                onPressed: _reload,
                tooltip: 'Refresh monitor',
                icon: const Icon(Icons.refresh_rounded, size: 20),
                style: IconButton.styleFrom(
                  backgroundColor: Colors.white.withValues(alpha: 0.10),
                  foregroundColor: Colors.white,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _statusPill(
                icon: Icons.radio_button_checked_rounded,
                label: 'Live',
                color: liveColor,
              ),
              _statusPill(
                icon: Icons.link_rounded,
                label: widget.activeConnectionLabel,
                color: okColor,
              ),
              _statusPill(
                icon: Icons.schedule_rounded,
                label: 'Reloaded ${_formatClock(_lastReloaded)}',
                color: const Color(0xFFFFCA28),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildLoadingOverlay(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      color: cs.surface,
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              SizedBox(
                width: 40,
                height: 40,
                child: CircularProgressIndicator(
                  strokeWidth: 2.5,
                  color: cs.primary,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                'Connecting to mobile monitor',
                style: Theme.of(context).textTheme.titleLarge,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 6),
              Text(
                'Checking camera streams and backend session.',
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildErrorOverlay(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      color: cs.surface,
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  color: cs.error.withValues(alpha: 0.10),
                  shape: BoxShape.circle,
                ),
                child: Icon(Icons.wifi_off_rounded, size: 30, color: cs.error),
              ),
              const SizedBox(height: 20),
              Text(
                'Mobile dashboard unavailable',
                style: Theme.of(context).textTheme.titleLarge,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                _friendlyError,
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(height: 1.55),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              Text(
                _displayDashboardUrl,
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: cs.primary),
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 22),
              FilledButton.icon(
                onPressed: _reload,
                icon: const Icon(Icons.refresh_rounded, size: 18),
                label: const Text('Retry'),
              ),
              if (widget.onOpenSettings != null) ...[
                const SizedBox(height: 8),
                TextButton.icon(
                  onPressed: widget.onOpenSettings,
                  icon: const Icon(Icons.tune_rounded, size: 18),
                  label: const Text('Open Settings'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildWebViewPane(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: cs.surfaceContainerHighest,
            border: Border.all(color: cs.outlineVariant),
          ),
          child: Stack(
            fit: StackFit.expand,
            children: [
              WebViewWidget(controller: _controller),
              if (_loading && _loadingProgress > 0 && _loadingProgress < 100)
                Positioned(
                  top: 0,
                  left: 0,
                  right: 0,
                  child: LinearProgressIndicator(
                    value: _loadingProgress / 100,
                    minHeight: 3,
                    color: cs.primary,
                    backgroundColor: Colors.transparent,
                  ),
                ),
              if (_loading && _loadingProgress == 0)
                _buildLoadingOverlay(context),
              if (_hasError) _buildErrorOverlay(context),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _buildHeader(context),
        Expanded(child: _buildWebViewPane(context)),
      ],
    );
  }
}
