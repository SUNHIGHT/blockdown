import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:health_app/api/api_client.dart';
import 'package:health_app/models/draft.dart';
import 'package:health_app/screens/meal_draft_screen.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

ParseResponse _draft() => ParseResponse(
      slot: '昼',
      usage: Usage(model: 'claude-haiku-5-5', inputTokens: 10, outputTokens: 5, requestId: 'req_1'),
      items: [
        DraftItem(name: '牛丼 並盛', kcal: 650, proteinG: 20, fatG: 22, carbsG: 90, kcalMin: 600, kcalMax: 700,
            confidence: 0.9, source: 'llm'),
        DraftItem(name: '謎の小鉢', kcal: 100, proteinG: 5, fatG: 5, carbsG: 8, kcalMin: 60, kcalMax: 160,
            confidence: 0.4, source: 'llm'),
      ],
    );

Future<List<http.Request>> _pump(WidgetTester tester, {int status = 201, void Function(String id)? onSaved}) async {
  // Tall viewport so ListView builds both cards (it is lazy).
  tester.view.physicalSize = const Size(900, 2400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  final seen = <http.Request>[];
  final client = MockClient((req) async {
    seen.add(req);
    return http.Response(jsonEncode({'meal_id': 'm-1'}), status, headers: {'content-type': 'application/json'});
  });
  final api = ApiClient(baseUrl: 'http://x', headers: () async => {'X-User-Id': 'u'}, client: client);
  await tester.pumpWidget(MaterialApp(
    home: MealDraftScreen(draft: _draft(), api: api, onSaved: onSaved, clock: () => DateTime(2026, 10, 17, 12, 30)),
  ));
  return seen;
}

String _text(WidgetTester t, String key) => (t.widget(find.byKey(Key(key))) as Text).data!;

void main() {
  testWidgets('shows items, totals and flags the low-confidence one', (tester) async {
    await _pump(tester);
    expect(_text(tester, 'total_kcal'), '750');
    expect(_text(tester, 'total_p'), '25 g');
    expect(find.text('牛丼 並盛'), findsOneWidget);
    expect(find.byKey(const Key('warn_icon')), findsOneWidget);       // only the 0.4 item
    expect(find.byKey(const Key('save_牛丼 並盛')), findsOneWidget);     // AI estimates can be saved as "いつもの"
  });

  testWidgets('tapping a size chip rescales the item and the totals immediately', (tester) async {
    await _pump(tester);
    await tester.tap(find.byKey(const Key('chip_牛丼 並盛_大')));
    await tester.pump();
    expect(_text(tester, 'line_牛丼 並盛'), startsWith('845 kcal'));
    expect(_text(tester, 'total_kcal'), '945');   // 845 + 100
    await tester.tap(find.byKey(const Key('chip_牛丼 並盛_小')));
    await tester.pump();
    expect(_text(tester, 'total_kcal'), '555');   // 455 + 100
  });

  testWidgets('removing an item updates totals; empty list disables saving', (tester) async {
    await _pump(tester);
    await tester.tap(find.byKey(const Key('remove_謎の小鉢')));
    await tester.pump();
    expect(_text(tester, 'total_kcal'), '650');
    await tester.tap(find.byKey(const Key('remove_牛丼 並盛')));
    await tester.pump();
    expect(tester.widget<FilledButton>(find.byKey(const Key('save_button'))).onPressed, isNull);
  });

  testWidgets('save posts corrected items + draft + usage to /meals', (tester) async {
    String? saved;
    final seen = await _pump(tester, onSaved: (id) => saved = id);
    await tester.tap(find.byKey(const Key('chip_牛丼 並盛_大')));
    await tester.tap(find.byKey(const Key('save_牛丼 並盛')));      // checkbox
    await tester.tap(find.byKey(const Key('slot_夜')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('save_button')));
    await tester.pumpAndSettle();

    expect(seen, hasLength(1));
    expect(seen.single.url.path, '/meals');
    expect(seen.single.headers['X-User-Id'], 'u');
    final body = jsonDecode(seen.single.body) as Map<String, dynamic>;
    expect(body['slot'], '夜');
    expect(body['local_date'], '2026-10-17');
    expect(body['input_kind'], 'text');
    final items = (body['items'] as List).cast<Map<String, dynamic>>();
    expect(items, hasLength(2));
    expect(items[0]['kcal'], closeTo(845, 1e-6));
    expect(items[0]['amount_ratio'], closeTo(1.3, 1e-9));
    expect(items[0]['user_corrected'], isTrue);
    expect(items[0]['save_to_my_foods'], isTrue);
    expect(items[1]['user_corrected'], isFalse);
    expect(((body['draft'] as List)[0] as Map)['kcal'], 650);          // original AI numbers kept
    expect((body['usage'] as Map)['request_id'], 'req_1');
    expect(saved, 'm-1');
  });

  testWidgets('server error keeps the screen and shows a message', (tester) async {
    await _pump(tester, status: 429);
    await tester.tap(find.byKey(const Key('save_button')));
    await tester.pumpAndSettle();
    expect(find.textContaining('混み合っています'), findsOneWidget);
    expect(find.byKey(const Key('save_button')), findsOneWidget);
  });
}
