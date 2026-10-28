import 'package:flutter/material.dart';

import '../models/glucose_measurement.dart';
import '../services/glucose_import_repository.dart';
import 'glucose_screen.dart';

/// Ofrece registrar una medición de glucosa relacionada con un registro
/// recién guardado y, si el usuario acepta, abre [GlucoseScreen].
///
/// Devuelve la medición construida por el usuario, o `null` si decide no
/// medir o cierra la pantalla de registro. La persistencia queda a cargo de
/// la pantalla llamadora para mantener explícitas sus dependencias.
Future<GlucoseMeasurement?> offerGlucoseMeasurement({
  required BuildContext context,
  required String associationDescription,
  GlucoseImportRepository? importRepository,
}) async {
  final wantsToMeasure = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      icon: const Icon(Icons.bloodtype, color: Colors.red),
      title: const Text('¿Registrar tu glucosa?'),
      content: Text(
        'Puedes registrar ahora una medición de glucosa '
        '$associationDescription.',
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, false),
          child: const Text('Ahora no'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, true),
          child: const Text('Medir glucosa'),
        ),
      ],
    ),
  );

  if (wantsToMeasure != true || !context.mounted) {
    return null;
  }

  return Navigator.push<GlucoseMeasurement>(
    context,
    MaterialPageRoute(
      builder: (context) => GlucoseScreen(importRepository: importRepository),
    ),
  );
}
