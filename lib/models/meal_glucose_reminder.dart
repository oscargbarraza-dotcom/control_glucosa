/// Estado de resolución de un [MealGlucoseReminder].
enum MealGlucoseReminderStatus {
  /// Todavía no venció, o venció pero aún no se intentó resolver.
  pending,

  /// Se resolvió solo: se encontró una medición del sensor/CGM cercana a
  /// [MealGlucoseReminder.dueAt] y se importó automáticamente.
  resolvedAutomatically,

  /// El usuario registró manualmente la medición pedida.
  resolvedManually,

  /// El usuario descartó el recordatorio sin registrar una medición.
  dismissed,
}

/// Recordatorio de tomar una medición de glucosa a los 60 o 90 minutos de
/// haber registrado una [Meal] (`mealId`).
///
/// Se generan dos instancias por cada comida guardada (una con
/// [offsetMinutes] 60 y otra con 90). [MealGlucoseReminderCoordinator] es
/// responsable de intentar resolverlos automáticamente vía sensores/CGM
/// cuando llega [dueAt], y de exponer los que requieren acción manual del
/// usuario (alarma sonora de día, popup silencioso de noche).
///
/// Es inmutable: cualquier cambio debe producir una nueva instancia
/// mediante [copyWith].
class MealGlucoseReminder {
  const MealGlucoseReminder({
    this.id,
    required this.mealId,
    required this.offsetMinutes,
    required this.dueAt,
    this.status = MealGlucoseReminderStatus.pending,
    this.resolvedMeasurementId,
  });

  /// Identificador único asignado por el almacenamiento persistente.
  ///
  /// Es `null` para recordatorios que aún no se han guardado.
  final int? id;

  /// Identificador de la [Meal] que originó este recordatorio.
  final int mealId;

  /// Minutos transcurridos desde [Meal.eatenAt] a los que corresponde
  /// esta medición (60 o 90).
  final int offsetMinutes;

  /// Momento exacto en el que la medición debería tomarse
  /// (`Meal.eatenAt + offsetMinutes`).
  final DateTime dueAt;

  /// Estado actual de resolución.
  final MealGlucoseReminderStatus status;

  /// `id` de la [GlucoseMeasurement] asociada a este recordatorio, una
  /// vez resuelto (automática o manualmente). Es `null` mientras está
  /// `pending` o si se descartó.
  final int? resolvedMeasurementId;

  /// Crea una copia de este recordatorio sustituyendo los campos
  /// indicados.
  MealGlucoseReminder copyWith({
    int? id,
    int? mealId,
    int? offsetMinutes,
    DateTime? dueAt,
    MealGlucoseReminderStatus? status,
    int? resolvedMeasurementId,
  }) {
    return MealGlucoseReminder(
      id: id ?? this.id,
      mealId: mealId ?? this.mealId,
      offsetMinutes: offsetMinutes ?? this.offsetMinutes,
      dueAt: dueAt ?? this.dueAt,
      status: status ?? this.status,
      resolvedMeasurementId:
          resolvedMeasurementId ?? this.resolvedMeasurementId,
    );
  }

  @override
  String toString() {
    return 'MealGlucoseReminder(id: $id, mealId: $mealId, '
        'offsetMinutes: $offsetMinutes, dueAt: $dueAt, status: $status, '
        'resolvedMeasurementId: $resolvedMeasurementId)';
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) {
      return true;
    }
    return other is MealGlucoseReminder &&
        other.id == id &&
        other.mealId == mealId &&
        other.offsetMinutes == offsetMinutes &&
        other.dueAt == dueAt &&
        other.status == status &&
        other.resolvedMeasurementId == resolvedMeasurementId;
  }

  @override
  int get hashCode => Object.hash(
    id,
    mealId,
    offsetMinutes,
    dueAt,
    status,
    resolvedMeasurementId,
  );
}
