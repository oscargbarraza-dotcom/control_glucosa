import 'package:sqflite/sqflite.dart';

import '../models/biometric_measurement.dart';
import 'app_database.dart';

/// Contrato de persistencia para el historial de mediciones biométricas
/// (peso corporal, y opcionalmente presión arterial y frecuencia
/// cardíaca).
///
/// Se define como interfaz abstracta para permitir sustituir la
/// implementación (por ejemplo, en pruebas) sin acoplar las pantallas a
/// `sqflite`.
abstract class BiometricRepository {
  /// Recupera la medición más reciente, o `null` si no existe ninguna.
  Future<BiometricMeasurement?> getLastMeasurement();

  /// Recupera el historial completo de mediciones, ordenado de la más
  /// reciente a la más antigua.
  Future<List<BiometricMeasurement>> getAllMeasurements();

  /// Guarda [measurement] como una nueva medición del historial.
  ///
  /// Devuelve la medición persistida, con [BiometricMeasurement.id]
  /// asignado por el almacenamiento.
  Future<BiometricMeasurement> addMeasurement(BiometricMeasurement measurement);

  /// Elimina todas las mediciones guardadas.
  Future<void> clearMeasurements();
}

/// Implementación de [BiometricRepository] basada en SQLite (`sqflite`).
///
/// Consume la tabla `biometric_measurements` de la base de datos
/// compartida ([AppDatabase]), permitiendo tanto obtener la última
/// medición como listar todo el historial para la pantalla
/// correspondiente.
class SqliteBiometricRepository implements BiometricRepository {
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
  SqliteBiometricRepository({
    DatabaseFactory? factory,
    String? databasePath,
    bool singleInstance = true,
  }) : _appDatabase = AppDatabase(
         factory: factory,
         databasePath: databasePath,
         singleInstance: singleInstance,
       );

  /// Permite reutilizar una [AppDatabase] ya creada (por ejemplo, la misma
  /// instancia compartida con [SqliteGlucoseRepository]), en lugar de
  /// abrir una conexión nueva.
  SqliteBiometricRepository.withDatabase(AppDatabase appDatabase)
    : _appDatabase = appDatabase;

  static const _table = 'biometric_measurements';

  final AppDatabase _appDatabase;

  Future<Database> get _db => _appDatabase.database;

  @override
  Future<BiometricMeasurement?> getLastMeasurement() async {
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
  Future<List<BiometricMeasurement>> getAllMeasurements() async {
    final db = await _db;
    final rows = await db.query(_table, orderBy: 'measured_at DESC, id DESC');
    return rows.map(_fromRow).toList();
  }

  @override
  Future<BiometricMeasurement> addMeasurement(
    BiometricMeasurement measurement,
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

  BiometricMeasurement _fromRow(Map<String, Object?> row) {
    return BiometricMeasurement(
      id: row['id'] as int,
      uuid: row['uuid'] as String,
      weightKg: (row['weight_kg'] as num).toDouble(),
      systolicPressure: row['systolic_pressure'] as int?,
      diastolicPressure: row['diastolic_pressure'] as int?,
      heartRateBpm: row['heart_rate_bpm'] as int?,
      measuredAt: DateTime.parse(row['measured_at'] as String),
      comment: row['comment'] as String?,
    );
  }

  Map<String, Object?> _toRow(BiometricMeasurement measurement) {
    return {
      'uuid': measurement.uuid,
      'weight_kg': measurement.weightKg,
      'systolic_pressure': measurement.systolicPressure,
      'diastolic_pressure': measurement.diastolicPressure,
      'heart_rate_bpm': measurement.heartRateBpm,
      'measured_at': measurement.measuredAt.toIso8601String(),
      'comment': measurement.comment,
    };
  }
}
