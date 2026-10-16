import 'package:flutter/material.dart';

import '../models/glucose_measurement.dart';

/// Datos visuales (icono y color) asociados a cada [GlucoseMoment].
const Map<GlucoseMoment, (IconData, Color)> _momentVisuals = {
  GlucoseMoment.now: (Icons.schedule, Colors.blue),
  GlucoseMoment.wakingUp: (Icons.wb_sunny, Colors.orange),
  GlucoseMoment.beforeBreakfast: (Icons.free_breakfast, Colors.brown),
  GlucoseMoment.afterBreakfast: (Icons.restaurant, Colors.green),
  GlucoseMoment.beforeLunch: (Icons.lunch_dining, Colors.orange),
  GlucoseMoment.afterLunch: (Icons.restaurant_menu, Colors.green),
  GlucoseMoment.beforeDinner: (Icons.dinner_dining, Colors.deepPurple),
  GlucoseMoment.afterDinner: (Icons.nightlife, Colors.indigo),
  GlucoseMoment.beforeSleep: (Icons.bedtime, Colors.blueGrey),
};

/// Pantalla de registro de una medición de glucosa.
///
/// Al guardar, retorna un [GlucoseMeasurement] a la pantalla anterior
/// mediante `Navigator.pop`.
class GlucoseScreen extends StatefulWidget {
  const GlucoseScreen({super.key});

  @override
  State<GlucoseScreen> createState() => _GlucoseScreenState();
}

class _GlucoseScreenState extends State<GlucoseScreen> {
  final _formKey = GlobalKey<FormState>();
  final TextEditingController _glucoseController = TextEditingController();
  final TextEditingController _commentController = TextEditingController();

  GlucoseMoment _selectedMoment = GlucoseMoment.now;

  @override
  void dispose() {
    _glucoseController.dispose();
    _commentController.dispose();
    super.dispose();
  }

  String? _validateGlucoseValue(String? input) {
    if (input == null || input.trim().isEmpty) {
      return 'Ingresa un valor de glucosa.';
    }
    final parsed = int.tryParse(input.trim());
    if (parsed == null) {
      return 'Ingresa solo números.';
    }
    if (parsed < 20 || parsed > 600) {
      return 'El valor debe estar entre 20 y 600 mg/dL.';
    }
    return null;
  }

  void _saveMeasurement() {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    final measurement = GlucoseMeasurement(
      value: int.parse(_glucoseController.text.trim()),
      moment: _selectedMoment,
      measuredAt: DateTime.now(),
      comment: _commentController.text.trim().isEmpty
          ? null
          : _commentController.text.trim(),
    );

    Navigator.pop(context, measurement);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Registrar glucosa')),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Form(
          key: _formKey,
          child: Column(
            children: [
              const Icon(Icons.bloodtype, color: Colors.red, size: 70),
              const SizedBox(height: 20),
              TextFormField(
                controller: _glucoseController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Glucosa mg/dL',
                  border: OutlineInputBorder(),
                ),
                validator: _validateGlucoseValue,
              ),
              const SizedBox(height: 20),
              DropdownButtonFormField<GlucoseMoment>(
                initialValue: _selectedMoment,
                style: const TextStyle(fontSize: 18, color: Colors.black87),
                decoration: const InputDecoration(
                  labelText: 'Momento de medición',
                  border: OutlineInputBorder(),
                ),
                items: GlucoseMoment.values.map((moment) {
                  final (icon, color) = _momentVisuals[moment]!;
                  return DropdownMenuItem(
                    value: moment,
                    child: Row(
                      children: [
                        Icon(icon, color: color),
                        const SizedBox(width: 12),
                        Text(
                          moment.label,
                          style: const TextStyle(fontSize: 18),
                        ),
                      ],
                    ),
                  );
                }).toList(),
                onChanged: (moment) {
                  if (moment == null) {
                    return;
                  }
                  setState(() {
                    _selectedMoment = moment;
                  });
                },
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
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _saveMeasurement,
                  child: const Text('Guardar'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
