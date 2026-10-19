import 'package:uuid/uuid.dart';

/// Representa una medición biométrica registrada por el usuario.
///
/// El peso corporal (en kg) es obligatorio en todo registro; la presión
/// arterial ([systolicPressure]/[diastolicPressure]) y la frecuencia
/// cardíaca ([heartRateBpm]) son opcionales, ya que no siempre se miden
/// junto con el peso. El índice de masa corporal (IMC) queda pendiente
/// para cuando exista un perfil de usuario con altura.
///
/// Es inmutable: cualquier cambio debe producir una nueva instancia
/// mediante [copyWith].
class BiometricMeasurement {
  /// Si [uuid] no se provee (caso normal al crear una medición nueva en
  /// el formulario de Biometría), se genera automáticamente un UUID v4.
  /// Al reconstruir una medición ya persistida (por ejemplo, desde una
  /// fila de SQLite), debe pasarse explícitamente el [uuid] original
  /// para preservarlo.
  BiometricMeasurement({
    this.id,
    String? uuid,
    required this.weightKg,
    this.systolicPressure,
    this.diastolicPressure,
    this.heartRateBpm,
    required this.measuredAt,
    this.comment,
  }) : uuid = uuid ?? const Uuid().v4();

  /// Identificador único asignado por el almacenamiento persistente.
  ///
  /// Es `null` para mediciones que aún no se han guardado (por ejemplo, el
  /// resultado recién construido en el formulario antes de persistirlo).
  final int? id;

  /// Identificador estable (UUID v4), independiente del almacenamiento
  /// local. A diferencia de [id] (autoincremental y propio de cada base
  /// SQLite), [uuid] no cambia si el registro se respalda o se mueve entre
  /// dispositivos, lo que lo convierte en la clave candidata para una
  /// futura sincronización/fusión sin duplicados (ver "Próximos pasos
  /// recomendados" en `PROJECT_CONTEXT.md`).
  final String uuid;

  /// Peso corporal en kilogramos.
  final double weightKg;

  /// Presión sistólica en mmHg, si se registró en esta medición.
  ///
  /// Siempre acompaña a [diastolicPressure]: ambas son `null` o ambas
  /// tienen valor.
  final int? systolicPressure;

  /// Presión diastólica en mmHg, si se registró en esta medición.
  final int? diastolicPressure;

  /// Frecuencia cardíaca en latidos por minuto, si se registró en esta
  /// medición.
  final int? heartRateBpm;

  /// Fecha y hora en la que se registró la medición.
  final DateTime measuredAt;

  /// Comentario opcional asociado a la medición.
  final String? comment;

  /// Indica si esta medición incluye presión arterial registrada.
  bool get hasBloodPressure =>
      systolicPressure != null && diastolicPressure != null;

  /// Crea una copia de esta medición sustituyendo los campos indicados.
  ///
  /// Para limpiar explícitamente un campo opcional (dejarlo en `null`),
  /// usa [clearSystolicPressure], [clearDiastolicPressure] o
  /// [clearHeartRateBpm]; de lo contrario el valor actual se conserva.
  BiometricMeasurement copyWith({
    int? id,
    String? uuid,
    double? weightKg,
    int? systolicPressure,
    bool clearSystolicPressure = false,
    int? diastolicPressure,
    bool clearDiastolicPressure = false,
    int? heartRateBpm,
    bool clearHeartRateBpm = false,
    DateTime? measuredAt,
    String? comment,
  }) {
    return BiometricMeasurement(
      id: id ?? this.id,
      uuid: uuid ?? this.uuid,
      weightKg: weightKg ?? this.weightKg,
      systolicPressure: clearSystolicPressure
          ? null
          : (systolicPressure ?? this.systolicPressure),
      diastolicPressure: clearDiastolicPressure
          ? null
          : (diastolicPressure ?? this.diastolicPressure),
      heartRateBpm: clearHeartRateBpm
          ? null
          : (heartRateBpm ?? this.heartRateBpm),
      measuredAt: measuredAt ?? this.measuredAt,
      comment: comment ?? this.comment,
    );
  }

  @override
  String toString() {
    return 'BiometricMeasurement(id: $id, uuid: $uuid, weightKg: $weightKg, '
        'systolicPressure: $systolicPressure, '
        'diastolicPressure: $diastolicPressure, '
        'heartRateBpm: $heartRateBpm, measuredAt: $measuredAt, '
        'comment: $comment)';
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) {
      return true;
    }
    return other is BiometricMeasurement &&
        other.id == id &&
        other.uuid == uuid &&
        other.weightKg == weightKg &&
        other.systolicPressure == systolicPressure &&
        other.diastolicPressure == diastolicPressure &&
        other.heartRateBpm == heartRateBpm &&
        other.measuredAt == measuredAt &&
        other.comment == comment;
  }

  @override
  int get hashCode => Object.hash(
    id,
    uuid,
    weightKg,
    systolicPressure,
    diastolicPressure,
    heartRateBpm,
    measuredAt,
    comment,
  );
}
