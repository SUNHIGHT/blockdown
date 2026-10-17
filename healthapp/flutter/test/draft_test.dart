import 'package:flutter_test/flutter_test.dart';
import 'package:health_app/models/draft.dart';

DraftItem _item({String name = '牛丼 並盛', double kcal = 650, double conf = 0.8, List<String> flags = const []}) =>
    DraftItem(
      name: name, kcal: kcal, proteinG: 20, fatG: 22, carbsG: 90, kcalMin: 600, kcalMax: 700,
      confidence: conf, source: 'llm', flags: flags,
    );

void main() {
  test('size presets rescale kcal, macros and range', () {
    final l = DraftLine(_item());
    l.preset = SizePreset.large;
    expect(l.kcal, closeTo(845, 1e-9));
    expect(l.proteinG, closeTo(26, 1e-9));
    expect(l.kcalMin, closeTo(780, 1e-9));
    expect(l.kcalMax, closeTo(910, 1e-9));
    expect(l.amountRatio, closeTo(1.3, 1e-9));
    expect(SizePreset.extra.chipLabel, '特盛 ×1.6');
  });

  test('totals add up the current presets', () {
    final a = DraftLine(_item());
    final b = DraftLine(_item(name: '味噌汁', kcal: 50));
    b.preset = SizePreset.small;
    final t = MealTotals.of([a, b]);
    expect(t.kcal, closeTo(650 + 35, 1e-9));
    expect(t.proteinG, closeTo(20 + 14, 1e-9));
  });

  test('low confidence: below 0.6 or kcal_mismatch flag', () {
    expect(DraftLine(_item(conf: 0.59)).lowConfidence, isTrue);
    expect(DraftLine(_item(conf: 0.9, flags: ['kcal_mismatch'])).lowConfidence, isTrue);
    expect(DraftLine(_item(conf: 0.6)).lowConfidence, isFalse);
  });

  test('confirm json carries scaled numbers, ratio and user_corrected', () {
    final l = DraftLine(_item(), saveToMyFoods: true)..preset = SizePreset.small;
    final j = l.toConfirmJson();
    expect(j['amount_ratio'], closeTo(0.7, 1e-9));
    expect(j['kcal'], closeTo(455, 1e-9));
    expect(j['user_corrected'], isTrue);
    expect(j['save_to_my_foods'], isTrue);
    expect(DraftLine(_item()).toConfirmJson()['user_corrected'], isFalse);
  });

  test('ParseResponse.fromJson reads the backend payload', () {
    final r = ParseResponse.fromJson({
      'items': [
        {
          'name': '中華そば', 'chain': '日高屋', 'amount_note': '', 'amount_ratio': 1.0, 'kcal': 636,
          'protein_g': 22.2, 'fat_g': 20.5, 'carbs_g': 89, 'kcal_min': 636, 'kcal_max': 636,
          'confidence': 0.85, 'source': 'official', 'macro_estimated': true, 'food_id': 7,
          'alternatives': [], 'flags': []
        }
      ],
      'slot': '昼', 'question': null, 'refused': false,
      'usage': {'model': 'claude-haiku-5-5', 'input_tokens': 10, 'output_tokens': 5, 'request_id': 'r'},
    });
    expect(r.items.single.foodId, 7);
    expect(r.items.single.macroEstimated, isTrue);
    expect(r.usage.model, 'claude-haiku-5-5');
  });
}
