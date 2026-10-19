import 'package:sqflite/sqflite.dart';

import '../models/food.dart';
import '../models/meal.dart';
import 'app_database.dart';

/// Contrato de persistencia para el historial de comidas y su catálogo de
/// alimentos.
///
/// Se define como interfaz abstracta para permitir sustituir la
/// implementación (por ejemplo, en pruebas) sin acoplar las pantallas a
/// `sqflite`.
abstract class MealRepository {
  /// Recupera el historial completo de comidas (con sus alimentos),
  /// ordenado de la más reciente a la más antigua.
  Future<List<Meal>> getAllMeals();

  /// Guarda [meal] como una nueva comida del historial.
  ///
  /// Los alimentos de [Meal.items] se resuelven contra el catálogo de
  /// [Food] por nombre: si un nombre ya existe, se reutiliza su [Food.id];
  /// si no existe, se crea una nueva entrada en el catálogo.
  ///
  /// Devuelve la comida persistida, con [Meal.id] y los `id` de cada
  /// [MealFoodItem] asignados por el almacenamiento.
  Future<Meal> addMeal(Meal meal);

  /// Elimina todas las comidas guardadas (no afecta el catálogo de
  /// alimentos).
  Future<void> clearMeals();

  /// Recupera el catálogo completo de alimentos, ordenado alfabéticamente.
  Future<List<Food>> getAllFoods();
}

/// Implementación de [MealRepository] basada en SQLite (`sqflite`).
///
/// Consume las tablas `meals`, `meal_food_items` y `foods` de la base de
/// datos compartida ([AppDatabase]).
class SqliteMealRepository implements MealRepository {
  /// Crea el repositorio usando [factory] como fábrica de la base de datos
  /// y, opcionalmente, [databasePath] como ruta explícita del archivo.
  ///
  /// Si [factory] no se provee, usa la fábrica por defecto de `sqflite`
  /// ([databaseFactory]), válida en Android/iOS.
  ///
  /// En tests se puede inyectar `databaseFactoryFfi` de
  /// `sqflite_common_ffi` junto con `inMemoryDatabasePath` como
  /// [databasePath] y [singleInstance] en `false`, para que cada instancia
  /// de este repositorio abra una base de datos en memoria propia y
  /// completamente aislada de otras pruebas.
  SqliteMealRepository({
    DatabaseFactory? factory,
    String? databasePath,
    bool singleInstance = true,
  }) : _appDatabase = AppDatabase(
         factory: factory,
         databasePath: databasePath,
         singleInstance: singleInstance,
       );

  /// Permite reutilizar una [AppDatabase] ya creada (por ejemplo, la misma
  /// instancia compartida con [SqliteGlucoseRepository]), en lugar de abrir
  /// una conexión nueva.
  SqliteMealRepository.withDatabase(AppDatabase appDatabase)
    : _appDatabase = appDatabase;

  static const _mealsTable = 'meals';
  static const _itemsTable = 'meal_food_items';
  static const _foodsTable = 'foods';

  final AppDatabase _appDatabase;

  Future<Database> get _db => _appDatabase.database;

  @override
  Future<List<Meal>> getAllMeals() async {
    final db = await _db;
    final mealRows = await db.query(
      _mealsTable,
      orderBy: 'eaten_at DESC, id DESC',
    );

    final meals = <Meal>[];
    for (final mealRow in mealRows) {
      final items = await _getItemsForMeal(db, mealRow['id'] as int);
      meals.add(_mealFromRow(mealRow, items));
    }
    return meals;
  }

  @override
  Future<Meal> addMeal(Meal meal) async {
    final db = await _db;

    return db.transaction((txn) async {
      final mealId = await txn.insert(_mealsTable, _mealToRow(meal));

      final savedItems = <MealFoodItem>[];
      for (final item in meal.items) {
        final foodId = await _resolveFoodId(txn, item.food.name);
        final itemId = await txn.insert(_itemsTable, {
          'meal_id': mealId,
          'food_id': foodId,
          'quantity': item.quantity,
        });
        savedItems.add(
          MealFoodItem(
            id: itemId,
            food: Food(id: foodId, name: item.food.name),
            quantity: item.quantity,
          ),
        );
      }

      return meal.copyWith(id: mealId, items: savedItems);
    });
  }

  @override
  Future<void> clearMeals() async {
    final db = await _db;
    await db.delete(_mealsTable);
  }

  @override
  Future<List<Food>> getAllFoods() async {
    final db = await _db;
    final rows = await db.query(_foodsTable, orderBy: 'name ASC');
    return rows
        .map((row) => Food(id: row['id'] as int, name: row['name'] as String))
        .toList();
  }

  /// Devuelve el `id` del alimento llamado [name] en el catálogo,
  /// reutilizando la fila existente si ya hay una con ese nombre (tras
  /// recortar espacios extremos), o creando una nueva en caso contrario.
  Future<int> _resolveFoodId(DatabaseExecutor txn, String name) async {
    final normalized = name.trim();
    final existing = await txn.query(
      _foodsTable,
      where: 'name = ?',
      whereArgs: [normalized],
      limit: 1,
    );
    if (existing.isNotEmpty) {
      return existing.first['id'] as int;
    }
    return txn.insert(_foodsTable, {'name': normalized});
  }

  Future<List<MealFoodItem>> _getItemsForMeal(
    DatabaseExecutor db,
    int mealId,
  ) async {
    final rows = await db.rawQuery(
      '''
      SELECT $_itemsTable.id AS item_id,
             $_itemsTable.quantity AS quantity,
             $_foodsTable.id AS food_id,
             $_foodsTable.name AS food_name
      FROM $_itemsTable
      INNER JOIN $_foodsTable ON $_foodsTable.id = $_itemsTable.food_id
      WHERE $_itemsTable.meal_id = ?
      ORDER BY $_itemsTable.id ASC
      ''',
      [mealId],
    );

    return rows.map((row) {
      return MealFoodItem(
        id: row['item_id'] as int,
        food: Food(id: row['food_id'] as int, name: row['food_name'] as String),
        quantity: row['quantity'] as String,
      );
    }).toList();
  }

  Meal _mealFromRow(Map<String, Object?> row, List<MealFoodItem> items) {
    final type =
        MealType.values.asNameMap()[row['type'] as String] ?? MealType.other;
    return Meal(
      id: row['id'] as int,
      uuid: row['uuid'] as String,
      type: type,
      eatenAt: DateTime.parse(row['eaten_at'] as String),
      comment: row['comment'] as String?,
      items: items,
    );
  }

  Map<String, Object?> _mealToRow(Meal meal) {
    return {
      'uuid': meal.uuid,
      'type': meal.type.name,
      'eaten_at': meal.eatenAt.toIso8601String(),
      'comment': meal.comment,
    };
  }
}
