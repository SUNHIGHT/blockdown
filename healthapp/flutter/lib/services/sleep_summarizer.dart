/// Pure-Dart sleep aggregation (no plugin imports, unit-testable).
///
/// HealthKit and Health Connect describe the same night differently:
///  * iOS: `inBed` + `asleep` (or light/deep/REM stage) samples
///  * Android: one `session` plus optional stage samples, often from several
///    apps at once (so samples overlap)
/// We merge everything into ONE main night: bedtime, wake time and the number
/// of minutes actually asleep (overlaps counted once).
library;

enum SleepKind {
  /// asleep, light, deep, REM: time actually asleep
  asleep,

  /// Health Connect SLEEP_SESSION: includes short awake periods
  session,

  /// HealthKit IN_BED
  inBed,
}

class SleepInterval {
  SleepInterval(this.start, this.end, this.kind);
  final DateTime start, end;
  final SleepKind kind;
  bool get valid => end.isAfter(start);
}

class SleepSummary {
  const SleepSummary({required this.bedAt, required this.wakeAt, required this.asleepMinutes});
  final DateTime bedAt, wakeAt;

  /// Minutes actually asleep (union of sleep samples; session length when no
  /// finer data exists).
  final int asleepMinutes;

  int get inBedMinutes => wakeAt.difference(bedAt).inMinutes;

  /// The day you woke up, in the device's local time.
  DateTime get localDate {
    final w = wakeAt.toLocal();
    return DateTime(w.year, w.month, w.day);
  }
}

int _unionMinutes(List<SleepInterval> xs) {
  if (xs.isEmpty) return 0;
  final s = [...xs]..sort((a, b) => a.start.compareTo(b.start));
  var total = Duration.zero;
  var curStart = s.first.start, curEnd = s.first.end;
  for (final x in s.skip(1)) {
    if (x.start.isAfter(curEnd)) {
      total += curEnd.difference(curStart);
      curStart = x.start;
      curEnd = x.end;
    } else if (x.end.isAfter(curEnd)) {
      curEnd = x.end;
    }
  }
  total += curEnd.difference(curStart);
  return total.inMinutes;
}

/// Picks the main sleep block (largest cluster; blocks closer than [gap] are one
/// night, so a 20-minute wake-up does not split it) and summarises it.
SleepSummary? summarizeSleep(
  Iterable<SleepInterval> intervals, {
  Duration gap = const Duration(minutes: 90),
}) {
  final all = intervals.where((i) => i.valid).toList();
  if (all.isEmpty) return null;

  List<SleepInterval> ofKind(SleepKind k) => all.where((i) => i.kind == k).toList();
  // Prefer true sleep samples; fall back to the session, then in-bed time.
  var core = ofKind(SleepKind.asleep);
  if (core.isEmpty) core = ofKind(SleepKind.session);
  if (core.isEmpty) core = ofKind(SleepKind.inBed);
  if (core.isEmpty) return null;

  core.sort((a, b) => a.start.compareTo(b.start));
  final clusters = <List<SleepInterval>>[];
  var clusterEnd = core.first.end;
  var cur = <SleepInterval>[core.first];
  for (final x in core.skip(1)) {
    if (x.start.difference(clusterEnd) > gap) {
      clusters.add(cur);
      cur = [x];
      clusterEnd = x.end;
    } else {
      cur.add(x);
      if (x.end.isAfter(clusterEnd)) clusterEnd = x.end;
    }
  }
  clusters.add(cur);

  SleepSummary? best;
  var bestMin = -1;
  for (final c in clusters) {
    final minutes = _unionMinutes(c);
    final start = c.map((e) => e.start).reduce((a, b) => a.isBefore(b) ? a : b);
    final end = c.map((e) => e.end).reduce((a, b) => a.isAfter(b) ? a : b);
    // Session / in-bed samples that overlap this block define the true bed/wake times.
    var bed = start, wake = end;
    for (final x in all) {
      if (x.kind == SleepKind.asleep) continue;
      if (x.start.isBefore(end) && x.end.isAfter(start)) {
        if (x.start.isBefore(bed)) bed = x.start;
        if (x.end.isAfter(wake)) wake = x.end;
      }
    }
    if (minutes > bestMin || (minutes == bestMin && best != null && wake.isAfter(best.wakeAt))) {
      bestMin = minutes;
      best = SleepSummary(bedAt: bed, wakeAt: wake, asleepMinutes: minutes);
    }
  }
  return best;
}
