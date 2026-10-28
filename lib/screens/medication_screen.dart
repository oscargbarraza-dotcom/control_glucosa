import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/medication.dart';
import '../models/medication_intake.dart';
import '../services/glucose_import_repository.dart';
import '../services/glucose_repository.dart';
import '../services/medication_repository.dart';
import 'glucose_measurement_prompt.dart';

/// Pantalla del módulo de Medicamentos, con dos pestañas: **Registrar**
/// (nueva toma) e **Historial** (tomas ya guardadas).
///
/// Sigue el mismo patrón que `MealScreen`: autocontenida, con pestañas
/// propias en lugar de depender de `HistoryScreen`, para mantener cada
/// módulo de dominio aislado y testeable.
class MedicationScreen extends StatefulWidget {
  const MedicationScreen({
    super.key,
    required this.repository,
    this.glucoseRepository,
    this.glucoseImportRepository,
  });

  /// Repositorio desde el que se cargan y guardan las tomas.
  final MedicationRepository repository;

  /// Repositorio de mediciones de glucosa. Si no es `null`, tras guardar
  /// una toma se ofrece registrar de inmediato una medición (mismo
  /// patrón que `MealScreen`). Si es `null`, no se ofrece esta opción
  /// (por ejemplo, en tests que no necesitan probar esta
  /// funcionalidad).
  final GlucoseRepository? glucoseRepository;

  /// Repositorio de importación manual desde sensores/CGM, reenviado a
  /// `GlucoseScreen` cuando el usuario elige registrar una medición
  /// justo después de guardar la toma. Si es `null`, esa pantalla no
  /// muestra el botón "Tomar desde sensor".
  final GlucoseImportRepository? glucoseImportRepository;

  @override
  State<MedicationScreen> createState() => _MedicationScreenState();
}

class _MedicationScreenState extends State<MedicationScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController = TabController(
    length: 2,
    vsync: this,
  );
  late Future<List<MedicationIntake>> _intakesFuture;

  @override
  void initState() {
    super.initState();
    _intakesFuture = widget.repository.getAllIntakes();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _handleIntakeSaved(MedicationIntake intake) async {
    await widget.repository.addIntake(intake);
    if (!mounted) {
      return;
    }

    setState(() {
      _intakesFuture = widget.repository.getAllIntakes();
    });
    _tabController.animateTo(1);

    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('Toma guardada.')));

    await _offerGlucoseMeasurement();
  }

  /// Tras guardar una toma, pregunta si se quiere registrar de
  /// inmediato una medición de glucosa, ya que varios medicamentos
  /// (insulina, hipoglucemiantes orales) afectan directamente la
  /// glucemia.
  ///
  /// No hace nada si no se proveyó [MedicationScreen.glucoseRepository]
  /// (por ejemplo, en tests que no necesitan probar esta
  /// funcionalidad).
  Future<void> _offerGlucoseMeasurement() async {
    final glucoseRepository = widget.glucoseRepository;
    if (glucoseRepository == null || !mounted) {
      return;
    }

    final measurement = await offerGlucoseMeasurement(
      context: context,
      associationDescription: 'asociada a esta toma',
      importRepository: widget.glucoseImportRepository,
    );
    if (measurement == null) {
      return;
    }

    await glucoseRepository.addMeasurement(measurement);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Medicamentos'),
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
          _MedicationForm(onSave: _handleIntakeSaved),
          _MedicationHistoryList(intakesFuture: _intakesFuture),
        ],
      ),
    );
  }
}

/// Un medicamento con dosis, tal como se va construyendo en el formulario
/// (antes de resolverse contra el catálogo de [Medication] al guardar).
class _DraftMedicationItem {
  _DraftMedicationItem({
    required this.medicationName,
    required this.quantity,
    required this.unit,
    this.customUnitLabel,
  });

  final String medicationName;
  final double quantity;
  final DoseUnit unit;
  final String? customUnitLabel;

  String get unitLabel {
    if (unit == DoseUnit.other &&
        customUnitLabel != null &&
        customUnitLabel!.trim().isNotEmpty) {
      return customUnitLabel!.trim();
    }
    return unit.label;
  }
}

/// Formulario de registro de una nueva toma: lista de medicamentos (con
/// cantidad numérica y unidad) y comentario opcional.
class _MedicationForm extends StatefulWidget {
  const _MedicationForm({required this.onSave});

  /// Invocado con la [MedicationIntake] construida al pulsar "Guardar".
  final Future<void> Function(MedicationIntake intake) onSave;

  @override
  State<_MedicationForm> createState() => _MedicationFormState();
}

class _MedicationFormState extends State<_MedicationForm> {
  final _formKey = GlobalKey<FormState>();
  final TextEditingController _medicationNameController =
      TextEditingController();
  final TextEditingController _quantityController = TextEditingController();
  final TextEditingController _customUnitController = TextEditingController();
  final TextEditingController _commentController = TextEditingController();

  DoseUnit _selectedUnit = DoseUnit.milligram;
  final List<_DraftMedicationItem> _items = [];
  bool _isSaving = false;

  @override
  void dispose() {
    _medicationNameController.dispose();
    _quantityController.dispose();
    _customUnitController.dispose();
    _commentController.dispose();
    super.dispose();
  }

  void _addItem() {
    final name = _medicationNameController.text.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Indica el nombre del medicamento.')),
      );
      return;
    }

    final quantity = _parseQuantity(_quantityController.text);
    if (quantity == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Ingresa una cantidad numérica válida.')),
      );
      return;
    }

    if (_selectedUnit == DoseUnit.other &&
        _customUnitController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Indica la unidad personalizada.')),
      );
      return;
    }

    setState(() {
      _items.add(
        _DraftMedicationItem(
          medicationName: name,
          quantity: quantity,
          unit: _selectedUnit,
          customUnitLabel: _selectedUnit == DoseUnit.other
              ? _customUnitController.text.trim()
              : null,
        ),
      );
      _medicationNameController.clear();
      _quantityController.clear();
      _customUnitController.clear();
      _selectedUnit = DoseUnit.milligram;
    });
  }

  void _removeItem(int index) {
    setState(() {
      _items.removeAt(index);
    });
  }

  /// Convierte el texto de cantidad a [double], aceptando tanto `.` como
  /// `,` como separador decimal (el teclado numérico en español suele
  /// insertar `,`, lo que hacía fallar [double.tryParse] en silencio).
  double? _parseQuantity(String input) {
    final normalized = input.trim().replaceAll(',', '.');
    if (normalized.isEmpty) {
      return null;
    }
    final quantity = double.tryParse(normalized);
    if (quantity == null || quantity <= 0) {
      return null;
    }
    return quantity;
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate() || _items.isEmpty) {
      if (_items.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Agrega al menos un medicamento a la toma.'),
          ),
        );
      }
      return;
    }

    setState(() => _isSaving = true);

    final intake = MedicationIntake(
      takenAt: DateTime.now(),
      comment: _commentController.text.trim().isEmpty
          ? null
          : _commentController.text.trim(),
      items: _items
          .map(
            (draft) => MedicationIntakeItem(
              medication: Medication(
                name: draft.medicationName,
                defaultUnit: draft.unit,
              ),
              quantity: draft.quantity,
              unit: draft.unit,
              customUnitLabel: draft.customUnitLabel,
            ),
          )
          .toList(),
    );

    await widget.onSave(intake);

    if (!mounted) {
      return;
    }
    setState(() {
      _items.clear();
      _selectedUnit = DoseUnit.milligram;
      _commentController.clear();
      _isSaving = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      child: ListView(
        // Clave estable para que los tests de widgets puedan identificar
        // sin ambigüedad este `ListView` (hay varios `Scrollable` en el
        // árbol: el `PageView` del `TabBarView`, los de cada campo de
        // texto, etc.) y hacerle scroll hasta el botón "Guardar".
        key: const Key('medicationFormListView'),
        padding: const EdgeInsets.all(20),
        children: [
          const Icon(Icons.medication, color: Colors.teal, size: 70),
          const SizedBox(height: 20),
          _MedicationItemInputRow(
            medicationNameController: _medicationNameController,
            quantityController: _quantityController,
            customUnitController: _customUnitController,
            selectedUnit: _selectedUnit,
            onUnitChanged: (unit) {
              if (unit == null) {
                return;
              }
              setState(() => _selectedUnit = unit);
            },
            onAdd: _addItem,
          ),
          const SizedBox(height: 12),
          _MedicationItemsList(items: _items, onRemove: _removeItem),
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

/// Fila con los campos "Medicamento", "Cantidad" y el selector de unidad
/// (más un campo de texto adicional cuando la unidad es [DoseUnit.other]),
/// y el botón para agregar el medicamento a la lista de la toma en
/// construcción.
class _MedicationItemInputRow extends StatelessWidget {
  const _MedicationItemInputRow({
    required this.medicationNameController,
    required this.quantityController,
    required this.customUnitController,
    required this.selectedUnit,
    required this.onUnitChanged,
    required this.onAdd,
  });

  final TextEditingController medicationNameController;
  final TextEditingController quantityController;
  final TextEditingController customUnitController;
  final DoseUnit selectedUnit;
  final ValueChanged<DoseUnit?> onUnitChanged;
  final VoidCallback onAdd;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextFormField(
          controller: medicationNameController,
          decoration: const InputDecoration(
            labelText: 'Medicamento',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 12),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: TextFormField(
                controller: quantityController,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(
                  labelText: 'Cantidad',
                  hintText: 'ej. 500',
                  border: OutlineInputBorder(),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: DropdownButtonFormField<DoseUnit>(
                initialValue: selectedUnit,
                // Evita que el botón se reduzca a su contenido mínimo;
                // ver el mismo ajuste (y su motivo) en GlucoseScreen.
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: 'Unidad',
                  border: OutlineInputBorder(),
                ),
                items: DoseUnit.values
                    .map(
                      (unit) => DropdownMenuItem(
                        value: unit,
                        child: Text(unit.label),
                      ),
                    )
                    .toList(),
                onChanged: onUnitChanged,
              ),
            ),
            const SizedBox(width: 8),
            IconButton(
              icon: const Icon(Icons.add_circle, color: Colors.green),
              tooltip: 'Agregar medicamento',
              onPressed: onAdd,
            ),
          ],
        ),
        if (selectedUnit == DoseUnit.other) ...[
          const SizedBox(height: 12),
          TextFormField(
            controller: customUnitController,
            decoration: const InputDecoration(
              labelText: 'Unidad personalizada',
              hintText: 'ej. parche, sobre',
              border: OutlineInputBorder(),
            ),
          ),
        ],
      ],
    );
  }
}

/// Lista de medicamentos ya agregados a la toma en construcción, con botón
/// de eliminación por cada uno.
class _MedicationItemsList extends StatelessWidget {
  const _MedicationItemsList({required this.items, required this.onRemove});

  final List<_DraftMedicationItem> items;
  final void Function(int index) onRemove;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 8),
        child: Text(
          'Todavía no agregaste medicamentos a esta toma.',
          style: TextStyle(color: Colors.grey),
        ),
      );
    }

    return Column(
      children: [
        for (var i = 0; i < items.length; i++)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.medication),
            title: Text(items[i].medicationName),
            subtitle: Text('${items[i].quantity} ${items[i].unitLabel}'),
            trailing: IconButton(
              icon: const Icon(Icons.delete_outline, color: Colors.red),
              onPressed: () => onRemove(i),
            ),
          ),
      ],
    );
  }
}

/// Vista de historial: tomas de la más reciente a la más antigua.
///
/// Carga su contenido desde [intakesFuture], resuelto una vez por
/// [MedicationScreen] y actualizado tras guardar una nueva toma.
class _MedicationHistoryList extends StatelessWidget {
  const _MedicationHistoryList({required this.intakesFuture});

  final Future<List<MedicationIntake>> intakesFuture;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<MedicationIntake>>(
      future: intakesFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }

        final intakes = snapshot.data ?? const [];
        if (intakes.isEmpty) {
          return const Center(child: Text('Todavía no hay tomas registradas.'));
        }

        return ListView.separated(
          padding: const EdgeInsets.symmetric(vertical: 8),
          itemCount: intakes.length,
          separatorBuilder: (context, index) => const Divider(height: 1),
          itemBuilder: (context, index) =>
              _MedicationTile(intake: intakes[index]),
        );
      },
    );
  }
}

/// Fila individual del historial con los medicamentos, fecha/hora y
/// comentario (si existe) de una toma.
class _MedicationTile extends StatelessWidget {
  const _MedicationTile({required this.intake});

  final MedicationIntake intake;

  @override
  Widget build(BuildContext context) {
    final formattedDate = DateFormat('dd/MM/yyyy HH:mm').format(intake.takenAt);
    final medicationsSummary = intake.items
        .map(
          (item) =>
              '${item.medication.name} (${item.quantity} '
              '${item.effectiveUnitLabel})',
        )
        .join(', ');

    return ListTile(
      leading: const Icon(Icons.medication, color: Colors.deepPurple),
      title: Text(
        medicationsSummary.isEmpty ? 'Toma' : medicationsSummary,
        style: const TextStyle(fontWeight: FontWeight.bold),
      ),
      subtitle: Text(
        [formattedDate, if (intake.comment != null) intake.comment!].join('\n'),
      ),
      isThreeLine: true,
    );
  }
}
