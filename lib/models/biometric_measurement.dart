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
  const BiometricMeasurement({
    this.id,
    required this.weightKg,
    this.systolicPressure,
    this.diastolicPressure,
    this.heartRateBpm,
    required this.measuredAt,
    this.comment,
  });

  /// Identificador único asignado por el almacenamiento persistente.
  ///
  /// Es `null` para mediciones que aún no se han guardado (por ejemplo, el
  /// resultado recién construido en el formulario antes de persistirlo).
  final int? id;

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
    return 'BiometricMeasurement(id: $id, weightKg: $weightKg, '
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
    weightKg,
    systolicPressure,
    diastolicPressure,
    heartRateBpm,
    measuredAt,
    comment,
  );
}
