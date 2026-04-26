import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../core/storage/settings_store.dart';
import '../models/snapshot_item.dart';
import '../services/backend_service.dart';

class SnapshotsScreen extends StatefulWidget {
  const SnapshotsScreen({
    super.key,
    required this.backendService,
    required this.settingsStore,
  });

  final BackendService backendService;
  final SettingsStore settingsStore;

  @override
  State<SnapshotsScreen> createState() => _SnapshotsScreenState();
}

class _SnapshotsScreenState extends State<SnapshotsScreen> {
  static const MethodChannel _filesChannel = MethodChannel('intruflare/files');

  bool _loading = true;
  String? _error;
  List<SnapshotItem> _snapshots = <SnapshotItem>[];
  String? _busySnapshotId;

  @override
  void initState() {
    super.initState();
    _loadSnapshots();
  }

  Future<void> _loadSnapshots() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final snapshots = await widget.backendService.fetchSnapshots();
      if (!mounted) {
        return;
      }
      setState(() {
        _snapshots = snapshots;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loading = false;
        _error = '$error';
      });
    }
  }

  String _absoluteSnapshotUrl(String snapshotPath) {
    final normalizedBase = widget.settingsStore.backendBaseUrl.endsWith('/')
        ? widget.settingsStore.backendBaseUrl
        : '${widget.settingsStore.backendBaseUrl}/';
    return Uri.parse(normalizedBase).resolve(snapshotPath).toString();
  }

  Map<String, String>? get _imageHeaders {
    final token = widget.settingsStore.authToken.trim();
    if (token.isEmpty) {
      return null;
    }
    return <String, String>{'Authorization': 'Bearer $token'};
  }

  String _displayTitle(SnapshotItem snapshot) {
    return snapshot.isPersonSnapshot ? 'Person Detected' : snapshot.title;
  }

  String _snapshotFileName(SnapshotItem snapshot) {
    final stamp = snapshot.capturedAt.toUtc().toIso8601String();
    final safeStamp = stamp.replaceAll(':', '-').replaceAll('.', '-');
    return 'snapshot_${snapshot.id}_$safeStamp.jpg';
  }

  Future<void> _downloadSnapshot(SnapshotItem snapshot) async {
    if (defaultTargetPlatform != TargetPlatform.android) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Download is currently supported on Android devices.')),
      );
      return;
    }

    setState(() => _busySnapshotId = snapshot.id);
    try {
      final headers = <String, String>{};
      final token = widget.settingsStore.authToken.trim();
      if (token.isNotEmpty) {
        headers['Authorization'] = 'Bearer $token';
      }

      await _filesChannel.invokeMethod<dynamic>('downloadSnapshot', <String, dynamic>{
        'url': _absoluteSnapshotUrl(snapshot.snapshotPath),
        'fileName': _snapshotFileName(snapshot),
        'headers': headers,
      });

      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Snapshot download queued. Check notifications.')),
      );
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Download failed: $error')),
      );
    } finally {
      if (mounted) {
        setState(() => _busySnapshotId = null);
      }
    }
  }

  Future<void> _deleteSnapshot(SnapshotItem snapshot) async {
    final shouldDelete = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Delete snapshot?'),
            content: const Text('This will remove the image from local storage. This action cannot be undone.'),
            actions: <Widget>[
              TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text('Delete'),
              ),
            ],
          ),
        ) ??
        false;
    if (!shouldDelete) {
      return;
    }

    setState(() => _busySnapshotId = snapshot.id);
    try {
      await widget.backendService.deleteSnapshot(snapshot.id);
      if (!mounted) {
        return;
      }
      setState(() {
        _snapshots = _snapshots.where((item) => item.id != snapshot.id).toList();
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Snapshot deleted.')),
      );
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Delete failed: $error')),
      );
    } finally {
      if (mounted) {
        setState(() => _busySnapshotId = null);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Snapshots')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        Text(
                          'Could not load snapshots.',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 8),
                        Text(_error!),
                        const SizedBox(height: 12),
                        FilledButton(
                          onPressed: _loadSnapshots,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : _snapshots.isEmpty
                  ? const Center(
                      child: Text('No alert snapshots available yet.'))
                  : RefreshIndicator(
                      onRefresh: _loadSnapshots,
                      child: ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: _snapshots.length,
                        itemBuilder: (context, index) {
                          final snapshot = _snapshots[index];
                          final url =
                              _absoluteSnapshotUrl(snapshot.snapshotPath);
                          return Card(
                            child: Padding(
                              padding: const EdgeInsets.all(12),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: <Widget>[
                                  _SnapshotImageWithOverlay(
                                    imageUrl: url,
                                    headers: _imageHeaders,
                                    overlays: snapshot.faceOverlays,
                                  ),
                                  const SizedBox(height: 10),
                                  Text(
                                    _displayTitle(snapshot),
                                    style:
                                        Theme.of(context).textTheme.titleMedium,
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    '${snapshot.severity.toUpperCase()} • ${snapshot.sourceNode} • ${snapshot.location}',
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                      snapshot.capturedAt.toLocal().toString()),
                                  const SizedBox(height: 8),
                                  Wrap(
                                    spacing: 8,
                                    runSpacing: 8,
                                    children: <Widget>[
                                      OutlinedButton.icon(
                                        onPressed: _busySnapshotId == snapshot.id
                                            ? null
                                            : () => _downloadSnapshot(snapshot),
                                        icon: const Icon(Icons.download_rounded, size: 18),
                                        label: const Text('Download'),
                                      ),
                                      OutlinedButton.icon(
                                        onPressed: _busySnapshotId == snapshot.id
                                            ? null
                                            : () => _deleteSnapshot(snapshot),
                                        icon: const Icon(Icons.delete_outline_rounded, size: 18),
                                        label: const Text('Delete'),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}

class _SnapshotImageWithOverlay extends StatefulWidget {
  const _SnapshotImageWithOverlay({
    required this.imageUrl,
    required this.headers,
    required this.overlays,
  });

  final String imageUrl;
  final Map<String, String>? headers;
  final List<FaceOverlay> overlays;

  @override
  State<_SnapshotImageWithOverlay> createState() =>
      _SnapshotImageWithOverlayState();
}

class _SnapshotImageWithOverlayState extends State<_SnapshotImageWithOverlay> {
  NetworkImage? _provider;
  ImageStream? _stream;
  ImageStreamListener? _listener;
  Size? _imageSize;
  bool _imageFailed = false;

  @override
  void initState() {
    super.initState();
    _resolveImageSize();
  }

  @override
  void didUpdateWidget(covariant _SnapshotImageWithOverlay oldWidget) {
    super.didUpdateWidget(oldWidget);
    final sameHeaders = _mapEquals(oldWidget.headers, widget.headers);
    if (oldWidget.imageUrl != widget.imageUrl || !sameHeaders) {
      _resolveImageSize();
    }
  }

  @override
  void dispose() {
    _detachImageStream();
    super.dispose();
  }

  bool _mapEquals(Map<String, String>? a, Map<String, String>? b) {
    if (identical(a, b)) {
      return true;
    }
    if (a == null || b == null || a.length != b.length) {
      return false;
    }
    for (final entry in a.entries) {
      if (b[entry.key] != entry.value) {
        return false;
      }
    }
    return true;
  }

  void _detachImageStream() {
    final stream = _stream;
    final listener = _listener;
    if (stream != null && listener != null) {
      stream.removeListener(listener);
    }
    _stream = null;
    _listener = null;
  }

  void _resolveImageSize() {
    _detachImageStream();

    final provider = NetworkImage(widget.imageUrl, headers: widget.headers);
    _provider = provider;
    final stream = provider.resolve(const ImageConfiguration());
    final listener = ImageStreamListener(
      (image, _) {
        if (!mounted) {
          return;
        }
        final nextSize =
            Size(image.image.width.toDouble(), image.image.height.toDouble());
        setState(() {
          _imageSize = nextSize;
          _imageFailed = false;
        });
      },
      onError: (_, __) {
        if (!mounted) {
          return;
        }
        setState(() {
          _imageFailed = true;
          _imageSize = null;
        });
      },
    );

    stream.addListener(listener);
    _stream = stream;
    _listener = listener;
  }

  @override
  Widget build(BuildContext context) {
    final provider = _provider ??
        NetworkImage(
          widget.imageUrl,
          headers: widget.headers,
        );

    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: AspectRatio(
        aspectRatio: 16 / 9,
        child: _imageFailed
            ? Container(
                color: Colors.black12,
                alignment: Alignment.center,
                child: const Text('Snapshot unavailable'),
              )
            : LayoutBuilder(
                builder: (context, constraints) {
                  final viewSize = Size(
                    constraints.maxWidth,
                    constraints.maxHeight,
                  );
                  return Stack(
                    fit: StackFit.expand,
                    children: <Widget>[
                      Image(
                        image: provider,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => Container(
                          color: Colors.black12,
                          alignment: Alignment.center,
                          child: const Text('Snapshot unavailable'),
                        ),
                      ),
                      if (_imageSize != null && widget.overlays.isNotEmpty)
                        CustomPaint(
                          painter: _FaceOverlayPainter(
                            overlays: widget.overlays,
                            imageSize: _imageSize!,
                            viewSize: viewSize,
                          ),
                        ),
                    ],
                  );
                },
              ),
      ),
    );
  }
}

class _FaceOverlayPainter extends CustomPainter {
  _FaceOverlayPainter({
    required this.overlays,
    required this.imageSize,
    required this.viewSize,
  });

  final List<FaceOverlay> overlays;
  final Size imageSize;
  final Size viewSize;

  @override
  void paint(Canvas canvas, Size size) {
    if (overlays.isEmpty || imageSize.width <= 0 || imageSize.height <= 0) {
      return;
    }

    final fitted = applyBoxFit(BoxFit.cover, imageSize, viewSize);
    final sourceRect =
        Alignment.center.inscribe(fitted.source, Offset.zero & imageSize);
    final destinationRect =
        Alignment.center.inscribe(fitted.destination, Offset.zero & viewSize);

    for (final overlay in overlays) {
      final rawRect = Rect.fromLTWH(
        overlay.x.toDouble(),
        overlay.y.toDouble(),
        overlay.width.toDouble(),
        overlay.height.toDouble(),
      );

      final clippedSource = rawRect.intersect(sourceRect);
      if (clippedSource.isEmpty ||
          clippedSource.width <= 0 ||
          clippedSource.height <= 0) {
        continue;
      }

      final leftFraction =
          (clippedSource.left - sourceRect.left) / sourceRect.width;
      final topFraction =
          (clippedSource.top - sourceRect.top) / sourceRect.height;
      final widthFraction = clippedSource.width / sourceRect.width;
      final heightFraction = clippedSource.height / sourceRect.height;

      final destinationBox = Rect.fromLTWH(
        destinationRect.left + leftFraction * destinationRect.width,
        destinationRect.top + topFraction * destinationRect.height,
        widthFraction * destinationRect.width,
        heightFraction * destinationRect.height,
      );

      final clampedBox = destinationBox.intersect(Offset.zero & size);
      if (clampedBox.isEmpty ||
          clampedBox.width <= 0 ||
          clampedBox.height <= 0) {
        continue;
      }

      final borderColor = overlay.isAuthorized
          ? const Color(0xFF2ECC71)
          : const Color(0xFFFF9800);
      final borderPaint = Paint()
        ..color = borderColor
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.0;
      canvas.drawRect(clampedBox, borderPaint);

      final normalizedClassification = overlay.classification.toUpperCase();
      final labelText = normalizedClassification == 'AUTHORIZED'
          ? 'AUTH'
          : (normalizedClassification == 'NON-AUTHORIZED' ||
                  normalizedClassification == 'UNAUTHORIZED' ||
                  normalizedClassification == 'UNKNOWN')
              ? 'NON-AUTH'
              : 'PERSON';
      final textPainter = TextPainter(
        text: TextSpan(
          text: labelText,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 10,
            fontWeight: FontWeight.w600,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout(maxWidth: size.width);

      const horizontalPadding = 6.0;
      const verticalPadding = 3.0;
      final labelWidth = textPainter.width + horizontalPadding * 2;
      final labelHeight = textPainter.height + verticalPadding * 2;

      var labelLeft = clampedBox.left;
      if (labelLeft + labelWidth > size.width) {
        labelLeft = size.width - labelWidth;
      }
      if (labelLeft < 0) {
        labelLeft = 0;
      }

      var labelTop = clampedBox.top - labelHeight;
      if (labelTop < 0) {
        labelTop = clampedBox.top;
      }

      final labelRect = Rect.fromLTWH(
        labelLeft,
        labelTop,
        labelWidth,
        labelHeight,
      );

      final labelPaint = Paint()..color = borderColor.withValues(alpha: 0.92);
      canvas.drawRRect(
        RRect.fromRectAndRadius(labelRect, const Radius.circular(4)),
        labelPaint,
      );

      textPainter.paint(
        canvas,
        Offset(labelLeft + horizontalPadding, labelTop + verticalPadding),
      );
    }
  }

  @override
  bool shouldRepaint(covariant _FaceOverlayPainter oldDelegate) {
    return oldDelegate.imageSize != imageSize ||
        oldDelegate.viewSize != viewSize ||
        oldDelegate.overlays != overlays;
  }
}
