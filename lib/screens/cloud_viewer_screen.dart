import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/app_user.dart';
import '../models/biometric_measurement.dart';
import '../models/glucose_measurement.dart';
import '../models/meal.dart';
import '../models/medication_intake.dart';
import '../services/auth_repository.dart';
import '../services/cloud_sync_repository.dart';
import 'auth_screen.dart';

/// Visor de **solo lectura** del historial de salud sincronizado en la
/// nube, pensado para las plataformas de escritorio (Windows, macOS)
/// donde la app no ofrece ningún flujo de creación, edición ni borrado
/// de registros: solo permite consultar lo que ya se registró desde un
/// celular (Android/iOS).
///
/// Linux queda fuera de este visor: ni `firebase_auth` ni
/// `cloud_firestore` tienen soporte oficial para esa plataforma en
/// Flutter (ver "Sincronización en tiempo real" en
/// `PROJECT_CONTEXT.md`).
///
/// Sin sesión iniciada no hay nada que mostrar (ver [AuthScreen] para
/// iniciar sesión); con sesión iniciada, cada pestaña escucha en vivo
/// su subcolección de Firestore mediante
/// [CloudSyncViewer.watchGlucoseMeasurements] y equivalentes.
class CloudViewerScreen extends StatelessWidget {
  const CloudViewerScreen({
    super.key,
    required this.authRepository,
    required this.syncViewer,
  });

  final AuthRepository authRepository;
  final CloudSyncViewer syncViewer;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Seguimiento Glucosa (solo lectura)')),
      body: StreamBuilder<AppUser?>(
        stream: authRepository.authStateChanges(),
        initialData: authRepository.currentUser,
        builder: (context, snapshot) {
          final user = snapshot.data;
          if (user == null) {
            return _SignedOutMessage(authRepository: authRepository);
          }
          return _CloudViewerTabs(syncViewer: syncViewer);
        },
      ),
    );
  }
}

/// Mensaje mostrado cuando nadie tiene sesión iniciada: en escritorio
/// no existe un formulario de registro propio, solo el acceso a
/// [AuthScreen] para iniciar sesión con la misma cuenta que en el
/// celular.
class _SignedOutMessage extends StatelessWidget {
  const _SignedOutMessage({required this.authRepository});

  final AuthRepository authRepository;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.cloud_off, size: 56, color: Colors.black38),
            const SizedBox(height: 16),
            const Text(
              'Inicia sesión con la misma cuenta que usas en tu celular '
              'para ver aquí tu historial.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.black54),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute<void>(
                    builder: (context) =>
                        AuthScreen(repository: authRepository),
                  ),
                );
              },
              child: const Text('Iniciar sesión'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Con sesión iniciada: cuatro pestañas de solo lectura, una por cada
/// tipo de dato de salud, cada una escuchando en vivo su subcolección
/// de Firestore.
class _CloudViewerTabs extends StatelessWidget {
  const _CloudViewerTabs({required this.syncViewer});

  final CloudSyncViewer syncViewer;

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 4,
      child: Column(
        children: [
          const Material(
            color: Colors.white,
            child: TabBar(
              isScrollable: true,
              labelColor: Colors.deepPurple,
              tabs: [
                Tab(text: 'Glucosa', icon: Icon(Icons.bloodtype)),
                Tab(text: 'Comida', icon: Icon(Icons.restaurant)),
                Tab(text: 'Medicamentos', icon: Icon(Icons.medication)),
                Tab(text: 'Biometría', icon: Icon(Icons.favorite)),
              ],
            ),
          ),
          Expanded(
            child: TabBarView(
              children: [
                _GlucoseTab(syncViewer: syncViewer),
                _MealTab(syncViewer: syncViewer),
                _MedicationTab(syncViewer: syncViewer),
                _BiometricTab(syncViewer: syncViewer),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Lista genérica de solo lectura, reutilizada por las cuatro pestañas:
/// muestra un indicador de carga mientras llega el primer valor del
/// stream, un mensaje si está vacío, o la lista con [itemBuilder] por
/// cada elemento ya emitido.
class _CloudList<T> extends StatelessWidget {
  const _CloudList({
    required this.stream,
    required this.emptyMessage,
    required this.itemBuilder,
  });

  final Stream<List<T>> stream;
  final String emptyMessage;
  final Widget Function(T item) itemBuilder;

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<List<T>>(
      stream: stream,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final items = snapshot.data!;
        if (items.isEmpty) {
          return Center(
            child: Text(emptyMessage, textAlign: TextAlign.center),
          );
        }
        return ListView.separated(
          padding: const EdgeInsets.symmetric(vertical: 8),
          itemCount: items.length,
          separatorBuilder: (context, index) => const Divider(height: 1),
          itemBuilder: (context, index) => itemBuilder(items[index]),
        );
      },
    );
  }
}

class _GlucoseTab extends StatelessWidget {
  const _GlucoseTab({required this.syncViewer});

  final CloudSyncViewer syncViewer;

  @override
  Widget build(BuildContext context) {
    return _CloudList<GlucoseMeasurement>(
      stream: syncViewer.watchGlucoseMeasurements(),
      emptyMessage: 'Todavía no hay mediciones de glucosa sincronizadas.',
      itemBuilder: (measurement) {
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
      },
    );
  }
}

class _MealTab extends StatelessWidget {
  const _MealTab({required this.syncViewer});

  final CloudSyncViewer syncViewer;

  @override
  Widget build(BuildContext context) {
    return _CloudList<Meal>(
      stream: syncViewer.watchMeals(),
      emptyMessage: 'Todavía no hay comidas sincronizadas.',
      itemBuilder: (meal) {
        final formattedDate = DateFormat(
          'dd/MM/yyyy HH:mm',
        ).format(meal.eatenAt);
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
      },
    );
  }
}

class _MedicationTab extends StatelessWidget {
  const _MedicationTab({required this.syncViewer});

  final CloudSyncViewer syncViewer;

  @override
  Widget build(BuildContext context) {
    return _CloudList<MedicationIntake>(
      stream: syncViewer.watchMedicationIntakes(),
      emptyMessage: 'Todavía no hay tomas de medicamentos sincronizadas.',
      itemBuilder: (intake) {
        final formattedDate = DateFormat(
          'dd/MM/yyyy HH:mm',
        ).format(intake.takenAt);
        final medsSummary = intake.items
            .map(
              (item) =>
                  '${item.medication.name} '
                  '(${item.quantity} ${item.effectiveUnitLabel})',
            )
            .join(', ');
        return ListTile(
          leading: const Icon(Icons.medication, color: Colors.teal),
          title: Text(
            medsSummary.isEmpty ? 'Toma de medicamentos' : medsSummary,
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
          subtitle: Text(
            intake.comment == null
                ? formattedDate
                : '$formattedDate\n${intake.comment}',
          ),
          isThreeLine: intake.comment != null,
        );
      },
    );
  }
}

class _BiometricTab extends StatelessWidget {
  const _BiometricTab({required this.syncViewer});

  final CloudSyncViewer syncViewer;

  @override
  Widget build(BuildContext context) {
    return _CloudList<BiometricMeasurement>(
      stream: syncViewer.watchBiometricMeasurements(),
      emptyMessage: 'Todavía no hay mediciones biométricas sincronizadas.',
      itemBuilder: (measurement) {
        final formattedDate = DateFormat(
          'dd/MM/yyyy HH:mm',
        ).format(measurement.measuredAt);
        final parts = <String>['${measurement.weightKg} kg'];
        if (measurement.hasBloodPressure) {
          parts.add(
            '${measurement.systolicPressure}/'
            '${measurement.diastolicPressure} mmHg',
          );
        }
        if (measurement.heartRateBpm != null) {
          parts.add('${measurement.heartRateBpm} lpm');
        }
        return ListTile(
          leading: const Icon(Icons.favorite, color: Colors.pink),
          title: Text(
            parts.join(' · '),
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
          subtitle: Text(
            measurement.comment == null
                ? formattedDate
                : '$formattedDate\n${measurement.comment}',
          ),
          isThreeLine: measurement.comment != null,
        );
      },
    );
  }
}
