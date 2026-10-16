/// Unidad en la que se mide la dosis de un [Medication] dentro de una toma.
///
/// [DoseUnit.other] es un comodín para unidades no listadas (ej. "parches",
/// "sobres"); en ese caso se complementa con un texto libre en
/// `MedicationIntakeItem.customUnitLabel` (ver `medication_intake.dart`).
enum DoseUnit { milligram, milliliter, tablet, unit, drop, other }

/// Extensión con el texto legible para cada [DoseUnit].
extension DoseUnitLabel on DoseUnit {
  String get label {
    switch (this) {
      case DoseUnit.milligram:
        return 'mg';
      case DoseUnit.milliliter:
        return 'ml';
      case DoseUnit.tablet:
        return 'Comprimido';
      case DoseUnit.unit:
        return 'Unidades';
      case DoseUnit.drop:
        return 'Gota';
      case DoseUnit.other:
        return 'Otro';
    }
  }
}

/// Medicamento del catálogo reutilizable, consumido dentro de una o más
/// `MedicationIntake` (ver `medication_intake.dart`) a través de
/// `MedicationIntakeItem`.
///
/// El catálogo evita repetir el nombre de un medicamento en cada toma: el
/// repositorio reutiliza el mismo [Medication] (por nombre) cuando ya existe.
class Medication {
  const Medication({this.id, required this.name, required this.defaultUnit});

  /// Identificador único asignado por el almacenamiento persistente.
  ///
  /// Es `null` para un medicamento que aún no se ha resuelto contra el
  /// catálogo (por ejemplo, el nombre recién escrito en el formulario,
  /// antes de guardarlo).
  final int? id;

  /// Nombre del medicamento (ej. "Metformina", "Insulina Glargina").
  final String name;

  /// Unidad de dosis habitual de este medicamento (ej. mg para Metformina,
  /// unidades para insulina), usada para pre-rellenar el selector al
  /// elegirlo en una toma.
  final DoseUnit defaultUnit;

  @override
  String toString() =>
      'Medication(id: $id, name: $name, defaultUnit: ${defaultUnit.label})';

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) {
      return true;
    }
    return other is Medication &&
        other.id == id &&
        other.name == name &&
        other.defaultUnit == defaultUnit;
  }

  @override
  int get hashCode => Object.hash(id, name, defaultUnit);
}
