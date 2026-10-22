// Pruebas unitarias para AppDatabase, enfocadas en la migración de
// esquema que agrega la columna `uuid` (versión 7 -> 8) a las cuatro
// tablas de datos de salud.
//
// Usan sqflite_common_ffi sobre un archivo temporal real (no en memoria):
// a diferencia de los demás tests de repositorios, aquí se necesita
// cerrar y reabrir la misma base de datos con una versión de esquema
// distinta para simular una instalación existente, lo que una base en
// memoria no permite (se destruye al cerrar la conexión).

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as p;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'package:seguimiento_glucosa/services/app_database.dart';

void main() {
  setUpAll(() {
    sqfliteFfiInit();
  });

  late Directory tempDir;
  late String dbPath;

  setUp(() {
    tempDir = Directory.systemTemp.createTempSync('app_database_test');
    dbPath = p.join(tempDir.path, 'test.db');
  });

  tearDown(() {
    tempDir.deleteSync(recursive: true);
  });

  test(
    'una instalación nueva crea la columna uuid como NOT NULL UNIQUE',
    () async {
      final appDatabase = AppDatabase(
        factory: databaseFactoryFfi,
        databasePath: dbPath,
      );
      final db = await appDatabase.database;

      await db.insert('glucose_measurements', {
        'uuid': 'uuid-1',
        'value': 100,
        'moment': 'now',
        'measured_at': DateTime(2026, 1, 1).toIso8601String(),
      });

      // El índice único rechaza un uuid repetido.
      await expectLater(
        db.insert('glucose_measurements', {
          'uuid': 'uuid-1',
          'value': 110,
          'moment': 'now',
          'measured_at': DateTime(2026, 1, 2).toIso8601String(),
        }),
        throwsA(isA<DatabaseException>()),
      );

      await db.close();
    },
  );

  test(
    'al migrar desde la versión 7 (sin columna uuid), rellena un uuid '
    'único por cada fila ya existente en las cuatro tablas de salud',
    () async {
      final legacy = await _openLegacyV7Database(dbPath);

      final glucoseId = await legacy.insert('glucose_measurements', {
        'value': 100,
        'moment': 'now',
        'measured_at': DateTime(2026, 1, 1).toIso8601String(),
      });
      final mealId = await legacy.insert('meals', {
        'type': 'breakfast',
        'eaten_at': DateTime(2026, 1, 1, 8).toIso8601String(),
      });
      final intakeId = await legacy.insert('medication_intakes', {
        'taken_at': DateTime(2026, 1, 1, 8).toIso8601String(),
      });
      final biometricId = await legacy.insert('biometric_measurements', {
        'weight_kg': 70.0,
        'measured_at': DateTime(2026, 1, 1).toIso8601String(),
      });
      await legacy.close();

      // Reabre con AppDatabase (versión actual), lo que dispara la
      // migración 7 -> 8 sobre la base ya existente.
      final appDatabase = AppDatabase(
        factory: databaseFactoryFfi,
        databasePath: dbPath,
      );
      final upgraded = await appDatabase.database;

      final glucoseUuid = await _uuidOf(
        upgraded,
        'glucose_measurements',
        glucoseId,
      );
      final mealUuid = await _uuidOf(upgraded, 'meals', mealId);
      final intakeUuid = await _uuidOf(
        upgraded,
        'medication_intakes',
        intakeId,
      );
      final biometricUuid = await _uuidOf(
        upgraded,
        'biometric_measurements',
        biometricId,
      );

      expect(glucoseUuid, isNotEmpty);
      expect(mealUuid, isNotEmpty);
      expect(intakeUuid, isNotEmpty);
      expect(biometricUuid, isNotEmpty);
      // Los cuatro uuid generados deben ser distintos entre sí.
      expect({glucoseUuid, mealUuid, intakeUuid, biometricUuid}, hasLength(4));

      // El índice único creado por la migración también rechaza un uuid
      // repetido en adelante.
      await expectLater(
        upgraded.insert('glucose_measurements', {
          'uuid': glucoseUuid,
          'value': 200,
          'moment': 'now',
          'measured_at': DateTime(2026, 1, 3).toIso8601String(),
        }),
        throwsA(isA<DatabaseException>()),
      );

      await upgraded.close();
    },
  );

  test(
    'deleteAllUserData vacía datos, catálogos, perfil y recordatorios',
    () async {
      final appDatabase = AppDatabase(
        factory: databaseFactoryFfi,
        databasePath: dbPath,
      );
      final db = await appDatabase.database;

      final mealId = await db.insert('meals', {
        'uuid': 'meal-1',
        'type': 'breakfast',
        'eaten_at': DateTime(2026, 1, 1, 8).toIso8601String(),
      });
      final foodId = await db.insert('foods', {'name': 'Pan'});
      await db.insert('meal_food_items', {
        'meal_id': mealId,
        'food_id': foodId,
        'quantity': '1 unidad',
      });
      await db.insert('meal_glucose_reminders', {
        'meal_id': mealId,
        'offset_minutes': 60,
        'due_at': DateTime(2026, 1, 1, 9).toIso8601String(),
        'status': 'pending',
      });

      final intakeId = await db.insert('medication_intakes', {
        'uuid': 'intake-1',
        'taken_at': DateTime(2026, 1, 1, 8).toIso8601String(),
      });
      final medicationId = await db.insert('medications', {
        'name': 'Insulina',
        'default_unit': 'units',
      });
      await db.insert('medication_intake_items', {
        'intake_id': intakeId,
        'medication_id': medicationId,
        'quantity': 1.0,
        'unit': 'units',
      });
      await db.insert('glucose_measurements', {
        'uuid': 'glucose-1',
        'value': 100,
        'moment': 'now',
        'measured_at': DateTime(2026, 1, 1).toIso8601String(),
      });
      await db.insert('biometric_measurements', {
        'uuid': 'biometric-1',
        'weight_kg': 70.0,
        'measured_at': DateTime(2026, 1, 1).toIso8601String(),
      });
      await db.insert('user_profile', {'id': 1, 'height_cm': 170.0});

      await appDatabase.deleteAllUserData();

      for (final table in [
        'meal_glucose_reminders',
        'meal_food_items',
        'medication_intake_items',
        'meals',
        'foods',
        'medication_intakes',
        'medications',
        'glucose_measurements',
        'biometric_measurements',
        'user_profile',
      ]) {
        expect(await db.query(table), isEmpty, reason: 'tabla $table');
      }

      await db.close();
    },
  );
}

/// Abre, en [dbPath], un esquema mínimo equivalente a la versión 7 (sin
/// la columna `uuid`) para las cuatro tablas afectadas por la migración
/// bajo prueba. No incluye el resto de las tablas de la v7 (`foods`,
/// `medications`, etc.) porque la migración (`oldVersion < 8`) no las
/// toca.
Future<Database> _openLegacyV7Database(String dbPath) {
  return databaseFactoryFfi.openDatabase(
    dbPath,
    options: OpenDatabaseOptions(
      version: 7,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE glucose_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            value INTEGER NOT NULL,
            moment TEXT NOT NULL,
            measured_at TEXT NOT NULL,
            comment TEXT
          )
        ''');
        await db.execute('''
          CREATE TABLE meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            eaten_at TEXT NOT NULL,
            comment TEXT
          )
        ''');
        await db.execute('''
          CREATE TABLE medication_intakes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            taken_at TEXT NOT NULL,
            comment TEXT
          )
        ''');
        await db.execute('''
          CREATE TABLE biometric_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weight_kg REAL NOT NULL,
            systolic_pressure INTEGER,
            diastolic_pressure INTEGER,
            heart_rate_bpm INTEGER,
            measured_at TEXT NOT NULL,
            comment TEXT
          )
        ''');
      },
    ),
  );
}

Future<String> _uuidOf(Database db, String table, int id) async {
  final rows = await db.query(table, where: 'id = ?', whereArgs: [id]);
  return rows.single['uuid'] as String;
}
