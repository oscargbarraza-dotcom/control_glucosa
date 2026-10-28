// Pruebas unitarias para la extensión MealTypeLabel de MealType.
//
// No dependen de Flutter ni de sqflite: solo Dart puro, ver
// `lib/models/meal.dart`.

import 'package:flutter_test/flutter_test.dart';

import 'package:seguimiento_glucosa/models/meal.dart';

void main() {
  group('MealTypeLabel', () {
    test('once se presenta como "Once", distinta de "Colación" (snack)', () {
      expect(MealType.once.label, 'Once');
      expect(MealType.snack.label, 'Colación');
    });

    test('cada valor del enum tiene una etiqueta legible no vacía', () {
      for (final type in MealType.values) {
        expect(type.label, isNotEmpty);
      }
    });
  });
}
