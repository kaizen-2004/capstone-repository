import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('basic widget test scaffold', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: Text('IntruFlare')),
      ),
    );

    expect(find.text('IntruFlare'), findsOneWidget);
  });
}
