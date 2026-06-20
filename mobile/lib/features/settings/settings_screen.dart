/// Settings screen — saved places (max 3) with notify toggles + phone login/logout.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';

import '../../core/network/dio_client.dart';
import '../../core/providers/alerts_providers.dart';
import '../../data/models/saved_place.dart';
import '../../design/theme/app_theme.dart';
import '../../design/widgets/fg_app_header.dart';
import '../../design/widgets/fg_card.dart';
import '../../design/widgets/skeleton_loader.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);
    final placesAsync = ref.watch(placesProvider);

    return Scaffold(
      appBar: const FgAppHeader(),
      backgroundColor: const Color(0xFFF1F5F9),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: [
          // ── Account section ───────────────────────────────────────────────
          _SectionLabel('Account'),
          const SizedBox(height: 8),
          FgCard(
            child: auth.isLoggedIn
                ? Row(
                    children: [
                      const Icon(Icons.person_outline,
                          color: AppColors.blue600, size: 22),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              auth.phone ?? 'Signed in',
                              style: const TextStyle(
                                  fontSize: 15,
                                  fontWeight: FontWeight.w600,
                                  color: AppColors.textPrimary),
                            ),
                            const Text('Tap "Sign out" to log out.',
                                style: TextStyle(
                                    fontSize: 12,
                                    color: AppColors.textMuted)),
                          ],
                        ),
                      ),
                      TextButton(
                        onPressed: () => _signOut(context, ref),
                        child: const Text('Sign out',
                            style: TextStyle(color: AppColors.riskSevere)),
                      ),
                    ],
                  )
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Sign in to save places and receive flood alerts.',
                        style: TextStyle(
                            fontSize: 14, color: AppColors.textPrimary),
                      ),
                      const SizedBox(height: 12),
                      SizedBox(
                        width: double.infinity,
                        child: FilledButton.icon(
                          onPressed: () => context.push('/auth'),
                          icon: const Icon(Icons.phone_outlined, size: 18),
                          label: const Text('Sign in with phone'),
                        ),
                      ),
                    ],
                  ),
          ),

          const SizedBox(height: 24),

          // ── Saved places section ──────────────────────────────────────────
          Row(
            children: [
              const Expanded(child: _SectionLabel('Saved Places')),
              if (auth.isLoggedIn)
                Text(
                  '${placesAsync.value?.length ?? 0}/3',
                  style: const TextStyle(
                      fontSize: 12, color: AppColors.textMuted),
                ),
            ],
          ),
          const SizedBox(height: 8),

          placesAsync.when(
            loading: () => const SkeletonBox(
                width: double.infinity, height: 80),
            error: (_, __) => FgCard(
              child: Row(
                children: [
                  const Icon(Icons.cloud_off_outlined,
                      color: AppColors.textMuted, size: 20),
                  const SizedBox(width: 12),
                  const Expanded(
                      child: Text('Could not load saved places.',
                          style: TextStyle(
                              fontSize: 14, color: AppColors.textMuted))),
                  TextButton(
                    onPressed: () =>
                        ref.read(placesProvider.notifier).fetch(),
                    child: const Text('Retry'),
                  ),
                ],
              ),
            ),
            data: (places) => Column(
              children: [
                for (final place in places) ...[
                  _PlaceCard(place: place),
                  const SizedBox(height: 8),
                ],
                if (auth.isLoggedIn && places.length < 3)
                  _AddPlaceButton(places: places),
                if (!auth.isLoggedIn)
                  FgCard(
                    child: const Text(
                      'Sign in to manage saved places.',
                      style: TextStyle(
                          fontSize: 14, color: AppColors.textMuted),
                      textAlign: TextAlign.center,
                    ),
                  ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // ── Notifications note ────────────────────────────────────────────
          _SectionLabel('Notifications'),
          const SizedBox(height: 8),
          FgCard(
            child: Row(
              children: const [
                Icon(Icons.notifications_active_outlined,
                    color: AppColors.blue600, size: 20),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'Push alerts are sent when flood risk rises at your saved places. '
                    'Toggle the bell icon on each place to control alerts.',
                    style:
                        TextStyle(fontSize: 13, color: AppColors.textMuted),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _signOut(BuildContext context, WidgetRef ref) async {
    await clearTokens();
    await ref.read(authProvider.notifier).logout();
  }
}

// ── Place card ────────────────────────────────────────────────────────────────

class _PlaceCard extends ConsumerWidget {
  final SavedPlace place;
  const _PlaceCard({required this.place});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return FgCard(
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppColors.blue600.withAlpha(20),
              borderRadius: BorderRadius.circular(10),
            ),
            alignment: Alignment.center,
            child: Text(place.labelEmoji,
                style: const TextStyle(fontSize: 20)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  place.label[0] + place.label.substring(1).toLowerCase(),
                  style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary),
                ),
                if (place.latitude != null)
                  Text(
                    '${place.latitude!.toStringAsFixed(4)}, '
                    '${place.longitude!.toStringAsFixed(4)}',
                    style: const TextStyle(
                        fontSize: 12, color: AppColors.textMuted),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          // Notify toggle
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                place.notify
                    ? Icons.notifications_active_outlined
                    : Icons.notifications_off_outlined,
                size: 16,
                color: place.notify
                    ? AppColors.blue600
                    : AppColors.textMuted,
              ),
              Switch(
                value: place.notify,
                onChanged: (_) =>
                    ref.read(placesProvider.notifier).toggleNotify(place),
                activeColor: AppColors.blue600,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ── Add place button / sheet ──────────────────────────────────────────────────

class _AddPlaceButton extends ConsumerWidget {
  final List<SavedPlace> places;
  const _AddPlaceButton({required this.places});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final usedLabels = places.map((p) => p.label).toSet();
    final available = ['HOME', 'OFFICE', 'OTHER']
        .where((l) => !usedLabels.contains(l))
        .toList();

    return FgCard(
      color: const Color(0xFFF8FAFF),
      onTap: () => _showAddSheet(context, ref, available),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: const [
          Icon(Icons.add_location_alt_outlined,
              color: AppColors.blue600, size: 20),
          SizedBox(width: 8),
          Text('Add saved place',
              style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  color: AppColors.blue600)),
        ],
      ),
    );
  }

  Future<void> _showAddSheet(
      BuildContext context, WidgetRef ref, List<String> available) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => _AddPlaceSheet(
        available: available,
        onAdd: (label, lat, lng) async {
          await ref
              .read(placesProvider.notifier)
              .addPlace(label, lat, lng, true);
        },
      ),
    );
  }
}

class _AddPlaceSheet extends StatefulWidget {
  final List<String> available;
  final Future<void> Function(String label, double lat, double lng) onAdd;

  const _AddPlaceSheet(
      {required this.available, required this.onAdd});

  @override
  State<_AddPlaceSheet> createState() => _AddPlaceSheetState();
}

class _AddPlaceSheetState extends State<_AddPlaceSheet> {
  late String _label;
  bool _locating = false;
  double? _lat;
  double? _lng;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _label = widget.available.first;
    _getLocation();
  }

  Future<void> _getLocation() async {
    setState(() => _locating = true);
    try {
      var perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) {
        perm = await Geolocator.requestPermission();
      }
      if (perm == LocationPermission.denied ||
          perm == LocationPermission.deniedForever) return;
      final pos = await Geolocator.getCurrentPosition(
          locationSettings:
              const LocationSettings(accuracy: LocationAccuracy.high));
      setState(() { _lat = pos.latitude; _lng = pos.longitude; });
    } catch (_) {} finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom + 24,
          left: 24, right: 24, top: 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Add Saved Place',
              style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                  color: AppColors.textPrimary)),
          const SizedBox(height: 16),
          const Text('Label',
              style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textMuted)),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            children: widget.available
                .map((l) => ChoiceChip(
                      label: Text(l[0] + l.substring(1).toLowerCase()),
                      selected: _label == l,
                      onSelected: (_) => setState(() => _label = l),
                      selectedColor: AppColors.blue600.withAlpha(30),
                    ))
                .toList(),
          ),
          const SizedBox(height: 16),
          if (_locating)
            const Row(children: [
              SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2)),
              SizedBox(width: 10),
              Text('Getting your location…',
                  style: TextStyle(
                      fontSize: 13, color: AppColors.textMuted)),
            ])
          else if (_lat != null)
            Row(children: [
              const Icon(Icons.location_on_outlined,
                  size: 16, color: AppColors.blue600),
              const SizedBox(width: 6),
              Text(
                '${_lat!.toStringAsFixed(5)}, ${_lng!.toStringAsFixed(5)}',
                style: const TextStyle(
                    fontSize: 13, color: AppColors.textPrimary),
              ),
              const SizedBox(width: 8),
              GestureDetector(
                onTap: _getLocation,
                child: const Icon(Icons.refresh,
                    size: 16, color: AppColors.blue600),
              ),
            ])
          else
            TextButton.icon(
              onPressed: _getLocation,
              icon: const Icon(Icons.my_location, size: 16),
              label: const Text('Get current location'),
            ),
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: (_lat == null || _saving)
                  ? null
                  : () async {
                      setState(() => _saving = true);
                      await widget.onAdd(_label, _lat!, _lng!);
                      if (mounted) Navigator.of(context).pop();
                    },
              child: _saving
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white))
                  : const Text('Save Place'),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

class _SectionLabel extends StatelessWidget {
  final String text;
  const _SectionLabel(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(
        fontSize: 17,
        fontWeight: FontWeight.w600,
        color: AppColors.textPrimary,
      ),
    );
  }
}
