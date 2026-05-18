import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../core/storage/settings_store.dart';
import '../models/snapshot_item.dart';
import '../services/backend_service.dart';
import '../widgets/snapshot_image_with_overlay.dart';

class SnapshotsScreen extends StatefulWidget {
  const SnapshotsScreen({
    super.key,
    required this.backendService,
    required this.settingsStore,
    this.initialDate,
    this.onAlertResolved,
  });

  final BackendService backendService;
  final SettingsStore settingsStore;
  final DateTime? initialDate;
  final VoidCallback? onAlertResolved;

  @override
  State<SnapshotsScreen> createState() => _SnapshotsScreenState();
}

class _SnapshotsScreenState extends State<SnapshotsScreen> {
  static const MethodChannel _filesChannel = MethodChannel('intruflare/files');

  bool _loading = true;
  String? _error;
  List<SnapshotItem> _snapshots = <SnapshotItem>[];
  String? _busySnapshotId;
  DateTime? _selectedDate;
  late final TextEditingController _searchController;
  String _searchQuery = '';
  String _selectedType = 'all';
  String _selectedReview = 'all';
  bool _groupTraining = false;

  @override
  void initState() {
    super.initState();
    _searchController = TextEditingController();
    if (widget.initialDate != null) {
      _selectedDate = DateTime(
        widget.initialDate!.year,
        widget.initialDate!.month,
        widget.initialDate!.day,
      );
    }
    _loadSnapshots();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadSnapshots() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final snapshots =
          await widget.backendService.fetchSnapshots(localDate: _selectedDate);
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
    final baseUrl = widget.backendService.apiClient.baseUrl;
    final normalizedBase = baseUrl.endsWith('/') ? baseUrl : '$baseUrl/';
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

  String _formatTimestamp(DateTime value) {
    final local = value.toLocal();
    final date =
        '${local.year}-${local.month.toString().padLeft(2, '0')}-${local.day.toString().padLeft(2, '0')}';
    final time =
        '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
    return '$date $time';
  }

  String _snapshotType(SnapshotItem snapshot) {
    final code = snapshot.eventCode.toUpperCase();
    final text = '${snapshot.title} ${snapshot.message}'.toLowerCase();
    if (code.contains('FIRE') ||
        code.contains('SMOKE') ||
        text.contains('fire') ||
        text.contains('smoke')) {
      return 'fire';
    }
    if (code.contains('AUTHORIZED')) {
      return 'authorized';
    }
    if (snapshot.supportsIntruderFeedback ||
        text.contains('intruder') ||
        text.contains('non-authorized')) {
      return 'intruder';
    }
    return 'system';
  }

  List<SnapshotItem> _filteredSnapshots() {
    final query = _searchQuery.toLowerCase().trim();
    return _snapshots.where((snapshot) {
      final matchesSearch = query.isEmpty ||
          snapshot.title.toLowerCase().contains(query) ||
          snapshot.message.toLowerCase().contains(query) ||
          snapshot.eventCode.toLowerCase().contains(query) ||
          snapshot.sourceNodeLabel.toLowerCase().contains(query) ||
          snapshot.location.toLowerCase().contains(query) ||
          snapshot.recordLabel.toLowerCase().contains(query);
      final matchesType =
          _selectedType == 'all' || _snapshotType(snapshot) == _selectedType;
      final matchesReview = _selectedReview == 'all' ||
          snapshot.reviewStatus.toLowerCase() == _selectedReview;
      return matchesSearch && matchesType && matchesReview;
    }).toList();
  }

  Widget _buildFilters(int visibleCount) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: cs.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '$visibleCount snapshot${visibleCount == 1 ? '' : 's'} shown',
            style: Theme.of(context).textTheme.labelLarge,
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _searchController,
            onChanged: (value) => setState(() => _searchQuery = value),
            decoration: const InputDecoration(
              labelText: 'Search snapshots',
              hintText: 'Title, code, location, source node',
              prefixIcon: Icon(Icons.search_rounded, size: 20),
            ),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<String>(
                  initialValue: _selectedType,
                  decoration: const InputDecoration(labelText: 'Type'),
                  items: const <DropdownMenuItem<String>>[
                    DropdownMenuItem(value: 'all', child: Text('All')),
                    DropdownMenuItem(
                        value: 'intruder', child: Text('Intruder')),
                    DropdownMenuItem(value: 'fire', child: Text('Fire')),
                    DropdownMenuItem(
                        value: 'authorized', child: Text('Authorized')),
                    DropdownMenuItem(value: 'system', child: Text('System')),
                  ],
                  onChanged: (value) => setState(
                    () => _selectedType = value ?? 'all',
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: DropdownButtonFormField<String>(
                  initialValue: _selectedReview,
                  decoration: const InputDecoration(labelText: 'Review'),
                  items: const <DropdownMenuItem<String>>[
                    DropdownMenuItem(value: 'all', child: Text('All')),
                    DropdownMenuItem(
                        value: 'needs_review', child: Text('Needs Review')),
                    DropdownMenuItem(
                        value: 'confirmed', child: Text('Confirmed')),
                    DropdownMenuItem(
                        value: 'false_positive', child: Text('False Positive')),
                    DropdownMenuItem(
                        value: 'resolved', child: Text('Resolved')),
                    DropdownMenuItem(
                        value: 'archived', child: Text('Archived')),
                  ],
                  onChanged: (value) => setState(
                    () => _selectedReview = value ?? 'all',
                  ),
                ),
              ),
            ],
          ),
          if (_searchQuery.trim().isNotEmpty ||
              _selectedType != 'all' ||
              _selectedReview != 'all') ...[
            const SizedBox(height: 10),
            TextButton.icon(
              onPressed: () {
                _searchController.clear();
                setState(() {
                  _searchQuery = '';
                  _selectedType = 'all';
                  _selectedReview = 'all';
                });
              },
              icon: const Icon(Icons.clear_rounded, size: 18),
              label: const Text('Clear filters'),
            ),
          ],
        ],
      ),
    );
  }

  String _formatReviewStatusLabel(String value) {
    final words = value.replaceAll('_', ' ').trim().split(RegExp(r'\s+'));
    return words
        .where((word) => word.isNotEmpty)
        .map((word) => '${word[0].toUpperCase()}${word.substring(1)}')
        .join(' ');
  }

  Color _severityColor(String severity) {
    switch (severity.toLowerCase()) {
      case 'critical':
        return Colors.red;
      case 'warning':
        return Colors.orange;
      default:
        return Colors.blue;
    }
  }

  String _snapshotFileName(SnapshotItem snapshot) {
    final stamp = snapshot.capturedAt.toUtc().toIso8601String();
    final safeStamp = stamp.replaceAll(':', '-').replaceAll('.', '-');
    return 'snapshot_${snapshot.id}_$safeStamp.jpg';
  }

  Future<void> _downloadSnapshot(SnapshotItem snapshot) async {
    if (defaultTargetPlatform != TargetPlatform.android) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content:
                Text('Download is currently supported on Android devices.')),
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

      await _filesChannel
          .invokeMethod<dynamic>('downloadSnapshot', <String, dynamic>{
        'url': _absoluteSnapshotUrl(snapshot.snapshotPath),
        'fileName': _snapshotFileName(snapshot),
        'headers': headers,
      });

      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Snapshot download queued. Check notifications.')),
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
    final alertId = snapshot.actionableAlertId;
    if (alertId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Only alert snapshots can be deleted.')),
      );
      return;
    }

    final shouldDelete = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Delete snapshot?'),
            content: const Text(
                'This will remove the image from local storage. This action cannot be undone.'),
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
      await widget.backendService.deleteSnapshot('$alertId');
      if (!mounted) {
        return;
      }
      setState(() {
        _snapshots = _snapshots
            .where((item) => item.snapshotPath != snapshot.snapshotPath)
            .toList();
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

  Future<void> _resolveSnapshotAlert(SnapshotItem snapshot) async {
    final alertId = snapshot.actionableAlertId;
    if (alertId == null) {
      return;
    }

    setState(() => _busySnapshotId = snapshot.id);
    try {
      await widget.backendService.updateAlertReview(
        '$alertId',
        reviewStatus: 'resolved',
        reviewNote: 'Resolved from mobile snapshot gallery.',
      );
      await _loadSnapshots();
      widget.onAlertResolved?.call();
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Alert #$alertId marked resolved.')),
      );
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Resolve failed: $error')),
      );
    } finally {
      if (mounted) {
        setState(() => _busySnapshotId = null);
      }
    }
  }

  Future<FaceProfile?> _selectFalseAlarmFaceProfile() async {
    List<FaceProfile> profiles;
    try {
      profiles = await widget.backendService.fetchFaceProfiles();
    } catch (error) {
      if (!mounted) {
        return null;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not load face profiles: $error')),
      );
      return null;
    }

    if (!mounted) {
      return null;
    }
    if (profiles.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No authorized face profiles available.')),
      );
      return null;
    }

    var selected = profiles.first;
    return showDialog<FaceProfile>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Who is this person?'),
          content: SizedBox(
            width: double.maxFinite,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                const Text(
                  'Select the authorized profile before importing this false alarm for retraining.',
                ),
                const SizedBox(height: 12),
                ConstrainedBox(
                  constraints: const BoxConstraints(maxHeight: 320),
                  child: SingleChildScrollView(
                    child: RadioGroup<FaceProfile>(
                      groupValue: selected,
                      onChanged: (value) {
                        if (value != null) {
                          setDialogState(() => selected = value);
                        }
                      },
                      child: Column(
                        children: profiles
                            .map(
                              (profile) => RadioListTile<FaceProfile>(
                                value: profile,
                                title: Text(profile.name),
                                subtitle:
                                    Text('${profile.sampleCount} samples'),
                              ),
                            )
                            .toList(),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(selected),
              child: const Text('Use Profile'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _submitSnapshotFeedback(
    SnapshotItem snapshot,
    String verdict,
  ) async {
    final alertId = snapshot.actionableAlertId;
    if (alertId == null) {
      return;
    }

    FaceProfile? profile;
    if (verdict == 'false_positive' && snapshot.supportsIntruderFeedback) {
      profile = await _selectFalseAlarmFaceProfile();
      if (profile == null) {
        return;
      }
    } else if (verdict == 'false_positive' && !snapshot.supportsFireFeedback) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
              'False-alarm learning is only available for intruder and fire snapshots.'),
        ),
      );
      return;
    }

    if (verdict == 'false_positive' && snapshot.supportsFireFeedback) {
      if (!mounted) {
        return;
      }
      final confirmed = await showDialog<bool>(
            context: context,
            builder: (context) => AlertDialog(
              title: const Text('Mark fire false alarm?'),
              content: const Text(
                'This will copy the snapshot into the fire hard-negative dataset for future model training.',
              ),
              actions: <Widget>[
                TextButton(
                  onPressed: () => Navigator.of(context).pop(false),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: () => Navigator.of(context).pop(true),
                  child: const Text('Mark False Alarm'),
                ),
              ],
            ),
          ) ??
          false;
      if (!confirmed) {
        return;
      }
    }

    setState(() => _busySnapshotId = snapshot.id);
    try {
      final result = await widget.backendService.submitSnapshotFeedback(
        '$alertId',
        verdict: verdict,
        faceName: profile?.name ?? '',
      );
      await _loadSnapshots();
      widget.onAlertResolved?.call();
      if (!mounted) {
        return;
      }
      final message = verdict == 'confirmed'
          ? 'Snapshot confirmed.'
          : snapshot.supportsIntruderFeedback
              ? 'False alarm saved for group retraining.'
              : 'False alarm saved as fire hard-negative sample.';
      final trainMessage = result.trainMessage.trim();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content:
              Text(trainMessage.isEmpty ? message : '$message $trainMessage'),
        ),
      );
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Feedback failed: $error')),
      );
    } finally {
      if (mounted) {
        setState(() => _busySnapshotId = null);
      }
    }
  }

  Future<void> _runGroupRetrain() async {
    if (_groupTraining) {
      return;
    }
    setState(() => _groupTraining = true);
    try {
      final result = await widget.backendService.trainFaceModel();
      if (!mounted) {
        return;
      }
      final message = result.ok
          ? 'Group retrain complete. ${result.message}'.trim()
          : 'Group retrain failed. ${result.message}'.trim();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(message)),
      );
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Group retrain failed: $error')),
      );
    } finally {
      if (mounted) {
        setState(() => _groupTraining = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final visibleSnapshots = _filteredSnapshots();
    return Scaffold(
      appBar: AppBar(
        title: const Text('Snapshots'),
        actions: [
          TextButton.icon(
            onPressed: _groupTraining ? null : _runGroupRetrain,
            icon: _groupTraining
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.psychology_alt_outlined, size: 18),
            label: Text(_groupTraining ? 'Retraining...' : 'Retrain'),
          ),
        ],
      ),
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
                        itemCount: visibleSnapshots.length + 1,
                        itemBuilder: (context, index) {
                          if (index == 0) {
                            return Padding(
                              padding: const EdgeInsets.only(bottom: 12),
                              child: Column(
                                children: [
                                  _buildFilters(visibleSnapshots.length),
                                  if (visibleSnapshots.isEmpty) ...[
                                    const SizedBox(height: 12),
                                    const _NoMatchingSnapshotsCard(),
                                  ],
                                ],
                              ),
                            );
                          }
                          final snapshot = visibleSnapshots[index - 1];
                          final url =
                              _absoluteSnapshotUrl(snapshot.snapshotPath);
                          final canReview =
                              snapshot.actionableAlertId != null &&
                                  !snapshot.isTerminalReviewStatus;
                          final canSubmitFeedback =
                              snapshot.actionableAlertId != null &&
                                  snapshot.supportsSnapshotFeedback &&
                                  !snapshot.hasFeedbackReview;
                          final canDelete = snapshot.actionableAlertId != null;
                          return Card(
                            clipBehavior: Clip.antiAlias,
                            child: Padding(
                              padding: const EdgeInsets.all(12),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: <Widget>[
                                  SnapshotImageWithOverlay(
                                    imageUrl: url,
                                    headers: _imageHeaders,
                                    overlays: snapshot.faceOverlays,
                                  ),
                                  const SizedBox(height: 10),
                                  Wrap(
                                    spacing: 6,
                                    runSpacing: 6,
                                    children: [
                                      _SnapshotStatusPill(
                                        label: snapshot.recordLabel,
                                        color: Theme.of(context)
                                            .colorScheme
                                            .primary,
                                      ),
                                      _SnapshotStatusPill(
                                        label: snapshot.severity.toUpperCase(),
                                        color:
                                            _severityColor(snapshot.severity),
                                        filled: true,
                                      ),
                                      if (snapshot.linkedRecordLabel.isNotEmpty)
                                        _SnapshotStatusPill(
                                          label: snapshot.linkedRecordLabel,
                                          color: const Color(0xFF7E57C2),
                                        ),
                                      if (snapshot.isAlertRecord)
                                        _SnapshotStatusPill(
                                          label: _formatReviewStatusLabel(
                                              snapshot.reviewStatus),
                                          color: const Color(0xFF1E88E5),
                                        ),
                                    ],
                                  ),
                                  const SizedBox(height: 10),
                                  Text(
                                    _displayTitle(snapshot),
                                    style:
                                        Theme.of(context).textTheme.titleMedium,
                                  ),
                                  if (snapshot.message.isNotEmpty) ...[
                                    const SizedBox(height: 4),
                                    Text(
                                      snapshot.message,
                                      maxLines: 3,
                                      overflow: TextOverflow.ellipsis,
                                      style: Theme.of(context)
                                          .textTheme
                                          .bodySmall
                                          ?.copyWith(height: 1.45),
                                    ),
                                  ],
                                  const SizedBox(height: 8),
                                  Wrap(
                                    spacing: 8,
                                    runSpacing: 8,
                                    children: [
                                      if (snapshot.eventCode.isNotEmpty)
                                        _SnapshotMetadataChip(
                                          icon: Icons
                                              .confirmation_number_outlined,
                                          label: snapshot.eventCode,
                                        ),
                                      if (snapshot.sourceNodeLabel.isNotEmpty)
                                        _SnapshotMetadataChip(
                                          icon: Icons.memory_rounded,
                                          label: snapshot.sourceNodeLabel,
                                        ),
                                      if (snapshot.location.isNotEmpty)
                                        _SnapshotMetadataChip(
                                          icon: Icons.place_outlined,
                                          label: snapshot.location,
                                        ),
                                      _SnapshotMetadataChip(
                                        icon: Icons.access_time_rounded,
                                        label: _formatTimestamp(
                                            snapshot.capturedAt),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 8),
                                  Wrap(
                                    spacing: 8,
                                    runSpacing: 8,
                                    children: <Widget>[
                                      if (canSubmitFeedback)
                                        FilledButton.icon(
                                          onPressed: _busySnapshotId ==
                                                  snapshot.id
                                              ? null
                                              : () => _submitSnapshotFeedback(
                                                    snapshot,
                                                    'confirmed',
                                                  ),
                                          icon: const Icon(
                                            Icons.verified_outlined,
                                            size: 18,
                                          ),
                                          label: const Text('Confirm'),
                                        ),
                                      if (canSubmitFeedback)
                                        FilledButton.tonalIcon(
                                          onPressed: _busySnapshotId ==
                                                  snapshot.id
                                              ? null
                                              : () => _submitSnapshotFeedback(
                                                    snapshot,
                                                    'false_positive',
                                                  ),
                                          icon: const Icon(
                                            Icons.report_gmailerrorred_rounded,
                                            size: 18,
                                          ),
                                          label: const Text('False Alarm'),
                                        ),
                                      if (canReview)
                                        FilledButton.tonalIcon(
                                          onPressed:
                                              _busySnapshotId == snapshot.id
                                                  ? null
                                                  : () => _resolveSnapshotAlert(
                                                      snapshot),
                                          icon: const Icon(
                                              Icons.task_alt_rounded,
                                              size: 18),
                                          label: const Text('Resolve'),
                                        ),
                                      OutlinedButton.icon(
                                        onPressed: _busySnapshotId ==
                                                snapshot.id
                                            ? null
                                            : () => _downloadSnapshot(snapshot),
                                        icon: const Icon(Icons.download_rounded,
                                            size: 18),
                                        label: const Text('Download'),
                                      ),
                                      if (canDelete)
                                        OutlinedButton.icon(
                                          onPressed: _busySnapshotId ==
                                                  snapshot.id
                                              ? null
                                              : () => _deleteSnapshot(snapshot),
                                          icon: const Icon(
                                              Icons.delete_outline_rounded,
                                              size: 18),
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

class _SnapshotStatusPill extends StatelessWidget {
  const _SnapshotStatusPill({
    required this.label,
    required this.color,
    this.filled = false,
  });

  final String label;
  final Color color;
  final bool filled;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: filled ? color : color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: filled ? Colors.white : color,
          fontSize: 10,
          fontWeight: FontWeight.w800,
          letterSpacing: 0.2,
        ),
      ),
    );
  }
}

class _NoMatchingSnapshotsCard extends StatelessWidget {
  const _NoMatchingSnapshotsCard();

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: cs.outlineVariant),
      ),
      child: const Row(
        children: [
          Icon(Icons.search_off_rounded),
          SizedBox(width: 10),
          Expanded(child: Text('No snapshots match the current filters.')),
        ],
      ),
    );
  }
}

class _SnapshotMetadataChip extends StatelessWidget {
  const _SnapshotMetadataChip({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest.withValues(alpha: 0.58),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: cs.outlineVariant),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: cs.onSurfaceVariant),
          const SizedBox(width: 5),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 180),
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: cs.onSurfaceVariant,
                fontSize: 11,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
