// Example wiring (copy what you need into your app).
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../screens/meal_draft_screen.dart';
import '../services/health_sync_service.dart';

/// Android emulator reaches the host machine at 10.0.2.2; use your server URL in release builds:
///   flutter run --dart-define=API_BASE_URL=https://api.example.com
const apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000');

/// DEV ONLY: the backend's `current_user_id` stub reads X-User-Id.
/// Replace with `Authorization: Bearer <access token>` when real auth is added.
final api = ApiClient(
  baseUrl: apiBaseUrl,
  headers: () async => {'X-User-Id': '00000000-0000-0000-0000-000000000001'},
);

/// Text and/or photo -> AI draft -> review screen. `photoJpeg` comes from
/// image_picker (resize to ~1280px first; the server also re-compresses).
Future<void> logMeal(BuildContext context, {String text = '', Uint8List? photoJpeg}) async {
  final messenger = ScaffoldMessenger.of(context);
  final nav = Navigator.of(context);
  try {
    final draft = await api.parseMeal(text: text, photoJpeg: photoJpeg);
    await nav.push(MaterialPageRoute<void>(
      builder: (_) => MealDraftScreen(
        draft: draft,
        api: api,
        inputKind: photoJpeg != null ? 'photo' : 'text',
        onSaved: (_) => nav.pop(),
      ),
    ));
  } on ApiException catch (e) {
    messenger.showSnackBar(SnackBar(content: Text(e.userMessage)));
  }
}

/// Sync sleep + steps every time the app comes to the foreground.
/// Register once: `WidgetsBinding.instance.addObserver(HealthSyncOnResume(api))`.
class HealthSyncOnResume with WidgetsBindingObserver {
  HealthSyncOnResume(ApiClient api) : _service = HealthSyncService(source: PluginHealthSource(), api: api);
  final HealthSyncService _service;
  bool _running = false;

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed || _running) return;
    _running = true;
    _service.syncRecent().whenComplete(() => _running = false);
  }
}
