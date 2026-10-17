// Pruebas unitarias para SqliteMealGlucoseReminderRepository.
//
// Usan sqflite_common_ffi para ejecutar sobre una base de datos SQLite en
// memoria, sin depender del plugin nativo de Android/iOS.

import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'package:seguimiento_glucosa/models/food.dart';
import 'package:seguimiento_glucosa/models/meal.dart';
import 'package:seguimiento_glucosa/models/meal_glucose_reminder.dart';
import 'package:seguimiento_glucosa/services/app_database.dart';
import 'package:seguimiento_glucosa/services/meal_glucose_reminder_repository.dart';
import 'package:seguimiento_glucosa/services/meal_repository.dart';

void main() {
  setUpAll(() {
    sqfliteFfiInit();
  });

  // singleInstance: false asegura que cada base de datos sea propia y
  // completamente aislada de las demás pruebas. Se comparte entre ambos
  // repositorios (igual que hacen las pantallas reales) porque
  // `meal_glucose_reminders.meal_id` referencia `meals.id`.
  ({SqliteMealRepository meals, SqliteMealGlucoseReminderRepository reminders})
  createRepositories() {
    final db = AppDatabase(
      factory: databaseFactoryFfi,
      databasePath: inMemoryDatabasePath,
      singleInstance: false,
    );
    return (
      meals: SqliteMealRepository.withDatabase(db),
      reminders: SqliteMealGlucoseReminderRepository.withDatabase(db),
    );
  }

  Future<Meal> saveMeal(SqliteMealRepository meals, DateTime eatenAt) {
    return meals.addMeal(
      Meal(
        type: MealType.breakfast,
        eatenAt: eatenAt,
        items: [
          MealFoodItem(
            food: const Food(name: 'Pan'),
            quantity: '2 rebanadas',
          ),
        ],
      ),
    );
  }

  test('getPendingDueBy devuelve vacío cuando no hay recordatorios', () async {
    final repos = createRepositories();
    final pending = await repos.reminders.getPendingDueBy(DateTime.now());
    expect(pending, isEmpty);
  });

  test('addReminders persiste y asigna un id autogenerado', () async {
    final repos = createRepositories();
    final meal = await saveMeal(repos.meals, DateTime(2026, 1, 1, 8));

    final saved = await repos.reminders.addReminders([
      MealGlucoseReminder(
        mealId: meal.id!,
        offsetMinutes: 60,
        dueAt: DateTime(2026, 1, 1, 9),
      ),
      MealGlucoseReminder(
        mealId: meal.id!,
        offsetMinutes: 90,
        dueAt: DateTime(2026, 1, 1, 9, 30),
      ),
    ]);

    expect(saved.length, 2);
    expect(saved[0].id, isNotNull);
    expect(saved[1].id, isNotNull);
    expect(saved[0].status, MealGlucoseReminderStatus.pending);
  });

  test('getPendingDueBy solo devuelve recordatorios pendientes vencidos '
      'antes del límite dado', () async {
    final repos = createRepositories();
    final meal = await saveMeal(repos.meals, DateTime(2026, 1, 1, 8));

    await repos.reminders.addReminders([
      MealGlucoseReminder(
        mealId: meal.id!,
        offsetMinutes: 60,
        dueAt: DateTime(2026, 1, 1, 9),
      ),
      MealGlucoseReminder(
        mealId: meal.id!,
        offsetMinutes: 90,
        dueAt: DateTime(2026, 1, 1, 9, 30),
      ),
    ]);

    final pending = await repos.reminders.getPendingDueBy(
      DateTime(2026, 1, 1, 9, 15),
    );

    expect(pending.length, 1);
    expect(pending.first.offsetMinutes, 60);
  });

  test('updateStatus marca un recordatorio como resuelto automáticamente '
      'y queda excluido de los pendientes', () async {
    final repos = createRepositories();
    final meal = await saveMeal(repos.meals, DateTime(2026, 1, 1, 8));

    final saved = await repos.reminders.addReminders([
      MealGlucoseReminder(
        mealId: meal.id!,
        offsetMinutes: 60,
        dueAt: DateTime(2026, 1, 1, 9),
      ),
    ]);

    await repos.reminders.updateStatus(
      saved.first.id!,
      status: MealGlucoseReminderStatus.resolvedAutomatically,
      resolvedMeasurementId: 42,
    );

    final pending = await repos.reminders.getPendingDueBy(
      DateTime(2026, 1, 1, 10),
    );
    expect(pending, isEmpty);
  });

  test('deleting the originating meal cascades to its reminders', () async {
    final repos = createRepositories();
    final meal = await saveMeal(repos.meals, DateTime(2026, 1, 1, 8));

    await repos.reminders.addReminders([
      MealGlucoseReminder(
        mealId: meal.id!,
        offsetMinutes: 60,
        dueAt: DateTime(2026, 1, 1, 9),
      ),
    ]);

    await repos.meals.clearMeals();

    final pending = await repos.reminders.getPendingDueBy(
      DateTime(2026, 1, 1, 10),
    );
    expect(pending, isEmpty);
  });
}
