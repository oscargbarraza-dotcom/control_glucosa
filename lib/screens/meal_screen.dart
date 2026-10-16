import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/food.dart';
import '../models/meal.dart';
import '../services/meal_repository.dart';

/// Pantalla del módulo de Comidas, con dos pestañas: **Registrar** (nueva
/// comida) e **Historial** (comidas ya guardadas).
///
/// A diferencia de glucosa (donde el registro y el historial viven en
/// pantallas separadas conectadas por `Navigator.pop`), aquí ambas vistas
/// conviven en la misma pantalla para que, tras guardar, el usuario vea de
/// inmediato el resultado en la pestaña de historial.
class MealScreen extends StatefulWidget {
  const MealScreen({super.key, required this.repository});

  /// Repositorio desde el que se cargan y guardan las comidas.
  final MealRepository repository;

  @override
  State<MealScreen> createState() => _MealScreenState();
}

class _MealScreenState extends State<MealScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController = TabController(
    length: 2,
    vsync: this,
  );
  late Future<List<Meal>> _mealsFuture;

  @override
  void initState() {
    super.initState();
    _mealsFuture = widget.repository.getAllMeals();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _handleMealSaved(Meal meal) async {
    await widget.repository.addMeal(meal);
    if (!mounted) {
      return;
    }

    setState(() {
      _mealsFuture = widget.repository.getAllMeals();
    });
    _tabController.animateTo(1);

    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('Comida guardada.')));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Comida'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Registrar', icon: Icon(Icons.add_circle_outline)),
            Tab(text: 'Historial', icon: Icon(Icons.list)),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _MealForm(onSave: _handleMealSaved),
          _MealHistoryList(mealsFuture: _mealsFuture),
        ],
      ),
    );
  }
}

/// Un alimento con cantidad, tal como se va construyendo en el formulario
/// (antes de resolverse contra el catálogo de [Food] al guardar).
class _DraftFoodItem {
  _DraftFoodItem({required this.foodName, required this.quantity});

  final String foodName;
  final String quantity;
}

/// Formulario de registro de una nueva comida: tipo, lista de alimentos
/// (con cantidad en texto libre) y comentario opcional.
class _MealForm extends StatefulWidget {
  const _MealForm({required this.onSave});

  /// Invocado con la [Meal] construida al pulsar "Guardar".
  final Future<void> Function(Meal meal) onSave;

  @override
  State<_MealForm> createState() => _MealFormState();
}

class _MealFormState extends State<_MealForm> {
  final _formKey = GlobalKey<FormState>();
  final TextEditingController _foodNameController = TextEditingController();
  final TextEditingController _quantityController = TextEditingController();
  final TextEditingController _commentController = TextEditingController();

  MealType _selectedType = MealType.breakfast;
  final List<_DraftFoodItem> _items = [];
  bool _isSaving = false;

  @override
  void dispose() {
    _foodNameController.dispose();
    _quantityController.dispose();
    _commentController.dispose();
    super.dispose();
  }

  void _addItem() {
    final name = _foodNameController.text.trim();
    final quantity = _quantityController.text.trim();
    if (name.isEmpty || quantity.isEmpty) {
      return;
    }

    setState(() {
      _items.add(_DraftFoodItem(foodName: name, quantity: quantity));
      _foodNameController.clear();
      _quantityController.clear();
    });
  }

  void _removeItem(int index) {
    setState(() {
      _items.removeAt(index);
    });
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate() || _items.isEmpty) {
      if (_items.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Agrega al menos un alimento a la comida.'),
          ),
        );
      }
      return;
    }

    setState(() => _isSaving = true);

    final meal = Meal(
      type: _selectedType,
      eatenAt: DateTime.now(),
      comment: _commentController.text.trim().isEmpty
          ? null
          : _commentController.text.trim(),
      items: _items
          .map(
            (draft) => MealFoodItem(
              food: Food(name: draft.foodName),
              quantity: draft.quantity,
            ),
          )
          .toList(),
    );

    await widget.onSave(meal);

    if (!mounted) {
      return;
    }
    setState(() {
      _items.clear();
      _selectedType = MealType.breakfast;
      _commentController.clear();
      _isSaving = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          DropdownButtonFormField<MealType>(
            initialValue: _selectedType,
            decoration: const InputDecoration(
              labelText: 'Tipo de comida',
              border: OutlineInputBorder(),
            ),
            items: MealType.values
                .map(
                  (type) =>
                      DropdownMenuItem(value: type, child: Text(type.label)),
                )
                .toList(),
            onChanged: (type) {
              if (type == null) {
                return;
              }
              setState(() => _selectedType = type);
            },
          ),
          const SizedBox(height: 20),
          _FoodItemInputRow(
            foodNameController: _foodNameController,
            quantityController: _quantityController,
            onAdd: _addItem,
          ),
          const SizedBox(height: 12),
          _FoodItemsList(items: _items, onRemove: _removeItem),
          const SizedBox(height: 12),
          TextField(
            controller: _commentController,
            maxLines: 3,
            decoration: const InputDecoration(
              labelText: 'Comentario',
              hintText: 'Opcional',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.note_alt),
            ),
          ),
          const SizedBox(height: 30),
          ElevatedButton(
            onPressed: _isSaving ? null : _save,
            child: _isSaving
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2.5),
                  )
                : const Text('Guardar'),
          ),
        ],
      ),
    );
  }
}

/// Fila con los campos "Alimento" y "Cantidad", más el botón para agregar
/// el alimento a la lista de la comida en construcción.
class _FoodItemInputRow extends StatelessWidget {
  const _FoodItemInputRow({
    required this.foodNameController,
    required this.quantityController,
    required this.onAdd,
  });

  final TextEditingController foodNameController;
  final TextEditingController quantityController;
  final VoidCallback onAdd;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          flex: 3,
          child: TextFormField(
            controller: foodNameController,
            decoration: const InputDecoration(
              labelText: 'Alimento',
              border: OutlineInputBorder(),
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          flex: 2,
          child: TextFormField(
            controller: quantityController,
            decoration: const InputDecoration(
              labelText: 'Cantidad',
              hintText: 'ej. 1 taza',
              border: OutlineInputBorder(),
            ),
          ),
        ),
        const SizedBox(width: 8),
        IconButton(
          icon: const Icon(Icons.add_circle, color: Colors.green),
          tooltip: 'Agregar alimento',
          onPressed: onAdd,
        ),
      ],
    );
  }
}

/// Lista de alimentos ya agregados a la comida en construcción, con botón
/// de eliminación por cada uno.
class _FoodItemsList extends StatelessWidget {
  const _FoodItemsList({required this.items, required this.onRemove});

  final List<_DraftFoodItem> items;
  final void Function(int index) onRemove;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 8),
        child: Text(
          'Todavía no agregaste alimentos a esta comida.',
          style: TextStyle(color: Colors.grey),
        ),
      );
    }

    return Column(
      children: [
        for (var i = 0; i < items.length; i++)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.restaurant_menu),
            title: Text(items[i].foodName),
            subtitle: Text(items[i].quantity),
            trailing: IconButton(
              icon: const Icon(Icons.delete_outline, color: Colors.red),
              onPressed: () => onRemove(i),
            ),
          ),
      ],
    );
  }
}

/// Vista de historial: comidas de la más reciente a la más antigua.
///
/// Carga su contenido desde [mealsFuture], resuelto una vez por
/// [MealScreen] y actualizado tras guardar una nueva comida.
class _MealHistoryList extends StatelessWidget {
  const _MealHistoryList({required this.mealsFuture});

  final Future<List<Meal>> mealsFuture;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Meal>>(
      future: mealsFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }

        final meals = snapshot.data ?? const [];
        if (meals.isEmpty) {
          return const Center(
            child: Text('Todavía no hay comidas registradas.'),
          );
        }

        return ListView.separated(
          padding: const EdgeInsets.symmetric(vertical: 8),
          itemCount: meals.length,
          separatorBuilder: (context, index) => const Divider(height: 1),
          itemBuilder: (context, index) => _MealTile(meal: meals[index]),
        );
      },
    );
  }
}

/// Fila individual del historial con el tipo, alimentos, fecha/hora y
/// comentario (si existe) de una comida.
class _MealTile extends StatelessWidget {
  const _MealTile({required this.meal});

  final Meal meal;

  @override
  Widget build(BuildContext context) {
    final formattedDate = DateFormat('dd/MM/yyyy HH:mm').format(meal.eatenAt);
    final foodsSummary = meal.items
        .map((item) => '${item.food.name} (${item.quantity})')
        .join(', ');

    return ListTile(
      leading: const Icon(Icons.restaurant, color: Colors.deepPurple),
      title: Text(
        meal.type.label,
        style: const TextStyle(fontWeight: FontWeight.bold),
      ),
      subtitle: Text(
        [
          formattedDate,
          if (foodsSummary.isNotEmpty) foodsSummary,
          if (meal.comment != null) meal.comment!,
        ].join('\n'),
      ),
      isThreeLine: true,
    );
  }
}
