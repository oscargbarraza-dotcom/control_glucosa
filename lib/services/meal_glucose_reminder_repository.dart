import 'package:sqflite/sqflite.dart';

import '../models/meal_glucose_reminder.dart';
import 'app_database.dart';

/// Contrato de persistencia para los recordatorios de medición de
/// glucosa post-comida (a los 60 y 90 minutos de registrar una [Meal]).
///
/// Se define como interfaz abstracta para permitir sustituir la
/// implementación (por ejemplo, en pruebas) sin acoplar
/// [MealGlucoseReminderCoordinator] a `sqflite`.
abstract class MealGlucoseReminderRepository {
  /// Guarda [reminders] (normalmente las dos instancias de 60 y 90
  /// minutos generadas al registrar una comida) como nuevos
  /// recordatorios.
  ///
  /// Devuelve los recordatorios persistidos, con [MealGlucoseReminder.id]
  /// asignado por el almacenamiento, en el mismo orden recibido.
  Future<List<MealGlucoseReminder>> addReminders(
    List<MealGlucoseReminder> reminders,
  );

  /// Recupera los recordatorios en estado
  /// [MealGlucoseReminderStatus.pending] cuyo [MealGlucoseReminder.dueAt]
  /// ya pasó (es menor o igual a [now]), ordenados del más antiguo al más
  /// reciente.
  Future<List<MealGlucoseReminder>> getPendingDueBy(DateTime now);

  /// Actualiza el estado del recordatorio [id] a [status], asociando
  /// opcionalmente [resolvedMeasurementId] (el `id` de la
  /// `GlucoseMeasurement` que lo resolvió).
  Future<void> updateStatus(
    int id, {
    required MealGlucoseReminderStatus status,
    int? resolvedMeasurementId,
  });
}

/// Implementación de [MealGlucoseReminderRepository] basada en SQLite
/// (`sqflite`).
///
/// Consume la tabla `meal_glucose_reminders` de la base de datos
/// compartida ([AppDatabase]), que referencia `meals` con
/// `ON DELETE CASCADE`: al borrar una comida se eliminan automáticamente
/// sus recordatorios.
class SqliteMealGlucoseReminderRepository
    implements MealGlucoseReminderRepository {
  /// Crea el repositorio usando [factory] como fábrica de la base de
  /// datos y, opcionalmente, [databasePath] como ruta explícita del
  /// archivo.
  ///
  /// Si [factory] no se provee, usa la fábrica por defecto de `sqflite`
  /// ([databaseFactory]), válida en Android/iOS.
  ///
  /// En tests se puede inyectar `databaseFactoryFfi` de
  /// `sqflite_common_ffi` junto con `inMemoryDatabasePath` como
  /// [databasePath] y [singleInstance] en `false`, para que cada
  /// instancia de este repositorio abra una base de datos en memoria
  /// propia y completamente aislada de otras pruebas.
  SqliteMealGlucoseReminderRepository({
    DatabaseFactory? factory,
    String? databasePath,
    bool singleInstance = true,
  }) : _appDatabase = AppDatabase(
         factory: factory,
         databasePath: databasePath,
         singleInstance: singleInstance,
       );

  /// Permite reutilizar una [AppDatabase] ya creada (por ejemplo, la
  /// misma instancia compartida con [SqliteMealRepository]), en lugar de
  /// abrir una conexión nueva. Es necesario para que `ON DELETE CASCADE`
  /// funcione de verdad: debe ser la misma conexión que inserta en
  /// `meals`.
  SqliteMealGlucoseReminderRepository.withDatabase(AppDatabase appDatabase)
    : _appDatabase = appDatabase;

  static const _table = 'meal_glucose_reminders';

  final AppDatabase _appDatabase;

  Future<Database> get _db => _appDatabase.database;

  @override
  Future<List<MealGlucoseReminder>> addReminders(
    List<MealGlucoseReminder> reminders,
  ) async {
    final db = await _db;
    return db.transaction((txn) async {
      final saved = <MealGlucoseReminder>[];
      for (final reminder in reminders) {
        final id = await txn.insert(_table, _toRow(reminder));
        saved.add(reminder.copyWith(id: id));
      }
      return saved;
    });
  }

  @override
  Future<List<MealGlucoseReminder>> getPendingDueBy(DateTime now) async {
    final db = await _db;
    final rows = await db.query(
      _table,
      where: 'status = ? AND due_at <= ?',
      whereArgs: [
        MealGlucoseReminderStatus.pending.name,
        now.toIso8601String(),
      ],
      orderBy: 'due_at ASC, id ASC',
    );
    return rows.map(_fromRow).toList();
  }

  @override
  Future<void> updateStatus(
    int id, {
    required MealGlucoseReminderStatus status,
    int? resolvedMeasurementId,
  }) async {
    final db = await _db;
    await db.update(
      _table,
      {'status': status.name, 'resolved_measurement_id': resolvedMeasurementId},
      where: 'id = ?',
      whereArgs: [id],
    );
  }

  MealGlucoseReminder _fromRow(Map<String, Object?> row) {
    final status =
        MealGlucoseReminderStatus.values.asNameMap()[row['status'] as String] ??
        MealGlucoseReminderStatus.pending;
    return MealGlucoseReminder(
      id: row['id'] as int,
      mealId: row['meal_id'] as int,
      offsetMinutes: row['offset_minutes'] as int,
      dueAt: DateTime.parse(row['due_at'] as String),
      status: status,
      resolvedMeasurementId: row['resolved_measurement_id'] as int?,
    );
  }

  Map<String, Object?> _toRow(MealGlucoseReminder reminder) {
    return {
      'meal_id': reminder.mealId,
      'offset_minutes': reminder.offsetMinutes,
      'due_at': reminder.dueAt.toIso8601String(),
      'status': reminder.status.name,
      'resolved_measurement_id': reminder.resolvedMeasurementId,
    };
  }
}
