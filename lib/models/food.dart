/// Alimento del catálogo reutilizable, consumido dentro de una o más
/// [Meal] (ver `meal.dart`) a través de [MealFoodItem].
///
/// El catálogo evita repetir el nombre de un alimento en cada comida: el
/// repositorio reutiliza el mismo [Food] (por nombre) cuando ya existe.
class Food {
  const Food({this.id, required this.name});

  /// Identificador único asignado por el almacenamiento persistente.
  ///
  /// Es `null` para un alimento que aún no se ha resuelto contra el
  /// catálogo (por ejemplo, el nombre recién escrito en el formulario,
  /// antes de guardarlo).
  final int? id;

  /// Nombre del alimento (ej. "Arroz", "Pollo a la plancha").
  final String name;

  @override
  String toString() => 'Food(id: $id, name: $name)';

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) {
      return true;
    }
    return other is Food && other.id == id && other.name == name;
  }

  @override
  int get hashCode => Object.hash(id, name);
}
