// Pruebas unitarias para la lógica pura de UserProfile (cálculo de IMC y
// su clasificación). No depende de Flutter ni de sqflite: solo Dart
// puro, ver `lib/models/user_profile.dart`.

import 'package:flutter_test/flutter_test.dart';

import 'package:seguimiento_glucosa/models/user_profile.dart';

void main() {
  group('UserProfile.bmiFor', () {
    test('calcula el IMC a partir de altura y peso', () {
      const profile = UserProfile(heightCm: 170);
      // 72.25 / (1.70 ^ 2) = 25.0
      expect(profile.bmiFor(72.25), closeTo(25.0, 0.001));
    });

    test('devuelve null si la altura no es positiva', () {
      const profile = UserProfile(heightCm: 0);
      expect(profile.bmiFor(70), isNull);
    });
  });

  group('bmiCategoryFor', () {
    test('clasifica bajo peso por debajo de 18.5', () {
      expect(bmiCategoryFor(17.9), BmiCategory.underweight);
    });

    test('clasifica normal entre 18.5 y 25 (exclusivo)', () {
      expect(bmiCategoryFor(18.5), BmiCategory.normal);
      expect(bmiCategoryFor(24.9), BmiCategory.normal);
    });

    test('clasifica sobrepeso entre 25 y 30 (exclusivo)', () {
      expect(bmiCategoryFor(25), BmiCategory.overweight);
      expect(bmiCategoryFor(29.9), BmiCategory.overweight);
    });

    test('clasifica obesidad desde 30', () {
      expect(bmiCategoryFor(30), BmiCategory.obese);
      expect(bmiCategoryFor(40), BmiCategory.obese);
    });
  });

  test('copyWith y los flags clear* permiten limpiar campos opcionales', () {
    final profile = UserProfile(
      heightCm: 170,
      birthDate: DateTime(1990, 1, 1),
      biologicalSex: BiologicalSex.male,
      displayName: 'Persona',
    );

    final cleared = profile.copyWith(
      clearBirthDate: true,
      clearBiologicalSex: true,
      clearDisplayName: true,
    );

    expect(cleared.heightCm, 170);
    expect(cleared.birthDate, isNull);
    expect(cleared.biologicalSex, isNull);
    expect(cleared.displayName, isNull);
  });
}
