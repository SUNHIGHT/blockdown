/// Pure-Dart models for the draft-review screen (no Flutter imports, easy to unit test).
library;

enum SizePreset {
  small(0.7, '小'),
  regular(1.0, '並'),
  large(1.3, '大'),
  extra(1.6, '特盛');

  const SizePreset(this.ratio, this.label);
  final double ratio;
  final String label;

  /// Chip text, e.g. "大 ×1.3".
  String get chipLabel => '$label ×${ratio.toStringAsFixed(1)}';
}

/// One item exactly as returned by `POST /meals/parse`.
class DraftItem {
  DraftItem({
    required this.name,
    required this.kcal,
    required this.proteinG,
    required this.fatG,
    required this.carbsG,
    required this.kcalMin,
    required this.kcalMax,
    required this.confidence,
    required this.source,
    this.chain,
    this.amountNote = '',
    this.amountRatio = 1.0,
    this.macroEstimated = false,
    this.foodId,
    this.alternatives = const [],
    this.flags = const [],
  });

  final String name;
  final String? chain;
  final String amountNote;
  final double amountRatio;
  final double kcal, proteinG, fatG, carbsG, kcalMin, kcalMax;
  final double confidence;
  final String source; // user | official | packaged | llm
  final bool macroEstimated;
  final int? foodId;
  final List<String> alternatives;
  final List<String> flags;

  factory DraftItem.fromJson(Map<String, dynamic> j) => DraftItem(
        name: j['name'] as String,
        chain: j['chain'] as String?,
        amountNote: (j['amount_note'] as String?) ?? '',
        amountRatio: ((j['amount_ratio'] as num?) ?? 1).toDouble(),
        kcal: (j['kcal'] as num).toDouble(),
        proteinG: (j['protein_g'] as num).toDouble(),
        fatG: (j['fat_g'] as num).toDouble(),
        carbsG: (j['carbs_g'] as num).toDouble(),
        kcalMin: (j['kcal_min'] as num).toDouble(),
        kcalMax: (j['kcal_max'] as num).toDouble(),
        confidence: (j['confidence'] as num).toDouble(),
        source: j['source'] as String,
        macroEstimated: (j['macro_estimated'] as bool?) ?? false,
        foodId: j['food_id'] as int?,
        alternatives: ((j['alternatives'] as List?) ?? const []).cast<String>(),
        flags: ((j['flags'] as List?) ?? const []).cast<String>(),
      );

  /// Echoed back to the server (stored in ai_estimates to measure AI accuracy).
  Map<String, dynamic> toJson() => {
        'name': name,
        'chain': chain,
        'amount_note': amountNote,
        'amount_ratio': amountRatio,
        'kcal': kcal,
        'protein_g': proteinG,
        'fat_g': fatG,
        'carbs_g': carbsG,
        'kcal_min': kcalMin,
        'kcal_max': kcalMax,
        'confidence': confidence,
        'source': source,
        'macro_estimated': macroEstimated,
        'food_id': foodId,
        'alternatives': alternatives,
        'flags': flags,
      };
}

class Usage {
  Usage({required this.model, this.inputTokens = 0, this.outputTokens = 0, this.requestId});
  final String model;
  final int inputTokens, outputTokens;
  final String? requestId;

  factory Usage.fromJson(Map<String, dynamic> j) => Usage(
        model: j['model'] as String,
        inputTokens: (j['input_tokens'] as num?)?.toInt() ?? 0,
        outputTokens: (j['output_tokens'] as num?)?.toInt() ?? 0,
        requestId: j['request_id'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'model': model,
        'input_tokens': inputTokens,
        'output_tokens': outputTokens,
        'request_id': requestId,
      };
}

class ParseResponse {
  ParseResponse({
    required this.items,
    required this.slot,
    required this.usage,
    this.question,
    this.refused = false,
  });
  final List<DraftItem> items;
  final String slot;
  final String? question;
  final bool refused;
  final Usage usage;

  factory ParseResponse.fromJson(Map<String, dynamic> j) => ParseResponse(
        items: (j['items'] as List).map((e) => DraftItem.fromJson(e as Map<String, dynamic>)).toList(),
        slot: j['slot'] as String,
        question: j['question'] as String?,
        refused: (j['refused'] as bool?) ?? false,
        usage: Usage.fromJson(j['usage'] as Map<String, dynamic>),
      );
}

/// Local, editable state of one draft item. Everything shown on screen is derived
/// from [item] (numbers at its returned amount) and the chosen [preset].
class DraftLine {
  DraftLine(this.item, {SizePreset? preset, this.saveToMyFoods = false})
      : preset = preset ?? SizePreset.regular;

  final DraftItem item;
  SizePreset preset;
  bool saveToMyFoods;

  /// Multiplier relative to the numbers the server returned.
  double get _scale => preset.ratio;

  double get kcal => item.kcal * _scale;
  double get proteinG => item.proteinG * _scale;
  double get fatG => item.fatG * _scale;
  double get carbsG => item.carbsG * _scale;
  double get kcalMin => item.kcalMin * _scale;
  double get kcalMax => item.kcalMax * _scale;

  /// Ratio against ONE standard serving (what the server stores in meal_items).
  double get amountRatio => item.amountRatio * _scale;

  bool get lowConfidence => item.confidence < 0.6 || item.flags.contains('kcal_mismatch');

  Map<String, dynamic> toConfirmJson() => {
        'name': item.name,
        'chain': item.chain,
        'food_id': item.foodId,
        'amount_ratio': amountRatio,
        'kcal': kcal,
        'protein_g': proteinG,
        'fat_g': fatG,
        'carbs_g': carbsG,
        'kcal_min': kcalMin,
        'kcal_max': kcalMax,
        'source': item.source,
        'confidence': item.confidence,
        'user_corrected': preset != SizePreset.regular,
        'save_to_my_foods': saveToMyFoods,
      };
}

class MealTotals {
  const MealTotals(this.kcal, this.kcalMin, this.kcalMax, this.proteinG, this.fatG, this.carbsG);
  final double kcal, kcalMin, kcalMax, proteinG, fatG, carbsG;

  factory MealTotals.of(Iterable<DraftLine> lines) {
    double k = 0, kmin = 0, kmax = 0, p = 0, f = 0, c = 0;
    for (final l in lines) {
      k += l.kcal;
      kmin += l.kcalMin;
      kmax += l.kcalMax;
      p += l.proteinG;
      f += l.fatG;
      c += l.carbsG;
    }
    return MealTotals(k, kmin, kmax, p, f, c);
  }
}
