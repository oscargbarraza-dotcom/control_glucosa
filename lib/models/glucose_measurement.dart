import 'package:uuid/uuid.dart';

/// Momento del día en el que se realiza una medición de glucosa.
enum GlucoseMoment {
  now,
  wakingUp,
  beforeBreakfast,
  afterBreakfast,
  beforeLunch,
  afterLunch,
  beforeDinner,
  afterDinner,
  beforeSleep,
}

/// Extensión con el texto legible para cada [GlucoseMoment].
extension GlucoseMomentLabel on GlucoseMoment {
  String get label {
    switch (this) {
      case GlucoseMoment.now:
        return 'Ahora';
      case GlucoseMoment.wakingUp:
        return 'Al despertar';
      case GlucoseMoment.beforeBreakfast:
        return 'Antes desayuno';
      case GlucoseMoment.afterBreakfast:
        return 'Después desayuno';
      case GlucoseMoment.beforeLunch:
        return 'Antes almuerzo';
      case GlucoseMoment.afterLunch:
        return 'Después almuerzo';
      case GlucoseMoment.beforeDinner:
        return 'Antes cena';
      case GlucoseMoment.afterDinner:
        return 'Después cena';
      case GlucoseMoment.beforeSleep:
        return 'Antes dormir';
    }
  }
}

/// Representa una medición de glucosa registrada por el usuario.
///
/// Es inmutable: cualquier cambio debe producir una nueva instancia
/// mediante [copyWith].
class GlucoseMeasurement {
  /// Si [uuid] no se provee (caso normal al crear una medición nueva en
  /// [GlucoseScreen]), se genera automáticamente un UUID v4. Al reconstruir
  /// una medición ya persistida (por ejemplo, desde una fila de SQLite),
  /// debe pasarse explícitamente el [uuid] original para preservarlo.
  GlucoseMeasurement({
    this.id,
    String? uuid,
    required this.value,
    required this.moment,
    required this.measuredAt,
    this.comment,
  }) : uuid = uuid ?? const Uuid().v4();

  /// Identificador único asignado por el almacenamiento persistente.
  ///
  /// Es `null` para mediciones que aún no se han guardado (por ejemplo, el
  /// resultado recién construido en [GlucoseScreen] antes de persistirlo).
  final int? id;

  /// Identificador estable (UUID v4), independiente del almacenamiento
  /// local. A diferencia de [id] (autoincremental y propio de cada base
  /// SQLite), [uuid] no cambia si el registro se respalda o se mueve entre
  /// dispositivos, lo que lo convierte en la clave candidata para una
  /// futura sincronización/fusión sin duplicados (ver "Próximos pasos
  /// recomendados" en `PROJECT_CONTEXT.md`).
  final String uuid;

  /// Valor de glucosa en mg/dL.
  final int value;

  /// Momento del día asociado a la medición.
  final GlucoseMoment moment;

  /// Fecha y hora en la que se registró la medición.
  final DateTime measuredAt;

  /// Comentario opcional asociado a la medición.
  final String? comment;

  /// Crea una copia de esta medición sustituyendo los campos indicados.
  GlucoseMeasurement copyWith({
    int? id,
    String? uuid,
    int? value,
    GlucoseMoment? moment,
    DateTime? measuredAt,
    String? comment,
  }) {
    return GlucoseMeasurement(
      id: id ?? this.id,
      uuid: uuid ?? this.uuid,
      value: value ?? this.value,
      moment: moment ?? this.moment,
      measuredAt: measuredAt ?? this.measuredAt,
      comment: comment ?? this.comment,
    );
  }

  @override
  String toString() {
    return 'GlucoseMeasurement(id: $id, uuid: $uuid, value: $value, '
        'moment: ${moment.label}, measuredAt: $measuredAt, '
        'comment: $comment)';
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) {
      return true;
    }
    return other is GlucoseMeasurement &&
        other.id == id &&
        other.uuid == uuid &&
        other.value == value &&
        other.moment == moment &&
        other.measuredAt == measuredAt &&
        other.comment == comment;
  }

  @override
  int get hashCode =>
      Object.hash(id, uuid, value, moment, measuredAt, comment);
}
