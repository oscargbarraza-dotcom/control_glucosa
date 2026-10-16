import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/glucose_measurement.dart';
import '../services/glucose_import_repository.dart';
import '../services/glucose_repository.dart';
import '../widgets/glucose_line_chart.dart';

/// Ventana de tiempo hacia atrás que cubre cada importación manual desde
/// sensores/CGM. La deduplicación por fecha/hora y valor
/// (`HealthGlucoseImportRepository`) hace seguro repetir la importación
/// sin crear duplicados, así que no es necesario recordar la fecha de la
/// última importación.
const Duration _healthImportLookback = Duration(days: 30);

/// Pantalla que muestra el historial completo de mediciones de glucosa, en
/// dos vistas: **Lista** (de la más reciente a la más antigua) y
/// **Gráfico** (evolución del valor a lo largo del tiempo).
///
/// Ambas vistas consumen [GlucoseRepository.getAllMeasurements] una sola
/// vez al abrir la pantalla.
class HistoryScreen extends StatefulWidget {
  const HistoryScreen({
    super.key,
    required this.repository,
    this.importRepository,
  });

  /// Repositorio desde el que se cargan las mediciones.
  final GlucoseRepository repository;

  /// Repositorio de importación manual desde sensores/CGM (Health
  /// Connect/Apple Health). Si es `null`, no se muestra el botón
  /// correspondiente (p. ej. en tests que no necesitan probar esa
  /// funcionalidad).
  final GlucoseImportRepository? importRepository;

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  late Future<List<GlucoseMeasurement>> _measurementsFuture;
  bool _isImporting = false;

  @override
  void initState() {
    super.initState();
    _measurementsFuture = widget.repository.getAllMeasurements();
  }

  Future<void> _importFromHealth() async {
    final importRepository = widget.importRepository;
    if (importRepository == null || _isImporting) {
      return;
    }

    setState(() {
      _isImporting = true;
    });

    String message;
    try {
      final available = await importRepository.isAvailable();
      if (!available) {
        message =
            'Health Connect no está disponible en este dispositivo. '
            'Instálalo desde la tienda de aplicaciones e intenta '
            'nuevamente.';
      } else {
        final granted = await importRepository.requestPermission();
        if (!granted) {
          message = 'Permiso de lectura de glucosa denegado.';
        } else {
          final imported = await importRepository.importMeasurements(
            since: DateTime.now().subtract(_healthImportLookback),
          );
          message = imported == 0
              ? 'No hay mediciones nuevas para importar.'
              : 'Se importaron $imported medición(es) nueva(s).';
          if (imported > 0) {
            setState(() {
              _measurementsFuture = widget.repository.getAllMeasurements();
            });
          }
        }
      }
    } on HealthImportException catch (e) {
      message = e.message;
    } finally {
      if (mounted) {
        setState(() {
          _isImporting = false;
        });
      }
    }

    if (!mounted) {
      return;
    }
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Historial'),
          actions: [
            if (widget.importRepository != null)
              IconButton(
                icon: _isImporting
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.5,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.sync),
                tooltip: 'Importar desde sensor',
                onPressed: _isImporting ? null : _importFromHealth,
              ),
          ],
          bottom: const TabBar(
            tabs: [
              Tab(text: 'Lista', icon: Icon(Icons.list)),
              Tab(text: 'Gráfico', icon: Icon(Icons.show_chart)),
            ],
          ),
        ),
        body: FutureBuilder<List<GlucoseMeasurement>>(
          future: _measurementsFuture,
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

            return TabBarView(
              children: [
                _MeasurementList(measurements: measurements),
                _MeasurementChart(measurements: measurements),
              ],
            );
          },
        ),
      ),
    );
  }
}

/// Vista de lista: de la medición más reciente a la más antigua.
class _MeasurementList extends StatelessWidget {
  const _MeasurementList({required this.measurements});

  final List<GlucoseMeasurement> measurements;

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemCount: measurements.length,
      separatorBuilder: (context, index) => const Divider(height: 1),
      itemBuilder: (context, index) {
        return _MeasurementTile(measurement: measurements[index]);
      },
    );
  }
}

/// Vista de gráfico: evolución de los valores de glucosa en el tiempo.
///
/// Requiere al menos 2 mediciones para dibujar una línea; con una sola
/// medición muestra un mensaje explicativo en su lugar.
class _MeasurementChart extends StatelessWidget {
  const _MeasurementChart({required this.measurements});

  final List<GlucoseMeasurement> measurements;

  @override
  Widget build(BuildContext context) {
    if (measurements.length < 2) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'Registra al menos dos mediciones para ver el gráfico de '
            'evolución.',
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 24, 20, 12),
      child: GlucoseLineChart(measurements: measurements),
    );
  }
}

/// Fila individual del historial con el valor, momento, fecha/hora y
/// comentario (si existe) de una medición.
class _MeasurementTile extends StatelessWidget {
  const _MeasurementTile({required this.measurement});

  final GlucoseMeasurement measurement;

  @override
  Widget build(BuildContext context) {
    final formattedDate = DateFormat(
      'dd/MM/yyyy HH:mm',
    ).format(measurement.measuredAt);

    return ListTile(
      leading: const Icon(Icons.bloodtype, color: Colors.red),
      title: Text(
        '${measurement.value} mg/dL · ${measurement.moment.label}',
        style: const TextStyle(fontWeight: FontWeight.bold),
      ),
      subtitle: Text(
        measurement.comment == null
            ? formattedDate
            : '$formattedDate\n${measurement.comment}',
      ),
      isThreeLine: measurement.comment != null,
    );
  }
}
