import 'dart:io' show Platform;

import 'package:health/health.dart';
import 'package:permission_handler/permission_handler.dart';

import '../api/api_client.dart';
import 'sleep_summarizer.dart';

/// What the sync logic needs from the OS health store. The real implementation
/// is [PluginHealthSource]; tests use a fake.
abstract class HealthSource {
  /// Asks for read access (steps + sleep). false = unavailable or denied.
  Future<bool> authorize();
  Future<List<SleepInterval>> sleepIntervals(DateTime from, DateTime to);
  Future<int?> steps(DateTime from, DateTime to);

  /// 'healthkit' on iOS, 'healthconnect' on Android (matches the backend enum).
  String get sourceName;
}

/// HealthKit (iOS) / Health Connect (Android) via the `health` package.
class PluginHealthSource implements HealthSource {
  PluginHealthSource({Health? health}) : _health = health ?? Health();
  final Health _health;
  bool _configured = false;

  // Candidate sleep types; each platform only supports some of them, so the list
  // is filtered with Health.isDataTypeAvailable.
  static const _sleepCandidates = [
    HealthDataType.SLEEP_SESSION, // Android
    HealthDataType.SLEEP_ASLEEP,
    HealthDataType.SLEEP_LIGHT,
    HealthDataType.SLEEP_DEEP,
    HealthDataType.SLEEP_REM,
    HealthDataType.SLEEP_IN_BED, // iOS
  ];

  List<HealthDataType> get _sleepTypes => _sleepCandidates.where(_health.isDataTypeAvailable).toList();

  @override
  String get sourceName => Platform.isIOS ? 'healthkit' : 'healthconnect';

  Future<void> _ensureConfigured() async {
    if (_configured) return;
    await _health.configure();
    _configured = true;
  }

  @override
  Future<bool> authorize() async {
    await _ensureConfigured();
    if (Platform.isAndroid) {
      // Steps need the runtime ACTIVITY_RECOGNITION permission.
      await Permission.activityRecognition.request();
      if (!await _health.isHealthConnectAvailable()) {
        await _health.installHealthConnect(); // opens the Play Store page
        return false;
      }
    }
    final types = [HealthDataType.STEPS, ..._sleepTypes];
    return _health.requestAuthorization(
      types,
      permissions: List.filled(types.length, HealthDataAccess.READ),
    );
  }

  @override
  Future<List<SleepInterval>> sleepIntervals(DateTime from, DateTime to) async {
    await _ensureConfigured();
    final points = await _health.getHealthDataFromTypes(
      types: _sleepTypes,
      startTime: from,
      endTime: to,
    );
    final out = <SleepInterval>[];
    for (final p in points) {
      final kind = switch (p.type) {
        HealthDataType.SLEEP_ASLEEP ||
        HealthDataType.SLEEP_LIGHT ||
        HealthDataType.SLEEP_DEEP ||
        HealthDataType.SLEEP_REM =>
          SleepKind.asleep,
        HealthDataType.SLEEP_SESSION => SleepKind.session,
        HealthDataType.SLEEP_IN_BED => SleepKind.inBed,
        _ => null,
      };
      if (kind != null) out.add(SleepInterval(p.dateFrom, p.dateTo, kind));
    }
    return out;
  }

  @override
  Future<int?> steps(DateTime from, DateTime to) async {
    await _ensureConfigured();
    return _health.getTotalStepsInInterval(from, to);
  }
}

class SyncReport {
  SyncReport({this.sleepNights = 0, this.stepDays = 0, this.permissionDenied = false, this.errors = const []});
  final int sleepNights, stepDays;
  final bool permissionDenied;
  final List<String> errors;
  bool get ok => !permissionDenied && errors.isEmpty;
}

/// Reads sleep and steps from the OS health store and uploads them.
/// Safe to call repeatedly: the server upserts by date.
class HealthSyncService {
  HealthSyncService({required this.source, required this.api, DateTime Function()? clock})
      : _now = clock ?? DateTime.now;

  final HealthSource source;
  final ApiClient api;
  final DateTime Function() _now;

  /// Main sleep ending on [day] (local): looks from 18:00 the evening before
  /// until 18:00 on [day] (or now, if that is earlier). Null if none recorded.
  Future<SleepSummary?> readSleepFor(DateTime day) async {
    final d = DateTime(day.year, day.month, day.day);
    final from = d.subtract(const Duration(hours: 6)); // 18:00 the day before
    var to = d.add(const Duration(hours: 18));
    final now = _now();
    if (to.isAfter(now)) to = now;
    if (!to.isAfter(from)) return null;
    final s = summarizeSleep(await source.sleepIntervals(from, to));
    // Keep only a night that really ended on [day] (not yesterday's late nap).
    if (s == null || s.localDate != d) return null;
    return s;
  }

  /// Steps for the whole local [day] (today: up to now).
  Future<int?> readStepsFor(DateTime day) async {
    final d = DateTime(day.year, day.month, day.day);
    var to = d.add(const Duration(days: 1));
    final now = _now();
    if (to.isAfter(now)) to = now;
    if (!to.isAfter(d)) return null;
    return source.steps(d, to);
  }

  /// Uploads yesterday and today (default [days] = 2).
  Future<SyncReport> syncRecent({int days = 2}) async {
    if (!await source.authorize()) return SyncReport(permissionDenied: true);
    final errors = <String>[];
    var nights = 0, stepDays = 0;
    final today = DateTime(_now().year, _now().month, _now().day);
    for (var i = days - 1; i >= 0; i--) {
      final day = today.subtract(Duration(days: i));
      try {
        final sleep = await readSleepFor(day);
        if (sleep != null) {
          await api.postSleep(
            localDate: sleep.localDate,
            bedAt: sleep.bedAt,
            wakeAt: sleep.wakeAt,
            asleepMinutes: sleep.asleepMinutes,
            source: source.sourceName,
          );
          nights++;
        }
        final steps = await readStepsFor(day);
        if (steps != null && steps > 0) {
          await api.postDailyActivity(localDate: day, steps: steps, source: source.sourceName);
          stepDays++;
        }
      } on ApiException catch (e) {
        errors.add('${day.month}/${day.day}: ${e.userMessage}');
      } catch (e) {
        errors.add('${day.month}/${day.day}: $e');
      }
    }
    return SyncReport(sleepNights: nights, stepDays: stepDays, errors: errors);
  }
}
