/// Live Radar screen — animated MapLibre raster tiles + timeline scrubber.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:maplibre_gl/maplibre_gl.dart';

import '../../core/providers/api_providers.dart';
import '../../data/models/radar_frame.dart';
import '../../design/theme/app_theme.dart';
import '../../design/widgets/fg_app_header.dart';
import 'widgets/radar_intensity_legend.dart';
import 'widgets/radar_timeline.dart';

const _kStyleUrl = 'https://tiles.openfreemap.org/styles/liberty';
const _kHydCenter = LatLng(17.3850, 78.4867);
const _kAnimInterval = Duration(milliseconds: 800);

// Static dBZ colour scale — always shown in legend regardless of live data
const _kStaticBands = [
  RadarIntensityBand(dbzMin: 0,  dbzMax: 10, color: '#00ffff', label: 'Trace'),
  RadarIntensityBand(dbzMin: 10, dbzMax: 20, color: '#00aaff', label: 'Light'),
  RadarIntensityBand(dbzMin: 20, dbzMax: 30, color: '#00cc00', label: 'Moderate'),
  RadarIntensityBand(dbzMin: 30, dbzMax: 40, color: '#ffff00', label: 'Heavy'),
  RadarIntensityBand(dbzMin: 40, dbzMax: 50, color: '#ff9900', label: 'Very heavy'),
  RadarIntensityBand(dbzMin: 50, dbzMax: 60, color: '#ff0000', label: 'Intense'),
  RadarIntensityBand(dbzMin: 60, dbzMax: 75, color: '#cc00cc', label: 'Extreme'),
];

// ── Provider ──────────────────────────────────────────────────────────────────

final radarFramesProvider = FutureProvider<List<RadarFrame>>((ref) async {
  final raw = await ref.watch(apiProvider).getRadarFrames();
  // API returns newest-first; reverse so timeline reads oldest → newest
  return raw
      .map((e) => RadarFrame.fromJson(e as Map<String, dynamic>))
      .toList()
      .reversed
      .toList();
});

// ── Screen ────────────────────────────────────────────────────────────────────

class RadarScreen extends ConsumerStatefulWidget {
  const RadarScreen({super.key});

  @override
  ConsumerState<RadarScreen> createState() => _RadarScreenState();
}

class _RadarScreenState extends ConsumerState<RadarScreen>
    with WidgetsBindingObserver {
  MapLibreMapController? _ctrl;
  bool _styleLoaded = false;
  bool _isPlaying = true;
  int _currentIndex = 0;
  Timer? _animTimer;
  String? _activeTileUrl;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    _animTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused) {
      _stopAnimation();
    } else if (state == AppLifecycleState.resumed && _isPlaying) {
      final frames = ref.read(radarFramesProvider).valueOrNull ?? [];
      if (frames.isNotEmpty) _startAnimation(frames);
    }
  }

  // ── Map lifecycle ─────────────────────────────────────────────────────────

  void _onMapCreated(MapLibreMapController ctrl) => _ctrl = ctrl;

  Future<void> _onStyleLoaded() async {
    if (!mounted) return;
    setState(() => _styleLoaded = true);

    // If frames already resolved before the style finished loading, start now
    final frames = ref.read(radarFramesProvider).valueOrNull ?? [];
    if (frames.isNotEmpty) {
      await _showFrame(frames, _currentIndex);
      if (_isPlaying) _startAnimation(frames);
    }
  }

  // ── Animation ─────────────────────────────────────────────────────────────

  void _startAnimation(List<RadarFrame> frames) {
    _animTimer?.cancel();
    if (frames.length <= 1) return;
    _animTimer = Timer.periodic(_kAnimInterval, (_) {
      if (!mounted) return;
      final next = (_currentIndex + 1) % frames.length;
      setState(() => _currentIndex = next);
      _showFrame(frames, next);
    });
  }

  void _stopAnimation() {
    _animTimer?.cancel();
    _animTimer = null;
  }

  void _togglePlayPause(List<RadarFrame> frames) {
    setState(() => _isPlaying = !_isPlaying);
    if (_isPlaying) {
      _startAnimation(frames);
    } else {
      _stopAnimation();
    }
  }

  void _selectFrame(List<RadarFrame> frames, int index) {
    _stopAnimation();
    setState(() {
      _currentIndex = index;
      _isPlaying = false;
    });
    _showFrame(frames, index);
  }

  // ── Radar tile swap ───────────────────────────────────────────────────────

  Future<void> _showFrame(List<RadarFrame> frames, int index) async {
    if (_ctrl == null || !_styleLoaded || frames.isEmpty) return;
    final url = frames[index].tileUrl;
    if (url == _activeTileUrl) return;
    _activeTileUrl = url;

    try { await _ctrl!.removeLayer('radar-live-layer'); } catch (_) {}
    try { await _ctrl!.removeSource('radar-live'); } catch (_) {}

    try {
      await _ctrl!.addSource(
        'radar-live',
        RasterSourceProperties(tiles: [url], tileSize: 512),
      );
      await _ctrl!.addRasterLayer(
        'radar-live',
        'radar-live-layer',
      );
    } catch (e) {
      debugPrint('[RadarScreen] tile swap: $e');
    }
  }

  // ── Build ─────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final framesAsync = ref.watch(radarFramesProvider);

    // ref.listen fires only on provider changes, never during build — safe for side-effects
    ref.listen<AsyncValue<List<RadarFrame>>>(radarFramesProvider, (_, next) {
      next.whenData((frames) {
        if (!mounted || frames.isEmpty || !_styleLoaded || _animTimer != null) return;
        _showFrame(frames, _currentIndex);
        if (_isPlaying) _startAnimation(frames);
      });
    });

    final frames = framesAsync.valueOrNull ?? [];
    final hasFrames = frames.isNotEmpty;
    final bottomPad = MediaQuery.of(context).padding.bottom;
    final timelineH = hasFrames ? 128.0 + bottomPad : 0.0;

    return Scaffold(
      appBar: FgAppHeader(
        key: const ValueKey('radar-header'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white, size: 22),
            tooltip: 'Refresh',
            onPressed: () {
              _stopAnimation();
              setState(() {
                _currentIndex = 0;
                _activeTileUrl = null;
                _isPlaying = true;
              });
              ref.invalidate(radarFramesProvider);
            },
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: Stack(
        children: [
          // ── Base map — always fills screen ───────────────────────────────
          Positioned.fill(
            bottom: timelineH,
            child: MapLibreMap(
              styleString: _kStyleUrl,
              initialCameraPosition: const CameraPosition(
                target: _kHydCenter,
                zoom: 9.5,
              ),
              onMapCreated: _onMapCreated,
              onStyleLoadedCallback: _onStyleLoaded,
              myLocationEnabled: false,
              compassEnabled: false,
              rotateGesturesEnabled: false,
              tiltGesturesEnabled: false,
            ),
          ),

          // ── Status chip (loading / error / no frames) ────────────────────
          framesAsync.when(
            loading: () => const Positioned(
              top: 12, left: 0, right: 0,
              child: Center(child: _StatusChip(
                icon: Icons.hourglass_top,
                label: 'Loading radar frames…',
                color: AppColors.blue600,
              )),
            ),
            error: (_, __) => Positioned(
              top: 12, left: 0, right: 0,
              child: Center(child: _StatusChip(
                icon: Icons.cloud_off,
                label: 'Radar unavailable — tap to retry',
                color: AppColors.riskHigh,
                onTap: () => ref.invalidate(radarFramesProvider),
              )),
            ),
            data: (f) => f.isEmpty
                ? const Positioned(
                    top: 12, left: 0, right: 0,
                    child: Center(child: _StatusChip(
                      icon: Icons.water_drop_outlined,
                      label: 'No precipitation detected',
                      color: AppColors.textMuted,
                    )),
                  )
                : const SizedBox.shrink(),
          ),

          // ── LIVE / PLAYBACK badge ────────────────────────────────────────
          if (hasFrames)
            Positioned(
              top: 12,
              right: 12,
              child: _LiveBadge(isLatest: _currentIndex == frames.length - 1),
            ),

          // ── dBZ legend — always visible ──────────────────────────────────
          Positioned(
            bottom: timelineH + 12,
            left: 12,
            child: const RadarIntensityLegend(bands: _kStaticBands),
          ),

          // ── Frame counter ────────────────────────────────────────────────
          if (hasFrames)
            Positioned(
              bottom: timelineH + 12,
              right: 12,
              child: _FrameCounter(
                current: _currentIndex + 1,
                total: frames.length,
              ),
            ),

          // ── Timeline scrubber ────────────────────────────────────────────
          if (hasFrames)
            Positioned(
              left: 0, right: 0, bottom: 0,
              child: RadarTimeline(
                frames: frames,
                selectedIndex: _currentIndex,
                isPlaying: _isPlaying,
                onFrameSelected: (i) => _selectFrame(frames, i),
                onPlayPause: () => _togglePlayPause(frames),
              ),
            ),
        ],
      ),
    );
  }
}

// ── Widgets ───────────────────────────────────────────────────────────────────

class _StatusChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback? onTap;
  const _StatusChip({required this.icon, required this.label, required this.color, this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: Colors.black54,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: color, size: 16),
            const SizedBox(width: 6),
            Text(label, style: TextStyle(color: color, fontSize: 12,
                fontWeight: FontWeight.w500)),
          ],
        ),
      ),
    );
  }
}

class _LiveBadge extends StatelessWidget {
  final bool isLatest;
  const _LiveBadge({required this.isLatest});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: isLatest ? AppColors.riskSevere : AppColors.textMuted,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (isLatest)
            Container(
              width: 6, height: 6,
              margin: const EdgeInsets.only(right: 5),
              decoration: const BoxDecoration(
                color: Colors.white, shape: BoxShape.circle,
              ),
            ),
          Text(
            isLatest ? 'LIVE' : 'PLAYBACK',
            style: const TextStyle(color: Colors.white, fontSize: 11,
                fontWeight: FontWeight.w700, letterSpacing: 0.8),
          ),
        ],
      ),
    );
  }
}

class _FrameCounter extends StatelessWidget {
  final int current;
  final int total;
  const _FrameCounter({required this.current, required this.total});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: Colors.black54,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text('$current / $total',
          style: const TextStyle(color: Colors.white, fontSize: 12,
              fontWeight: FontWeight.w600)),
    );
  }
}
