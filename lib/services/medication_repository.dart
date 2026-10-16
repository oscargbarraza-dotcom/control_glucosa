import 'package:sqflite/sqflite.dart';

import '../models/medication.dart';
import '../models/medication_intake.dart';
import 'app_database.dart';

/// Contrato de persistencia para el historial de tomas de medicamentos y su
/// catálogo de medicamentos.
///
/// Se define como interfaz abstracta para permitir sustituir la
/// implementación (por ejemplo, en pruebas) sin acoplar las pantallas a
/// `sqflite`.
abstract class MedicationRepository {
  /// Recupera el historial completo de tomas (con sus medicamentos),
  /// ordenado de la más reciente a la más antigua.
  Future<List<MedicationIntake>> getAllIntakes();

  /// Guarda [intake] como una nueva toma del historial.
  ///
  /// Los medicamentos de [MedicationIntake.items] se resuelven contra el
  /// catálogo de [Medication] por nombre: si un nombre ya existe, se
  /// reutiliza su [Medication.id]; si no existe, se crea una nueva entrada
  /// en el catálogo (con [Medication.defaultUnit] tomado del primer ítem
  /// que lo use).
  ///
  /// Devuelve la toma persistida, con [MedicationIntake.id] y los `id` de
  /// cada [MedicationIntakeItem] asignados por el almacenamiento.
  Future<MedicationIntake> addIntake(MedicationIntake intake);

  /// Elimina todas las tomas guardadas (no afecta el catálogo de
  /// medicamentos).
  Future<void> clearIntakes();

  /// Recupera el catálogo completo de medicamentos, ordenado
  /// alfabéticamente.
  Future<List<Medication>> getAllMedications();
}

/// Implementación de [MedicationRepository] basada en SQLite (`sqflite`).
///
/// Consume las tablas `medication_intakes`, `medication_intake_items` y
/// `medications` de la base de datos compartida ([AppDatabase]).
class SqliteMedicationRepository implements MedicationRepository {
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
  SqliteMedicationRepository({
    DatabaseFactory? factory,
    String? databasePath,
    bool singleInstance = true,
  }) : _appDatabase = AppDatabase(
         factory: factory,
         databasePath: databasePath,
         singleInstance: singleInstance,
       );

  /// Permite reutilizar una [AppDatabase] ya creada (por ejemplo, la misma
  /// instancia compartida con [SqliteGlucoseRepository] y
  /// [SqliteMealRepository]), en lugar de abrir una conexión nueva.
  SqliteMedicationRepository.withDatabase(AppDatabase appDatabase)
    : _appDatabase = appDatabase;

  static const _intakesTable = 'medication_intakes';
  static const _itemsTable = 'medication_intake_items';
  static const _medicationsTable = 'medications';

  final AppDatabase _appDatabase;

  Future<Database> get _db => _appDatabase.database;

  @override
  Future<List<MedicationIntake>> getAllIntakes() async {
    final db = await _db;
    final intakeRows = await db.query(
      _intakesTable,
      orderBy: 'taken_at DESC, id DESC',
    );

    final intakes = <MedicationIntake>[];
    for (final intakeRow in intakeRows) {
      final items = await _getItemsForIntake(db, intakeRow['id'] as int);
      intakes.add(_intakeFromRow(intakeRow, items));
    }
    return intakes;
  }

  @override
  Future<MedicationIntake> addIntake(MedicationIntake intake) async {
    final db = await _db;

    return db.transaction((txn) async {
      final intakeId = await txn.insert(_intakesTable, _intakeToRow(intake));

      final savedItems = <MedicationIntakeItem>[];
      for (final item in intake.items) {
        final medicationId = await _resolveMedicationId(
          txn,
          item.medication.name,
          item.unit,
        );
        final itemId = await txn.insert(_itemsTable, {
          'intake_id': intakeId,
          'medication_id': medicationId,
          'quantity': item.quantity,
          'unit': item.unit.name,
          'custom_unit_label': item.customUnitLabel,
        });
        savedItems.add(
          MedicationIntakeItem(
            id: itemId,
            medication: Medication(
              id: medicationId,
              name: item.medication.name,
              defaultUnit: item.medication.defaultUnit,
            ),
            quantity: item.quantity,
            unit: item.unit,
            customUnitLabel: item.customUnitLabel,
          ),
        );
      }

      return intake.copyWith(id: intakeId, items: savedItems);
    });
  }

  @override
  Future<void> clearIntakes() async {
    final db = await _db;
    await db.delete(_intakesTable);
  }

  @override
  Future<List<Medication>> getAllMedications() async {
    final db = await _db;
    final rows = await db.query(_medicationsTable, orderBy: 'name ASC');
    return rows.map(_medicationFromRow).toList();
  }

  /// Devuelve el `id` del medicamento llamado [name] en el catálogo,
  /// reutilizando la fila existente si ya hay una con ese nombre (tras
  /// recortar espacios extremos), o creando una nueva con [defaultUnit] en
  /// caso contrario.
  Future<int> _resolveMedicationId(
    DatabaseExecutor txn,
    String name,
    DoseUnit defaultUnit,
  ) async {
    final normalized = name.trim();
    final existing = await txn.query(
      _medicationsTable,
      where: 'name = ?',
      whereArgs: [normalized],
      limit: 1,
    );
    if (existing.isNotEmpty) {
      return existing.first['id'] as int;
    }
    return txn.insert(_medicationsTable, {
      'name': normalized,
      'default_unit': defaultUnit.name,
    });
  }

  Future<List<MedicationIntakeItem>> _getItemsForIntake(
    DatabaseExecutor db,
    int intakeId,
  ) async {
    final rows = await db.rawQuery(
      '''
      SELECT $_itemsTable.id AS item_id,
             $_itemsTable.quantity AS quantity,
             $_itemsTable.unit AS unit,
             $_itemsTable.custom_unit_label AS custom_unit_label,
             $_medicationsTable.id AS medication_id,
             $_medicationsTable.name AS medication_name,
             $_medicationsTable.default_unit AS medication_default_unit
      FROM $_itemsTable
      INNER JOIN $_medicationsTable
        ON $_medicationsTable.id = $_itemsTable.medication_id
      WHERE $_itemsTable.intake_id = ?
      ORDER BY $_itemsTable.id ASC
      ''',
      [intakeId],
    );

    return rows.map((row) {
      return MedicationIntakeItem(
        id: row['item_id'] as int,
        medication: Medication(
          id: row['medication_id'] as int,
          name: row['medication_name'] as String,
          defaultUnit: _parseUnit(row['medication_default_unit'] as String),
        ),
        quantity: (row['quantity'] as num).toDouble(),
        unit: _parseUnit(row['unit'] as String),
        customUnitLabel: row['custom_unit_label'] as String?,
      );
    }).toList();
  }

  Medication _medicationFromRow(Map<String, Object?> row) {
    return Medication(
      id: row['id'] as int,
      name: row['name'] as String,
      defaultUnit: _parseUnit(row['default_unit'] as String),
    );
  }

  DoseUnit _parseUnit(String name) {
    return DoseUnit.values.asNameMap()[name] ?? DoseUnit.other;
  }

  MedicationIntake _intakeFromRow(
    Map<String, Object?> row,
    List<MedicationIntakeItem> items,
  ) {
    return MedicationIntake(
      id: row['id'] as int,
      takenAt: DateTime.parse(row['taken_at'] as String),
      comment: row['comment'] as String?,
      items: items,
    );
  }

  Map<String, Object?> _intakeToRow(MedicationIntake intake) {
    return {
      'taken_at': intake.takenAt.toIso8601String(),
      'comment': intake.comment,
    };
  }
}
