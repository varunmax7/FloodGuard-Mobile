/// Phone-number + password login screen.
/// One screen, two modes: Sign In (existing user) or Create Account.
library;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/network/dio_client.dart';
import '../../core/providers/alerts_providers.dart';
import '../../core/providers/api_providers.dart';
import '../../design/theme/app_theme.dart';
import '../../design/widgets/fg_app_header.dart';

class AuthScreen extends ConsumerStatefulWidget {
  const AuthScreen({super.key});

  @override
  ConsumerState<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends ConsumerState<AuthScreen> {
  final _phoneCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  bool _isRegistering = false;
  bool _obscurePassword = true;
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _phoneCtrl.dispose();
    _passwordCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final phone = _phoneCtrl.text.trim();
    final password = _passwordCtrl.text;
    if (phone.isEmpty || password.isEmpty) {
      setState(() => _error = 'Enter phone number and password.');
      return;
    }
    if (_isRegistering && password.length < 6) {
      setState(() => _error = 'Password must be at least 6 characters.');
      return;
    }

    setState(() { _loading = true; _error = null; });
    try {
      final api = ref.read(apiProvider);
      final result = _isRegistering
          ? await api.register(phone, password)
          : await api.login(phone, password);

      final access = result['access'] as String? ?? '';
      final refresh = result['refresh'] as String? ?? '';
      if (access.isNotEmpty) {
        await saveTokens(access: access, refresh: refresh);
        await ref.read(authProvider.notifier).login(phone);
        ref.read(placesProvider.notifier).fetch();
      }
      if (mounted) context.pop();
    } on DioException catch (e) {
      final code = e.response?.statusCode;
      final detail = (e.response?.data is Map)
          ? (e.response!.data as Map)['detail']?.toString()
          : null;
      if (mounted) {
        setState(() {
          _loading = false;
          _error = detail ??
              (code == 401
                  ? 'Invalid phone number or password.'
                  : code == 409
                      ? 'That phone number is already registered. Sign in instead.'
                      : 'Something went wrong. Try again.');
        });
      }
    } catch (e) {
      if (mounted) setState(() { _loading = false; _error = e.toString(); });
    }
  }

  @override
  Widget build(BuildContext context) {
    final actionLabel = _isRegistering ? 'Create account' : 'Sign in';
    final toggleLabel = _isRegistering
        ? 'Already have an account? Sign in'
        : "Don't have an account? Create one";

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
              Text(actionLabel,
                  style: const TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w700,
                      color: AppColors.textPrimary)),
              const SizedBox(height: 8),
              const Text(
                'Use your phone number to sign in. Indian numbers can be entered as 10 digits (we add +91).',
                style: TextStyle(fontSize: 14, color: AppColors.textMuted),
              ),
              const SizedBox(height: 32),
              TextField(
                controller: _phoneCtrl,
                keyboardType: TextInputType.phone,
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(
                  labelText: 'Phone number',
                  hintText: '8798767578  or  +919876543210',
                  prefixIcon: Icon(Icons.phone_outlined),
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _passwordCtrl,
                obscureText: _obscurePassword,
                textInputAction: TextInputAction.done,
                onSubmitted: (_) => _submit(),
                decoration: InputDecoration(
                  labelText: 'Password',
                  hintText: _isRegistering ? 'At least 6 characters' : 'Enter your password',
                  prefixIcon: const Icon(Icons.lock_outline),
                  suffixIcon: IconButton(
                    icon: Icon(_obscurePassword
                        ? Icons.visibility_outlined
                        : Icons.visibility_off_outlined),
                    onPressed: () =>
                        setState(() => _obscurePassword = !_obscurePassword),
                  ),
                ),
              ),
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _loading ? null : _submit,
                  child: _loading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: Colors.white))
                      : Text(actionLabel),
                ),
              ),
              const SizedBox(height: 12),
              Center(
                child: TextButton(
                  onPressed: _loading
                      ? null
                      : () => setState(() {
                            _isRegistering = !_isRegistering;
                            _error = null;
                          }),
                  child: Text(toggleLabel),
                ),
              ),
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
