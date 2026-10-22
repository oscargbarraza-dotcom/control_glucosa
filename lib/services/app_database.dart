import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';
import 'package:uuid/uuid.dart';

/// Gestiona la única conexión SQLite compartida por todos los repositorios
/// de la app (mediciones de glucosa, comidas, medicamentos, biometría,
/// perfil de usuario, etc.), incluyendo la creación y migración de
/// esquema.
///
/// Centralizar la apertura de la base de datos aquí evita que cada
/// repositorio defina su propia lógica de versión/`onCreate`, lo que sería
/// propenso a desincronizarse a medida que se agregan más tablas.
class AppDatabase {
  /// Crea el gestor de base de datos usando [factory] como fábrica y,
  /// opcionalmente, [databasePath] como ruta explícita del archivo.
  ///
  /// Si [factory] no se provee, usa la fábrica por defecto de `sqflite`
  /// ([databaseFactory]), válida en Android/iOS.
  ///
  /// En tests se puede inyectar `databaseFactoryFfi` de
  /// `sqflite_common_ffi` junto con `inMemoryDatabasePath` como
  /// [databasePath] y [singleInstance] en `false`, para que cada instancia
  /// abra una base de datos en memoria propia y aislada de otras pruebas.
  // No se usan initializing formals (`this._databasePath`, etc.) porque
  // los parámetros deben mantener nombres públicos (`databasePath`,
  // `singleInstance`) para que las pantallas y los tests puedan invocarlos
  // por nombre, mientras los campos internos permanecen privados.
  AppDatabase({
    DatabaseFactory? factory,
    String? databasePath,
    bool singleInstance = true,
  }) : _databaseFactory = factory ?? databaseFactory,
       // ignore: prefer_initializing_formals
       _databasePath = databasePath,
       // ignore: prefer_initializing_formals
       _singleInstance = singleInstance;

  static const _databaseFileName = 'seguimiento_glucosa.db';

  /// Versión actual del esquema. Cada tabla nueva debe sumar su creación en
  /// [_onCreate] (instalaciones nuevas) y en [_onUpgrade] (instalaciones
  /// existentes), incrementando este número.
  static const _schemaVersion = 8;

  final DatabaseFactory _databaseFactory;
  final String? _databasePath;
  final bool _singleInstance;
  Database? _database;

  /// Obtiene la conexión abierta, abriéndola (y migrándola si corresponde)
  /// la primera vez que se solicita.
  Future<Database> get database async {
    final existing = _database;
    if (existing != null) {
      return existing;
    }

    final path =
        _databasePath ??
        p.join(await _databaseFactory.getDatabasesPath(), _databaseFileName);

    final opened = await _databaseFactory.openDatabase(
      path,
      options: OpenDatabaseOptions(
        version: _schemaVersion,
        singleInstance: _singleInstance,
        // Necesario para que SQLite respete `ON DELETE CASCADE` en
        // `meal_food_items` al borrar una comida, y en
        // `medication_intake_items` al borrar una toma (no está activo por
        // defecto en cada conexión).
        onConfigure: (db) => db.execute('PRAGMA foreign_keys = ON'),
        onCreate: (db, version) => _createAll(db),
        onUpgrade: (db, oldVersion, newVersion) => _upgrade(db, oldVersion),
      ),
    );

    _database = opened;
    return opened;
  }

  /// Elimina de forma transaccional **todos** los datos locales del
  /// usuario (historiales, catálogos auxiliares, perfil y
  /// recordatorios), sin borrar el archivo SQLite ni alterar su
  /// esquema. Se usa exclusivamente desde el flujo explícito de
  /// "eliminar cuenta y datos" de la pantalla Cuenta.
  ///
  /// Las tablas hijas se vacían antes que sus tablas padre para no
  /// depender únicamente de `ON DELETE CASCADE` y mantener el método
  /// robusto incluso si una conexión de prueba no habilitó las claves
  /// foráneas.
  Future<void> deleteAllUserData() async {
    final db = await database;
    await db.transaction((txn) async {
      await txn.delete('meal_glucose_reminders');
      await txn.delete('meal_food_items');
      await txn.delete('medication_intake_items');
      await txn.delete('meals');
      await txn.delete('foods');
      await txn.delete('medication_intakes');
      await txn.delete('medications');
      await txn.delete('glucose_measurements');
      await txn.delete('biometric_measurements');
      await txn.delete('user_profile');
    });
  }

  Future<void> _createAll(Database db) async {
    await db.execute(_createGlucoseMeasurementsTable);
    await db.execute(_createFoodsTable);
    await db.execute(_createMealsTable);
    await db.execute(_createMealFoodItemsTable);
    await db.execute(_createMedicationsTable);
    await db.execute(_createMedicationIntakesTable);
    await db.execute(_createMedicationIntakeItemsTable);
    await db.execute(_createBiometricMeasurementsTable);
    await db.execute(_createUserProfileTable);
    await db.execute(_createMealGlucoseRemindersTable);
  }

  Future<void> _upgrade(Database db, int oldVersion) async {
    if (oldVersion < 2) {
      await db.execute(_createFoodsTable);
      await db.execute(_createMealsTable);
      await db.execute(_createMealFoodItemsTable);
    }
    if (oldVersion < 3) {
      await db.execute(_createMedicationsTable);
      await db.execute(_createMedicationIntakesTable);
      await db.execute(_createMedicationIntakeItemsTable);
    }
    if (oldVersion < 4) {
      await db.execute(_createBiometricMeasurementsTable);
    }
    if (oldVersion < 5) {
      await db.execute(
        'ALTER TABLE biometric_measurements ADD COLUMN systolic_pressure INTEGER',
      );
      await db.execute(
        'ALTER TABLE biometric_measurements ADD COLUMN diastolic_pressure INTEGER',
      );
      await db.execute(
        'ALTER TABLE biometric_measurements ADD COLUMN heart_rate_bpm INTEGER',
      );
    }
    if (oldVersion < 6) {
      await db.execute(_createUserProfileTable);
    }
    if (oldVersion < 7) {
      await db.execute(_createMealGlucoseRemindersTable);
    }
    if (oldVersion < 8) {
      await _addUuidColumn(db, 'glucose_measurements');
      await _addUuidColumn(db, 'meals');
      await _addUuidColumn(db, 'medication_intakes');
      await _addUuidColumn(db, 'biometric_measurements');
    }
  }

  /// Agrega la columna `uuid` a una tabla de datos de salud ya existente
  /// (creada en una versión de esquema anterior a la 8, antes de que
  /// [_createAll] la incluyera desde el inicio) y la rellena para cada
  /// fila preexistente.
  ///
  /// SQLite no permite agregar una columna `NOT NULL UNIQUE` con
  /// `ALTER TABLE` cuando la tabla ya tiene filas (no hay forma de
  /// proveer un valor por defecto distinto para cada una), por lo que el
  /// proceso ocurre en tres pasos: agregar la columna sin restricciones,
  /// rellenarla fila por fila con un UUID v4 nuevo, y recién entonces
  /// crear el índice único.
  Future<void> _addUuidColumn(Database db, String table) async {
    await db.execute('ALTER TABLE $table ADD COLUMN uuid TEXT');

    const uuidGenerator = Uuid();
    final rows = await db.query(table, columns: ['id']);
    for (final row in rows) {
      await db.update(
        table,
        {'uuid': uuidGenerator.v4()},
        where: 'id = ?',
        whereArgs: [row['id'] as int],
      );
    }

    await db.execute(
      'CREATE UNIQUE INDEX IF NOT EXISTS idx_${table}_uuid ON $table (uuid)',
    );
  }

  static const _createGlucoseMeasurementsTable = '''
    CREATE TABLE glucose_measurements (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      uuid TEXT NOT NULL UNIQUE,
      value INTEGER NOT NULL,
      moment TEXT NOT NULL,
      measured_at TEXT NOT NULL,
      comment TEXT
    )
  ''';

  static const _createFoodsTable = '''
    CREATE TABLE foods (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE
    )
  ''';

  static const _createMealsTable = '''
    CREATE TABLE meals (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      uuid TEXT NOT NULL UNIQUE,
      type TEXT NOT NULL,
      eaten_at TEXT NOT NULL,
      comment TEXT
    )
  ''';

  static const _createMealFoodItemsTable = '''
    CREATE TABLE meal_food_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      meal_id INTEGER NOT NULL REFERENCES meals (id) ON DELETE CASCADE,
      food_id INTEGER NOT NULL REFERENCES foods (id),
      quantity TEXT NOT NULL
    )
  ''';

  static const _createMedicationsTable = '''
    CREATE TABLE medications (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      default_unit TEXT NOT NULL
    )
  ''';

  static const _createMedicationIntakesTable = '''
    CREATE TABLE medication_intakes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      uuid TEXT NOT NULL UNIQUE,
      taken_at TEXT NOT NULL,
      comment TEXT
    )
  ''';

  static const _createMedicationIntakeItemsTable = '''
    CREATE TABLE medication_intake_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      intake_id INTEGER NOT NULL
        REFERENCES medication_intakes (id) ON DELETE CASCADE,
      medication_id INTEGER NOT NULL REFERENCES medications (id),
      quantity REAL NOT NULL,
      unit TEXT NOT NULL,
      custom_unit_label TEXT
    )
  ''';

  static const _createBiometricMeasurementsTable = '''
    CREATE TABLE biometric_measurements (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      uuid TEXT NOT NULL UNIQUE,
      weight_kg REAL NOT NULL,
      systolic_pressure INTEGER,
      diastolic_pressure INTEGER,
      heart_rate_bpm INTEGER,
      measured_at TEXT NOT NULL,
      comment TEXT
    )
  ''';

  static const _createUserProfileTable = '''
    CREATE TABLE user_profile (
      id INTEGER PRIMARY KEY,
      height_cm REAL NOT NULL,
      birth_date TEXT,
      biological_sex TEXT,
      display_name TEXT
    )
  ''';

  static const _createMealGlucoseRemindersTable = '''
    CREATE TABLE meal_glucose_reminders (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      meal_id INTEGER NOT NULL REFERENCES meals (id) ON DELETE CASCADE,
      offset_minutes INTEGER NOT NULL,
      due_at TEXT NOT NULL,
      status TEXT NOT NULL,
      resolved_measurement_id INTEGER
    )
  ''';
}
