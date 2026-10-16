// Pruebas unitarias para SqliteMedicationRepository.
//
// Usan sqflite_common_ffi para ejecutar sobre una base de datos SQLite en
// memoria, sin depender del plugin nativo de Android/iOS.

import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'package:seguimiento_glucosa/models/medication.dart';
import 'package:seguimiento_glucosa/models/medication_intake.dart';
import 'package:seguimiento_glucosa/services/medication_repository.dart';

void main() {
  setUpAll(() {
    sqfliteFfiInit();
  });

  // singleInstance: false asegura que cada repositorio abra su propia base
  // de datos en memoria, completamente aislada de las demás pruebas.
  SqliteMedicationRepository createRepository() {
    return SqliteMedicationRepository(
      factory: databaseFactoryFfi,
      databasePath: inMemoryDatabasePath,
      singleInstance: false,
    );
  }

  test('getAllIntakes devuelve lista vacía cuando no hay datos', () async {
    final repository = createRepository();
    expect(await repository.getAllIntakes(), isEmpty);
  });

  test('addIntake persiste la toma y asigna ids a toma e items', () async {
    final repository = createRepository();

    final saved = await repository.addIntake(
      MedicationIntake(
        takenAt: DateTime(2026, 1, 1, 8),
        comment: 'prueba',
        items: [
          MedicationIntakeItem(
            medication: const Medication(
              name: 'Metformina',
              defaultUnit: DoseUnit.milligram,
            ),
            quantity: 500,
            unit: DoseUnit.milligram,
          ),
          MedicationIntakeItem(
            medication: const Medication(
              name: 'Insulina',
              defaultUnit: DoseUnit.unit,
            ),
            quantity: 10,
            unit: DoseUnit.unit,
          ),
        ],
      ),
    );

    expect(saved.id, isNotNull);
    expect(saved.comment, 'prueba');
    expect(saved.items, hasLength(2));
    expect(saved.items[0].id, isNotNull);
    expect(saved.items[0].medication.id, isNotNull);
    expect(saved.items[0].medication.name, 'Metformina');
    expect(saved.items[0].quantity, 500);
    expect(saved.items[1].medication.name, 'Insulina');
  });

  test('addIntake reutiliza un medicamento existente en el catálogo', () async {
    final repository = createRepository();

    final first = await repository.addIntake(
      MedicationIntake(
        takenAt: DateTime(2026, 1, 1, 8),
        items: [
          MedicationIntakeItem(
            medication: const Medication(
              name: 'Metformina',
              defaultUnit: DoseUnit.milligram,
            ),
            quantity: 500,
            unit: DoseUnit.milligram,
          ),
        ],
      ),
    );
    final second = await repository.addIntake(
      MedicationIntake(
        takenAt: DateTime(2026, 1, 1, 20),
        items: [
          MedicationIntakeItem(
            medication: const Medication(
              name: 'Metformina',
              defaultUnit: DoseUnit.milligram,
            ),
            quantity: 850,
            unit: DoseUnit.milligram,
          ),
        ],
      ),
    );

    expect(first.items.single.medication.id, second.items.single.medication.id);
    expect(await repository.getAllMedications(), hasLength(1));
  });

  test('addIntake respeta una unidad personalizada (DoseUnit.other)', () async {
    final repository = createRepository();

    final saved = await repository.addIntake(
      MedicationIntake(
        takenAt: DateTime(2026, 1, 1, 9),
        items: [
          MedicationIntakeItem(
            medication: const Medication(
              name: 'Parche de nicotina',
              defaultUnit: DoseUnit.other,
            ),
            quantity: 1,
            unit: DoseUnit.other,
            customUnitLabel: 'parche',
          ),
        ],
      ),
    );

    expect(saved.items.single.unit, DoseUnit.other);
    expect(saved.items.single.customUnitLabel, 'parche');
    expect(saved.items.single.effectiveUnitLabel, 'parche');
  });

  test(
    'getAllIntakes ordena de más reciente a más antigua, con sus items',
    () async {
      final repository = createRepository();

      await repository.addIntake(
        MedicationIntake(
          takenAt: DateTime(2026, 1, 1, 8),
          items: [
            MedicationIntakeItem(
              medication: const Medication(
                name: 'Metformina',
                defaultUnit: DoseUnit.milligram,
              ),
              quantity: 500,
              unit: DoseUnit.milligram,
            ),
          ],
        ),
      );
      await repository.addIntake(
        MedicationIntake(
          takenAt: DateTime(2026, 1, 2, 21),
          items: [
            MedicationIntakeItem(
              medication: const Medication(
                name: 'Insulina',
                defaultUnit: DoseUnit.unit,
              ),
              quantity: 10,
              unit: DoseUnit.unit,
            ),
          ],
        ),
      );

      final all = await repository.getAllIntakes();
      expect(all.map((i) => i.items.single.medication.name).toList(), [
        'Insulina',
        'Metformina',
      ]);
    },
  );

  test('clearIntakes elimina las tomas pero conserva el catálogo', () async {
    final repository = createRepository();

    await repository.addIntake(
      MedicationIntake(
        takenAt: DateTime(2026, 1, 1),
        items: [
          MedicationIntakeItem(
            medication: const Medication(
              name: 'Aspirina',
              defaultUnit: DoseUnit.tablet,
            ),
            quantity: 1,
            unit: DoseUnit.tablet,
          ),
        ],
      ),
    );
    await repository.clearIntakes();

    expect(await repository.getAllIntakes(), isEmpty);
    expect(await repository.getAllMedications(), hasLength(1));
  });
}
