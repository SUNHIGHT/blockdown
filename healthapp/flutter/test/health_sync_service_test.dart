import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:health_app/api/api_client.dart';
import 'package:health_app/services/health_sync_service.dart';
import 'package:health_app/services/sleep_summarizer.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class FakeSource implements HealthSource {
  FakeSource({this.allowed = true, this.sleep = const [], this.stepsByDay = const {}});
  final bool allowed;
  final List<SleepInterval> sleep;
  final Map<String, int> stepsByDay;
  final windows = <List<DateTime>>[];

  @override
  String get sourceName => 'healthkit';
  @override
  Future<bool> authorize() async => allowed;
  @override
  Future<List<SleepInterval>> sleepIntervals(DateTime from, DateTime to) async {
    windows.add([from, to]);
    return sleep.where((i) => i.start.isBefore(to) && i.end.isAfter(from)).toList();
  }

  @override
  Future<int?> steps(DateTime from, DateTime to) async =>
      stepsByDay['${from.year}-${from.month}-${from.day}'];
}

SleepInterval _i(String a, String b, SleepKind k) => SleepInterval(DateTime.parse(a), DateTime.parse(b), k);

void main() {
  late List<http.Request> seen;
  late ApiClient api;
  setUp(() {
    seen = [];
    api = ApiClient(
      baseUrl: 'http://x',
      headers: () async => {'X-User-Id': 'u'},
      client: MockClient((r) async {
        seen.add(r);
        return http.Response('', 204);
      }),
    );
  });

  final now = DateTime(2026, 10, 17, 9, 0); // morning of the 17th

  test('uploads last night (dated by wake-up day) and steps for yesterday + today', () async {
    final src = FakeSource(
      sleep: [
        _i('2026-10-16 23:40', '2026-10-17 07:05', SleepKind.inBed),
        _i('2026-10-16 23:55', '2026-10-17 07:00', SleepKind.asleep),
        // the night before: must be reported on the 16th, not the 17th
        _i('2026-10-15 23:10', '2026-10-16 06:50', SleepKind.asleep),
      ],
      stepsByDay: {'2026-10-16': 7421, '2026-10-17': 1234},
    );
    final r = await HealthSyncService(source: src, api: api, clock: () => now).syncRecent();
    expect(r.ok, isTrue);
    expect(r.sleepNights, 2);
    expect(r.stepDays, 2);

    final sleepPosts = seen.where((q) => q.url.path == '/sleep_logs').map((q) => jsonDecode(q.body) as Map).toList();
    expect(sleepPosts.map((m) => m['local_date']), ['2026-10-16', '2026-10-17']);
    final last = sleepPosts.last;
    expect(last['asleep_min'], 425); // 23:55 -> 07:00
    expect(last['source'], 'healthkit');
    expect(DateTime.parse(last['bed_at'] as String).isUtc, isTrue);      // sent with a timezone (Z)
    expect(DateTime.parse(last['bed_at'] as String).toLocal(), DateTime.parse('2026-10-16 23:40'));

    final act = seen.where((q) => q.url.path == '/activity/daily').map((q) => jsonDecode(q.body) as Map).toList();
    expect(act.map((m) => [m['local_date'], m['steps']]), [
      ['2026-10-16', 7421],
      ['2026-10-17', 1234],
    ]);
  });

  test('permission denied -> nothing is sent', () async {
    final r = await HealthSyncService(source: FakeSource(allowed: false), api: api, clock: () => now).syncRecent();
    expect(r.permissionDenied, isTrue);
    expect(seen, isEmpty);
  });

  test('no sleep recorded and zero steps -> nothing is sent for that day', () async {
    final r = await HealthSyncService(source: FakeSource(stepsByDay: {'2026-10-16': 0}), api: api, clock: () => now)
        .syncRecent();
    expect(r.ok, isTrue);
    expect(seen, isEmpty);
  });

  test('sleep window never reaches into the future', () async {
    final src = FakeSource();
    await HealthSyncService(source: src, api: api, clock: () => now).readSleepFor(DateTime(2026, 10, 17));
    expect(src.windows.single[0], DateTime(2026, 10, 16, 18));
    expect(src.windows.single[1], now);
  });

  test('a server error on one day is reported and the other day still syncs', () async {
    var n = 0;
    final flaky = ApiClient(
      baseUrl: 'http://x',
      headers: () async => {},
      client: MockClient((r) async {
        n++;
        return n == 1 ? http.Response('boom', 500) : http.Response('', 204);
      }),
    );
    final src = FakeSource(stepsByDay: {'2026-10-16': 5000, '2026-10-17': 800});
    final r = await HealthSyncService(source: src, api: flaky, clock: () => now).syncRecent();
    expect(r.errors, hasLength(1));
    expect(r.stepDays, 1);
  });
}
