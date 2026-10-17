import 'package:flutter_test/flutter_test.dart';
import 'package:health_app/services/sleep_summarizer.dart';

SleepInterval _i(String from, String to, SleepKind k) =>
    SleepInterval(DateTime.parse(from), DateTime.parse(to), k);

void main() {
  test('iOS style: in-bed + asleep stages -> bed/wake from in-bed, minutes from stages', () {
    final s = summarizeSleep([
      _i('2026-10-16 23:30', '2026-10-17 07:10', SleepKind.inBed),
      _i('2026-10-16 23:45', '2026-10-17 02:00', SleepKind.asleep),
      _i('2026-10-17 02:10', '2026-10-17 06:55', SleepKind.asleep), // 10 min awake in between
    ])!;
    expect(s.bedAt, DateTime.parse('2026-10-16 23:30'));
    expect(s.wakeAt, DateTime.parse('2026-10-17 07:10'));
    expect(s.asleepMinutes, 135 + 285); // 2h15 + 4h45
    expect(s.inBedMinutes, 460);
    expect(s.localDate, DateTime(2026, 10, 17));
  });

  test('Android style: session + stages from two apps overlap -> counted once', () {
    final s = summarizeSleep([
      _i('2026-10-16 23:40', '2026-10-17 07:05', SleepKind.session),
      _i('2026-10-16 23:50', '2026-10-17 03:00', SleepKind.asleep), // app A
      _i('2026-10-16 23:50', '2026-10-17 03:00', SleepKind.asleep), // app B duplicate
      _i('2026-10-17 01:00', '2026-10-17 05:00', SleepKind.asleep), // overlaps both
      _i('2026-10-17 05:10', '2026-10-17 07:00', SleepKind.asleep),
    ])!;
    expect(s.bedAt, DateTime.parse('2026-10-16 23:40'));
    expect(s.wakeAt, DateTime.parse('2026-10-17 07:05'));
    // union: 23:50-05:00 (310) + 05:10-07:00 (110)
    expect(s.asleepMinutes, 420);
  });

  test('session only (no stage data): session length is the sleep time', () {
    final s = summarizeSleep([_i('2026-10-17 00:10', '2026-10-17 06:40', SleepKind.session)])!;
    expect(s.asleepMinutes, 390);
    expect(s.bedAt, DateTime.parse('2026-10-17 00:10'));
  });

  test('a short wake-up (< 90 min) does not split the night; an afternoon nap is not chosen', () {
    final s = summarizeSleep([
      _i('2026-10-17 00:00', '2026-10-17 03:00', SleepKind.asleep),
      _i('2026-10-17 03:40', '2026-10-17 07:00', SleepKind.asleep),
      _i('2026-10-17 14:00', '2026-10-17 14:30', SleepKind.asleep), // nap
    ])!;
    expect(s.bedAt, DateTime.parse('2026-10-17 00:00'));
    expect(s.wakeAt, DateTime.parse('2026-10-17 07:00'));
    expect(s.asleepMinutes, 180 + 200);
  });

  test('empty or invalid input -> null', () {
    expect(summarizeSleep([]), isNull);
    expect(summarizeSleep([_i('2026-10-17 07:00', '2026-10-17 07:00', SleepKind.asleep)]), isNull);
  });
}
