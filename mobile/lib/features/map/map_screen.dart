/// Risk Map screen — MapLibre GL + H3 choropleth + layer toggle + location FAB.
library;

import 'dart:async';
import 'dart:convert' show jsonDecode;
import 'dart:math' show Point;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';
import 'package:maplibre_gl/maplibre_gl.dart';

import '../../core/providers/api_providers.dart';
import '../../core/services/web_notifications.dart';
import '../../design/theme/app_theme.dart';
import 'widgets/layer_toggle.dart';
import 'widgets/location_card.dart';
import 'widgets/map_search_bar.dart';
import 'widgets/risk_legend_chip.dart';

// Free basemap — OpenFreeMap Liberty (no API key required)
const _kStyleUrl = 'https://tiles.openfreemap.org/styles/liberty';

// Assam centre (Guwahati) — fits the whole state at zoom ~7.5.
const _kRegionCenter = LatLng(26.1445, 91.7362);
const _kRegionInitialZoom = 7.5;

// Risk level → hex colour. LOW is intentionally near-invisible so HIGH/SEVERE
// hexes really pop; the user's report overlay draws attention where it matters.
const _kRiskFillColor = [
  'match',
  ['get', 'risk_level'],
  'LOW', '#86EFAC',       // very pale green
  'MODERATE', '#FACC15',
  'HIGH', '#F97316',
  'SEVERE', '#DC2626',    // deep red
  '#CBD5E1',
];
const _kRiskFillOpacity = [
  'match',
  ['get', 'risk_level'],
  'LOW', 0.20,
  'MODERATE', 0.55,
  'HIGH', 0.75,
  'SEVERE', 0.85,
  0.15,
];

// 24-hour cumulative rainfall (mm) → blue-scale intensity.
// Chosen to make even trace rain visible without misrepresenting flood risk.
// 0 mm  → very pale (near-transparent grey), 30+ mm → deep blue.
const _kRainFillColor = [
  'interpolate', ['linear'], ['get', 'rain_24h'],
  0,   '#F1F5F9',
  1,   '#DBEAFE',
  5,   '#93C5FD',
  15,  '#3B82F6',
  30,  '#1D4ED8',
  60,  '#1E3A8A',
];

class RiskMapScreen extends ConsumerStatefulWidget {
  const RiskMapScreen({super.key});

  @override
  ConsumerState<RiskMapScreen> createState() => _RiskMapScreenState();
}

class _RiskMapScreenState extends ConsumerState<RiskMapScreen> {
  MapLibreMapController? _ctrl;
  String _activeLayer = 'risk'; // 'risk' | 'radar'
  Map<String, dynamic>? _locationData;
  double? _locationLat;
  double? _locationLng;
  bool _fetchingHexes = false;
  bool _fetchingLocation = false;
  Timer? _debounce;
  Timer? _reportsPollTimer;
  bool _layersAdded = false;
  bool _reportsLayerAdded = false;
  Set<String> _seenReportIds = <String>{};
  bool _isFirstReportsFetch = true;

  @override
  void dispose() {
    _debounce?.cancel();
    _reportsPollTimer?.cancel();
    super.dispose();
  }

  // ── Map lifecycle ────────────────────────────────────────────────────────────

  Future<void> _onMapCreated(MapLibreMapController ctrl) async {
    _ctrl = ctrl;
  }

  Future<void> _onStyleLoaded() async {
    if (_ctrl == null || _layersAdded) return;
    _layersAdded = true;

    // Add empty GeoJSON source for risk hexes
    await _ctrl!.addGeoJsonSource('risk-hexes', _emptyFeatureCollection());

    // Fill layer coloured by risk_level, with per-level opacity so LOW hexes
    // stay quiet and HIGH/SEVERE really pop.
    const fillProps = FillLayerProperties(
      fillColor: _kRiskFillColor,
      fillOpacity: _kRiskFillOpacity,
      fillOutlineColor: '#FFFFFF',
    );

    bool layerAdded = false;
    for (final below in ['label_other', 'poi_label', 'place_label', 'road_label']) {
      try {
        await _ctrl!.addFillLayer(
          'risk-hexes',
          'risk-fill',
          fillProps,
          belowLayerId: below,
        );
        layerAdded = true;
        break;
      } catch (_) {
        // Layer ID not found in this style — try next
      }
    }

    if (!layerAdded) {
      // Last resort: add without belowLayerId (renders on top)
      try {
        await _ctrl!.addFillLayer('risk-hexes', 'risk-fill', fillProps);
      } catch (e) {
        debugPrint('[RiskMap] addFillLayer failed: $e');
      }
    }

    // Install the user-report heatmap + circles layer.
    await _ensureReportsLayer();
    _refreshReports();
    _reportsPollTimer?.cancel();
    _reportsPollTimer = Timer.periodic(const Duration(seconds: 60), (_) {
      if (mounted) _refreshReports();
    });

    // Ask browser permission for local flood-report notifications (web only,
    // no-op on native). Fires as a browser popup on first map view.
    if (kIsWeb) {
      // Non-blocking — user can dismiss.
      unawaited(WebNotifications.requestPermission());
    }

    // Initial hex fetch
    _scheduleHexFetch();
  }

  // ── Reports overlay (heatmap + per-report circles) ───────────────────────────

  Future<void> _ensureReportsLayer() async {
    if (_ctrl == null || _reportsLayerAdded) return;
    try {
      await _ctrl!.addGeoJsonSource(
        'reports-src',
        const {'type': 'FeatureCollection', 'features': []},
      );
      // Heatmap for zoomed-out overview
      await _ctrl!.addHeatmapLayer(
        'reports-src',
        'reports-heat',
        HeatmapLayerProperties(
          heatmapWeight: [
            'interpolate', ['linear'], ['get', 'weight'],
            1, 0.3, 4, 1.0,
          ],
          heatmapIntensity: [
            'interpolate', ['linear'], ['zoom'],
            9, 1, 15, 3,
          ],
          heatmapColor: [
            'interpolate', ['linear'], ['heatmap-density'],
            0.0, 'rgba(0, 0, 0, 0)',
            0.2, 'rgba(255, 200, 0, 0.5)',
            0.5, 'rgba(255, 100, 0, 0.75)',
            0.8, 'rgba(230, 40, 20, 0.9)',
            1.0, 'rgba(180, 0, 0, 0.95)',
          ],
          heatmapRadius: [
            'interpolate', ['linear'], ['zoom'],
            9, 18, 13, 40, 16, 70,
          ],
          heatmapOpacity: [
            'interpolate', ['linear'], ['zoom'],
            9, 0.85, 15, 0.35,
          ],
        ),
      );
      // Individual red dots when zoomed in — never miss a single report.
      await _ctrl!.addCircleLayer(
        'reports-src',
        'reports-dots',
        CircleLayerProperties(
          circleRadius: [
            'interpolate', ['linear'], ['get', 'weight'],
            1, 5, 4, 12,
          ],
          circleColor: '#DC2626',
          circleOpacity: [
            'interpolate', ['linear'], ['zoom'],
            9, 0.0, 12, 0.8,
          ],
          circleStrokeColor: '#FFFFFF',
          circleStrokeWidth: 1.5,
        ),
      );
      _reportsLayerAdded = true;
    } catch (e) {
      debugPrint('[RiskMap] reports layer add failed: $e');
    }
  }

  Future<void> _refreshReports() async {
    if (_ctrl == null || !_reportsLayerAdded) return;
    try {
      final geojson =
          await ref.read(apiProvider).getReportsHeatmap(sinceHours: 24);
      await _ctrl!.setGeoJsonSource('reports-src', geojson);

      // Notify on new reports since last poll (skip the first fetch so the
      // user isn't spammed with an alert for every historical report).
      final feats = (geojson['features'] as List?) ?? const [];
      final currentIds = feats
          .map((f) => (f as Map)['properties']?['id']?.toString() ?? '')
          .where((s) => s.isNotEmpty)
          .toSet();
      if (!_isFirstReportsFetch) {
        final newIds = currentIds.difference(_seenReportIds);
        if (newIds.isNotEmpty && kIsWeb) {
          for (final f in feats) {
            final props = (f as Map)['properties'] as Map?;
            final id = props?['id']?.toString();
            if (id != null && newIds.contains(id)) {
              WebNotifications.show(
                title: 'New flood report',
                body:
                    '${props?['depth'] ?? 'Flood'} reported nearby — tap to see the map.',
              );
            }
          }
        }
      }
      _seenReportIds = currentIds;
      _isFirstReportsFetch = false;
    } catch (e) {
      debugPrint('[RiskMap] reports refresh failed: $e');
    }
  }

  void _onCameraIdle() => _scheduleHexFetch();

  void _scheduleHexFetch() {
    if (_activeLayer != 'risk') return;
    _debounce?.cancel();
    _debounce =
        Timer(const Duration(milliseconds: 600), _fetchAndRenderHexes);
  }

  // ── Risk hex layer ────────────────────────────────────────────────────────────

  Future<void> _fetchAndRenderHexes() async {
    if (_ctrl == null || _fetchingHexes || _activeLayer != 'risk') return;
    setState(() => _fetchingHexes = true);

    try {
      final region = await _ctrl!.getVisibleRegion();
      final sw = region.southwest;
      final ne = region.northeast;
      final bbox =
          '${sw.longitude},${sw.latitude},${ne.longitude},${ne.latitude}';

      final api = ref.read(apiProvider);
      final geojson = await api.getRiskHexes(bbox);

      if (_ctrl != null && (_activeLayer == 'risk' || _activeLayer == 'rain')) {
        await _ctrl!.setGeoJsonSource('risk-hexes', geojson);
      }
    } catch (e) {
      debugPrint('[RiskMap] hex fetch failed: $e');
    } finally {
      if (mounted) setState(() => _fetchingHexes = false);
    }
  }

  // ── Layer toggle ─────────────────────────────────────────────────────────────

  Future<void> _toggleLayer(String layer) async {
    if (layer == _activeLayer || _ctrl == null) return;
    setState(() => _activeLayer = layer);

    if (layer == 'risk') {
      await _setLayerVisibility('risk-fill', true);
      await _setLayerVisibility('radar-raster', false);
      await _setFillExpression(_kRiskFillColor);
      _scheduleHexFetch();
    } else if (layer == 'rain') {
      await _setLayerVisibility('risk-fill', true);
      await _setLayerVisibility('radar-raster', false);
      await _setFillExpression(_kRainFillColor);
      _scheduleHexFetch();
    } else {
      await _setLayerVisibility('risk-fill', false);
      await _showRadarLayer();
    }
  }

  Future<void> _setFillExpression(List<dynamic> expr) async {
    try {
      // Risk mode uses per-level opacity so LOW fades and SEVERE pops.
      // Rain mode uses a single opacity because the colour ramp is continuous.
      final opacity = identical(expr, _kRiskFillColor) ? _kRiskFillOpacity : 0.65;
      await _ctrl!.setLayerProperties(
        'risk-fill',
        FillLayerProperties(
          fillColor: expr,
          fillOpacity: opacity,
          fillOutlineColor: '#FFFFFF',
        ),
      );
    } catch (e) {
      debugPrint('[RiskMap] setLayerProperties failed: $e');
    }
  }

  Future<void> _setLayerVisibility(String layerId, bool visible) async {
    try {
      await _ctrl!.setLayerVisibility(layerId, visible);
    } catch (_) {} // layer may not exist yet
  }

  Future<void> _showRadarLayer() async {
    try {
      final api = ref.read(apiProvider);
      final frames = await api.getRadarFrames();
      if (frames.isEmpty || _ctrl == null) return;

      final tileUrl = frames.first['tile_url_template'] as String?;
      if (tileUrl == null) return;

      // Add or update raster source
      try {
        await _ctrl!.removeLayer('radar-raster');
        await _ctrl!.removeSource('radar-source');
      } catch (_) {}

      await _ctrl!.addSource(
        'radar-source',
        RasterSourceProperties(
          tiles: [tileUrl], 
          tileSize: 256,
          maxzoom: 6,
        ),
      );
      await _ctrl!.addRasterLayer(
        'radar-source',
        'radar-raster',
        const RasterLayerProperties(rasterOpacity: 0.65),
      );
    } catch (e) {
      debugPrint('[RiskMap] radar layer failed: $e');
    }
  }

  // ── My Location ───────────────────────────────────────────────────────────────

  Future<void> _myLocation() async {
    if (_fetchingLocation) return;
    setState(() => _fetchingLocation = true);

    try {
      LocationPermission perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) {
        perm = await Geolocator.requestPermission();
      }
      if (perm == LocationPermission.deniedForever) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('Location permission denied. Enable in Settings.'),
          ));
        }
        return;
      }

      final pos = await Geolocator.getCurrentPosition(
        locationSettings:
            const LocationSettings(accuracy: LocationAccuracy.high),
      );

      await _ctrl?.animateCamera(
        CameraUpdate.newLatLngZoom(
            LatLng(pos.latitude, pos.longitude), 14.0),
      );

      final api = ref.read(apiProvider);
      final data = await api.getRiskLocation(pos.latitude, pos.longitude);
      if (mounted) {
        setState(() {
          _locationData = data;
          _locationLat = pos.latitude;
          _locationLng = pos.longitude;
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Location unavailable: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _fetchingLocation = false);
    }
  }

  // ── Map tap → report modal OR area detail ────────────────────────────────────

  Future<void> _onMapClick(Point<double> point, LatLng coords) async {
    // First: check whether the user tapped a flood-report dot. queryRenderedFeatures
    // only returns dots that are currently visible/rendered, so this is a no-op
    // when the reports layer isn't showing (very zoomed out).
    if (_reportsLayerAdded && _ctrl != null) {
      try {
        final features = await _ctrl!.queryRenderedFeatures(
          point,
          ['reports-dots'],
          null,
        );
        if (features.isNotEmpty) {
          await _openReportDetail(features.first, coords);
          return;
        }
      } catch (_) {
        // Feature query not supported on this platform — fall through.
      }
    }

    // Fallback: existing risk-location lookup (shows the LocationCard).
    try {
      final api = ref.read(apiProvider);
      final data =
          await api.getRiskLocation(coords.latitude, coords.longitude);
      final h3 = data['h3_index'] as String?;
      if (h3 != null && mounted) {
        setState(() {
          _locationData = data;
          _locationLat = coords.latitude;
          _locationLng = coords.longitude;
        });
      }
    } catch (_) {}
  }

  Future<void> _openReportDetail(dynamic feature, LatLng tapCoords) async {
    // queryRenderedFeatures returns either a Map or a JSON string depending on
    // the platform binding; normalize to Map<String, dynamic>.
    Map<String, dynamic>? feat;
    if (feature is Map) feat = Map<String, dynamic>.from(feature);
    else if (feature is String) {
      try {
        final decoded = jsonDecode(feature);
        if (decoded is Map) feat = Map<String, dynamic>.from(decoded);
      } catch (_) {}
    }
    final props = feat?['properties'] is Map
        ? Map<String, dynamic>.from(feat!['properties'] as Map)
        : <String, dynamic>{};
    final geom = feat?['geometry'] is Map
        ? Map<String, dynamic>.from(feat!['geometry'] as Map)
        : <String, dynamic>{};
    final coords = (geom['coordinates'] is List && (geom['coordinates'] as List).length >= 2)
        ? geom['coordinates'] as List
        : [tapCoords.longitude, tapCoords.latitude];
    final lng = (coords[0] as num).toDouble();
    final lat = (coords[1] as num).toDouble();
    final id = props['id']?.toString();

    // Heatmap features only carry id/depth/status; fetch the full row from
    // /reports/nearby/ which includes photo_url and description.
    Map<String, dynamic>? full;
    try {
      final nearby = await ref
          .read(apiProvider)
          .getReportsNearby(lat: lat, lng: lng, radiusM: 150, sinceMin: 60 * 24 * 7);
      for (final r in nearby) {
        if (r is Map && r['id']?.toString() == id) {
          full = Map<String, dynamic>.from(r);
          break;
        }
      }
      full ??= nearby.isNotEmpty ? Map<String, dynamic>.from(nearby.first as Map) : null;
    } catch (_) {}

    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => _ReportDetailSheet(
        report: full ?? {'id': id, 'depth': props['depth'], 'lat': lat, 'lng': lng},
      ),
    );
  }

  void _viewAreaDetail() {
    final h3 = _locationData?['h3_index'] as String?;
    if (h3 == null) return;
    final lat = _locationLat ?? _kRegionCenter.latitude;
    final lng = _locationLng ?? _kRegionCenter.longitude;
    final uri = Uri(
      path: '/area/$h3',
      queryParameters: {'lat': lat.toString(), 'lng': lng.toString()},
    );
    context.push(uri.toString());
  }

  // ── Search ────────────────────────────────────────────────────────────────────

  Future<void> _onSearchResult(result) async {
    await _ctrl?.animateCamera(
      CameraUpdate.newLatLngZoom(LatLng(result.lat, result.lng), 14.0),
    );
    _scheduleHexFetch();
  }

  // ── Build ─────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final topPad = MediaQuery.of(context).padding.top;

    return Scaffold(
      body: Stack(
        children: [
          // ── MapLibre map ─────────────────────────────────────────────────────
          MapLibreMap(
            styleString: _kStyleUrl,
            initialCameraPosition: const CameraPosition(
              target: _kRegionCenter,
              zoom: _kRegionInitialZoom,
            ),
            onMapCreated: _onMapCreated,
            onStyleLoadedCallback: _onStyleLoaded,
            onCameraIdle: _onCameraIdle,
            onMapClick: _onMapClick,
            myLocationEnabled: false,
            trackCameraPosition: true,
            annotationOrder: const [AnnotationType.fill],
          ),

          // ── Search bar (top) ─────────────────────────────────────────────────
          Positioned(
            top: topPad + 8,
            left: 16,
            right: 16,
            child: MapSearchBar(onResultSelected: _onSearchResult),
          ),

          // ── Layer toggle (top-right, below search) ───────────────────────────
          Positioned(
            top: topPad + 64,
            right: 16,
            child: LayerToggle(
                active: _activeLayer, onToggle: _toggleLayer),
          ),

          // ── Loading indicator ────────────────────────────────────────────────
          if (_fetchingHexes)
            Positioned(
              top: topPad + 120,
              right: 16,
              child: Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(8),
                  boxShadow: const [
                    BoxShadow(
                        color: Color(0x1A0F172A),
                        blurRadius: 6,
                        offset: Offset(0, 2)),
                  ],
                ),
                child: const Padding(
                  padding: EdgeInsets.all(6),
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ),
            ),

          // ── Legend chip (bottom-left) — swaps between risk & rain modes ─────
          if (_activeLayer == 'risk' || _activeLayer == 'rain')
            Positioned(
              bottom: (_locationData != null ? 190 : 100),
              left: 16,
              child: RiskLegendChip(mode: _activeLayer),
            ),

          // ── Radar mode banner ────────────────────────────────────────────────
          if (_activeLayer == 'radar')
            Positioned(
              bottom: 100,
              left: 16,
              right: 72,
              child: _RadarBanner(),
            ),

          // ── Location card (bottom) ───────────────────────────────────────────
          if (_locationData != null)
            Positioned(
              bottom: 0,
              left: 0,
              right: 0,
              child: LocationCard(
                data: _locationData!,
                onDismiss: () => setState(() => _locationData = null),
                onViewDetail: _viewAreaDetail,
              ),
            ),
        ],
      ),

      // ── My Location FAB ───────────────────────────────────────────────────────
      floatingActionButton: FloatingActionButton(
        onPressed: _myLocation,
        backgroundColor: Colors.white,
        foregroundColor: AppColors.blue600,
        elevation: 4,
        child: _fetchingLocation
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2))
            : const Icon(Icons.my_location),
      ),
    );
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

Map<String, dynamic> _emptyFeatureCollection() =>
    {'type': 'FeatureCollection', 'features': []};

class _RadarBanner extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.all(Radius.circular(12)),
        boxShadow: [
          BoxShadow(
              color: Color(0x1A0F172A),
              blurRadius: 8,
              offset: Offset(0, 2)),
        ],
      ),
      child: const Row(
        children: [
          Icon(Icons.radar, color: AppColors.blue600, size: 18),
          SizedBox(width: 8),
          Expanded(
            child: Text(
              'Radar overlay active — live dBZ tiles',
              style: TextStyle(fontSize: 12, color: AppColors.textPrimary),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Report detail bottom sheet ────────────────────────────────────────────────

class _ReportDetailSheet extends StatelessWidget {
  final Map<String, dynamic> report;
  const _ReportDetailSheet({required this.report});

  static const _depthLabels = {
    'ANKLE': 'Ankle deep',
    'KNEE': 'Knee deep',
    'WAIST': 'Waist deep',
    'VEHICLE': 'Vehicle level',
  };
  static const _roadLabels = {
    'PASSABLE': 'Road passable',
    'DIFFICULT': 'Road difficult',
    'BLOCKED': 'Road blocked',
  };

  String _timeAgo(String? iso) {
    if (iso == null) return '';
    try {
      final ts = DateTime.parse(iso);
      final diff = DateTime.now().difference(ts);
      if (diff.inMinutes < 1) return 'just now';
      if (diff.inHours < 1) return '${diff.inMinutes}m ago';
      if (diff.inDays < 1) return '${diff.inHours}h ago';
      return '${diff.inDays}d ago';
    } catch (_) {
      return '';
    }
  }

  @override
  Widget build(BuildContext context) {
    final photo = report['photo_url'] as String?;
    final depth = report['depth']?.toString() ?? '';
    final road = report['road']?.toString() ?? '';
    final status = report['status']?.toString() ?? 'PENDING';
    final description = report['description']?.toString() ?? '';
    final observedAt = report['observed_at']?.toString();
    final partySize = report['party_size'] as int? ?? 1;
    final lat = (report['lat'] as num?)?.toDouble();
    final lng = (report['lng'] as num?)?.toDouble();

    final statusColor = status == 'VERIFIED'
        ? AppColors.riskLow
        : status == 'PENDING'
            ? AppColors.riskModerate
            : AppColors.textMuted;

    return SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Center(
            child: Container(
              width: 40,
              height: 4,
              margin: const EdgeInsets.only(top: 8),
              decoration: BoxDecoration(
                color: const Color(0xFFCBD5E1),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: Row(
              children: [
                const Icon(Icons.warning_amber_rounded,
                    color: AppColors.riskSevere, size: 22),
                const SizedBox(width: 8),
                const Expanded(
                  child: Text('Flood report',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textPrimary,
                      )),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    status,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: statusColor,
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (photo != null && photo.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: Image.network(
                  photo,
                  width: double.infinity,
                  height: 220,
                  fit: BoxFit.cover,
                  loadingBuilder: (_, child, progress) =>
                      progress == null
                          ? child
                          : Container(
                              height: 220,
                              color: const Color(0xFFF1F5F9),
                              alignment: Alignment.center,
                              child: const CircularProgressIndicator(strokeWidth: 2),
                            ),
                  errorBuilder: (_, __, ___) => Container(
                    height: 120,
                    color: const Color(0xFFF1F5F9),
                    alignment: Alignment.center,
                    child: const Text('Photo unavailable',
                        style: TextStyle(color: AppColors.textMuted)),
                  ),
                ),
              ),
            )
          else
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Container(
                height: 100,
                decoration: BoxDecoration(
                  color: const Color(0xFFF1F5F9),
                  borderRadius: BorderRadius.circular(10),
                ),
                alignment: Alignment.center,
                child: const Text('No photo attached',
                    style: TextStyle(color: AppColors.textMuted, fontSize: 13)),
              ),
            ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                if (depth.isNotEmpty)
                  _Chip(
                    icon: Icons.water,
                    label: _depthLabels[depth] ?? depth,
                    bg: const Color(0xFFDBEAFE),
                    fg: const Color(0xFF1E40AF),
                  ),
                if (road.isNotEmpty)
                  _Chip(
                    icon: Icons.directions_car_outlined,
                    label: _roadLabels[road] ?? road,
                    bg: const Color(0xFFFEF3C7),
                    fg: const Color(0xFF92400E),
                  ),
                _Chip(
                  icon: Icons.people_outline,
                  label: partySize <= 1
                      ? 'Alone'
                      : '$partySize${partySize >= 6 ? '+' : ''} people',
                  bg: const Color(0xFFE0E7FF),
                  fg: const Color(0xFF4338CA),
                ),
              ],
            ),
          ),
          if (description.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFF1F5F9),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  '"$description"',
                  style: const TextStyle(
                    fontSize: 14,
                    color: AppColors.textPrimary,
                    fontStyle: FontStyle.italic,
                    height: 1.4,
                  ),
                ),
              ),
            ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: Row(
              children: [
                const Icon(Icons.schedule,
                    size: 14, color: AppColors.textMuted),
                const SizedBox(width: 6),
                Text(_timeAgo(observedAt),
                    style: const TextStyle(
                        fontSize: 12, color: AppColors.textMuted)),
                if (lat != null && lng != null) ...[
                  const SizedBox(width: 12),
                  const Icon(Icons.location_on_outlined,
                      size: 14, color: AppColors.textMuted),
                  const SizedBox(width: 6),
                  Text('${lat.toStringAsFixed(5)}, ${lng.toStringAsFixed(5)}',
                      style: const TextStyle(
                          fontSize: 12, color: AppColors.textMuted)),
                ],
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 20),
            child: Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('Close'),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color bg;
  final Color fg;
  const _Chip({
    required this.icon,
    required this.label,
    required this.bg,
    required this.fg,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(6)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: fg),
          const SizedBox(width: 6),
          Text(label,
              style: TextStyle(
                  fontSize: 12, fontWeight: FontWeight.w600, color: fg)),
        ],
      ),
    );
  }
}
