/// Risk Map screen — MapLibre GL + H3 choropleth + layer toggle + location FAB.
library;

import 'dart:async';
import 'dart:math' show Point;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';
import 'package:maplibre_gl/maplibre_gl.dart';

import '../../core/providers/api_providers.dart';
import '../../design/theme/app_theme.dart';
import 'widgets/layer_toggle.dart';
import 'widgets/location_card.dart';
import 'widgets/map_search_bar.dart';
import 'widgets/risk_legend_chip.dart';

// Free basemap — OpenFreeMap Liberty (no API key required)
const _kStyleUrl = 'https://tiles.openfreemap.org/styles/liberty';

// Hyderabad centre
const _kHydCenter = LatLng(17.3850, 78.4867);

// Risk level → hex colour (§2 tokens)
const _kRiskFillColor = [
  'match',
  ['get', 'risk_level'],
  'LOW', '#22C55E',
  'MODERATE', '#FACC15',
  'HIGH', '#F97316',
  'SEVERE', '#EF4444',
  '#94A3B8',
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
  bool _fetchingHexes = false;
  bool _fetchingLocation = false;
  Timer? _debounce;
  bool _layersAdded = false;

  @override
  void dispose() {
    _debounce?.cancel();
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

    // Fill layer coloured by risk_level
    await _ctrl!.addFillLayer(
      'risk-hexes',
      'risk-fill',
      FillLayerProperties(
        fillColor: _kRiskFillColor,
        fillOpacity: 0.55,
        fillOutlineColor: '#FFFFFF',
      ),
    );

    // Initial hex fetch
    _scheduleHexFetch();
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

      if (_ctrl != null && _activeLayer == 'risk') {
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
      // Show risk fill, hide radar
      await _setLayerVisibility('risk-fill', true);
      await _setLayerVisibility('radar-raster', false);
      _scheduleHexFetch();
    } else {
      // Hide risk fill, show radar raster
      await _setLayerVisibility('risk-fill', false);
      await _showRadarLayer();
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
        const RasterSourceProperties(tileSize: 256),
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
      if (mounted) setState(() => _locationData = data);
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

  // ── Map tap → area detail ─────────────────────────────────────────────────────

  Future<void> _onMapClick(Point<double> point, LatLng coords) async {
    try {
      final api = ref.read(apiProvider);
      final data =
          await api.getRiskLocation(coords.latitude, coords.longitude);
      final h3 = data['h3_index'] as String?;
      if (h3 != null && mounted) {
        setState(() => _locationData = data);
      }
    } catch (_) {}
  }

  void _viewAreaDetail() {
    final h3 = _locationData?['h3_index'] as String?;
    if (h3 != null) context.push('/area/$h3');
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
              target: _kHydCenter,
              zoom: 11.0,
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

          // ── Risk legend chip (bottom-left) ───────────────────────────────────
          if (_activeLayer == 'risk')
            Positioned(
              bottom: (_locationData != null ? 190 : 100),
              left: 16,
              child: const RiskLegendChip(),
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
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: const [
          BoxShadow(
              color: Color(0x1A0F172A),
              blurRadius: 8,
              offset: Offset(0, 2)),
        ],
      ),
      child: Row(
        children: [
          const Icon(Icons.radar, color: AppColors.blue600, size: 18),
          const SizedBox(width: 8),
          const Expanded(
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
