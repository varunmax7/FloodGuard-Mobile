/// 3-step offline-first flood report flow.
/// Step 0: Photo  →  Step 1: Details  →  Step 2: Success
library;

import 'dart:io' show File;

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_image_compress/flutter_image_compress.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:intl/intl.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';

import '../../core/platform/camera_capture.dart';
import '../../core/providers/api_providers.dart';
import '../../core/services/web_speech.dart';
import '../../data/models/flood_report.dart';
import '../../design/theme/app_theme.dart';
import '../../design/widgets/fg_app_header.dart';
import '../../design/widgets/fg_card.dart';
import '../../design/widgets/risk_dot.dart';
import '../../design/widgets/skeleton_loader.dart';
import '../area_detail/area_detail_providers.dart';
import '../radar/radar_screen.dart' show reportsHeatmapProvider;
import 'report_constants.dart';

// ── Screen ─────────────────────────────────────────────────────────────────────

class ReportScreen extends ConsumerStatefulWidget {
  const ReportScreen({super.key});

  @override
  ConsumerState<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends ConsumerState<ReportScreen> {
  int _step = 0;

  // Photo
  XFile? _photo;

  // Location
  double? _lat;
  double? _lng;
  bool _gettingLocation = false;

  // Details
  String _depth = 'ANKLE';
  String _road = 'PASSABLE';
  int _partySize = 1; // 1 = alone; capped at 6 (6 chip means "6+")
  DateTime _observedAt = DateTime.now();
  final TextEditingController _descriptionCtrl = TextEditingController();

  // Submit state
  bool _isSubmitting = false;
  String _syncStatus = 'idle'; // idle | queued | synced

  @override
  void initState() {
    super.initState();
    _fetchLocationSilently();
  }

  @override
  void dispose() {
    _descriptionCtrl.dispose();
    super.dispose();
  }

  // ── Location ──────────────────────────────────────────────────────────────

  Future<void> _fetchLocationSilently() async {
    try {
      var perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) {
        perm = await Geolocator.requestPermission();
      }
      if (perm == LocationPermission.denied ||
          perm == LocationPermission.deniedForever) return;

      final pos = await Geolocator.getCurrentPosition(
        locationSettings:
            const LocationSettings(accuracy: LocationAccuracy.high),
      );
      if (mounted) {
        setState(() {
          _lat = pos.latitude;
          _lng = pos.longitude;
        });
      }
    } catch (_) {}
  }

  Future<void> _refreshLocation() async {
    setState(() => _gettingLocation = true);
    try {
      var perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) {
        perm = await Geolocator.requestPermission();
      }
      if (perm == LocationPermission.deniedForever && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Location permission denied. Enable in Settings.'),
        ));
        return;
      }
      final pos = await Geolocator.getCurrentPosition(
        locationSettings:
            const LocationSettings(accuracy: LocationAccuracy.high),
      );
      if (mounted) setState(() { _lat = pos.latitude; _lng = pos.longitude; });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Location unavailable: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _gettingLocation = false);
    }
  }

  // ── Photo ─────────────────────────────────────────────────────────────────

  Future<void> _pickPhoto(ImageSource source) async {
    try {
      XFile? file;
      if (source == ImageSource.camera && kIsWeb) {
        // On web, use getUserMedia overlay instead of image_picker camera.
        file = await captureWebcam();
      } else {
        file = await ImagePicker().pickImage(
          source: source,
          imageQuality: 90,
          maxWidth: 1600,
          maxHeight: 1600,
        );
      }
      if (file == null) return;
      final compressed = await _compressPhoto(file);
      if (mounted) setState(() => _photo = compressed);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not access photo: $e')),
        );
      }
    }
  }

  Future<XFile> _compressPhoto(XFile file) async {
    if (kIsWeb) return file;
    try {
      final dir = await getTemporaryDirectory();
      final target = p.join(
          dir.path, 'fg_${DateTime.now().millisecondsSinceEpoch}.jpg');
      final result = await FlutterImageCompress.compressAndGetFile(
        file.path,
        target,
        quality: ReportConstants.compressQuality,
        minWidth: ReportConstants.compressMaxDim,
        minHeight: ReportConstants.compressMaxDim,
      );
      return result ?? file;
    } catch (_) {
      return file;
    }
  }

  // ── Submit ────────────────────────────────────────────────────────────────

  Future<void> _submit() async {
    if (_photo == null || _lat == null || _lng == null) return;
    setState(() => _isSubmitting = true);

    final uuid = const Uuid().v4();
    final db = ref.read(dbServiceProvider);
    final api = ref.read(apiProvider);

    // 1. Always write to local outbox first (offline-safe).
    await db.enqueuePendingReport({
      'id': uuid,
      'lat': _lat!,
      'lng': _lng!,
      'depth': _depth,
      'road': _road,
      'photoPath': kIsWeb ? null : _photo!.path,
      'observedAt': _observedAt,
      'clientUuid': uuid,
    });

    // 2. Attempt immediate online sync.
    try {
      await api.submitReport(
        lat: _lat!,
        lng: _lng!,
        depth: _depth,
        road: _road,
        clientUuid: uuid,
        observedAt: _observedAt,
        partySize: _partySize,
        description: _descriptionCtrl.text,
        photo: _photo,
      );
      await db.markSynced(uuid);
      _syncStatus = 'synced';
      // Refresh dependent views so the new report appears immediately:
      // radar heatmap overlay + nearby-reports strips.
      ref.invalidate(reportsHeatmapProvider);
    } catch (_) {
      // Offline — WorkManager will flush when connectivity returns.
      _syncStatus = 'queued';
    }

    if (mounted) setState(() { _isSubmitting = false; _step = 2; });
  }

  // ── Build ─────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const FgAppHeader(),
      backgroundColor: const Color(0xFFF1F5F9),
      body: Column(
        children: [
          // Nearby context strip — visible from step 0 & 1 once GPS is ready.
          if (_lat != null && _step < 2)
            _NearbyContextStrip(lat: _lat!, lng: _lng!),

          // Step indicator
          if (_step < 2) _StepHeader(currentStep: _step),

          // Step body
          Expanded(
            child: switch (_step) {
              0 => _PhotoStep(
                  photo: _photo,
                  onPickCamera: () => _pickPhoto(ImageSource.camera),
                  onPickGallery: () => _pickPhoto(ImageSource.gallery),
                  onNext: _photo != null
                      ? () => setState(() => _step = 1)
                      : null,
                ),
              1 => _DetailsStep(
                  depth: _depth,
                  road: _road,
                  partySize: _partySize,
                  lat: _lat,
                  lng: _lng,
                  observedAt: _observedAt,
                  gettingLocation: _gettingLocation,
                  isSubmitting: _isSubmitting,
                  descriptionCtrl: _descriptionCtrl,
                  onDepthChanged: (v) => setState(() => _depth = v),
                  onRoadChanged: (v) => setState(() => _road = v),
                  onPartySizeChanged: (v) => setState(() => _partySize = v),
                  onRefreshLocation: _refreshLocation,
                  onObservedAtChanged: (dt) =>
                      setState(() => _observedAt = dt),
                  onBack: () => setState(() => _step = 0),
                  onSubmit: _lat != null ? _submit : null,
                ),
              _ => _SuccessStep(
                  syncStatus: _syncStatus,
                  onHome: () => context.go('/'),
                ),
            },
          ),
        ],
      ),
    );
  }
}

// ── Step header ───────────────────────────────────────────────────────────────

class _StepHeader extends StatelessWidget {
  final int currentStep;
  const _StepHeader({required this.currentStep});

  static const _labels = ['Photo', 'Details', 'Submit'];

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Row(
        children: [
          for (int i = 0; i < 3; i++) ...[
            Expanded(child: _StepCircle(index: i, current: currentStep, label: _labels[i])),
            if (i < 2)
              Container(
                height: 1,
                width: 32,
                color: i < currentStep ? AppColors.blue600 : const Color(0xFFE2E8F0),
              ),
          ],
        ],
      ),
    );
  }
}

class _StepCircle extends StatelessWidget {
  final int index;
  final int current;
  final String label;
  const _StepCircle({required this.index, required this.current, required this.label});

  @override
  Widget build(BuildContext context) {
    final isDone = index < current;
    final isActive = index == current;
    final bg = isDone
        ? AppColors.riskLow
        : isActive
            ? AppColors.blue600
            : const Color(0xFFE2E8F0);
    final fg = (isDone || isActive) ? Colors.white : AppColors.textMuted;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          width: 32,
          height: 32,
          decoration: BoxDecoration(color: bg, shape: BoxShape.circle),
          alignment: Alignment.center,
          child: isDone
              ? const Icon(Icons.check, size: 16, color: Colors.white)
              : Text('${index + 1}',
                  style: TextStyle(
                      color: fg, fontSize: 13, fontWeight: FontWeight.w700)),
        ),
        const SizedBox(height: 4),
        Text(label,
            style: TextStyle(
                fontSize: 11,
                color: isActive ? AppColors.blue600 : AppColors.textMuted,
                fontWeight:
                    isActive ? FontWeight.w600 : FontWeight.w400)),
      ],
    );
  }
}

// ── Nearby context strip ──────────────────────────────────────────────────────

class _NearbyContextStrip extends ConsumerWidget {
  final double lat;
  final double lng;
  const _NearbyContextStrip({required this.lat, required this.lng});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final args = (
      lat: lat,
      lng: lng,
      sinceMin: ReportConstants.nearbyContextMinutes,
    );
    final reportsAsync = ref.watch(nearbyReportsProvider(args));

    return Container(
      color: Colors.white,
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              const Icon(Icons.location_on_outlined,
                  size: 14, color: AppColors.textMuted),
              const SizedBox(width: 4),
              const Text(
                'Nearby reports (last 1h, 1km)',
                style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                    color: AppColors.textMuted),
              ),
              const Spacer(),
              reportsAsync.maybeWhen(
                data: (r) => Text('${r.length} found',
                    style: const TextStyle(
                        fontSize: 12, color: AppColors.textMuted)),
                orElse: () => const SizedBox.shrink(),
              ),
            ],
          ),
          const SizedBox(height: 8),
          reportsAsync.when(
            loading: () => SizedBox(
              height: 72,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: 3,
                separatorBuilder: (_, __) => const SizedBox(width: 8),
                itemBuilder: (_, __) =>
                    const SkeletonBox(width: 64, height: 72, radius: 10),
              ),
            ),
            error: (_, __) => const SizedBox(
              height: 32,
              child: Center(
                child: Text('Could not load nearby reports',
                    style: TextStyle(
                        fontSize: 12, color: AppColors.textMuted)),
              ),
            ),
            data: (reports) => reports.isEmpty
                ? const SizedBox(
                    height: 32,
                    child: Center(
                      child: Text('No recent reports nearby — be the first!',
                          style: TextStyle(
                              fontSize: 12, color: AppColors.textMuted)),
                    ),
                  )
                : SizedBox(
                    height: 80,
                    child: ListView.separated(
                      scrollDirection: Axis.horizontal,
                      itemCount: reports.length,
                      separatorBuilder: (_, __) => const SizedBox(width: 8),
                      itemBuilder: (_, i) =>
                          _NearbyThumb(report: reports[i]),
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}

class _NearbyThumb extends StatelessWidget {
  final FloodReport report;
  const _NearbyThumb({required this.report});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 64,
      child: Column(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: report.photoUrl != null
                ? CachedNetworkImage(
                    imageUrl: report.photoUrl!,
                    width: 60,
                    height: 60,
                    fit: BoxFit.cover,
                    placeholder: (_, __) => const _ThumbPlaceholder(),
                    errorWidget: (_, __, ___) => const _ThumbPlaceholder(),
                  )
                : const _ThumbPlaceholder(),
          ),
          const SizedBox(height: 3),
          Text(
            report.depthLabel,
            style: const TextStyle(fontSize: 10, color: AppColors.textMuted),
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

class _ThumbPlaceholder extends StatelessWidget {
  const _ThumbPlaceholder();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 60,
      height: 60,
      color: const Color(0xFFF1F5F9),
      child: const Icon(Icons.water_outlined,
          color: AppColors.textMuted, size: 24),
    );
  }
}

// ── Step 0: Photo ─────────────────────────────────────────────────────────────

class _PhotoStep extends StatelessWidget {
  final XFile? photo;
  final VoidCallback onPickCamera;
  final VoidCallback onPickGallery;
  final VoidCallback? onNext;

  const _PhotoStep({
    required this.photo,
    required this.onPickCamera,
    required this.onPickGallery,
    required this.onNext,
  });

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          const SizedBox(height: 8),
          // Preview area
          GestureDetector(
            onTap: photo == null ? onPickGallery : null,
            child: Container(
              width: double.infinity,
              height: 280,
              decoration: BoxDecoration(
                color: const Color(0xFFF1F5F9),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: photo == null
                      ? const Color(0xFFCBD5E1)
                      : Colors.transparent,
                  width: 1.5,
                ),
              ),
              clipBehavior: Clip.antiAlias,
              child: photo == null
                  ? Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.add_a_photo_outlined,
                            size: 52,
                            color: AppColors.textMuted.withAlpha(128)),
                        const SizedBox(height: 12),
                        const Text('Tap to add photo',
                            style: TextStyle(
                                fontSize: 14, color: AppColors.textMuted)),
                      ],
                    )
                  : _photoWidget(photo!),
            ),
          ),
          const SizedBox(height: 16),

          // Camera / Gallery buttons
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: onPickCamera,
                  icon: const Icon(Icons.camera_alt_outlined, size: 18),
                  label: const Text('Camera'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: onPickGallery,
                  icon: const Icon(Icons.photo_library_outlined, size: 18),
                  label: const Text('Gallery'),
                ),
              ),
            ],
          ),

          if (photo != null) ...[
            const SizedBox(height: 8),
            TextButton.icon(
              onPressed: onPickGallery,
              icon: const Icon(Icons.refresh, size: 16),
              label: const Text('Retake / Change'),
            ),
          ],

          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: onNext,
              child: const Text('Next: Details'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _photoWidget(XFile file) {
    if (kIsWeb) {
      return Image.network(file.path, fit: BoxFit.cover,
          width: double.infinity, height: 280);
    }
    return Image.file(File(file.path),
        fit: BoxFit.cover, width: double.infinity, height: 280);
  }
}

// ── Step 1: Details ───────────────────────────────────────────────────────────

class _DetailsStep extends StatefulWidget {
  final String depth;
  final String road;
  final int partySize;
  final double? lat;
  final double? lng;
  final DateTime observedAt;
  final bool gettingLocation;
  final bool isSubmitting;
  final TextEditingController descriptionCtrl;
  final ValueChanged<String> onDepthChanged;
  final ValueChanged<String> onRoadChanged;
  final ValueChanged<int> onPartySizeChanged;
  final VoidCallback onRefreshLocation;
  final ValueChanged<DateTime> onObservedAtChanged;
  final VoidCallback onBack;
  final VoidCallback? onSubmit;

  const _DetailsStep({
    required this.depth,
    required this.road,
    required this.partySize,
    required this.lat,
    required this.lng,
    required this.observedAt,
    required this.gettingLocation,
    required this.isSubmitting,
    required this.descriptionCtrl,
    required this.onDepthChanged,
    required this.onRoadChanged,
    required this.onPartySizeChanged,
    required this.onRefreshLocation,
    required this.onObservedAtChanged,
    required this.onBack,
    required this.onSubmit,
  });

  @override
  State<_DetailsStep> createState() => _DetailsStepState();
}

class _DetailsStepState extends State<_DetailsStep> {
  bool _listening = false;
  void Function()? _stopListening;
  String _speechBaseline = ''; // text before current mic session

  void _toggleMic() {
    if (_listening) {
      _stopListening?.call();
      setState(() {
        _listening = false;
        _stopListening = null;
      });
      return;
    }
    _speechBaseline = widget.descriptionCtrl.text;
    final stop = WebSpeech.listen(
      onResult: (transcript, isFinal) {
        if (!mounted) return;
        final sep = _speechBaseline.isEmpty ||
                _speechBaseline.endsWith(' ') ||
                _speechBaseline.endsWith('\n')
            ? ''
            : ' ';
        widget.descriptionCtrl.text = '$_speechBaseline$sep$transcript';
        widget.descriptionCtrl.selection = TextSelection.collapsed(
          offset: widget.descriptionCtrl.text.length,
        );
        if (isFinal) {
          _speechBaseline = widget.descriptionCtrl.text;
          setState(() {
            _listening = false;
            _stopListening = null;
          });
        }
      },
      onError: (reason) {
        if (!mounted) return;
        setState(() {
          _listening = false;
          _stopListening = null;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Voice input error: $reason')),
        );
      },
    );
    if (stop == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Voice input is not supported in this browser. Try Chrome.'),
        ),
      );
      return;
    }
    setState(() {
      _listening = true;
      _stopListening = stop;
    });
  }

  @override
  void dispose() {
    _stopListening?.call();
    super.dispose();
  }

  // Convenience wrappers so the build() body reads like the original.
  String get depth => widget.depth;
  String get road => widget.road;
  int get partySize => widget.partySize;
  double? get lat => widget.lat;
  double? get lng => widget.lng;
  DateTime get observedAt => widget.observedAt;
  bool get gettingLocation => widget.gettingLocation;
  bool get isSubmitting => widget.isSubmitting;
  ValueChanged<String> get onDepthChanged => widget.onDepthChanged;
  ValueChanged<String> get onRoadChanged => widget.onRoadChanged;
  ValueChanged<int> get onPartySizeChanged => widget.onPartySizeChanged;
  VoidCallback get onRefreshLocation => widget.onRefreshLocation;
  ValueChanged<DateTime> get onObservedAtChanged => widget.onObservedAtChanged;
  VoidCallback get onBack => widget.onBack;
  VoidCallback? get onSubmit => widget.onSubmit;

  static const _depths = [
    ('ANKLE', 'Ankle deep', Icons.water_outlined),
    ('KNEE', 'Knee deep', Icons.water_outlined),
    ('WAIST', 'Waist deep', Icons.water),
    ('VEHICLE', 'Vehicle level', Icons.directions_car_outlined),
  ];

  static const _roads = [
    ('PASSABLE', 'Passable', AppColors.riskLow),
    ('DIFFICULT', 'Difficult', AppColors.riskHigh),
    ('BLOCKED', 'Blocked', AppColors.riskSevere),
  ];

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Flood depth
          _sectionLabel('Flood Depth'),
          const SizedBox(height: 8),
          FgCard(
            padding: const EdgeInsets.all(12),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _depths
                  .map((opt) => _SelectChip(
                        label: opt.$2,
                        selected: depth == opt.$1,
                        onTap: () => onDepthChanged(opt.$1),
                      ))
                  .toList(),
            ),
          ),

          const SizedBox(height: 16),

          // Road status
          _sectionLabel('Road Status'),
          const SizedBox(height: 8),
          FgCard(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: _roads
                  .map((opt) => Expanded(
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 3),
                          child: _RoadChip(
                            label: opt.$2,
                            color: opt.$3,
                            selected: road == opt.$1,
                            onTap: () => onRoadChanged(opt.$1),
                          ),
                        ),
                      ))
                  .toList(),
            ),
          ),

          const SizedBox(height: 16),

          // People with you
          _sectionLabel('People with you'),
          const SizedBox(height: 8),
          FgCard(
            padding: const EdgeInsets.all(12),
            child: _PartySizePicker(
              value: partySize,
              onChanged: onPartySizeChanged,
            ),
          ),

          const SizedBox(height: 16),

          // Description + voice input
          _sectionLabel('Describe the situation (optional)'),
          const SizedBox(height: 8),
          FgCard(
            padding: const EdgeInsets.fromLTRB(12, 4, 8, 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextField(
                  controller: widget.descriptionCtrl,
                  maxLines: 4,
                  minLines: 3,
                  maxLength: 500,
                  textInputAction: TextInputAction.newline,
                  decoration: const InputDecoration(
                    hintText:
                        "What's happening here? Do you need help? "
                        "e.g. 'Water is rising fast, need boat to evacuate 4 people.'",
                    hintStyle: TextStyle(fontSize: 13, color: AppColors.textMuted),
                    border: InputBorder.none,
                    isDense: true,
                    contentPadding: EdgeInsets.symmetric(vertical: 8),
                    counterText: '',
                  ),
                  style: const TextStyle(fontSize: 14, color: AppColors.textPrimary),
                ),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      _listening ? 'Listening… speak now' : 'Tap the mic to speak',
                      style: TextStyle(
                        fontSize: 11,
                        color: _listening ? AppColors.blue600 : AppColors.textMuted,
                        fontWeight: _listening ? FontWeight.w600 : FontWeight.normal,
                      ),
                    ),
                    IconButton(
                      onPressed: _toggleMic,
                      tooltip: _listening ? 'Stop recording' : 'Speak',
                      icon: Icon(
                        _listening ? Icons.stop_circle : Icons.mic,
                        color: _listening ? AppColors.riskSevere : AppColors.blue600,
                        size: 26,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // Location
          _sectionLabel('Location'),
          const SizedBox(height: 8),
          FgCard(
            child: Row(
              children: [
                const Icon(Icons.location_on_outlined,
                    color: AppColors.blue600, size: 22),
                const SizedBox(width: 12),
                Expanded(
                  child: lat == null
                      ? const Text('Getting location…',
                          style: TextStyle(
                              fontSize: 14, color: AppColors.textMuted))
                      : Text(
                          '${lat!.toStringAsFixed(5)}, ${lng!.toStringAsFixed(5)}',
                          style: const TextStyle(
                              fontSize: 13,
                              color: AppColors.textPrimary,
                              fontFeatures: []),
                        ),
                ),
                IconButton(
                  icon: gettingLocation
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.my_location,
                          color: AppColors.blue600, size: 20),
                  onPressed: gettingLocation ? null : onRefreshLocation,
                  tooltip: 'Refresh location',
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // Observed at
          _sectionLabel('When did you observe this?'),
          const SizedBox(height: 8),
          FgCard(
            onTap: () => _pickDateTime(context),
            child: Row(
              children: [
                const Icon(Icons.schedule_outlined,
                    color: AppColors.blue600, size: 22),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    DateFormat('dd MMM yyyy, HH:mm').format(observedAt),
                    style: const TextStyle(
                        fontSize: 14, color: AppColors.textPrimary),
                  ),
                ),
                const Icon(Icons.chevron_right,
                    color: AppColors.textMuted, size: 20),
              ],
            ),
          ),

          const SizedBox(height: 32),

          // Navigation buttons
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: onBack,
                  child: const Text('Back'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                flex: 2,
                child: FilledButton(
                  onPressed: isSubmitting ? null : onSubmit,
                  child: isSubmitting
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: Colors.white))
                      : const Text('Submit Report'),
                ),
              ),
            ],
          ),

          if (lat == null) ...[
            const SizedBox(height: 8),
            const Text(
              'Waiting for GPS location before you can submit.',
              style: TextStyle(fontSize: 12, color: AppColors.textMuted),
              textAlign: TextAlign.center,
            ),
          ],
        ],
      ),
    );
  }

  Future<void> _pickDateTime(BuildContext context) async {
    final date = await showDatePicker(
      context: context,
      initialDate: observedAt,
      firstDate: DateTime.now().subtract(const Duration(days: 7)),
      lastDate: DateTime.now(),
    );
    if (date == null || !context.mounted) return;

    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(observedAt),
    );
    if (time == null) return;

    onObservedAtChanged(DateTime(
        date.year, date.month, date.day, time.hour, time.minute));
  }

  Widget _sectionLabel(String text) => Text(
        text,
        style: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: AppColors.textPrimary,
        ),
      );
}

class _PartySizePicker extends StatelessWidget {
  final int value;
  final ValueChanged<int> onChanged;

  const _PartySizePicker({required this.value, required this.onChanged});

  // Chip options: (party_size stored, display label)
  static const _options = [
    (1, 'Alone'),
    (2, '2'),
    (3, '3'),
    (4, '4'),
    (5, '5'),
    (6, '6+'),
  ];

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: _options.map((opt) {
        final selected = value == opt.$1;
        return GestureDetector(
          onTap: () => onChanged(opt.$1),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: BoxDecoration(
              color: selected ? AppColors.blue600 : const Color(0xFFF1F5F9),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color:
                    selected ? AppColors.blue600 : const Color(0xFFCBD5E1),
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  opt.$1 == 1 ? Icons.person_outline : Icons.group_outlined,
                  size: 14,
                  color: selected ? Colors.white : AppColors.textPrimary,
                ),
                const SizedBox(width: 6),
                Text(
                  opt.$2,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: selected ? Colors.white : AppColors.textPrimary,
                  ),
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }
}

class _SelectChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _SelectChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? AppColors.blue600 : const Color(0xFFF1F5F9),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: selected ? AppColors.blue600 : const Color(0xFFCBD5E1),
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w500,
            color: selected ? Colors.white : AppColors.textPrimary,
          ),
        ),
      ),
    );
  }
}

class _RoadChip extends StatelessWidget {
  final String label;
  final Color color;
  final bool selected;
  final VoidCallback onTap;

  const _RoadChip({
    required this.label,
    required this.color,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(vertical: 10),
        decoration: BoxDecoration(
          color: selected ? color.withAlpha(26) : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: selected ? color : const Color(0xFFE2E8F0),
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Column(
          children: [
            RiskDot(
              level: label == 'Passable'
                  ? 'LOW'
                  : label == 'Difficult'
                      ? 'HIGH'
                      : 'SEVERE',
              size: 8,
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w500,
                color: selected ? color : AppColors.textMuted,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

// ── Step 2: Success ───────────────────────────────────────────────────────────

class _SuccessStep extends StatelessWidget {
  final String syncStatus; // synced | queued
  final VoidCallback onHome;

  const _SuccessStep({required this.syncStatus, required this.onHome});

  @override
  Widget build(BuildContext context) {
    final isSynced = syncStatus == 'synced';

    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 96,
            height: 96,
            decoration: BoxDecoration(
              color: AppColors.riskLow.withAlpha(26),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.check_circle_outline,
                size: 56, color: AppColors.riskLow),
          ),
          const SizedBox(height: 24),
          const Text(
            'Thank you!',
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Your flood report has been submitted.\nIt helps keep your community safe.',
            style: TextStyle(fontSize: 15, color: AppColors.textMuted),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 20),
          // Sync status badge
          AnimatedContainer(
            duration: const Duration(milliseconds: 300),
            padding:
                const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: isSynced
                  ? AppColors.riskLow.withAlpha(20)
                  : AppColors.riskHigh.withAlpha(20),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: isSynced
                    ? AppColors.riskLow.withAlpha(80)
                    : AppColors.riskHigh.withAlpha(80),
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  isSynced ? Icons.cloud_done_outlined : Icons.cloud_upload_outlined,
                  size: 16,
                  color: isSynced ? AppColors.riskLow : AppColors.riskHigh,
                ),
                const SizedBox(width: 8),
                Text(
                  isSynced
                      ? 'Synced to server'
                      : 'Queued — will sync when online',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color:
                        isSynced ? AppColors.riskLow : AppColors.riskHigh,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 40),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: onHome,
              child: const Text('Back to Home'),
            ),
          ),
        ],
      ),
    );
  }
}
