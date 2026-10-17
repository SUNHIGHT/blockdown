import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../models/draft.dart';

class ApiException implements Exception {
  ApiException(this.statusCode, this.body);
  final int statusCode;
  final String body;

  /// Short text suitable for a SnackBar.
  String get userMessage => switch (statusCode) {
        413 => '写真が大きすぎます。撮り直してください。',
        422 => '入力内容を確認してください。',
        429 => '混み合っています。少し待ってからやり直してください。',
        >= 500 => 'サーバーで問題が起きました。時間をおいて再度お試しください。',
        _ => '送信に失敗しました（$statusCode）。',
      };

  @override
  String toString() => 'ApiException($statusCode): $body';
}

/// Thin client for the FastAPI backend.
///
/// [headers] is called per request. In development the backend accepts
/// `X-User-Id`; swap it for `Authorization: Bearer <jwt>` once real auth exists.
class ApiClient {
  ApiClient({
    required this.baseUrl,
    required this.headers,
    http.Client? client,
  }) : _http = client ?? http.Client();

  final String baseUrl;
  final Future<Map<String, String>> Function() headers;
  final http.Client _http;

  Uri _u(String path) => Uri.parse('$baseUrl$path');

  Future<http.Response> _check(http.Response r) async {
    if (r.statusCode >= 200 && r.statusCode < 300) return r;
    throw ApiException(r.statusCode, utf8.decode(r.bodyBytes));
  }

  /// `POST /meals/parse` (multipart). Send text, a photo, or both.
  Future<ParseResponse> parseMeal({
    String text = '',
    Uint8List? photoJpeg,
    int? hour,
  }) async {
    final req = http.MultipartRequest('POST', _u('/meals/parse'))
      ..headers.addAll(await headers())
      ..fields['text'] = text
      ..fields['hour'] = '${hour ?? DateTime.now().hour}';
    if (photoJpeg != null) {
      req.files.add(http.MultipartFile.fromBytes('photo', photoJpeg, filename: 'meal.jpg'));
    }
    final res = await _check(await http.Response.fromStream(await _http.send(req)));
    return ParseResponse.fromJson(jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>);
  }

  Future<Map<String, String>> _jsonHeaders() async => {
        ...await headers(),
        'content-type': 'application/json; charset=utf-8',
      };

  Future<T> _post<T>(String path, Map<String, dynamic> body, T Function(http.Response) map) async {
    final r = await _http.post(_u(path), headers: await _jsonHeaders(), body: jsonEncode(body));
    return map(await _check(r));
  }

  /// `POST /meals`. Returns the new meal id.
  Future<String> confirmMeal(Map<String, dynamic> body) => _post(
        '/meals',
        body,
        (r) => (jsonDecode(utf8.decode(r.bodyBytes)) as Map<String, dynamic>)['meal_id'] as String,
      );

  /// `POST /sleep_logs` (upsert by wake-up date).
  Future<void> postSleep({
    required DateTime localDate,
    required DateTime bedAt,
    required DateTime wakeAt,
    String source = 'healthkit',
    int? quality,
    int? asleepMinutes,
  }) =>
      _post(
        '/sleep_logs',
        {
          'local_date': _date(localDate),
          'bed_at': bedAt.toUtc().toIso8601String(),
          'wake_at': wakeAt.toUtc().toIso8601String(),
          'source': source,
          'quality': ?quality,
          'asleep_min': ?asleepMinutes,
        },
        (_) {},
      );

  /// `POST /activity/daily` (upsert by date).
  Future<void> postDailyActivity({
    required DateTime localDate,
    required int steps,
    String source = 'healthkit',
  }) =>
      _post('/activity/daily', {'local_date': _date(localDate), 'steps': steps, 'source': source}, (_) {});

  static String _date(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
}
