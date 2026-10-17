import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../models/draft.dart';

/// Review-and-correct screen for the result of `POST /meals/parse`.
///
/// * One card per item with size chips (小 / 並 / 大 / 特盛). Tapping a chip
///   rescales that item locally and the totals at the top update at once.
/// * Items the AI is unsure about (confidence < 0.6, or an inconsistent kcal)
///   get an amber background and a warning icon.
/// * "この内容で記録する" sends the corrected items to `POST /meals`.
class MealDraftScreen extends StatefulWidget {
  const MealDraftScreen({
    super.key,
    required this.draft,
    required this.api,
    this.inputKind = 'text',
    this.onSaved,
    this.clock,
  });

  final ParseResponse draft;
  final ApiClient api;

  /// text | photo | barcode | manual | copy
  final String inputKind;

  /// Called after the server confirmed the meal (e.g. to pop back to the diary).
  final void Function(String mealId)? onSaved;

  /// Injectable clock (tests); defaults to [DateTime.now].
  final DateTime Function()? clock;

  @override
  State<MealDraftScreen> createState() => _MealDraftScreenState();
}

class _MealDraftScreenState extends State<MealDraftScreen> {
  static const _slots = ['朝', '昼', '夜', '間食'];

  late final List<DraftLine> _lines = widget.draft.items.map(DraftLine.new).toList();
  late String _slot = _slots.contains(widget.draft.slot) ? widget.draft.slot : '間食';
  bool _saving = false;

  DateTime get _now => (widget.clock ?? DateTime.now)();

  Future<void> _save() async {
    if (_lines.isEmpty || _saving) return;
    setState(() => _saving = true);
    final messenger = ScaffoldMessenger.of(context);
    try {
      final now = _now;
      final id = await widget.api.confirmMeal({
        'local_date': '${now.year.toString().padLeft(4, '0')}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}',
        'eaten_at': now.toUtc().toIso8601String(),
        'slot': _slot,
        'input_kind': widget.inputKind,
        'items': _lines.map((l) => l.toConfirmJson()).toList(),
        // The untouched AI draft + token usage: used to measure estimation error later.
        'usage': widget.draft.usage.toJson(),
        'draft': widget.draft.items.map((i) => i.toJson()).toList(),
      });
      if (!mounted) return;
      widget.onSaved?.call(id);
      messenger.showSnackBar(const SnackBar(content: Text('記録しました')));
    } on ApiException catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(e.userMessage)));
    } catch (_) {
      messenger.showSnackBar(const SnackBar(content: Text('通信に失敗しました。電波の良い場所で再度お試しください。')));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final totals = MealTotals.of(_lines);
    return Scaffold(
      appBar: AppBar(title: const Text('内容を確認')),
      body: Column(
        children: [
          _TotalsHeader(totals: totals),
          if (widget.draft.question != null)
            _Banner(icon: Icons.help_outline, text: widget.draft.question!),
          if (widget.draft.refused)
            const _Banner(icon: Icons.info_outline, text: '写真・文章から読み取れませんでした。内容を変えてもう一度お試しください。'),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
            child: Row(
              children: [
                for (final s in _slots)
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      key: Key('slot_$s'),
                      label: Text(s),
                      selected: _slot == s,
                      onSelected: (_) => setState(() => _slot = s),
                    ),
                  ),
              ],
            ),
          ),
          Expanded(
            child: _lines.isEmpty
                ? const Center(child: Text('品目がありません'))
                : ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: _lines.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 12),
                    itemBuilder: (context, i) => _ItemCard(
                      key: ValueKey(_lines[i]),
                      line: _lines[i],
                      onPreset: (p) => setState(() => _lines[i].preset = p),
                      onSaveToggle: (v) => setState(() => _lines[i].saveToMyFoods = v),
                      onRemove: () => setState(() => _lines.removeAt(i)),
                    ),
                  ),
          ),
        ],
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
          child: FilledButton(
            key: const Key('save_button'),
            onPressed: _lines.isEmpty || _saving ? null : _save,
            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
            child: _saving
                ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5))
                : const Text('この内容で記録する'),
          ),
        ),
      ),
    );
  }
}

class _TotalsHeader extends StatelessWidget {
  const _TotalsHeader({required this.totals});
  final MealTotals totals;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final range = (totals.kcalMax - totals.kcalMin).round() > 0
        ? '${totals.kcalMin.round()}〜${totals.kcalMax.round()} kcal'
        : null;
    Widget macro(String key, String label, double v, Color c) => Expanded(
          child: Column(
            children: [
              Text(label, style: t.textTheme.labelMedium?.copyWith(color: c, fontWeight: FontWeight.w700)),
              Text('${v.round()} g', key: Key(key), style: t.textTheme.titleMedium),
            ],
          ),
        );
    return Container(
      width: double.infinity,
      color: t.colorScheme.surfaceContainerHighest,
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text('${totals.kcal.round()}', key: const Key('total_kcal'), style: t.textTheme.displaySmall),
              const SizedBox(width: 6),
              const Text('kcal'),
            ],
          ),
          if (range != null)
            Text(range, key: const Key('total_range'), style: t.textTheme.bodySmall),
          const SizedBox(height: 8),
          Row(
            children: [
              macro('total_p', 'P たんぱく質', totals.proteinG, Colors.blue),
              macro('total_f', 'F 脂質', totals.fatG, Colors.orange),
              macro('total_c', 'C 炭水化物', totals.carbsG, Colors.green),
            ],
          ),
        ],
      ),
    );
  }
}

class _Banner extends StatelessWidget {
  const _Banner({required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        color: Theme.of(context).colorScheme.secondaryContainer,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        child: Row(children: [Icon(icon, size: 20), const SizedBox(width: 8), Expanded(child: Text(text))]),
      );
}

class _ItemCard extends StatelessWidget {
  const _ItemCard({
    super.key,
    required this.line,
    required this.onPreset,
    required this.onSaveToggle,
    required this.onRemove,
  });

  final DraftLine line;
  final ValueChanged<SizePreset> onPreset;
  final ValueChanged<bool> onSaveToggle;
  final VoidCallback onRemove;

  static String _sourceLabel(DraftItem i) => switch (i.source) {
        'user' => 'いつもの',
        'official' => i.macroEstimated ? '公式カロリー' : '公式',
        'packaged' => '商品データ',
        _ => 'AI推定',
      };

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final warn = line.lowConfidence;
    final amber = Theme.of(context).brightness == Brightness.dark ? Colors.amber.shade900 : Colors.amber.shade100;
    return Card(
      key: Key('card_${line.item.name}'),
      margin: EdgeInsets.zero,
      color: warn ? amber : null,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 12, 6, 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                if (warn)
                  const Padding(
                    padding: EdgeInsets.only(right: 6),
                    child: Icon(Icons.warning_amber_rounded, key: Key('warn_icon'), size: 22),
                  ),
                Expanded(child: Text(line.item.name, style: t.textTheme.titleMedium)),
                IconButton(
                  key: Key('remove_${line.item.name}'),
                  tooltip: '外す',
                  icon: const Icon(Icons.close),
                  onPressed: onRemove,
                ),
              ],
            ),
            Wrap(
              spacing: 8,
              runSpacing: 2,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Chip(
                  label: Text(_sourceLabel(line.item)),
                  visualDensity: VisualDensity.compact,
                  padding: EdgeInsets.zero,
                ),
                if (line.item.amountNote.isNotEmpty) Text(line.item.amountNote, style: t.textTheme.bodySmall),
                if (warn) Text('念のため確認してください', style: t.textTheme.bodySmall),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              '${line.kcal.round()} kcal　P ${line.proteinG.toStringAsFixed(1)}　F ${line.fatG.toStringAsFixed(1)}　C ${line.carbsG.toStringAsFixed(1)}',
              key: Key('line_${line.item.name}'),
              style: t.textTheme.bodyLarge,
            ),
            if ((line.kcalMax - line.kcalMin).round() > 0)
              Text('${line.kcalMin.round()}〜${line.kcalMax.round()} kcal の範囲', style: t.textTheme.bodySmall),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: [
                for (final p in SizePreset.values)
                  ChoiceChip(
                    key: Key('chip_${line.item.name}_${p.label}'),
                    label: Text(p.chipLabel),
                    selected: line.preset == p,
                    onSelected: (_) => onPreset(p),
                  ),
              ],
            ),
            if (line.item.source == 'llm')
              CheckboxListTile(
                key: Key('save_${line.item.name}'),
                dense: true,
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
                title: const Text('次回から「いつもの」として使う'),
                value: line.saveToMyFoods,
                onChanged: (v) => onSaveToggle(v ?? false),
              ),
          ],
        ),
      ),
    );
  }
}
