// Pruebas unitarias para SqliteGlucoseRepository.
//
// Usan sqflite_common_ffi para ejecutar sobre una base de datos SQLite en
// memoria, sin depender del plugin nativo de Android/iOS.

import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'package:seguimiento_glucosa/models/glucose_measurement.dart';
import 'package:seguimiento_glucosa/services/glucose_repository.dart';

void main() {
  setUpAll(() {
    sqfliteFfiInit();
  });

  // singleInstance: false asegura que cada repositorio abra su propia base
  // de datos en memoria, completamente aislada de las demás pruebas (sin
  // esto, sqflite cachearía y reutilizaría una única conexión por path,
  // incluyendo ':memory:').
  SqliteGlucoseRepository createRepository() {
    return SqliteGlucoseRepository(
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
      GlucoseMeasurement(
        value: 110,
        moment: GlucoseMoment.beforeLunch,
        measuredAt: DateTime(2026, 1, 1, 13),
        comment: 'prueba',
      ),
    );

    expect(saved.id, isNotNull);
    expect(saved.value, 110);
    expect(saved.comment, 'prueba');
  });

  test('getLastMeasurement devuelve la medición más reciente', () async {
    final repository = createRepository();

    await repository.addMeasurement(
      GlucoseMeasurement(
        value: 100,
        moment: GlucoseMoment.beforeBreakfast,
        measuredAt: DateTime(2026, 1, 1, 8),
      ),
    );
    await repository.addMeasurement(
      GlucoseMeasurement(
        value: 140,
        moment: GlucoseMoment.afterDinner,
        measuredAt: DateTime(2026, 1, 2, 21),
      ),
    );

    final last = await repository.getLastMeasurement();
    expect(last?.value, 140);
  });

  test('getAllMeasurements ordena de más reciente a más antigua', () async {
    final repository = createRepository();

    await repository.addMeasurement(
      GlucoseMeasurement(
        value: 90,
        moment: GlucoseMoment.wakingUp,
        measuredAt: DateTime(2026, 1, 1, 7),
      ),
    );
    await repository.addMeasurement(
      GlucoseMeasurement(
        value: 130,
        moment: GlucoseMoment.beforeSleep,
        measuredAt: DateTime(2026, 1, 3, 23),
      ),
    );
    await repository.addMeasurement(
      GlucoseMeasurement(
        value: 115,
        moment: GlucoseMoment.afterLunch,
        measuredAt: DateTime(2026, 1, 2, 14),
      ),
    );

    final all = await repository.getAllMeasurements();
    expect(all.map((m) => m.value).toList(), [130, 115, 90]);
  });

  test(
    'addMeasurement genera un uuid distinto por cada medición cuando no '
    'se provee uno',
    () async {
      final repository = createRepository();

      final first = await repository.addMeasurement(
        GlucoseMeasurement(
          value: 100,
          moment: GlucoseMoment.now,
          measuredAt: DateTime(2026, 1, 1),
        ),
      );
      final second = await repository.addMeasurement(
        GlucoseMeasurement(
          value: 110,
          moment: GlucoseMoment.now,
          measuredAt: DateTime(2026, 1, 2),
        ),
      );

      expect(first.uuid, isNotEmpty);
      expect(second.uuid, isNotEmpty);
      expect(first.uuid, isNot(second.uuid));
    },
  );

  test('el uuid persiste al recargar el historial desde SQLite', () async {
    final repository = createRepository();

    final saved = await repository.addMeasurement(
      GlucoseMeasurement(
        value: 120,
        moment: GlucoseMoment.afterLunch,
        measuredAt: DateTime(2026, 1, 1, 14),
      ),
    );

    final reloaded = await repository.getLastMeasurement();
    expect(reloaded?.uuid, saved.uuid);
  });

  test('clearMeasurements elimina todo el historial', () async {
    final repository = createRepository();

    await repository.addMeasurement(
      GlucoseMeasurement(
        value: 100,
        moment: GlucoseMoment.now,
        measuredAt: DateTime(2026, 1, 1),
      ),
    );
    await repository.clearMeasurements();

    expect(await repository.getAllMeasurements(), isEmpty);
    expect(await repository.getLastMeasurement(), isNull);
  });
}
