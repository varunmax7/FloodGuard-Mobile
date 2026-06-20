/// Providers for alerts, saved places, and auth state.
library;

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/network/dio_client.dart';
import '../../data/api/floodguard_api.dart';
import '../../data/models/alert_event.dart';
import '../../data/models/saved_place.dart';
import 'api_providers.dart';

// ── Auth state ────────────────────────────────────────────────────────────────

const _kPhoneKey = 'fg_user_phone';
const _kLoggedInKey = 'fg_logged_in';

class AuthState {
  final bool isLoggedIn;
  final String? phone;
  const AuthState({required this.isLoggedIn, this.phone});
}

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier() : super(const AuthState(isLoggedIn: false)) {
    _load();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final loggedIn = prefs.getBool(_kLoggedInKey) ?? false;
    final phone = prefs.getString(_kPhoneKey);
    state = AuthState(isLoggedIn: loggedIn, phone: phone);
  }

  Future<void> login(String phone) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_kLoggedInKey, true);
    await prefs.setString(_kPhoneKey, phone);
    state = AuthState(isLoggedIn: true, phone: phone);
  }

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kLoggedInKey);
    await prefs.remove(_kPhoneKey);
    state = const AuthState(isLoggedIn: false);
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>(
  (_) => AuthNotifier(),
);

// ── Alerts ────────────────────────────────────────────────────────────────────

/// Returns empty list (not an error) when the user is not logged in (401).
final alertsProvider =
    FutureProvider.family<List<AlertEvent>, String>((ref, scope) async {
  // Skip the call if there is no access token stored.
  final token = await getAccessToken();
  if (token == null) return [];

  try {
    final raw = await ref.read(apiProvider).getAlerts(scope: scope);
    return raw
        .whereType<Map<String, dynamic>>()
        .map(AlertEvent.fromJson)
        .toList();
  } on DioException catch (e) {
    if (e.response?.statusCode == 401) return [];
    rethrow;
  }
});

// ── Saved places ──────────────────────────────────────────────────────────────

class PlacesNotifier extends StateNotifier<AsyncValue<List<SavedPlace>>> {
  final FloodGuardApi _api;
  PlacesNotifier(this._api) : super(const AsyncValue.data([])) {
    fetch();
  }

  Future<void> fetch() async {
    // Skip API call if no token — stay empty, not an error.
    final token = await getAccessToken();
    if (token == null) {
      state = const AsyncValue.data([]);
      return;
    }

    state = const AsyncValue.loading();
    try {
      final raw = await _api.getPlaces();
      final places = raw
          .whereType<Map<String, dynamic>>()
          .map(SavedPlace.fromJson)
          .toList();
      state = AsyncValue.data(places);
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        state = const AsyncValue.data([]);
      } else {
        state = AsyncValue.error(e, StackTrace.current);
      }
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  Future<SavedPlace?> addPlace(
      String label, double lat, double lng, bool notify) async {
    try {
      final json = await _api.createPlace(label, lat, lng, notify);
      final place = SavedPlace.fromJson(json);
      final current = state.value ?? [];
      state = AsyncValue.data([...current, place]);
      return place;
    } catch (_) {
      return null;
    }
  }

  Future<void> toggleNotify(SavedPlace place) async {
    final updated = place.copyWith(notify: !place.notify);
    final current = state.value ?? [];
    // Optimistic update
    state = AsyncValue.data(
        current.map((p) => p.id == place.id ? updated : p).toList());
    try {
      await _api.patchPlace(place.id, updated.notify);
    } catch (_) {
      // Revert on failure
      state = AsyncValue.data(
          current.map((p) => p.id == place.id ? place : p).toList());
    }
  }
}

final placesProvider =
    StateNotifierProvider<PlacesNotifier, AsyncValue<List<SavedPlace>>>(
  (ref) => PlacesNotifier(ref.read(apiProvider)),
);
