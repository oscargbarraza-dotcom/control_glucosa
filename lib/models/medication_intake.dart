import 'medication.dart';

/// Un medicamento, con su dosis, dentro de una [MedicationIntake].
///
/// Representa la fila de la tabla intermedia `medication_intake_items`, ya
/// resuelta contra el catálogo de [Medication].
class MedicationIntakeItem {
  const MedicationIntakeItem({
    this.id,
    required this.medication,
    required this.quantity,
    required this.unit,
    this.customUnitLabel,
  });

  /// Identificador único asignado por el almacenamiento persistente.
  final int? id;

  /// Medicamento del catálogo al que corresponde esta dosis.
  final Medication medication;

  /// Cantidad numérica de la dosis (ej. `500` para "500 mg").
  final double quantity;

  /// Unidad de la dosis. Cuando es [DoseUnit.other], [customUnitLabel]
  /// contiene el texto libre ingresado por el usuario.
  final DoseUnit unit;

  /// Etiqueta de unidad personalizada, solo relevante cuando [unit] es
  /// [DoseUnit.other] (ej. "parche", "sobre").
  final String? customUnitLabel;

  /// Texto de la unidad a mostrar: [customUnitLabel] si [unit] es
  /// [DoseUnit.other] y no está vacío, o [DoseUnit.label] en cualquier otro
  /// caso.
  String get effectiveUnitLabel {
    if (unit == DoseUnit.other &&
        customUnitLabel != null &&
        customUnitLabel!.trim().isNotEmpty) {
      return customUnitLabel!.trim();
    }
    return unit.label;
  }

  @override
  String toString() {
    return 'MedicationIntakeItem(medication: ${medication.name}, '
        'quantity: $quantity, unit: $effectiveUnitLabel)';
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) {
      return true;
    }
    return other is MedicationIntakeItem &&
        other.id == id &&
        other.medication == medication &&
        other.quantity == quantity &&
        other.unit == unit &&
        other.customUnitLabel == customUnitLabel;
  }

  @override
  int get hashCode =>
      Object.hash(id, medication, quantity, unit, customUnitLabel);
}

/// Representa una toma de medicamentos registrada por el usuario, con los
/// medicamentos (y su dosis) que incluye.
///
/// Es inmutable: cualquier cambio debe producir una nueva instancia mediante
/// [copyWith].
class MedicationIntake {
  const MedicationIntake({
    this.id,
    required this.takenAt,
    this.comment,
    this.items = const [],
  });

  /// Identificador único asignado por el almacenamiento persistente.
  ///
  /// Es `null` para tomas que aún no se han guardado.
  final int? id;

  /// Fecha y hora en la que se registró la toma.
  final DateTime takenAt;

  /// Comentario opcional asociado a la toma.
  final String? comment;

  /// Medicamentos (con su dosis) que componen esta toma.
  final List<MedicationIntakeItem> items;

  /// Crea una copia de esta toma sustituyendo los campos indicados.
  MedicationIntake copyWith({
    int? id,
    DateTime? takenAt,
    String? comment,
    List<MedicationIntakeItem>? items,
  }) {
    return MedicationIntake(
      id: id ?? this.id,
      takenAt: takenAt ?? this.takenAt,
      comment: comment ?? this.comment,
      items: items ?? this.items,
    );
  }

  @override
  String toString() {
    return 'MedicationIntake(id: $id, takenAt: $takenAt, '
        'comment: $comment, items: $items)';
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) {
      return true;
    }
    return other is MedicationIntake &&
        other.id == id &&
        other.takenAt == takenAt &&
        other.comment == comment &&
        _sameItems(other.items);
  }

  bool _sameItems(List<MedicationIntakeItem> otherItems) {
    if (items.length != otherItems.length) {
      return false;
    }
    for (var i = 0; i < items.length; i++) {
      if (items[i] != otherItems[i]) {
        return false;
      }
    }
    return true;
  }

  @override
  int get hashCode => Object.hash(id, takenAt, comment, Object.hashAll(items));
}
