/// Phone OTP login screen.
/// Web  → signInWithPhoneNumber + RecaptchaVerifier (invisible).
/// Native → verifyPhoneNumber (Android auto-verify supported).
library;

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:dio/dio.dart';
import '../../core/network/dio_client.dart';
import '../../core/providers/alerts_providers.dart';
import '../../core/providers/api_providers.dart';
import '../../design/theme/app_theme.dart';
import '../../design/widgets/fg_app_header.dart';
import '../../../main.dart' show firebaseReady;

class AuthScreen extends ConsumerStatefulWidget {
  const AuthScreen({super.key});

  @override
  ConsumerState<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends ConsumerState<AuthScreen> {
  int _step = 0;
  final _phoneCtrl = TextEditingController();
  final _otpCtrl   = TextEditingController();

  // Web flow
  ConfirmationResult? _confirmationResult;

  // Native flow
  String? _verificationId;

  bool    _loading = false;
  String? _error;

  @override
  void dispose() {
    _phoneCtrl.dispose();
    _otpCtrl.dispose();
    super.dispose();
  }

  // ── Step 0: send OTP ─────────────────────────────────────────────────────

  Future<void> _sendOtp() async {
    final phone = _phoneCtrl.text.trim();
    if (phone.isEmpty) return;

    if (!firebaseReady) {
      await _devLogin();
      return;
    }

    setState(() { _loading = true; _error = null; });

    try {
      if (kIsWeb) {
        await _sendOtpWeb(phone);
      } else {
        await _sendOtpNative(phone);
      }
    } catch (e) {
      if (mounted) setState(() { _loading = false; _error = _friendly(e); });
    }
  }

  Future<void> _sendOtpWeb(String phone) async {
    // signInWithPhoneNumber on web auto-creates an invisible reCAPTCHA.
    final result = await FirebaseAuth.instance.signInWithPhoneNumber(phone);

    if (mounted) {
      setState(() {
        _confirmationResult = result;
        _step = 1;
        _loading = false;
      });
    }
  }

  Future<void> _sendOtpNative(String phone) async {
    await FirebaseAuth.instance.verifyPhoneNumber(
      phoneNumber: phone,
      timeout: const Duration(seconds: 60),
      verificationCompleted: (PhoneAuthCredential cred) async {
        await _signInWithCredential(cred);
      },
      verificationFailed: (FirebaseAuthException e) {
        if (mounted) setState(() { _loading = false; _error = _friendly(e); });
      },
      codeSent: (String verificationId, int? _) {
        if (mounted) {
          setState(() {
            _verificationId = verificationId;
            _step = 1;
            _loading = false;
          });
        }
      },
      codeAutoRetrievalTimeout: (_) {},
    );
  }

  // ── Step 1: verify OTP ────────────────────────────────────────────────────

  Future<void> _verifyOtp() async {
    if (!firebaseReady) { await _devLogin(); return; }
    final code = _otpCtrl.text.trim();
    if (code.length != 6) return;
    setState(() { _loading = true; _error = null; });

    try {
      if (kIsWeb && _confirmationResult != null) {
        final cred = await _confirmationResult!.confirm(code);
        await _exchangeToken(cred);
      } else if (_verificationId != null) {
        final credential = PhoneAuthProvider.credential(
          verificationId: _verificationId!,
          smsCode: code,
        );
        await _signInWithCredential(credential);
      }
    } on FirebaseAuthException catch (e) {
      if (mounted) setState(() { _loading = false; _error = _friendly(e); });
    } catch (e) {
      if (mounted) setState(() { _loading = false; _error = _friendly(e); });
    }
  }

  Future<void> _signInWithCredential(PhoneAuthCredential credential) async {
    final cred = await FirebaseAuth.instance.signInWithCredential(credential);
    await _exchangeToken(cred);
  }

  /// Exchange Firebase ID token for backend JWT and persist auth state.
  /// Falls back to phone-number exchange when backend is in dev mode (no
  /// Firebase Admin SDK configured — verify_firebase_token rejects the JWT).
  Future<void> _exchangeToken(UserCredential cred) async {
    final phone   = cred.user?.phoneNumber ?? _phoneCtrl.text.trim();
    final idToken = await cred.user?.getIdToken() ?? phone;

    final api = ref.read(apiProvider);
    Map<String, dynamic> result;

    try {
      // Production path: backend verifies the real Firebase ID token.
      result = await api.verifyOtp(idToken);
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        // Dev-mode backend: no Firebase Admin SDK configured — it expects the
        // raw E.164 phone number as id_token.
        result = await api.verifyOtp(phone);
      } else {
        rethrow;
      }
    }

    final access  = result['access']  as String? ?? '';
    final refresh = result['refresh'] as String? ?? '';

    if (access.isNotEmpty) {
      await saveTokens(access: access, refresh: refresh);
      await ref.read(authProvider.notifier).login(phone);
      ref.read(placesProvider.notifier).fetch();
    }

    if (mounted) context.pop();
  }

  // ── Dev-mode shortcut ─────────────────────────────────────────────────────

  Future<void> _devLogin() async {
    final phone = _phoneCtrl.text.trim();
    if (!phone.startsWith('+')) {
      setState(() => _error = 'Enter E.164 format, e.g. +917207157982');
      return;
    }
    setState(() { _loading = true; _error = null; });
    try {
      final result  = await ref.read(apiProvider).verifyOtp(phone);
      final access  = result['access']  as String? ?? '';
      final refresh = result['refresh'] as String? ?? '';
      if (access.isNotEmpty) {
        await saveTokens(access: access, refresh: refresh);
        await ref.read(authProvider.notifier).login(phone);
        ref.read(placesProvider.notifier).fetch();
      }
      if (mounted) context.pop();
    } catch (e) {
      if (mounted) setState(() { _loading = false; _error = _friendly(e); });
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  String _friendly(Object e) {
    if (e is FirebaseAuthException) {
      return switch (e.code) {
        'invalid-phone-number'   => 'Invalid phone number format.',
        'too-many-requests'      => 'Too many attempts. Try again later.',
        'invalid-verification-code' => 'Wrong OTP. Check and try again.',
        'quota-exceeded'         => 'SMS quota exceeded. Use Dev login.',
        'captcha-check-failed'   => 'reCAPTCHA failed. Refresh and retry.',
        _                        => e.message ?? 'Authentication failed.',
      };
    }
    return e.toString();
  }

  // ── Build ─────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const FgAppHeader(),
      backgroundColor: const Color(0xFFF1F5F9),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 24),
              const Text('Sign in',
                  style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textPrimary)),
              const SizedBox(height: 8),
              Text(
                _step == 0
                    ? 'Enter your phone number to receive an OTP.'
                    : 'Enter the 6-digit code sent to ${_phoneCtrl.text}.',
                style: const TextStyle(fontSize: 15, color: AppColors.textMuted),
              ),
              const SizedBox(height: 32),

              if (_step == 0) ...[
                TextField(
                  controller: _phoneCtrl,
                  keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(
                    labelText: 'Phone number',
                    hintText: '+91 9999 999 999',
                    prefixIcon: Icon(Icons.phone_outlined),
                  ),
                  onSubmitted: (_) => _sendOtp(),
                ),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: _loading ? null : _sendOtp,
                    child: _loading
                        ? const SizedBox(
                            width: 20, height: 20,
                            child: CircularProgressIndicator(
                                strokeWidth: 2, color: Colors.white))
                        : Text(firebaseReady ? 'Send OTP' : 'Sign in (dev mode)'),
                  ),
                ),
                if (firebaseReady) ...[
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton(
                      onPressed: _loading ? null : _devLogin,
                      child: const Text('Dev login (skip Firebase)'),
                    ),
                  ),
                ],
              ] else ...[
                TextField(
                  controller: _otpCtrl,
                  keyboardType: TextInputType.number,
                  maxLength: 6,
                  autofocus: true,
                  decoration: const InputDecoration(
                    labelText: '6-digit OTP',
                    hintText: '123456',
                    prefixIcon: Icon(Icons.lock_outlined),
                  ),
                  onSubmitted: (_) => _verifyOtp(),
                ),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: _loading ? null : _verifyOtp,
                    child: _loading
                        ? const SizedBox(
                            width: 20, height: 20,
                            child: CircularProgressIndicator(
                                strokeWidth: 2, color: Colors.white))
                        : const Text('Verify OTP'),
                  ),
                ),
                const SizedBox(height: 12),
                TextButton(
                  onPressed: _loading
                      ? null
                      : () => setState(() {
                            _step = 0;
                            _otpCtrl.clear();
                            _confirmationResult = null;
                            _verificationId = null;
                          }),
                  child: const Text('← Back / Resend'),
                ),
              ],

              if (_error != null) ...[
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.severeBg,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.error_outline,
                          color: AppColors.riskSevere, size: 16),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(_error!,
                            style: const TextStyle(
                                fontSize: 13, color: AppColors.riskSevere)),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
