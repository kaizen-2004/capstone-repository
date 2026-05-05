import 'package:flutter/material.dart';

import '../models/snapshot_item.dart';

class SnapshotImageWithOverlay extends StatefulWidget {
  const SnapshotImageWithOverlay({
    super.key,
    required this.imageUrl,
    required this.headers,
    required this.overlays,
    this.borderRadius = const BorderRadius.all(Radius.circular(12)),
  });

  final String imageUrl;
  final Map<String, String>? headers;
  final List<FaceOverlay> overlays;
  final BorderRadiusGeometry borderRadius;

  @override
  State<SnapshotImageWithOverlay> createState() =>
      _SnapshotImageWithOverlayState();
}

class _SnapshotImageWithOverlayState extends State<SnapshotImageWithOverlay> {
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
  void didUpdateWidget(covariant SnapshotImageWithOverlay oldWidget) {
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
      borderRadius: widget.borderRadius,
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
        ..strokeWidth = 1.2;
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
            fontSize: 8,
            fontWeight: FontWeight.w600,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout(maxWidth: size.width);

      const horizontalPadding = 4.0;
      const verticalPadding = 2.0;
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
        RRect.fromRectAndRadius(labelRect, const Radius.circular(3)),
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
