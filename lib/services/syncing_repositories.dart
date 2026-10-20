// Decoradores que envuelven cada repositorio local (SQLite) para
// disparar la sincronización automática y silenciosa en la nube
// (roadmap: "Sincronización en tiempo real") justo después de guardar
// un registro nuevo, sin cambiar el contrato que ya consumen las
// pantallas.
//
// El envío a la nube (`CloudSyncRepository.pushGlucoseMeasurement` y
// equivalentes) nunca lanza excepciones ni retrasa la respuesta a
// quien llamó a `addX`: se dispara sin esperarlo (`unawaited`), porque
// SQLite ya es la fuente de verdad local y la app debe seguir
// funcionando igual con o sin conexión.
//
// Se requieren parámetros con nombre explícito (`delegate: ...`,
// `syncRepository: ...`) para legibilidad en el sitio de construcción;
// con initializing formals el nombre externo del parámetro quedaría
// igual al del campo privado (`_delegate`), lo que no es válido para
// parámetros nombrados.
// ignore_for_file: prefer_initializing_formals

import 'dart:async';

import '../models/biometric_measurement.dart';
import '../models/food.dart';
import '../models/glucose_measurement.dart';
import '../models/meal.dart';
import '../models/medication.dart';
import '../models/medication_intake.dart';
import 'biometric_repository.dart';
import 'cloud_sync_repository.dart';
import 'glucose_repository.dart';
import 'meal_repository.dart';
import 'medication_repository.dart';

/// Envuelve un [GlucoseRepository] para sincronizar cada medición nueva
/// con la nube automáticamente al guardarla.
class SyncingGlucoseRepository implements GlucoseRepository {
  SyncingGlucoseRepository({
    required GlucoseRepository delegate,
    required CloudSyncRepository syncRepository,
  }) : _delegate = delegate,
       _syncRepository = syncRepository;

  final GlucoseRepository _delegate;
  final CloudSyncRepository _syncRepository;

  @override
  Future<GlucoseMeasurement?> getLastMeasurement() =>
      _delegate.getLastMeasurement();

  @override
  Future<List<GlucoseMeasurement>> getAllMeasurements() =>
      _delegate.getAllMeasurements();

  @override
  Future<void> clearMeasurements() => _delegate.clearMeasurements();

  @override
  Future<GlucoseMeasurement> addMeasurement(
    GlucoseMeasurement measurement,
  ) async {
    final saved = await _delegate.addMeasurement(measurement);
    unawaited(_syncRepository.pushGlucoseMeasurement(saved));
    return saved;
  }
}

/// Envuelve un [MealRepository] para sincronizar cada comida nueva con
/// la nube automáticamente al guardarla.
class SyncingMealRepository implements MealRepository {
  SyncingMealRepository({
    required MealRepository delegate,
    required CloudSyncRepository syncRepository,
  }) : _delegate = delegate,
       _syncRepository = syncRepository;

  final MealRepository _delegate;
  final CloudSyncRepository _syncRepository;

  @override
  Future<List<Meal>> getAllMeals() => _delegate.getAllMeals();

  @override
  Future<List<Food>> getAllFoods() => _delegate.getAllFoods();

  @override
  Future<void> clearMeals() => _delegate.clearMeals();

  @override
  Future<Meal> addMeal(Meal meal) async {
    final saved = await _delegate.addMeal(meal);
    unawaited(_syncRepository.pushMeal(saved));
    return saved;
  }
}

/// Envuelve un [MedicationRepository] para sincronizar cada toma nueva
/// con la nube automáticamente al guardarla.
class SyncingMedicationRepository implements MedicationRepository {
  SyncingMedicationRepository({
    required MedicationRepository delegate,
    required CloudSyncRepository syncRepository,
  }) : _delegate = delegate,
       _syncRepository = syncRepository;

  final MedicationRepository _delegate;
  final CloudSyncRepository _syncRepository;

  @override
  Future<List<MedicationIntake>> getAllIntakes() => _delegate.getAllIntakes();

  @override
  Future<List<Medication>> getAllMedications() =>
      _delegate.getAllMedications();

  @override
  Future<void> clearIntakes() => _delegate.clearIntakes();

  @override
  Future<MedicationIntake> addIntake(MedicationIntake intake) async {
    final saved = await _delegate.addIntake(intake);
    unawaited(_syncRepository.pushMedicationIntake(saved));
    return saved;
  }
}

/// Envuelve un [BiometricRepository] para sincronizar cada medición
/// nueva con la nube automáticamente al guardarla.
class SyncingBiometricRepository implements BiometricRepository {
  SyncingBiometricRepository({
    required BiometricRepository delegate,
    required CloudSyncRepository syncRepository,
  }) : _delegate = delegate,
       _syncRepository = syncRepository;

  final BiometricRepository _delegate;
  final CloudSyncRepository _syncRepository;

  @override
  Future<BiometricMeasurement?> getLastMeasurement() =>
      _delegate.getLastMeasurement();

  @override
  Future<List<BiometricMeasurement>> getAllMeasurements() =>
      _delegate.getAllMeasurements();

  @override
  Future<void> clearMeasurements() => _delegate.clearMeasurements();

  @override
  Future<BiometricMeasurement> addMeasurement(
    BiometricMeasurement measurement,
  ) async {
    final saved = await _delegate.addMeasurement(measurement);
    unawaited(_syncRepository.pushBiometricMeasurement(saved));
    return saved;
  }
}
