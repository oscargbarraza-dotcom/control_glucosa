import 'food.dart';

/// Tipo de comida registrada.
enum MealType { breakfast, lunch, snack, dinner, other }

/// Extensión con el texto legible para cada [MealType].
extension MealTypeLabel on MealType {
  String get label {
    switch (this) {
      case MealType.breakfast:
        return 'Desayuno';
      case MealType.lunch:
        return 'Almuerzo';
      case MealType.snack:
        return 'Once/Merienda';
      case MealType.dinner:
        return 'Cena';
      case MealType.other:
        return 'Otro/Snack';
    }
  }
}

/// Un alimento, con su cantidad, dentro de una [Meal].
///
/// Representa la fila de la tabla intermedia `meal_food_items`, ya resuelta
/// contra el catálogo de [Food].
class MealFoodItem {
  const MealFoodItem({this.id, required this.food, required this.quantity});

  /// Identificador único asignado por el almacenamiento persistente.
  final int? id;

  /// Alimento del catálogo al que corresponde esta cantidad.
  final Food food;

  /// Cantidad en texto libre (ej. "1 taza", "2 rebanadas", "150 g").
  final String quantity;

  @override
  String toString() => 'MealFoodItem(food: ${food.name}, quantity: $quantity)';

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) {
      return true;
    }
    return other is MealFoodItem &&
        other.id == id &&
        other.food == food &&
        other.quantity == quantity;
  }

  @override
  int get hashCode => Object.hash(id, food, quantity);
}

/// Representa una comida registrada por el usuario, con los alimentos que
/// contiene.
///
/// Es inmutable: cualquier cambio debe producir una nueva instancia
/// mediante [copyWith].
class Meal {
  const Meal({
    this.id,
    required this.type,
    required this.eatenAt,
    this.comment,
    this.items = const [],
  });

  /// Identificador único asignado por el almacenamiento persistente.
  ///
  /// Es `null` para comidas que aún no se han guardado.
  final int? id;

  /// Tipo de comida (desayuno, almuerzo, etc.).
  final MealType type;

  /// Fecha y hora en la que se registró la comida.
  final DateTime eatenAt;

  /// Comentario opcional asociado a la comida.
  final String? comment;

  /// Alimentos (con su cantidad) que componen esta comida.
  final List<MealFoodItem> items;

  /// Crea una copia de esta comida sustituyendo los campos indicados.
  Meal copyWith({
    int? id,
    MealType? type,
    DateTime? eatenAt,
    String? comment,
    List<MealFoodItem>? items,
  }) {
    return Meal(
      id: id ?? this.id,
      type: type ?? this.type,
      eatenAt: eatenAt ?? this.eatenAt,
      comment: comment ?? this.comment,
      items: items ?? this.items,
    );
  }

  @override
  String toString() {
    return 'Meal(id: $id, type: ${type.label}, eatenAt: $eatenAt, '
        'comment: $comment, items: $items)';
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) {
      return true;
    }
    return other is Meal &&
        other.id == id &&
        other.type == type &&
        other.eatenAt == eatenAt &&
        other.comment == comment &&
        _sameItems(other.items);
  }

  bool _sameItems(List<MealFoodItem> otherItems) {
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
  int get hashCode =>
      Object.hash(id, type, eatenAt, comment, Object.hashAll(items));
}
