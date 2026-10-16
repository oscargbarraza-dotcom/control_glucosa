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
  const GlucoseMeasurement({
    this.id,
    required this.value,
    required this.moment,
    required this.measuredAt,
    this.comment,
  });

  /// Identificador único asignado por el almacenamiento persistente.
  ///
  /// Es `null` para mediciones que aún no se han guardado (por ejemplo, el
  /// resultado recién construido en [GlucoseScreen] antes de persistirlo).
  final int? id;

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
    int? value,
    GlucoseMoment? moment,
    DateTime? measuredAt,
    String? comment,
  }) {
    return GlucoseMeasurement(
      id: id ?? this.id,
      value: value ?? this.value,
      moment: moment ?? this.moment,
      measuredAt: measuredAt ?? this.measuredAt,
      comment: comment ?? this.comment,
    );
  }

  @override
  String toString() {
    return 'GlucoseMeasurement(id: $id, value: $value, '
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
        other.value == value &&
        other.moment == moment &&
        other.measuredAt == measuredAt &&
        other.comment == comment;
  }

  @override
  int get hashCode => Object.hash(id, value, moment, measuredAt, comment);
}
