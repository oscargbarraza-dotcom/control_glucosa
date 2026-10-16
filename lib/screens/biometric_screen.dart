import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/biometric_measurement.dart';
import '../services/biometric_repository.dart';

/// Pantalla del módulo de Biometría, con dos pestañas: **Registrar**
/// (nueva medición) e **Historial** (mediciones ya guardadas).
///
/// El peso corporal es obligatorio en cada registro; la presión arterial
/// y la frecuencia cardíaca son opcionales. El IMC queda previsto para
/// cuando exista un perfil de usuario con altura. Sigue el mismo patrón
/// que `MedicationScreen`: autocontenida, con pestañas propias en lugar
/// de depender de `HistoryScreen`, para mantener cada módulo de dominio
/// aislado y testeable.
class BiometricScreen extends StatefulWidget {
  const BiometricScreen({super.key, required this.repository});

  /// Repositorio desde el que se cargan y guardan las mediciones.
  final BiometricRepository repository;

  @override
  State<BiometricScreen> createState() => _BiometricScreenState();
}

class _BiometricScreenState extends State<BiometricScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController = TabController(
    length: 2,
    vsync: this,
  );
  late Future<List<BiometricMeasurement>> _measurementsFuture;

  @override
  void initState() {
    super.initState();
    _measurementsFuture = widget.repository.getAllMeasurements();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _handleMeasurementSaved(BiometricMeasurement measurement) async {
    await widget.repository.addMeasurement(measurement);
    if (!mounted) {
      return;
    }

    setState(() {
      _measurementsFuture = widget.repository.getAllMeasurements();
    });
    _tabController.animateTo(1);

    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('Medición guardada.')));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Biometría'),
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
          _BiometricForm(onSave: _handleMeasurementSaved),
          _BiometricHistoryList(measurementsFuture: _measurementsFuture),
        ],
      ),
    );
  }
}

/// Formulario de registro de una nueva medición: peso corporal
/// (obligatorio), presión arterial y frecuencia cardíaca (opcionales), y
/// comentario (opcional).
class _BiometricForm extends StatefulWidget {
  const _BiometricForm({required this.onSave});

  /// Invocado con la [BiometricMeasurement] construida al pulsar
  /// "Guardar".
  final Future<void> Function(BiometricMeasurement measurement) onSave;

  @override
  State<_BiometricForm> createState() => _BiometricFormState();
}

class _BiometricFormState extends State<_BiometricForm> {
  final _formKey = GlobalKey<FormState>();
  final TextEditingController _weightController = TextEditingController();
  final TextEditingController _systolicController = TextEditingController();
  final TextEditingController _diastolicController = TextEditingController();
  final TextEditingController _heartRateController = TextEditingController();
  final TextEditingController _commentController = TextEditingController();

  bool _isSaving = false;

  @override
  void dispose() {
    _weightController.dispose();
    _systolicController.dispose();
    _diastolicController.dispose();
    _heartRateController.dispose();
    _commentController.dispose();
    super.dispose();
  }

  String? _validateWeight(String? input) {
    if (input == null || input.trim().isEmpty) {
      return 'Ingresa el peso corporal.';
    }
    final parsed = double.tryParse(input.trim());
    if (parsed == null) {
      return 'Ingresa solo números.';
    }
    if (parsed < 20 || parsed > 400) {
      return 'El peso debe estar entre 20 y 400 kg.';
    }
    return null;
  }

  /// Valida un campo de presión arterial (sistólica o diastólica).
  ///
  /// Es opcional, pero si se completa uno de los dos campos del par, el
  /// otro también debe completarse: [partnerText] es el texto actual del
  /// campo complementario.
  String? _validatePressure(
    String? input, {
    required int min,
    required int max,
    required String partnerText,
  }) {
    final ownEmpty = input == null || input.trim().isEmpty;
    final partnerEmpty = partnerText.trim().isEmpty;
    if (ownEmpty) {
      return partnerEmpty
          ? null
          : 'Completa ambos valores de presión, o ninguno.';
    }
    final parsed = int.tryParse(input.trim());
    if (parsed == null) {
      return 'Ingresa solo números.';
    }
    if (parsed < min || parsed > max) {
      return 'Debe estar entre $min y $max mmHg.';
    }
    return null;
  }

  String? _validateHeartRate(String? input) {
    if (input == null || input.trim().isEmpty) {
      return null;
    }
    final parsed = int.tryParse(input.trim());
    if (parsed == null) {
      return 'Ingresa solo números.';
    }
    if (parsed < 30 || parsed > 220) {
      return 'Debe estar entre 30 y 220 lpm.';
    }
    return null;
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() => _isSaving = true);

    final systolicText = _systolicController.text.trim();
    final diastolicText = _diastolicController.text.trim();
    final heartRateText = _heartRateController.text.trim();

    final measurement = BiometricMeasurement(
      weightKg: double.parse(_weightController.text.trim()),
      systolicPressure: systolicText.isEmpty ? null : int.parse(systolicText),
      diastolicPressure: diastolicText.isEmpty
          ? null
          : int.parse(diastolicText),
      heartRateBpm: heartRateText.isEmpty ? null : int.parse(heartRateText),
      measuredAt: DateTime.now(),
      comment: _commentController.text.trim().isEmpty
          ? null
          : _commentController.text.trim(),
    );

    await widget.onSave(measurement);

    if (!mounted) {
      return;
    }
    setState(() {
      _weightController.clear();
      _systolicController.clear();
      _diastolicController.clear();
      _heartRateController.clear();
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
          const Icon(Icons.monitor_weight, color: Colors.teal, size: 70),
          const SizedBox(height: 20),
          TextFormField(
            controller: _weightController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(
              labelText: 'Peso corporal (kg)',
              border: OutlineInputBorder(),
            ),
            validator: _validateWeight,
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: TextFormField(
                  controller: _systolicController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Sistólica (mmHg)',
                    hintText: 'Opcional',
                    border: OutlineInputBorder(),
                  ),
                  validator: (input) => _validatePressure(
                    input,
                    min: 60,
                    max: 250,
                    partnerText: _diastolicController.text,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextFormField(
                  controller: _diastolicController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Diastólica (mmHg)',
                    hintText: 'Opcional',
                    border: OutlineInputBorder(),
                  ),
                  validator: (input) => _validatePressure(
                    input,
                    min: 30,
                    max: 150,
                    partnerText: _systolicController.text,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          TextFormField(
            controller: _heartRateController,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: 'Frecuencia cardíaca (lpm)',
              hintText: 'Opcional',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.favorite),
            ),
            validator: _validateHeartRate,
          ),
          const SizedBox(height: 20),
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

/// Vista de historial: pesos de la más reciente a la más antigua.
///
/// Carga su contenido desde [measurementsFuture], resuelto una vez por
/// [BiometricScreen] y actualizado tras guardar un nuevo peso.
class _BiometricHistoryList extends StatelessWidget {
  const _BiometricHistoryList({required this.measurementsFuture});

  final Future<List<BiometricMeasurement>> measurementsFuture;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<BiometricMeasurement>>(
      future: measurementsFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }

        final measurements = snapshot.data ?? const [];
        if (measurements.isEmpty) {
          return const Center(
            child: Text('Todavía no hay mediciones registradas.'),
          );
        }

        return ListView.separated(
          padding: const EdgeInsets.symmetric(vertical: 8),
          itemCount: measurements.length,
          separatorBuilder: (context, index) => const Divider(height: 1),
          itemBuilder: (context, index) =>
              _BiometricTile(measurement: measurements[index]),
        );
      },
    );
  }
}

/// Fila individual del historial con el peso, fecha/hora y comentario (si
/// existe) de una medición.
class _BiometricTile extends StatelessWidget {
  const _BiometricTile({required this.measurement});

  final BiometricMeasurement measurement;

  @override
  Widget build(BuildContext context) {
    final formattedDate = DateFormat(
      'dd/MM/yyyy HH:mm',
    ).format(measurement.measuredAt);

    final lines = <String>[formattedDate];
    if (measurement.hasBloodPressure) {
      lines.add(
        'Presión: ${measurement.systolicPressure}/'
        '${measurement.diastolicPressure} mmHg',
      );
    }
    if (measurement.heartRateBpm != null) {
      lines.add('Frecuencia cardíaca: ${measurement.heartRateBpm} lpm');
    }
    if (measurement.comment != null) {
      lines.add(measurement.comment!);
    }

    return ListTile(
      leading: const Icon(Icons.monitor_weight, color: Colors.teal),
      title: Text(
        '${measurement.weightKg} kg',
        style: const TextStyle(fontWeight: FontWeight.bold),
      ),
      subtitle: Text(lines.join('\n')),
      isThreeLine: lines.length > 2,
    );
  }
}
