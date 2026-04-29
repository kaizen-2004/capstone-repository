import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

class MonitorScreen extends StatefulWidget {
  const MonitorScreen({
    super.key,
    required this.backendBaseUrl,
    required this.authToken,
  });

  final String backendBaseUrl;
  final String authToken;

  @override
  State<MonitorScreen> createState() => _MonitorScreenState();
}

class _MonitorScreenState extends State<MonitorScreen> {
  late WebViewController _controller;
  bool _loading = true;
  bool _hasError = false;
  int _loadingProgress = 0;
  String _lastError = '';

  String get _mobileDashboardUrl {
    final normalizedBase = widget.backendBaseUrl.endsWith('/')
        ? widget.backendBaseUrl
        : '${widget.backendBaseUrl}/';
    final bootstrap =
        Uri.parse(normalizedBase).resolve('api/auth/mobile/webview-session');
    return bootstrap.replace(queryParameters: <String, String>{
      'token': widget.authToken.trim(),
      'next': '/dashboard/remote/mobile',
    }).toString();
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
    });
    _controller.loadRequest(Uri.parse(_mobileDashboardUrl));
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Stack(
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
          Container(
            color: cs.surface,
            child: Center(
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
                    'Loading mobile dashboard…',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    _mobileDashboardUrl,
                    style: Theme.of(context).textTheme.bodySmall,
                    textAlign: TextAlign.center,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ),
        if (_hasError)
          Container(
            color: cs.surface,
            child: Center(
              child: Padding(
                padding: const EdgeInsets.all(32),
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
                      child: Icon(Icons.wifi_off_rounded,
                          size: 30, color: cs.error),
                    ),
                    const SizedBox(height: 20),
                    Text(
                      'Mobile dashboard unavailable',
                      style: Theme.of(context).textTheme.titleLarge,
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _lastError.isEmpty
                          ? 'Could not reach the mobile dashboard endpoint. Check backend connectivity.'
                          : _lastError,
                      style: Theme.of(context)
                          .textTheme
                          .bodySmall
                          ?.copyWith(height: 1.55),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _mobileDashboardUrl,
                      style: Theme.of(context)
                          .textTheme
                          .bodySmall
                          ?.copyWith(color: cs.primary),
                      textAlign: TextAlign.center,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 24),
                    FilledButton.icon(
                      onPressed: _reload,
                      icon: const Icon(Icons.refresh_rounded, size: 18),
                      label: const Text('Retry'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        if (!_loading && !_hasError)
          Positioned(
            top: 12,
            right: 12,
            child: Material(
              color: cs.surfaceContainerHighest.withValues(alpha: 0.9),
              borderRadius: BorderRadius.circular(8),
              child: InkWell(
                borderRadius: BorderRadius.circular(8),
                onTap: _reload,
                child: Padding(
                  padding: const EdgeInsets.all(8),
                  child: Icon(Icons.refresh_rounded,
                      size: 18, color: cs.onSurface),
                ),
              ),
            ),
          ),
      ],
    );
  }
}
