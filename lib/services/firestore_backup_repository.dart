import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart' as fb_auth;

import '../models/biometric_measurement.dart';
import '../models/food.dart';
import '../models/glucose_measurement.dart';
import '../models/meal.dart';
import '../models/medication.dart';
import '../models/medication_intake.dart';
import 'backup_repository.dart';
import 'biometric_repository.dart';
import 'glucose_repository.dart';
import 'meal_repository.dart';
import 'medication_repository.dart';

/// Implementación de [BackupRepository] basada en Cloud Firestore.
///
/// Guarda un único documento por usuario (`backups/{uid}`) con una
/// copia serializada de las cuatro colecciones de datos de salud. No es
/// apta para historiales extremadamente largos (Firestore limita cada
/// documento a 1 MiB), lo cual es razonable para el uso personal de
/// esta app; si se vuelve una limitación real, la solución futura es
/// dividir el respaldo en subcolecciones en lugar de un solo documento.
class FirestoreBackupRepository implements BackupRepository {
  FirestoreBackupRepository({
    fb_auth.FirebaseAuth? firebaseAuth,
    FirebaseFirestore? firestore,
    required GlucoseRepository glucoseRepository,
    required MealRepository mealRepository,
    required MedicationRepository medicationRepository,
    required BiometricRepository biometricRepository,
  }) : _firebaseAuth = firebaseAuth ?? fb_auth.FirebaseAuth.instance,
       _firestore = firestore ?? FirebaseFirestore.instance,
       // Se requieren parámetros con nombre explícito para legibilidad
       // en el sitio de construcción (p. ej. `glucoseRepository: ...`),
       // por lo que no se usan initializing formals aquí.
       // ignore: prefer_initializing_formals
       _glucoseRepository = glucoseRepository,
       // ignore: prefer_initializing_formals
       _mealRepository = mealRepository,
       // ignore: prefer_initializing_formals
       _medicationRepository = medicationRepository,
       // ignore: prefer_initializing_formals
       _biometricRepository = biometricRepository;

  final fb_auth.FirebaseAuth _firebaseAuth;
  final FirebaseFirestore _firestore;
  final GlucoseRepository _glucoseRepository;
  final MealRepository _mealRepository;
  final MedicationRepository _medicationRepository;
  final BiometricRepository _biometricRepository;

  static const _collection = 'backups';

  String _requireUid() {
    final uid = _firebaseAuth.currentUser?.uid;
    if (uid == null) {
      throw const BackupException(
        'Inicia sesión para respaldar o restaurar tus datos.',
      );
    }
    return uid;
  }

  @override
  Future<void> backup() async {
    final uid = _requireUid();

    try {
      final glucose = await _glucoseRepository.getAllMeasurements();
      final meals = await _mealRepository.getAllMeals();
      final intakes = await _medicationRepository.getAllIntakes();
      final biometrics = await _biometricRepository.getAllMeasurements();

      await _firestore.collection(_collection).doc(uid).set({
        'glucose': glucose.map(_glucoseToMap).toList(),
        'meals': meals.map(_mealToMap).toList(),
        'medicationIntakes': intakes.map(_intakeToMap).toList(),
        'biometrics': biometrics.map(_biometricToMap).toList(),
        'updatedAt': FieldValue.serverTimestamp(),
      });
    } catch (e) {
      if (e is BackupException) {
        rethrow;
      }
      throw const BackupException(
        'No se pudo respaldar en la nube. Verifica tu conexión e '
        'intenta nuevamente.',
      );
    }
  }

  @override
  Future<void> restore() async {
    final uid = _requireUid();

    Map<String, Object?> data;
    try {
      final snapshot = await _firestore.collection(_collection).doc(uid).get();
      if (!snapshot.exists || snapshot.data() == null) {
        throw const BackupException(
          'Todavía no tienes ningún respaldo guardado en la nube.',
        );
      }
      data = snapshot.data()!;
    } catch (e) {
      if (e is BackupException) {
        rethrow;
      }
      throw const BackupException(
        'No se pudo leer el respaldo desde la nube. Verifica tu '
        'conexión e intenta nuevamente.',
      );
    }

    try {
      await _glucoseRepository.clearMeasurements();
      await _mealRepository.clearMeals();
      await _medicationRepository.clearIntakes();
      await _biometricRepository.clearMeasurements();

      for (final raw in (data['glucose'] as List?) ?? const []) {
        await _glucoseRepository.addMeasurement(
          _glucoseFromMap(raw as Map<String, Object?>),
        );
      }
      for (final raw in (data['meals'] as List?) ?? const []) {
        await _mealRepository.addMeal(
          _mealFromMap(raw as Map<String, Object?>),
        );
      }
      for (final raw in (data['medicationIntakes'] as List?) ?? const []) {
        await _medicationRepository.addIntake(
          _intakeFromMap(raw as Map<String, Object?>),
        );
      }
      for (final raw in (data['biometrics'] as List?) ?? const []) {
        await _biometricRepository.addMeasurement(
          _biometricFromMap(raw as Map<String, Object?>),
        );
      }
    } catch (e) {
      throw const BackupException(
        'No se pudo completar la restauración. Algunos datos locales '
        'pueden haber quedado incompletos; intenta restaurar de nuevo.',
      );
    }
  }

  @override
  Future<BackupMergeSummary> mergeFromCloud() async {
    final uid = _requireUid();

    Map<String, Object?> data;
    try {
      final snapshot = await _firestore.collection(_collection).doc(uid).get();
      if (!snapshot.exists || snapshot.data() == null) {
        throw const BackupException(
          'Todavía no tienes ningún respaldo guardado en la nube.',
        );
      }
      data = snapshot.data()!;
    } catch (e) {
      if (e is BackupException) {
        rethrow;
      }
      throw const BackupException(
        'No se pudo leer el respaldo desde la nube. Verifica tu '
        'conexión e intenta nuevamente.',
      );
    }

    try {
      final existingGlucoseUuids = (await _glucoseRepository
              .getAllMeasurements())
          .map((m) => m.uuid)
          .toSet();
      final existingMealUuids = (await _mealRepository.getAllMeals())
          .map((m) => m.uuid)
          .toSet();
      final existingIntakeUuids = (await _medicationRepository
              .getAllIntakes())
          .map((i) => i.uuid)
          .toSet();
      final existingBiometricUuids = (await _biometricRepository
              .getAllMeasurements())
          .map((m) => m.uuid)
          .toSet();

      var addedGlucose = 0;
      for (final raw in (data['glucose'] as List?) ?? const []) {
        final measurement = _glucoseFromMap(raw as Map<String, Object?>);
        if (existingGlucoseUuids.contains(measurement.uuid)) {
          continue;
        }
        await _glucoseRepository.addMeasurement(measurement);
        addedGlucose++;
      }

      var addedMeals = 0;
      for (final raw in (data['meals'] as List?) ?? const []) {
        final meal = _mealFromMap(raw as Map<String, Object?>);
        if (existingMealUuids.contains(meal.uuid)) {
          continue;
        }
        await _mealRepository.addMeal(meal);
        addedMeals++;
      }

      var addedIntakes = 0;
      for (final raw in (data['medicationIntakes'] as List?) ?? const []) {
        final intake = _intakeFromMap(raw as Map<String, Object?>);
        if (existingIntakeUuids.contains(intake.uuid)) {
          continue;
        }
        await _medicationRepository.addIntake(intake);
        addedIntakes++;
      }

      var addedBiometrics = 0;
      for (final raw in (data['biometrics'] as List?) ?? const []) {
        final measurement = _biometricFromMap(raw as Map<String, Object?>);
        if (existingBiometricUuids.contains(measurement.uuid)) {
          continue;
        }
        await _biometricRepository.addMeasurement(measurement);
        addedBiometrics++;
      }

      return BackupMergeSummary(
        addedGlucoseMeasurements: addedGlucose,
        addedMeals: addedMeals,
        addedMedicationIntakes: addedIntakes,
        addedBiometricMeasurements: addedBiometrics,
      );
    } catch (e) {
      if (e is BackupException) {
        rethrow;
      }
      throw const BackupException(
        'No se pudo completar la fusión. Algunos datos locales pueden '
        'haber quedado incompletos; intenta fusionar de nuevo.',
      );
    }
  }

  @override
  Future<DateTime?> getLastBackupTime() async {
    final uid = _firebaseAuth.currentUser?.uid;
    if (uid == null) {
      return null;
    }
    final snapshot = await _firestore.collection(_collection).doc(uid).get();
    final updatedAt = snapshot.data()?['updatedAt'];
    if (updatedAt is Timestamp) {
      return updatedAt.toDate();
    }
    return null;
  }

  // ---- Serialización: GlucoseMeasurement ----

  Map<String, Object?> _glucoseToMap(GlucoseMeasurement m) => {
    'uuid': m.uuid,
    'value': m.value,
    'moment': m.moment.name,
    'measuredAt': m.measuredAt.toIso8601String(),
    'comment': m.comment,
  };

  GlucoseMeasurement _glucoseFromMap(Map<String, Object?> map) {
    return GlucoseMeasurement(
      uuid: map['uuid'] as String?,
      value: map['value'] as int,
      moment:
          GlucoseMoment.values.asNameMap()[map['moment'] as String] ??
          GlucoseMoment.now,
      measuredAt: DateTime.parse(map['measuredAt'] as String),
      comment: map['comment'] as String?,
    );
  }

  // ---- Serialización: Meal ----

  Map<String, Object?> _mealToMap(Meal m) => {
    'uuid': m.uuid,
    'type': m.type.name,
    'eatenAt': m.eatenAt.toIso8601String(),
    'comment': m.comment,
    'items': m.items
        .map((item) => {'foodName': item.food.name, 'quantity': item.quantity})
        .toList(),
  };

  Meal _mealFromMap(Map<String, Object?> map) {
    final items = ((map['items'] as List?) ?? const [])
        .cast<Map<String, Object?>>()
        .map(
          (item) => MealFoodItem(
            food: Food(name: item['foodName'] as String),
            quantity: item['quantity'] as String,
          ),
        )
        .toList();
    return Meal(
      uuid: map['uuid'] as String?,
      type:
          MealType.values.asNameMap()[map['type'] as String] ?? MealType.other,
      eatenAt: DateTime.parse(map['eatenAt'] as String),
      comment: map['comment'] as String?,
      items: items,
    );
  }

  // ---- Serialización: MedicationIntake ----

  Map<String, Object?> _intakeToMap(MedicationIntake intake) => {
    'uuid': intake.uuid,
    'takenAt': intake.takenAt.toIso8601String(),
    'comment': intake.comment,
    'items': intake.items
        .map(
          (item) => {
            'medicationName': item.medication.name,
            'defaultUnit': item.medication.defaultUnit.name,
            'quantity': item.quantity,
            'unit': item.unit.name,
            'customUnitLabel': item.customUnitLabel,
          },
        )
        .toList(),
  };

  MedicationIntake _intakeFromMap(Map<String, Object?> map) {
    final items = ((map['items'] as List?) ?? const [])
        .cast<Map<String, Object?>>()
        .map((item) {
          final defaultUnit =
              DoseUnit.values.asNameMap()[item['defaultUnit'] as String] ??
              DoseUnit.other;
          final unit =
              DoseUnit.values.asNameMap()[item['unit'] as String] ??
              DoseUnit.other;
          return MedicationIntakeItem(
            medication: Medication(
              name: item['medicationName'] as String,
              defaultUnit: defaultUnit,
            ),
            quantity: (item['quantity'] as num).toDouble(),
            unit: unit,
            customUnitLabel: item['customUnitLabel'] as String?,
          );
        })
        .toList();
    return MedicationIntake(
      uuid: map['uuid'] as String?,
      takenAt: DateTime.parse(map['takenAt'] as String),
      comment: map['comment'] as String?,
      items: items,
    );
  }

  // ---- Serialización: BiometricMeasurement ----

  Map<String, Object?> _biometricToMap(BiometricMeasurement m) => {
    'uuid': m.uuid,
    'weightKg': m.weightKg,
    'systolicPressure': m.systolicPressure,
    'diastolicPressure': m.diastolicPressure,
    'heartRateBpm': m.heartRateBpm,
    'measuredAt': m.measuredAt.toIso8601String(),
    'comment': m.comment,
  };

  BiometricMeasurement _biometricFromMap(Map<String, Object?> map) {
    return BiometricMeasurement(
      uuid: map['uuid'] as String?,
      weightKg: (map['weightKg'] as num).toDouble(),
      systolicPressure: map['systolicPressure'] as int?,
      diastolicPressure: map['diastolicPressure'] as int?,
      heartRateBpm: map['heartRateBpm'] as int?,
      measuredAt: DateTime.parse(map['measuredAt'] as String),
      comment: map['comment'] as String?,
    );
  }
}
