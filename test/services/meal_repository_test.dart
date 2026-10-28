// Pruebas unitarias para SqliteMealRepository.
//
// Usan sqflite_common_ffi para ejecutar sobre una base de datos SQLite en
// memoria, sin depender del plugin nativo de Android/iOS.

import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'package:seguimiento_glucosa/models/food.dart';
import 'package:seguimiento_glucosa/models/meal.dart';
import 'package:seguimiento_glucosa/services/meal_repository.dart';

void main() {
  setUpAll(() {
    sqfliteFfiInit();
  });

  // singleInstance: false asegura que cada repositorio abra su propia base
  // de datos en memoria, completamente aislada de las demás pruebas.
  SqliteMealRepository createRepository() {
    return SqliteMealRepository(
      factory: databaseFactoryFfi,
      databasePath: inMemoryDatabasePath,
      singleInstance: false,
    );
  }

  test('getAllMeals devuelve lista vacía cuando no hay datos', () async {
    final repository = createRepository();
    expect(await repository.getAllMeals(), isEmpty);
  });

  test('addMeal persiste la comida y asigna ids a comida e items', () async {
    final repository = createRepository();

    final saved = await repository.addMeal(
      Meal(
        type: MealType.breakfast,
        eatenAt: DateTime(2026, 1, 1, 8),
        comment: 'prueba',
        items: [
          MealFoodItem(
            food: const Food(name: 'Pan'),
            quantity: '2 rebanadas',
          ),
          MealFoodItem(
            food: const Food(name: 'Huevo'),
            quantity: '1 unidad',
          ),
        ],
      ),
    );

    expect(saved.id, isNotNull);
    expect(saved.comment, 'prueba');
    expect(saved.items, hasLength(2));
    expect(saved.items[0].id, isNotNull);
    expect(saved.items[0].food.id, isNotNull);
    expect(saved.items[0].food.name, 'Pan');
    expect(saved.items[1].food.name, 'Huevo');
  });

  test('addMeal reutiliza un alimento existente en el catálogo', () async {
    final repository = createRepository();

    final first = await repository.addMeal(
      Meal(
        type: MealType.lunch,
        eatenAt: DateTime(2026, 1, 1, 13),
        items: [
          MealFoodItem(
            food: const Food(name: 'Arroz'),
            quantity: '1 taza',
          ),
        ],
      ),
    );
    final second = await repository.addMeal(
      Meal(
        type: MealType.dinner,
        eatenAt: DateTime(2026, 1, 1, 20),
        items: [
          MealFoodItem(
            food: const Food(name: 'Arroz'),
            quantity: '1/2 taza',
          ),
        ],
      ),
    );

    expect(first.items.single.food.id, second.items.single.food.id);
    expect(await repository.getAllFoods(), hasLength(1));
  });

  test(
    'getAllMeals ordena de más reciente a más antigua, con sus items',
    () async {
      final repository = createRepository();

      await repository.addMeal(
        Meal(
          type: MealType.breakfast,
          eatenAt: DateTime(2026, 1, 1, 8),
          items: [
            MealFoodItem(
              food: const Food(name: 'Avena'),
              quantity: '1 bowl',
            ),
          ],
        ),
      );
      await repository.addMeal(
        Meal(
          type: MealType.dinner,
          eatenAt: DateTime(2026, 1, 2, 21),
          items: [
            MealFoodItem(
              food: const Food(name: 'Pollo'),
              quantity: '150 g',
            ),
          ],
        ),
      );

      final all = await repository.getAllMeals();
      expect(all.map((m) => m.type).toList(), [
        MealType.dinner,
        MealType.breakfast,
      ]);
      expect(all.first.items.single.food.name, 'Pollo');
    },
  );

  test('addMeal genera un uuid distinto por cada comida cuando no se '
      'provee uno, y persiste al recargar', () async {
    final repository = createRepository();

    final first = await repository.addMeal(
      Meal(
        type: MealType.breakfast,
        eatenAt: DateTime(2026, 1, 1, 8),
        items: [
          MealFoodItem(
            food: const Food(name: 'Pan'),
            quantity: '1',
          ),
        ],
      ),
    );
    final second = await repository.addMeal(
      Meal(
        type: MealType.lunch,
        eatenAt: DateTime(2026, 1, 1, 13),
        items: [
          MealFoodItem(
            food: const Food(name: 'Arroz'),
            quantity: '1',
          ),
        ],
      ),
    );

    expect(first.uuid, isNotEmpty);
    expect(second.uuid, isNotEmpty);
    expect(first.uuid, isNot(second.uuid));

    final all = await repository.getAllMeals();
    expect(all.map((m) => m.uuid), containsAll([first.uuid, second.uuid]));
  });

  test('addMeal persiste y recupera comidas de tipo once', () async {
    final repository = createRepository();

    final saved = await repository.addMeal(
      Meal(
        type: MealType.once,
        eatenAt: DateTime(2026, 1, 1, 17),
        items: [
          MealFoodItem(
            food: const Food(name: 'Té'),
            quantity: '1 taza',
          ),
        ],
      ),
    );

    expect(saved.type, MealType.once);

    final all = await repository.getAllMeals();
    expect(all.single.type, MealType.once);
  });

  test('clearMeals elimina las comidas pero conserva el catálogo', () async {
    final repository = createRepository();

    await repository.addMeal(
      Meal(
        type: MealType.snack,
        eatenAt: DateTime(2026, 1, 1),
        items: [
          MealFoodItem(
            food: const Food(name: 'Manzana'),
            quantity: '1 unidad',
          ),
        ],
      ),
    );
    await repository.clearMeals();

    expect(await repository.getAllMeals(), isEmpty);
    expect(await repository.getAllFoods(), hasLength(1));
  });
}
