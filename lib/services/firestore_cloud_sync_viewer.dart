import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart' as fb_auth;

import '../models/biometric_measurement.dart';
import '../models/glucose_measurement.dart';
import '../models/meal.dart';
import '../models/medication_intake.dart';
import 'cloud_sync_repository.dart';
import 'cloud_sync_serialization.dart';

/// Implementación de [CloudSyncViewer] para plataformas de solo
/// lectura (Windows, macOS), que a diferencia de
/// [FirestoreCloudSyncRepository] **no depende de ningún repositorio
/// SQLite**: en Windows no hay soporte nativo de `sqflite` sin
/// configurar `sqflite_common_ffi` aparte, y esta app no lo hace en
/// escritorio porque el visor nunca necesita almacenamiento local (ver
/// `CloudViewerScreen`).
///
/// Lee los mismos documentos que escribe `FirestoreCloudSyncRepository`
/// desde el celular (`users/{uid}/...`), usando las funciones de
/// (de)serialización compartidas en `cloud_sync_serialization.dart`.
class FirestoreCloudSyncViewer implements CloudSyncViewer {
  FirestoreCloudSyncViewer({
    fb_auth.FirebaseAuth? firebaseAuth,
    FirebaseFirestore? firestore,
  }) : _firebaseAuth = firebaseAuth ?? fb_auth.FirebaseAuth.instance,
       _firestore = firestore ?? FirebaseFirestore.instance;

  final fb_auth.FirebaseAuth _firebaseAuth;
  final FirebaseFirestore _firestore;

  static const _usersCollection = 'users';
  static const _glucoseSubcollection = 'glucose_measurements';
  static const _mealsSubcollection = 'meals';
  static const _intakesSubcollection = 'medication_intakes';
  static const _biometricsSubcollection = 'biometric_measurements';

  CollectionReference<Map<String, Object?>> _subcollection(
    String uid,
    String name,
  ) => _firestore.collection(_usersCollection).doc(uid).collection(name);

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

  /// Ver la documentación del método homónimo en
  /// `FirestoreCloudSyncRepository`: mismo comportamiento, duplicado
  /// deliberadamente para no acoplar este visor a ningún repositorio
  /// SQLite.
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
            (snapshot) =>
                snapshot.docs.map((d) => fromMap(d.data())).toList(),
          );
    });
  }
}
