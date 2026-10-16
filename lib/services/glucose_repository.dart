import 'package:sqflite/sqflite.dart';

import '../models/glucose_measurement.dart';
import 'app_database.dart';

/// Contrato de persistencia para el historial de mediciones de glucosa.
///
/// Se define como interfaz abstracta para permitir sustituir la
/// implementación (por ejemplo, en pruebas) sin acoplar las pantallas a
/// `sqflite`.
abstract class GlucoseRepository {
  /// Recupera la medición más reciente, o `null` si no existe ninguna.
  Future<GlucoseMeasurement?> getLastMeasurement();

  /// Recupera el historial completo de mediciones, ordenado de la más
  /// reciente a la más antigua.
  Future<List<GlucoseMeasurement>> getAllMeasurements();

  /// Guarda [measurement] como una nueva medición del historial.
  ///
  /// Devuelve la medición persistida, con [GlucoseMeasurement.id] asignado
  /// por el almacenamiento.
  Future<GlucoseMeasurement> addMeasurement(GlucoseMeasurement measurement);

  /// Elimina todas las mediciones guardadas.
  Future<void> clearMeasurements();
}

/// Implementación de [GlucoseRepository] basada en SQLite (`sqflite`).
///
/// Consume la tabla `glucose_measurements` de la base de datos compartida
/// ([AppDatabase]), permitiendo tanto obtener la última medición como
/// listar todo el historial para la pantalla correspondiente.
class SqliteGlucoseRepository implements GlucoseRepository {
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
  SqliteGlucoseRepository({
    DatabaseFactory? factory,
    String? databasePath,
    bool singleInstance = true,
  }) : _appDatabase = AppDatabase(
         factory: factory,
         databasePath: databasePath,
         singleInstance: singleInstance,
       );

  /// Permite reutilizar una [AppDatabase] ya creada (por ejemplo, la misma
  /// instancia compartida con [SqliteMealRepository]), en lugar de abrir
  /// una conexión nueva.
  SqliteGlucoseRepository.withDatabase(AppDatabase appDatabase)
    : _appDatabase = appDatabase;

  static const _table = 'glucose_measurements';

  final AppDatabase _appDatabase;

  Future<Database> get _db => _appDatabase.database;

  @override
  Future<GlucoseMeasurement?> getLastMeasurement() async {
    final db = await _db;
    final rows = await db.query(
      _table,
      orderBy: 'measured_at DESC, id DESC',
      limit: 1,
    );
    if (rows.isEmpty) {
      return null;
    }
    return _fromRow(rows.first);
  }

  @override
  Future<List<GlucoseMeasurement>> getAllMeasurements() async {
    final db = await _db;
    final rows = await db.query(_table, orderBy: 'measured_at DESC, id DESC');
    return rows.map(_fromRow).toList();
  }

  @override
  Future<GlucoseMeasurement> addMeasurement(
    GlucoseMeasurement measurement,
  ) async {
    final db = await _db;
    final id = await db.insert(_table, _toRow(measurement));
    return measurement.copyWith(id: id);
  }

  @override
  Future<void> clearMeasurements() async {
    final db = await _db;
    await db.delete(_table);
  }

  GlucoseMeasurement _fromRow(Map<String, Object?> row) {
    final moment =
        GlucoseMoment.values.asNameMap()[row['moment'] as String] ??
        GlucoseMoment.now;
    return GlucoseMeasurement(
      id: row['id'] as int,
      value: row['value'] as int,
      moment: moment,
      measuredAt: DateTime.parse(row['measured_at'] as String),
      comment: row['comment'] as String?,
    );
  }

  Map<String, Object?> _toRow(GlucoseMeasurement measurement) {
    return {
      'value': measurement.value,
      'moment': measurement.moment.name,
      'measured_at': measurement.measuredAt.toIso8601String(),
      'comment': measurement.comment,
    };
  }
}
