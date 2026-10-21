import 'package:flutter/material.dart';

import '../models/glucose_measurement.dart';
import '../services/glucose_import_repository.dart';

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
  const GlucoseScreen({super.key, this.importRepository});

  /// Repositorio de importación manual desde sensores/CGM (Health
  /// Connect/Apple Health), usado por el botón "Tomar desde sensor"
  /// para prellenar el valor sin que el usuario tenga que escribirlo.
  /// Si es `null`, el botón no se muestra (p. ej. en tests que no
  /// necesitan probar esa funcionalidad).
  final GlucoseImportRepository? importRepository;

  @override
  State<GlucoseScreen> createState() => _GlucoseScreenState();
}

class _GlucoseScreenState extends State<GlucoseScreen> {
  final _formKey = GlobalKey<FormState>();
  final TextEditingController _glucoseController = TextEditingController();
  final TextEditingController _commentController = TextEditingController();

  GlucoseMoment _selectedMoment = GlucoseMoment.now;
  bool _isFetchingFromSensor = false;

  @override
  void dispose() {
    _glucoseController.dispose();
    _commentController.dispose();
    super.dispose();
  }

  Future<void> _takeFromSensor() async {
    final importRepository = widget.importRepository;
    if (importRepository == null || _isFetchingFromSensor) {
      return;
    }

    setState(() {
      _isFetchingFromSensor = true;
    });

    String? errorMessage;
    GlucoseMeasurement? measurement;
    try {
      final available = await importRepository.isAvailable();
      if (!available) {
        errorMessage =
            'Health Connect no está disponible en este dispositivo. '
            'Instálalo desde la tienda de aplicaciones e intenta '
            'nuevamente.';
      } else {
        final granted = await importRepository.requestPermission();
        if (!granted) {
          errorMessage = 'Permiso de lectura de glucosa denegado.';
        } else {
          measurement = await importRepository.fetchLatestMeasurement();
          if (measurement == null) {
            errorMessage = 'El sensor no tiene mediciones recientes.';
          }
        }
      }
    } on HealthImportException catch (e) {
      errorMessage = e.message;
    } finally {
      if (mounted) {
        setState(() {
          _isFetchingFromSensor = false;
        });
      }
    }

    if (!mounted) {
      return;
    }

    if (measurement != null) {
      _glucoseController.text = measurement.value.toString();
      if (measurement.comment != null) {
        _commentController.text = measurement.comment!;
      }
      return;
    }

    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(errorMessage!)));
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
      appBar: AppBar(
        title: const Text('Registrar glucosa'),
        actions: [
          if (widget.importRepository != null)
            IconButton(
              icon: _isFetchingFromSensor
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2.5,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.sensors),
              tooltip: 'Tomar desde sensor',
              onPressed: _isFetchingFromSensor ? null : _takeFromSensor,
            ),
        ],
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(20),
          keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
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
              // El botón mide su contenido por defecto, y el `Row` con
              // ícono + texto de las etiquetas más largas (p. ej.
              // "Después desayuno") no entra en ese ancho mínimo, lo
              // que producía un `RenderFlex overflowed` horizontal.
              // `isExpanded` hace que el botón ocupe todo el ancho del
              // campo, dándole espacio suficiente al `Row` interno.
              isExpanded: true,
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
                      Expanded(
                        child: Text(
                          moment.label,
                          style: const TextStyle(fontSize: 18),
                          overflow: TextOverflow.ellipsis,
                        ),
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
    );
  }
}
