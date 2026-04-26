import 'dart:io';
import 'dart:math';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/network/api_client.dart';
import '../services/backend_service.dart';

class EnrollmentScreen extends StatefulWidget {
  const EnrollmentScreen({super.key, required this.backendService});

  final BackendService backendService;

  @override
  State<EnrollmentScreen> createState() => _EnrollmentScreenState();
}

class _EnrollmentScreenState extends State<EnrollmentScreen> {
  final _nameController = TextEditingController();
  final _userCodeController = TextEditingController();
  final List<XFile> _images = [];
  final _random = Random();
  List<FaceProfile> _existingProfiles = const [];
  String? _selectedProfileId;
  String? _profilesError;
  bool _loadingProfiles = false;
  bool _uploading = false;
  String? _result;
  bool _isSuccess = false;
  EnrollmentStatus? _enrollmentStatus;

  static const _requiredSamples = 5;

  @override
  void initState() {
    super.initState();
    _loadExistingProfiles();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _userCodeController.dispose();
    super.dispose();
  }

  Future<void> _openInAppCamera() async {
    if (_uploading) {
      return;
    }

    final captured = await Navigator.of(context).push<List<XFile>>(
      MaterialPageRoute<List<XFile>>(
        builder: (_) => _InAppCaptureScreen(
          initialCount: _images.length,
          requiredCount: _requiredSamples,
        ),
      ),
    );
    if (!mounted || captured == null || captured.isEmpty) {
      return;
    }

    setState(() => _images.addAll(captured));
    final remainingLocal = max(0, _requiredSamples - _images.length);
    if (remainingLocal == 0) {
      _showResult(
        'Added ${captured.length} sample(s). Ready to upload this batch.',
        success: true,
      );
    } else {
      _showResult(
        'Added ${captured.length} sample(s). Capture $remainingLocal more for this batch.',
        success: true,
      );
    }
  }

  void _removeImage(int index) => setState(() => _images.removeAt(index));

  String _generateUserCode() {
    final now = DateTime.now();
    final date =
        '${now.year}${now.month.toString().padLeft(2, '0')}${now.day.toString().padLeft(2, '0')}';
    final suffix = (_random.nextInt(9000) + 1000).toString();
    return 'USR-$date-$suffix';
  }

  void _autoGenerateUserCode() {
    setState(() {
      _selectedProfileId = '';
      _userCodeController.text = _generateUserCode();
    });
  }

  String _formatEnrollmentProgress(EnrollmentStatus status) {
    final minRequired =
        status.minRequired > 0 ? status.minRequired : status.target;
    final target = status.target > 0 ? status.target : minRequired;
    return 'Backend progress: ${status.count}/$target samples (${status.remaining} remaining, min $minRequired).';
  }

  bool _isMinimumSamplesError(String message) {
    return message.toLowerCase().contains('minimum samples not met');
  }

  String _friendlyEnrollmentMessage(String message) {
    if (_isMinimumSamplesError(message)) {
      final remainingMatch =
          RegExp(r'remaining\s*=\s*(\d+)').firstMatch(message);
      final remaining = int.tryParse(remainingMatch?.group(1) ?? '');
      if (remaining != null) {
        return 'Upload succeeded. $remaining more sample(s) needed before training can complete.';
      }
      return 'Upload succeeded. More samples are needed before training can complete.';
    }
    return message;
  }

  Future<void> _loadExistingProfiles() async {
    setState(() {
      _loadingProfiles = true;
      _profilesError = null;
    });
    try {
      final profiles = await widget.backendService.fetchFaceProfiles();
      if (!mounted) {
        return;
      }
      setState(() {
        _existingProfiles = profiles;
        _loadingProfiles = false;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loadingProfiles = false;
        _profilesError = 'Unable to load existing profiles.';
      });
    }
  }

  void _onProfileSelected(String? profileId) {
    final selectedId = (profileId ?? '').trim();
    setState(() {
      _selectedProfileId = selectedId;
    });

    if (selectedId.isEmpty) {
      return;
    }

    final match = _existingProfiles.where((p) => p.profileId == selectedId);
    if (match.isEmpty) {
      return;
    }

    final profile = match.first;
    _nameController.text = profile.name;
    _userCodeController.text = profile.profileId;
  }

  Future<void> _submitEnrollment() async {
    final name = _nameController.text.trim();
    var userCode = _userCodeController.text.trim();
    if (name.isEmpty) {
      _showResult('Authorized user full name is required.', success: false);
      return;
    }
    if (userCode.isEmpty) {
      userCode = _generateUserCode();
      _userCodeController.text = userCode;
    }
    if (_images.length < _requiredSamples) {
      _showResult(
        'Capture at least $_requiredSamples images before completing enrollment.',
        success: false,
      );
      return;
    }
    setState(() {
      _uploading = true;
      _result = null;
    });
    var uploadedAllSamples = false;
    try {
      final startStatus = await widget.backendService
          .submitEnrollmentStart(fullName: name, userCode: userCode);
      if (mounted) {
        setState(() => _enrollmentStatus = startStatus);
      }

      for (var i = 0; i < _images.length; i++) {
        final uploadStatus = await widget.backendService.uploadEnrollmentImage(
          userCode: userCode,
          filePath: _images[i].path,
          sampleIndex: i + 1,
        );
        if (mounted) {
          setState(() => _enrollmentStatus = uploadStatus);
        }
      }
      uploadedAllSamples = true;

      final completeStatus =
          await widget.backendService.completeEnrollment(userCode: userCode);
      if (mounted) {
        setState(() => _enrollmentStatus = completeStatus);
      }

      _showResult(
        'Enrollment completed. ${_formatEnrollmentProgress(completeStatus)}',
        success: true,
      );
      _images.clear();
      await _loadExistingProfiles();
    } on ApiException catch (error) {
      final isMinimumSamples = _isMinimumSamplesError(error.message);
      if (uploadedAllSamples && isMinimumSamples) {
        _images.clear();
        await _loadExistingProfiles();
      }
      _showResult(
        _friendlyEnrollmentMessage(error.message),
        success: uploadedAllSamples && isMinimumSamples,
      );
    } catch (_) {
      _showResult('Enrollment upload failed. Please try again.',
          success: false);
    } finally {
      if (mounted) {
        setState(() => _uploading = false);
      }
    }
  }

  void _showResult(String message, {required bool success}) => setState(() {
        _result = message;
        _isSuccess = success;
      });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;
    final progress = (_images.length / _requiredSamples).clamp(0.0, 1.0);
    final captureBusy = _uploading;
    final selectedProfileId =
        _existingProfiles.any((p) => p.profileId == _selectedProfileId)
            ? (_selectedProfileId ?? '')
            : '';
    final hasExistingProfile = selectedProfileId.isNotEmpty;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
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
              Icon(Icons.info_outline_rounded, size: 18, color: cs.primary),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Capture authorized user samples fully inside the app camera. You can create a new profile or select an existing one to add more images.',
                  style: tt.bodySmall?.copyWith(height: 1.55),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        Row(
          children: [
            Text(
              'EXISTING PROFILE (OPTIONAL)',
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w700,
                color: cs.onSurfaceVariant,
                letterSpacing: 1.3,
              ),
            ),
            const Spacer(),
            IconButton(
              onPressed: captureBusy || _loadingProfiles
                  ? null
                  : _loadExistingProfiles,
              tooltip: 'Refresh profiles',
              icon: const Icon(Icons.refresh_rounded, size: 18),
            ),
          ],
        ),
        if (_loadingProfiles)
          const Padding(
            padding: EdgeInsets.only(top: 4, bottom: 8),
            child: LinearProgressIndicator(minHeight: 2),
          ),
        DropdownButtonFormField<String>(
          key: ValueKey<String>(selectedProfileId),
          initialValue: selectedProfileId,
          decoration: const InputDecoration(
            labelText: 'Select existing profile',
            prefixIcon: Icon(Icons.folder_shared_outlined, size: 20),
          ),
          items: [
            const DropdownMenuItem<String>(
              value: '',
              child: Text('Create new profile'),
            ),
            ..._existingProfiles.map(
              (profile) => DropdownMenuItem<String>(
                value: profile.profileId,
                child: Text(
                  profile.displayLabel,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ),
          ],
          onChanged: captureBusy ? null : _onProfileSelected,
        ),
        if (_profilesError != null) ...[
          const SizedBox(height: 8),
          Text(
            _profilesError!,
            style: tt.bodySmall?.copyWith(color: cs.error),
          ),
        ],
        const SizedBox(height: 20),
        Text(
          'USER DETAILS',
          style: TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w700,
            color: cs.onSurfaceVariant,
            letterSpacing: 1.3,
          ),
        ),
        const SizedBox(height: 10),
        TextField(
          controller: _nameController,
          textInputAction: TextInputAction.next,
          readOnly: hasExistingProfile,
          decoration: const InputDecoration(
            labelText: 'Authorized user full name',
            prefixIcon: Icon(Icons.person_outline_rounded, size: 20),
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _userCodeController,
          textInputAction: TextInputAction.done,
          decoration: InputDecoration(
            labelText: 'User code / profile ID',
            prefixIcon: const Icon(Icons.badge_outlined, size: 20),
            suffixIcon: IconButton(
              onPressed: captureBusy ? null : _autoGenerateUserCode,
              tooltip: 'Auto-generate user code',
              icon: const Icon(Icons.auto_awesome_outlined, size: 20),
            ),
          ),
        ),
        const SizedBox(height: 24),
        Row(
          children: [
            Text(
              'FACE SAMPLES',
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w700,
                color: cs.onSurfaceVariant,
                letterSpacing: 1.3,
              ),
            ),
            const Spacer(),
            Text(
              '${_images.length} / $_requiredSamples',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: _images.length >= _requiredSamples
                    ? const Color(0xFF26A69A)
                    : cs.primary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: progress,
            minHeight: 4,
            color: _images.length >= _requiredSamples
                ? const Color(0xFF26A69A)
                : cs.primary,
            backgroundColor: cs.outlineVariant,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          _enrollmentStatus == null
              ? 'Batch minimum is $_requiredSamples images. Backend training requires more total samples over time.'
              : _formatEnrollmentProgress(_enrollmentStatus!),
          style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant),
        ),
        const SizedBox(height: 14),
        LayoutBuilder(
          builder: (context, constraints) {
            final itemSize = (constraints.maxWidth - 48) / 4;
            return Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                ..._images.asMap().entries.map(
                      (entry) => _ImageThumb(
                        index: entry.key,
                        file: entry.value,
                        size: itemSize,
                        onRemove: () => _removeImage(entry.key),
                      ),
                    ),
                GestureDetector(
                  onTap: captureBusy ? null : _openInAppCamera,
                  child: Container(
                    width: itemSize,
                    height: itemSize,
                    decoration: BoxDecoration(
                      color: cs.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                          color: cs.primary.withValues(alpha: 0.4), width: 1.5),
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.add_a_photo_outlined,
                          size: 20,
                          color: cs.primary,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Add',
                          style: TextStyle(
                            color: cs.primary,
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            );
          },
        ),
        const SizedBox(height: 10),
        FilledButton.tonalIcon(
          onPressed: captureBusy ? null : _openInAppCamera,
          icon: const Icon(Icons.camera_alt_outlined, size: 18),
          label: const Text('Open In-App Camera'),
        ),
        const SizedBox(height: 8),
        Text(
          'Camera stays inside the app. Capture multiple shots continuously, then tap Done.',
          style: tt.bodySmall?.copyWith(color: cs.onSurfaceVariant),
        ),
        const SizedBox(height: 20),
        FilledButton.icon(
          onPressed: captureBusy ? null : _submitEnrollment,
          icon: _uploading
              ? const SizedBox.square(
                  dimension: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white,
                  ),
                )
              : const Icon(Icons.cloud_upload_outlined, size: 20),
          label: Text(_uploading ? 'Uploading…' : 'Upload Enrollment'),
        ),
        if (_result != null) ...[
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
                    style: tt.bodySmall?.copyWith(height: 1.5),
                    maxLines: 5,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

class _ImageThumb extends StatelessWidget {
  const _ImageThumb({
    required this.index,
    required this.file,
    required this.size,
    required this.onRemove,
  });

  final int index;
  final XFile file;
  final double size;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: Image.file(
              File(file.path),
              width: size,
              height: size,
              fit: BoxFit.cover,
            ),
          ),
          Positioned(
            left: 5,
            bottom: 5,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
              decoration: BoxDecoration(
                color: Colors.black54,
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                '${index + 1}',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
          Positioned(
            right: -4,
            top: -4,
            child: GestureDetector(
              onTap: onRemove,
              child: Container(
                width: 22,
                height: 22,
                decoration: const BoxDecoration(
                    color: Colors.black54, shape: BoxShape.circle),
                child: const Icon(Icons.close_rounded,
                    size: 14, color: Colors.white),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _InAppCaptureScreen extends StatefulWidget {
  const _InAppCaptureScreen({
    required this.initialCount,
    required this.requiredCount,
  });

  final int initialCount;
  final int requiredCount;

  @override
  State<_InAppCaptureScreen> createState() => _InAppCaptureScreenState();
}

class _InAppCaptureScreenState extends State<_InAppCaptureScreen>
    with WidgetsBindingObserver {
  static const MethodChannel _ttsChannel = MethodChannel('intruflare/tts');
  static const List<int> _timerOptions = <int>[0, 2, 3, 5];
  static const List<int> _batchTargetOptions = <int>[3, 5, 10, 15];

  CameraController? _controller;
  List<CameraDescription> _cameras = const [];
  final List<XFile> _captured = [];
  bool _initializing = true;
  bool _capturing = false;
  bool _batchRunning = false;
  int _batchTarget = 5;
  int _batchCapturedCount = 0;
  int _countdownSeconds = 3;
  int? _countdownValue;
  String? _error;
  int _activeCameraIndex = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _initializeCamera();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _controller?.dispose();
    _stopTtsSilently();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) {
      return;
    }
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      if (_batchRunning && mounted) {
        setState(() {
          _batchRunning = false;
          _countdownValue = null;
        });
      }
      _stopTtsSilently();
      controller.dispose();
      _controller = null;
      return;
    }
    if (state == AppLifecycleState.resumed) {
      _initializeCamera(preferredIndex: _activeCameraIndex);
    }
  }

  Future<void> _initializeCamera({int? preferredIndex}) async {
    if (mounted) {
      setState(() {
        _initializing = true;
        _error = null;
      });
    }

    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        throw CameraException('no_camera', 'No camera found on this device.');
      }

      final frontIndex = cameras.indexWhere(
        (camera) => camera.lensDirection == CameraLensDirection.front,
      );
      final resolvedIndex =
          preferredIndex ?? (frontIndex >= 0 ? frontIndex : 0);
      final boundedIndex = resolvedIndex.clamp(0, cameras.length - 1);

      final controller = CameraController(
        cameras[boundedIndex],
        ResolutionPreset.medium,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.jpeg,
      );
      await controller.initialize();

      if (!mounted) {
        await controller.dispose();
        return;
      }

      final previous = _controller;
      setState(() {
        _cameras = cameras;
        _activeCameraIndex = boundedIndex;
        _controller = controller;
        _initializing = false;
        _error = null;
      });
      await previous?.dispose();
    } on CameraException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _initializing = false;
        _error = (error.description ?? error.code).trim();
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _initializing = false;
        _error = 'Unable to initialize camera.';
      });
    }
  }

  Future<void> _switchCamera() async {
    if (_cameras.length < 2 || _initializing || _capturing || _batchRunning) {
      return;
    }
    final next = (_activeCameraIndex + 1) % _cameras.length;
    await _initializeCamera(preferredIndex: next);
  }

  Future<void> _startBatchCapture() async {
    if (_batchRunning || _capturing || _initializing) {
      return;
    }

    setState(() {
      _batchRunning = true;
      _batchCapturedCount = 0;
      _countdownValue = null;
    });

    while (mounted && _batchRunning && _batchCapturedCount < _batchTarget) {
      final ready = await _runCountdownBeforeShot();
      if (!ready || !_batchRunning) {
        break;
      }
      final captured = await _captureImage(fromBatch: true);
      if (!captured) {
        break;
      }
    }

    await _stopTts();
    if (!mounted) {
      return;
    }

    final finishedBatch = _batchCapturedCount >= _batchTarget;
    setState(() {
      _batchRunning = false;
      _countdownValue = null;
    });

    if (finishedBatch) {
      await HapticFeedback.heavyImpact();
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Batch complete: $_batchCapturedCount / $_batchTarget captured.',
          ),
        ),
      );
    }
  }

  Future<void> _stopBatchCapture() async {
    if (!_batchRunning) {
      return;
    }
    setState(() {
      _batchRunning = false;
      _countdownValue = null;
    });
    await _stopTts();
    await HapticFeedback.lightImpact();
  }

  Future<bool> _runCountdownBeforeShot() async {
    if (!_batchRunning || !mounted) {
      return false;
    }
    if (_countdownSeconds <= 0) {
      return true;
    }

    for (var value = _countdownSeconds; value > 0; value--) {
      if (!_batchRunning || !mounted) {
        return false;
      }

      setState(() => _countdownValue = value);
      await _speakText('$value');
      await HapticFeedback.selectionClick();
      await Future<void>.delayed(const Duration(seconds: 1));
    }

    if (!mounted || !_batchRunning) {
      return false;
    }

    setState(() => _countdownValue = null);
    await _speakText('capture');
    await HapticFeedback.mediumImpact();
    return true;
  }

  Future<bool> _captureImage({bool fromBatch = false}) async {
    final controller = _controller;
    if (controller == null ||
        !controller.value.isInitialized ||
        _capturing ||
        _initializing) {
      return false;
    }

    setState(() => _capturing = true);
    try {
      final file = await controller.takePicture();
      if (!mounted) {
        return false;
      }
      setState(() {
        _captured.add(file);
        if (fromBatch) {
          _batchCapturedCount += 1;
        }
      });
      await HapticFeedback.lightImpact();
      return true;
    } on CameraException catch (error) {
      if (!mounted) {
        return false;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text((error.description ?? error.code).trim()),
        ),
      );
      return false;
    } finally {
      if (mounted) {
        setState(() => _capturing = false);
      }
    }
  }

  Future<void> _speakText(String text) async {
    try {
      await _ttsChannel.invokeMethod<void>('speak', <String, dynamic>{
        'text': text,
      });
    } on MissingPluginException {
      // No native TTS channel available for this platform.
    } on PlatformException {
      // Ignore TTS failures and continue capture flow.
    } catch (_) {
      // Ignore any non-fatal TTS errors.
    }
  }

  Future<void> _stopTts() async {
    try {
      await _ttsChannel.invokeMethod<void>('stop');
    } catch (_) {
      // Ignore stop failures.
    }
  }

  void _stopTtsSilently() {
    _ttsChannel.invokeMethod<void>('stop').catchError((_) {});
  }

  Future<void> _done() async {
    if (_batchRunning && mounted) {
      setState(() {
        _batchRunning = false;
        _countdownValue = null;
      });
    }
    await _stopTts();
    if (!mounted) {
      return;
    }
    Navigator.of(context).pop(List<XFile>.from(_captured));
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final totalCount = widget.initialCount + _captured.length;
    final remaining = max(0, widget.requiredCount - totalCount);
    final controlsDisabled = _initializing || _capturing;

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) {
          _done();
        }
      },
      child: Scaffold(
        backgroundColor: const Color(0xFF071A2A),
        appBar: AppBar(
          backgroundColor: const Color(0xFF071A2A),
          foregroundColor: Colors.white,
          leading: IconButton(
            icon: const Icon(Icons.close_rounded),
            onPressed: () => _done(),
          ),
          title: const Text('In-App Camera'),
          actions: [
            TextButton(
              onPressed: _captured.isEmpty ? null : () => _done(),
              child: Text(
                'Done (${_captured.length})',
                style: TextStyle(
                  color: _captured.isEmpty ? Colors.white54 : Colors.white,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
        body: _initializing
            ? const Center(child: CircularProgressIndicator())
            : (_error != null)
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(
                            Icons.videocam_off_outlined,
                            size: 34,
                            color: Colors.white70,
                          ),
                          const SizedBox(height: 12),
                          Text(
                            _error!,
                            textAlign: TextAlign.center,
                            style: const TextStyle(color: Colors.white70),
                          ),
                          const SizedBox(height: 12),
                          FilledButton.tonalIcon(
                            onPressed: _initializeCamera,
                            icon: const Icon(Icons.refresh_rounded),
                            label: const Text('Retry Camera'),
                          ),
                        ],
                      ),
                    ),
                  )
                : Column(
                    children: [
                      Expanded(
                        child: Padding(
                          padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(16),
                            child: Stack(
                              fit: StackFit.expand,
                              children: [
                                ColoredBox(
                                  color: Colors.black,
                                  child: Center(
                                    child: AspectRatio(
                                      aspectRatio:
                                          _controller!.value.aspectRatio,
                                      child: CameraPreview(_controller!),
                                    ),
                                  ),
                                ),
                                Positioned(
                                  top: 10,
                                  left: 10,
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 10,
                                      vertical: 6,
                                    ),
                                    decoration: BoxDecoration(
                                      color: Colors.black54,
                                      borderRadius: BorderRadius.circular(20),
                                    ),
                                    child: Text(
                                      'Session ${_captured.length} | Total $totalCount',
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 12,
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                  ),
                                ),
                                Positioned(
                                  top: 10,
                                  right: 10,
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 10,
                                      vertical: 6,
                                    ),
                                    decoration: BoxDecoration(
                                      color: Colors.black54,
                                      borderRadius: BorderRadius.circular(20),
                                    ),
                                    child: Text(
                                      _batchRunning
                                          ? 'Batch $_batchCapturedCount/$_batchTarget'
                                          : (remaining == 0
                                              ? 'Batch ready'
                                              : '$remaining to batch-ready'),
                                      style: TextStyle(
                                        color: _batchRunning
                                            ? cs.primary
                                            : (remaining == 0
                                                ? const Color(0xFF26A69A)
                                                : Colors.white),
                                        fontSize: 12,
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                  ),
                                ),
                                if (_countdownValue != null)
                                  Center(
                                    child: Container(
                                      width: 124,
                                      height: 124,
                                      decoration: BoxDecoration(
                                        color: Colors.black54,
                                        shape: BoxShape.circle,
                                        border: Border.all(
                                          color: Colors.white70,
                                          width: 2,
                                        ),
                                      ),
                                      alignment: Alignment.center,
                                      child: Text(
                                        '$_countdownValue',
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontSize: 52,
                                          fontWeight: FontWeight.w800,
                                        ),
                                      ),
                                    ),
                                  ),
                              ],
                            ),
                          ),
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
                        child: Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Colors.white10,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: Colors.white24),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                'Auto-Capture Timer',
                                style: TextStyle(
                                  color: Colors.white70,
                                  fontSize: 11,
                                  fontWeight: FontWeight.w700,
                                  letterSpacing: 1.1,
                                ),
                              ),
                              const SizedBox(height: 8),
                              Wrap(
                                spacing: 8,
                                runSpacing: 8,
                                children: _timerOptions
                                    .map(
                                      (value) => ChoiceChip(
                                        label: Text(
                                          value == 0 ? 'No Timer' : '${value}s',
                                        ),
                                        selected: _countdownSeconds == value,
                                        onSelected: controlsDisabled
                                            ? null
                                            : (_) => setState(
                                                  () =>
                                                      _countdownSeconds = value,
                                                ),
                                      ),
                                    )
                                    .toList(),
                              ),
                              const SizedBox(height: 12),
                              const Text(
                                'One-Tap Batch (Stop at N shots)',
                                style: TextStyle(
                                  color: Colors.white70,
                                  fontSize: 11,
                                  fontWeight: FontWeight.w700,
                                  letterSpacing: 1.1,
                                ),
                              ),
                              const SizedBox(height: 8),
                              Wrap(
                                spacing: 8,
                                runSpacing: 8,
                                children: _batchTargetOptions
                                    .map(
                                      (value) => ChoiceChip(
                                        label: Text('$value shots'),
                                        selected: _batchTarget == value,
                                        onSelected: controlsDisabled
                                            ? null
                                            : (_) => setState(
                                                () => _batchTarget = value),
                                      ),
                                    )
                                    .toList(),
                              ),
                              const SizedBox(height: 10),
                              FilledButton.tonalIcon(
                                onPressed: controlsDisabled
                                    ? null
                                    : (_batchRunning
                                        ? _stopBatchCapture
                                        : _startBatchCapture),
                                icon: Icon(
                                  _batchRunning
                                      ? Icons.stop_circle_outlined
                                      : Icons.timer_outlined,
                                  size: 18,
                                ),
                                label: Text(
                                  _batchRunning
                                      ? 'Stop Batch ($_batchCapturedCount/$_batchTarget)'
                                      : 'Start One-Tap Batch',
                                ),
                              ),
                              const SizedBox(height: 6),
                              const Text(
                                'Voice countdown and haptic ticks are enabled during batch capture.',
                                style: TextStyle(
                                  color: Colors.white60,
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      if (_captured.isNotEmpty)
                        SizedBox(
                          height: 72,
                          child: ListView.separated(
                            padding: const EdgeInsets.symmetric(horizontal: 12),
                            scrollDirection: Axis.horizontal,
                            itemBuilder: (_, index) => _CapturedThumb(
                              file: _captured[index],
                              index: index,
                            ),
                            separatorBuilder: (_, __) =>
                                const SizedBox(width: 8),
                            itemCount: _captured.length,
                          ),
                        ),
                      const SizedBox(height: 8),
                      Padding(
                        padding: const EdgeInsets.fromLTRB(16, 0, 16, 20),
                        child: Row(
                          children: [
                            IconButton.filledTonal(
                              onPressed: _cameras.length > 1 &&
                                      !_capturing &&
                                      !_batchRunning
                                  ? _switchCamera
                                  : null,
                              icon:
                                  const Icon(Icons.flip_camera_android_rounded),
                            ),
                            const Spacer(),
                            GestureDetector(
                              onTap: (_capturing || _batchRunning)
                                  ? null
                                  : () => _captureImage(),
                              child: Container(
                                width: 76,
                                height: 76,
                                padding: const EdgeInsets.all(4),
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  border: Border.all(
                                    color: Colors.white,
                                    width: 3,
                                  ),
                                ),
                                child: Container(
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    color: _capturing
                                        ? Colors.white54
                                        : cs.primary,
                                  ),
                                ),
                              ),
                            ),
                            const Spacer(),
                            IconButton.filledTonal(
                              onPressed:
                                  _captured.isEmpty ? null : () => _done(),
                              icon: const Icon(Icons.check_rounded),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
      ),
    );
  }
}

class _CapturedThumb extends StatelessWidget {
  const _CapturedThumb({required this.file, required this.index});

  final XFile file;
  final int index;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: Stack(
        children: [
          Image.file(
            File(file.path),
            width: 66,
            height: 66,
            fit: BoxFit.cover,
          ),
          Positioned(
            left: 4,
            bottom: 4,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
              decoration: BoxDecoration(
                color: Colors.black54,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                '${index + 1}',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
