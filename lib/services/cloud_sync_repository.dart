import '../models/biometric_measurement.dart';
import '../models/glucose_measurement.dart';
import '../models/meal.dart';
import '../models/medication_intake.dart';

/// Excepción de sincronización con un mensaje ya listo para mostrar al
/// usuario (en español, sin exponer detalles internos del SDK).
///
/// Solo se lanza desde operaciones explícitas como [CloudSyncRepository.
/// pullMissingFromCloud]; el envío automático en segundo plano
/// ([CloudSyncRepository.pushGlucoseMeasurement] y similares) nunca
/// lanza excepciones, para no interrumpir al usuario por fallas de red.
class CloudSyncException implements Exception {
  const CloudSyncException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Resultado de [CloudSyncRepository.pullMissingFromCloud]: cuántos
/// registros nuevos se agregaron localmente en cada categoría, al traer
/// desde la nube lo que todavía no existía en este dispositivo.
class CloudSyncPullSummary {
  const CloudSyncPullSummary({
    required this.addedGlucoseMeasurements,
    required this.addedMeals,
    required this.addedMedicationIntakes,
    required this.addedBiometricMeasurements,
  });

  final int addedGlucoseMeasurements;
  final int addedMeals;
  final int addedMedicationIntakes;
  final int addedBiometricMeasurements;

  /// Total de registros nuevos agregados, sumando las cuatro categorías.
  int get totalAdded =>
      addedGlucoseMeasurements +
      addedMeals +
      addedMedicationIntakes +
      addedBiometricMeasurements;
}

/// Lado de solo lectura de la sincronización en la nube: permite
/// observar en tiempo real los cuatro tipos de datos de salud de un
/// usuario autenticado, sin poder crearlos, editarlos ni eliminarlos.
///
/// Es el contrato que usan las plataformas de escritorio (Windows,
/// macOS), donde la app actúa como un visor de solo lectura: ver
/// `CloudViewerScreen` y la sección "Sincronización en la nube" de
/// `PROJECT_CONTEXT.md`. Cada stream emite la lista completa (más
/// reciente primero) cada vez que cambia algo en la nube para ese
/// usuario, y una lista vacía si nadie tiene sesión iniciada.
abstract class CloudSyncViewer {
  Stream<List<GlucoseMeasurement>> watchGlucoseMeasurements();
  Stream<List<Meal>> watchMeals();
  Stream<List<MedicationIntake>> watchMedicationIntakes();
  Stream<List<BiometricMeasurement>> watchBiometricMeasurements();
}

/// Contrato para la sincronización automática en la nube de todos los
/// datos de salud (glucosa, comidas, medicamentos, biometría) entre los
/// dispositivos móviles (Android/iOS) de un mismo usuario.
///
/// A diferencia del antiguo respaldo manual (un botón "Respaldar"/
/// "Restaurar"), esta sincronización es automática y silenciosa:
///
/// * Cada [pushGlucoseMeasurement] (y equivalentes) se dispara solo,
///   justo después de guardar el registro en SQLite —ver los
///   decoradores `Syncing*Repository`—, sin bloquear la UI ni mostrar
///   ningún error si falla (por ejemplo, sin conexión): Firestore ya
///   reintenta el envío solo cuando vuelve la red.
/// * [pullMissingFromCloud] se dispara solo al iniciar sesión en un
///   dispositivo (típicamente, uno nuevo, al migrar desde el anterior),
///   trayendo los registros que falten localmente sin duplicar nada
///   (identificados por su `uuid` estable) y sin tocar lo que ya existe
///   en este dispositivo.
///
/// SQLite sigue siendo el almacenamiento principal en Android/iOS; esta
/// interfaz nunca reemplaza datos locales, solo los complementa.
abstract class CloudSyncRepository implements CloudSyncViewer {
  /// Sube [measurement] a la nube bajo el usuario autenticado, de forma
  /// idempotente (sobrescribe si ya existía un registro con el mismo
  /// `uuid`). Si no hay sesión iniciada o falla el envío, no hace nada:
  /// nunca lanza una excepción ni bloquea a quien la llama.
  Future<void> pushGlucoseMeasurement(GlucoseMeasurement measurement);

  /// Análogo a [pushGlucoseMeasurement] para una comida.
  Future<void> pushMeal(Meal meal);

  /// Análogo a [pushGlucoseMeasurement] para una toma de medicamentos.
  Future<void> pushMedicationIntake(MedicationIntake intake);

  /// Análogo a [pushGlucoseMeasurement] para una medición biométrica.
  Future<void> pushBiometricMeasurement(BiometricMeasurement measurement);

  /// Agrega localmente los registros de la nube que todavía no existan
  /// en este dispositivo (identificados por su `uuid` estable), sin
  /// tocar ni eliminar ningún registro local ya existente.
  ///
  /// Pensada para ejecutarse automáticamente al detectar una sesión
  /// recién iniciada (ver `HomeScreen`), de forma que un dispositivo
  /// nuevo (por ejemplo, tras cambiar de celular) recupere el
  /// historial completo sin ninguna acción manual del usuario.
  ///
  /// Lanza [CloudSyncException] si el usuario no tiene sesión iniciada,
  /// si esta plataforma no tiene almacenamiento local disponible (ver
  /// `CloudViewerScreen`, que nunca invoca este método), o si falla la
  /// operación.
  Future<CloudSyncPullSummary> pullMissingFromCloud();
}
