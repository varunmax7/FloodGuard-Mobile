/// Map search bar — Nominatim geocoding, fly-to on selection.
library;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import '../../../design/theme/app_theme.dart';

class MapSearchResult {
  final String displayName;
  final double lat;
  final double lng;

  const MapSearchResult(
      {required this.displayName, required this.lat, required this.lng});
}

class MapSearchBar extends StatefulWidget {
  final ValueChanged<MapSearchResult> onResultSelected;

  const MapSearchBar({super.key, required this.onResultSelected});

  @override
  State<MapSearchBar> createState() => _MapSearchBarState();
}

class _MapSearchBarState extends State<MapSearchBar> {
  final _controller = TextEditingController();
  final _focus = FocusNode();
  final _dio = Dio();
  List<MapSearchResult> _results = [];
  bool _loading = false;
  bool _expanded = false;

  Future<void> _search(String query) async {
    if (query.trim().length < 3) {
      setState(() => _results = []);
      return;
    }
    setState(() => _loading = true);
    try {
      final res = await _dio.get<List<dynamic>>(
        'https://nominatim.openstreetmap.org/search',
        queryParameters: {
          'q': '$query Telangana Andhra Pradesh',
          'format': 'json',
          'limit': 5,
          // Nominatim viewbox order: left,top,right,bottom (lng,lat,lng,lat).
          // TG + AP combined roughly spans 76.5°E–84.8°E, 12.5°N–19.9°N.
          'viewbox': '76.5,19.9,84.8,12.5',
          'bounded': 1,
          'countrycodes': 'in',
        },
        options: Options(headers: {'User-Agent': 'FloodGuard/1.0'}),
      );
      setState(() {
        _results = (res.data ?? [])
            .map((r) => MapSearchResult(
                  displayName: _shortName(r['display_name'] as String),
                  lat: double.parse(r['lat'] as String),
                  lng: double.parse(r['lon'] as String),
                ))
            .toList();
      });
    } catch (_) {
      setState(() => _results = []);
    } finally {
      setState(() => _loading = false);
    }
  }

  String _shortName(String full) {
    final parts = full.split(', ');
    return parts.take(2).join(', ');
  }

  void _select(MapSearchResult r) {
    _controller.text = r.displayName;
    _focus.unfocus();
    setState(() {
      _results = [];
      _expanded = false;
    });
    widget.onResultSelected(r);
  }

  @override
  void dispose() {
    _controller.dispose();
    _focus.dispose();
    _dio.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Search bar
        Container(
          height: 44,
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
              const SizedBox(width: 12),
              const Icon(Icons.search, color: AppColors.textMuted, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  controller: _controller,
                  focusNode: _focus,
                  style: const TextStyle(fontSize: 14),
                  decoration: const InputDecoration(
                    border: InputBorder.none,
                    hintText: 'Search area in Telangana or AP...',
                    hintStyle:
                        TextStyle(fontSize: 14, color: AppColors.textMuted),
                    isDense: true,
                    contentPadding: EdgeInsets.zero,
                  ),
                  onChanged: (v) {
                    setState(() => _expanded = true);
                    _search(v);
                  },
                ),
              ),
              if (_loading)
                const Padding(
                  padding: EdgeInsets.all(10),
                  child: SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2)),
                )
              else if (_controller.text.isNotEmpty)
                IconButton(
                  icon: const Icon(Icons.close, size: 18),
                  onPressed: () {
                    _controller.clear();
                    setState(() {
                      _results = [];
                      _expanded = false;
                    });
                  },
                ),
            ],
          ),
        ),

        // Results dropdown
        if (_expanded && _results.isNotEmpty)
          Container(
            margin: const EdgeInsets.only(top: 4),
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
            child: ListView.separated(
              shrinkWrap: true,
              padding: EdgeInsets.zero,
              itemCount: _results.length,
              separatorBuilder: (_, __) =>
                  const Divider(height: 1, indent: 16),
              itemBuilder: (_, i) {
                final r = _results[i];
                return ListTile(
                  dense: true,
                  leading: const Icon(Icons.location_on_outlined,
                      size: 18, color: AppColors.textMuted),
                  title: Text(r.displayName,
                      style: const TextStyle(fontSize: 13)),
                  onTap: () => _select(r),
                );
              },
            ),
          ),
      ],
    );
  }
}
