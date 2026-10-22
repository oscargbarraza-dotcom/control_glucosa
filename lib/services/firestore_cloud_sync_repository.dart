import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart' as fb_auth;

import '../models/biometric_measurement.dart';
import '../models/glucose_measurement.dart';
import '../models/meal.dart';
import '../models/medication_intake.dart';
import 'biometric_repository.dart';
import 'cloud_sync_repository.dart';
import 'cloud_sync_serialization.dart';
import 'glucose_repository.dart';
import 'meal_repository.dart';
import 'medication_repository.dart';

/// Implementación de [CloudSyncRepository] basada en Cloud Firestore.
///
/// Guarda cada registro de salud como un documento independiente,
/// identificado por su `uuid` estable, en una subcolección propia bajo
/// `users/{uid}/...`:
///
/// * `users/{uid}/glucose_measurements/{uuid}`
/// * `users/{uid}/meals/{uuid}`
/// * `users/{uid}/medication_intakes/{uuid}`
/// * `users/{uid}/biometric_measurements/{uuid}`
///
/// A diferencia del antiguo `backups/{uid}` (un solo documento con
/// arrays completos), este esquema permite tanto el envío incremental
/// de un registro a la vez ([pushGlucoseMeasurement] y equivalentes)
/// como la escucha en tiempo real de cada subcolección
/// ([watchGlucoseMeasurements] y equivalentes), sin acercarse al límite
/// de 1 MiB por documento de Firestore.
class FirestoreCloudSyncRepository implements CloudSyncRepository {
  FirestoreCloudSyncRepository({
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

  static const _usersCollection = 'users';
  static const _glucoseSubcollection = 'glucose_measurements';
  static const _mealsSubcollection = 'meals';
  static const _intakesSubcollection = 'medication_intakes';
  static const _biometricsSubcollection = 'biometric_measurements';

  CollectionReference<Map<String, Object?>> _subcollection(
    String uid,
    String name,
  ) => _firestore.collection(_usersCollection).doc(uid).collection(name);

  String? get _currentUid => _firebaseAuth.currentUser?.uid;

  String _requireUid() {
    final uid = _currentUid;
    if (uid == null) {
      throw const CloudSyncException(
        'Inicia sesión para sincronizar tus datos.',
      );
    }
    return uid;
  }

  // ---- Push (subida automática y silenciosa) ----

  @override
  Future<void> pushGlucoseMeasurement(GlucoseMeasurement measurement) async {
    final uid = _currentUid;
    if (uid == null) {
      return;
    }
    try {
      await _subcollection(
        uid,
        _glucoseSubcollection,
      ).doc(measurement.uuid).set(glucoseToMap(measurement));
    } catch (_) {
      // Falla silenciosa: la sincronización nunca debe bloquear ni
      // molestar al usuario (ver documentación de la interfaz). El dato
      // ya quedó guardado en SQLite, que es el almacenamiento principal.
    }
  }

  @override
  Future<void> pushMeal(Meal meal) async {
    final uid = _currentUid;
    if (uid == null) {
      return;
    }
    try {
      await _subcollection(
        uid,
        _mealsSubcollection,
      ).doc(meal.uuid).set(mealToMap(meal));
    } catch (_) {
      // Ver comentario en pushGlucoseMeasurement.
    }
  }

  @override
  Future<void> pushMedicationIntake(MedicationIntake intake) async {
    final uid = _currentUid;
    if (uid == null) {
      return;
    }
    try {
      await _subcollection(
        uid,
        _intakesSubcollection,
      ).doc(intake.uuid).set(intakeToMap(intake));
    } catch (_) {
      // Ver comentario en pushGlucoseMeasurement.
    }
  }

  @override
  Future<void> pushBiometricMeasurement(
    BiometricMeasurement measurement,
  ) async {
    final uid = _currentUid;
    if (uid == null) {
      return;
    }
    try {
      await _subcollection(
        uid,
        _biometricsSubcollection,
      ).doc(measurement.uuid).set(biometricToMap(measurement));
    } catch (_) {
      // Ver comentario en pushGlucoseMeasurement.
    }
  }

  // ---- Pull (fusión automática al iniciar sesión) ----

  @override
  Future<CloudSyncPullSummary> pullMissingFromCloud() async {
    final uid = _requireUid();

    try {
      final existingGlucoseUuids =
          (await _glucoseRepository.getAllMeasurements())
              .map((m) => m.uuid)
              .toSet();
      final existingMealUuids = (await _mealRepository.getAllMeals())
          .map((m) => m.uuid)
          .toSet();
      final existingIntakeUuids = (await _medicationRepository.getAllIntakes())
          .map((i) => i.uuid)
          .toSet();
      final existingBiometricUuids =
          (await _biometricRepository.getAllMeasurements())
              .map((m) => m.uuid)
              .toSet();

      final remoteGlucose = await _subcollection(
        uid,
        _glucoseSubcollection,
      ).get();
      var addedGlucose = 0;
      for (final doc in remoteGlucose.docs) {
        final measurement = glucoseFromMap(doc.data());
        if (existingGlucoseUuids.contains(measurement.uuid)) {
          continue;
        }
        await _glucoseRepository.addMeasurement(measurement);
        addedGlucose++;
      }

      final remoteMeals = await _subcollection(uid, _mealsSubcollection).get();
      var addedMeals = 0;
      for (final doc in remoteMeals.docs) {
        final meal = mealFromMap(doc.data());
        if (existingMealUuids.contains(meal.uuid)) {
          continue;
        }
        await _mealRepository.addMeal(meal);
        addedMeals++;
      }

      final remoteIntakes = await _subcollection(
        uid,
        _intakesSubcollection,
      ).get();
      var addedIntakes = 0;
      for (final doc in remoteIntakes.docs) {
        final intake = intakeFromMap(doc.data());
        if (existingIntakeUuids.contains(intake.uuid)) {
          continue;
        }
        await _medicationRepository.addIntake(intake);
        addedIntakes++;
      }

      final remoteBiometrics = await _subcollection(
        uid,
        _biometricsSubcollection,
      ).get();
      var addedBiometrics = 0;
      for (final doc in remoteBiometrics.docs) {
        final measurement = biometricFromMap(doc.data());
        if (existingBiometricUuids.contains(measurement.uuid)) {
          continue;
        }
        await _biometricRepository.addMeasurement(measurement);
        addedBiometrics++;
      }

      return CloudSyncPullSummary(
        addedGlucoseMeasurements: addedGlucose,
        addedMeals: addedMeals,
        addedMedicationIntakes: addedIntakes,
        addedBiometricMeasurements: addedBiometrics,
      );
    } catch (e) {
      if (e is CloudSyncException) {
        rethrow;
      }
      throw const CloudSyncException(
        'No se pudo sincronizar con la nube. Verifica tu conexión e '
        'intenta nuevamente.',
      );
    }
  }

  // ---- Delete (eliminación de cuenta y datos) ----

  @override
  Future<void> deleteAllCloudData() async {
    final uid = _requireUid();
    try {
      await Future.wait([
        _deleteAllDocsIn(uid, _glucoseSubcollection),
        _deleteAllDocsIn(uid, _mealsSubcollection),
        _deleteAllDocsIn(uid, _intakesSubcollection),
        _deleteAllDocsIn(uid, _biometricsSubcollection),
      ]);
    } catch (e) {
      if (e is CloudSyncException) {
        rethrow;
      }
      throw const CloudSyncException(
        'No se pudieron eliminar tus datos de la nube. Verifica tu '
        'conexión e intenta nuevamente.',
      );
    }
  }

  /// Elimina todos los documentos de la subcolección [name] del
  /// usuario [uid], en lotes de hasta 400 operaciones (`WriteBatch`),
  /// por debajo del límite de 500 escrituras por batch de Firestore.
  /// Firestore no ofrece un borrado recursivo nativo desde el SDK de
  /// cliente, por lo que se repite hasta que la subcolección quede
  /// vacía.
  Future<void> _deleteAllDocsIn(String uid, String name) async {
    final collection = _subcollection(uid, name);
    while (true) {
      final snapshot = await collection.limit(400).get();
      if (snapshot.docs.isEmpty) {
        return;
      }
      final batch = _firestore.batch();
      for (final doc in snapshot.docs) {
        batch.delete(doc.reference);
      }
      await batch.commit();
    }
  }

  // ---- Watch (lectura en tiempo real, para el visor de escritorio) ----

  @override
  Stream<List<GlucoseMeasurement>> watchGlucoseMeasurements() {
    return _watchCollection(
      _glucoseSubcollection,
      'measuredAt',
      glucoseFromMap,
    );
  }

  @override
  Stream<List<Meal>> watchMeals() {
    return _watchCollection(_mealsSubcollection, 'eatenAt', mealFromMap);
  }

  @override
  Stream<List<MedicationIntake>> watchMedicationIntakes() {
    return _watchCollection(_intakesSubcollection, 'takenAt', intakeFromMap);
  }

  @override
  Stream<List<BiometricMeasurement>> watchBiometricMeasurements() {
    return _watchCollection(
      _biometricsSubcollection,
      'measuredAt',
      biometricFromMap,
    );
  }

  /// Escucha los cambios de autenticación para reaccionar a inicios y
  /// cierres de sesión, y por cada estado escucha la subcolección
  /// [name] del usuario actual (vacía si nadie tiene sesión iniciada),
  /// ordenada de la más reciente a la más antigua por [dateField].
  Stream<List<T>> _watchCollection<T>(
    String name,
    String dateField,
    T Function(Map<String, Object?>) fromMap,
  ) {
    return _firebaseAuth.authStateChanges().asyncExpand((user) {
      if (user == null) {
        return Stream<List<T>>.value(const []);
      }
      return _subcollection(user.uid, name)
          .orderBy(dateField, descending: true)
          .snapshots()
          .map(
            (snapshot) => snapshot.docs.map((d) => fromMap(d.data())).toList(),
          );
    });
  }
}
