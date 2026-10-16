// Pruebas unitarias para SqliteBiometricRepository.
//
// Usan sqflite_common_ffi para ejecutar sobre una base de datos SQLite en
// memoria, sin depender del plugin nativo de Android/iOS.

import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'package:seguimiento_glucosa/models/biometric_measurement.dart';
import 'package:seguimiento_glucosa/services/biometric_repository.dart';

void main() {
  setUpAll(() {
    sqfliteFfiInit();
  });

  // singleInstance: false asegura que cada repositorio abra su propia base
  // de datos en memoria, completamente aislada de las demás pruebas.
  SqliteBiometricRepository createRepository() {
    return SqliteBiometricRepository(
      factory: databaseFactoryFfi,
      databasePath: inMemoryDatabasePath,
      singleInstance: false,
    );
  }

  test('getLastMeasurement devuelve null cuando no hay datos', () async {
    final repository = createRepository();
    expect(await repository.getLastMeasurement(), isNull);
  });

  test('addMeasurement persiste y asigna un id autogenerado', () async {
    final repository = createRepository();

    final saved = await repository.addMeasurement(
      BiometricMeasurement(
        weightKg: 70.5,
        measuredAt: DateTime(2026, 1, 1, 8),
        comment: 'prueba',
      ),
    );

    expect(saved.id, isNotNull);
    expect(saved.weightKg, 70.5);
    expect(saved.comment, 'prueba');
  });

  test('getLastMeasurement devuelve la medición más reciente', () async {
    final repository = createRepository();

    await repository.addMeasurement(
      BiometricMeasurement(weightKg: 70, measuredAt: DateTime(2026, 1, 1, 8)),
    );
    await repository.addMeasurement(
      BiometricMeasurement(weightKg: 69, measuredAt: DateTime(2026, 1, 2, 8)),
    );

    final last = await repository.getLastMeasurement();
    expect(last?.weightKg, 69);
  });

  test('getAllMeasurements ordena de más reciente a más antigua', () async {
    final repository = createRepository();

    await repository.addMeasurement(
      BiometricMeasurement(weightKg: 72, measuredAt: DateTime(2026, 1, 1, 7)),
    );
    await repository.addMeasurement(
      BiometricMeasurement(weightKg: 68, measuredAt: DateTime(2026, 1, 3, 7)),
    );
    await repository.addMeasurement(
      BiometricMeasurement(weightKg: 70, measuredAt: DateTime(2026, 1, 2, 7)),
    );

    final all = await repository.getAllMeasurements();
    expect(all.map((m) => m.weightKg).toList(), [68, 70, 72]);
  });

  test('addMeasurement persiste presión arterial y frecuencia cardíaca '
      'opcionales', () async {
    final repository = createRepository();

    final saved = await repository.addMeasurement(
      BiometricMeasurement(
        weightKg: 80,
        systolicPressure: 120,
        diastolicPressure: 80,
        heartRateBpm: 70,
        measuredAt: DateTime(2026, 1, 1, 8),
      ),
    );

    expect(saved.systolicPressure, 120);
    expect(saved.diastolicPressure, 80);
    expect(saved.heartRateBpm, 70);

    final reloaded = await repository.getLastMeasurement();
    expect(reloaded?.systolicPressure, 120);
    expect(reloaded?.diastolicPressure, 80);
    expect(reloaded?.heartRateBpm, 70);
  });

  test('addMeasurement sin presión ni frecuencia cardíaca guarda esos campos '
      'como null', () async {
    final repository = createRepository();

    final saved = await repository.addMeasurement(
      BiometricMeasurement(weightKg: 65, measuredAt: DateTime(2026, 1, 1)),
    );

    expect(saved.systolicPressure, isNull);
    expect(saved.diastolicPressure, isNull);
    expect(saved.heartRateBpm, isNull);
    expect(saved.hasBloodPressure, isFalse);
  });

  test('clearMeasurements elimina todo el historial', () async {
    final repository = createRepository();

    await repository.addMeasurement(
      BiometricMeasurement(weightKg: 70, measuredAt: DateTime(2026, 1, 1)),
    );
    await repository.clearMeasurements();

    expect(await repository.getAllMeasurements(), isEmpty);
    expect(await repository.getLastMeasurement(), isNull);
  });
}
