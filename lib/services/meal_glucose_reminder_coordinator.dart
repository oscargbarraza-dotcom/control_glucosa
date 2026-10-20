// Se requieren parámetros con nombre explícito (`reminderRepository: ...`,
// etc.) para legibilidad en el sitio de construcción; con initializing
// formals el nombre externo del parámetro quedaría igual al del campo
// privado (`_reminderRepository`), lo que no es válido para parámetros
// nombrados. Mismo patrón ya usado en `FirestoreCloudSyncRepository`.
// ignore_for_file: prefer_initializing_formals

import '../models/glucose_measurement.dart';
import '../models/meal.dart';
import '../models/meal_glucose_reminder.dart';
import 'glucose_import_repository.dart';
import 'glucose_repository.dart';
import 'meal_glucose_reminder_repository.dart';
import 'notification_service.dart';

/// Un [MealGlucoseReminder] vencido que no pudo resolverse solo y necesita
/// que el usuario tome (o descarte) la medición manualmente.
///
/// [isDaytime] determina cómo debe notificarse en la UI: alarma sonora
/// (día, 07:00–22:00) o popup silencioso (noche, 22:00–07:00). El cálculo
/// de franja horaria vive en [MealGlucoseReminderCoordinator.isDaytime].
class PendingMealGlucoseReminder {
  const PendingMealGlucoseReminder({
    required this.reminder,
    required this.isDaytime,
  });

  final MealGlucoseReminder reminder;
  final bool isDaytime;
}

/// Resultado de [MealGlucoseReminderCoordinator.reviewPending]: separa los
/// recordatorios que se resolvieron solos (vía CGM) de los que requieren
/// acción del usuario.
class MealGlucoseReminderReviewResult {
  const MealGlucoseReminderReviewResult({
    required this.resolvedAutomatically,
    required this.needsManualAction,
  });

  /// Recordatorios ya en estado
  /// [MealGlucoseReminderStatus.resolvedAutomatically] tras esta revisión.
  final List<MealGlucoseReminder> resolvedAutomatically;

  /// Recordatorios vencidos que siguen pendientes y deben mostrarse al
  /// usuario (alarma/popup), junto con si corresponde horario diurno.
  final List<PendingMealGlucoseReminder> needsManualAction;
}

/// Orquesta el ciclo de vida de los recordatorios de medición post-comida
/// (a los 60 y 90 minutos de registrar una [Meal]): su creación, el
/// intento de auto-resolución vía sensores/CGM, y la resolución o
/// descarte manual por parte del usuario.
///
/// Es lógica pura de aplicación (sin widgets): [reviewPending] puede
/// invocarse, por ejemplo, cada vez que se abre `HomeScreen`, para que la
/// UI muestre un diálogo por cada
/// [MealGlucoseReminderReviewResult.needsManualAction].
class MealGlucoseReminderCoordinator {
  MealGlucoseReminderCoordinator({
    required MealGlucoseReminderRepository reminderRepository,
    required GlucoseRepository glucoseRepository,
    GlucoseImportRepository? importRepository,
    NotificationService? notificationService,
    DateTime Function() now = DateTime.now,
  }) : _reminderRepository = reminderRepository,
       _glucoseRepository = glucoseRepository,
       _importRepository = importRepository,
       _notificationService = notificationService,
       _now = now;

  /// Hora de inicio de la franja diurna (inclusive). Fuera de
  /// [_dayStartHour, _dayEndHour) se considera noche.
  static const _dayStartHour = 7;

  /// Hora de inicio de la franja nocturna (exclusive del lado diurno).
  static const _dayEndHour = 22;

  /// Offsets, en minutos desde [Meal.eatenAt], para los que se genera un
  /// recordatorio al registrar una comida.
  static const offsetsMinutes = [60, 90];

  /// Tolerancia para aceptar una medición del sensor/CGM como respuesta a
  /// un recordatorio: se busca la más cercana a
  /// [MealGlucoseReminder.dueAt] dentro de este margen, en cualquier
  /// dirección.
  static const _autoResolveTolerance = Duration(minutes: 10);

  final MealGlucoseReminderRepository _reminderRepository;
  final GlucoseRepository _glucoseRepository;
  final GlucoseImportRepository? _importRepository;
  final NotificationService? _notificationService;
  final DateTime Function() _now;

  /// Indica si [moment] cae en la franja diurna (07:00 inclusive –
  /// 22:00 exclusive), usada para decidir entre alarma sonora y popup
  /// silencioso.
  static bool isDaytime(DateTime moment) {
    return moment.hour >= _dayStartHour && moment.hour < _dayEndHour;
  }

  /// Genera y persiste los recordatorios (60 y 90 minutos) para [meal],
  /// y programa la notificación push correspondiente a cada uno si hay
  /// un [NotificationService] configurado (roadmap punto 17, Fase B).
  ///
  /// [meal] debe tener [Meal.id] ya asignado (una comida persistida).
  Future<List<MealGlucoseReminder>> addRemindersForMeal(Meal meal) async {
    final reminders = offsetsMinutes.map((offset) {
      return MealGlucoseReminder(
        mealId: meal.id!,
        offsetMinutes: offset,
        dueAt: meal.eatenAt.add(Duration(minutes: offset)),
      );
    }).toList();

    final saved = await _reminderRepository.addReminders(reminders);
    for (final reminder in saved) {
      await _scheduleNotification(reminder);
    }
    return saved;
  }

  /// Reprograma la notificación push de cada recordatorio todavía
  /// pendiente (vencido o no), sin tocar su estado en
  /// [MealGlucoseReminderRepository].
  ///
  /// Red de seguridad para arrancar la app (roadmap punto 17, Fase B):
  /// cubre, por ejemplo, recordatorios creados antes de que el usuario
  /// concediera el permiso de notificaciones, o alarmas que el sistema
  /// operativo haya podido perder (reinstalación de la app, etc.). Es
  /// seguro llamarla repetidamente: programar con el mismo
  /// [MealGlucoseReminder.id] reemplaza la notificación anterior en
  /// vez de duplicarla.
  Future<void> rescheduleAllPending() async {
    final pending = await _reminderRepository.getAllPending();
    for (final reminder in pending) {
      await _scheduleNotification(reminder);
    }
  }

  /// Revisa los recordatorios pendientes ya vencidos: para cada uno,
  /// intenta encontrar una medición ya existente (o recién importada
  /// desde el sensor/CGM, si [GlucoseImportRepository] está disponible)
  /// cercana a [MealGlucoseReminder.dueAt]; si no la encuentra, lo deja
  /// para acción manual.
  Future<MealGlucoseReminderReviewResult> reviewPending() async {
    final now = _now();
    final pending = await _reminderRepository.getPendingDueBy(now);
    if (pending.isEmpty) {
      return const MealGlucoseReminderReviewResult(
        resolvedAutomatically: [],
        needsManualAction: [],
      );
    }

    await _tryImportFromSensor();
    final candidates = await _glucoseRepository.getAllMeasurements();
    final usedMeasurementIds = <int>{};

    final resolved = <MealGlucoseReminder>[];
    final needsManualAction = <PendingMealGlucoseReminder>[];

    for (final reminder in pending) {
      final match = _closestUnusedMatch(
        candidates,
        reminder.dueAt,
        usedMeasurementIds,
      );
      if (match != null) {
        usedMeasurementIds.add(match.id!);
        await _reminderRepository.updateStatus(
          reminder.id!,
          status: MealGlucoseReminderStatus.resolvedAutomatically,
          resolvedMeasurementId: match.id,
        );
        await _cancelNotification(reminder);
        resolved.add(
          reminder.copyWith(
            status: MealGlucoseReminderStatus.resolvedAutomatically,
            resolvedMeasurementId: match.id,
          ),
        );
      } else {
        needsManualAction.add(
          PendingMealGlucoseReminder(
            reminder: reminder,
            isDaytime: isDaytime(now),
          ),
        );
      }
    }

    return MealGlucoseReminderReviewResult(
      resolvedAutomatically: resolved,
      needsManualAction: needsManualAction,
    );
  }

  /// Descarta [reminder] sin asociarle ninguna medición.
  Future<void> dismiss(MealGlucoseReminder reminder) async {
    await _reminderRepository.updateStatus(
      reminder.id!,
      status: MealGlucoseReminderStatus.dismissed,
    );
    await _cancelNotification(reminder);
  }

  /// Registra [measurement] (tomada manualmente por el usuario) como la
  /// medición que resuelve [reminder].
  ///
  /// Si el usuario no escribió comentario, se autogenera uno que indica
  /// que es una medición post-comida a los
  /// [MealGlucoseReminder.offsetMinutes] minutos (mismo patrón que usa la
  /// importación CGM con "Importado desde..."), sin agregar ningún campo
  /// de vínculo al modelo [GlucoseMeasurement]: queda guardada como
  /// cualquier otra medición manual del historial.
  Future<GlucoseMeasurement> resolveManually(
    MealGlucoseReminder reminder,
    GlucoseMeasurement measurement,
  ) async {
    final withComment = measurement.comment == null
        ? measurement.copyWith(
            comment: 'Medición post-comida (+${reminder.offsetMinutes} min).',
          )
        : measurement;

    final saved = await _glucoseRepository.addMeasurement(withComment);

    await _reminderRepository.updateStatus(
      reminder.id!,
      status: MealGlucoseReminderStatus.resolvedManually,
      resolvedMeasurementId: saved.id,
    );
    await _cancelNotification(reminder);

    return saved;
  }

  /// Programa la notificación push del sistema para [reminder], si hay
  /// un [NotificationService] configurado.
  ///
  /// Se usa [MealGlucoseReminder.id] como identificador de la
  /// notificación: es estable y único por recordatorio, por lo que
  /// reprogramar (ver [rescheduleAllPending]) reemplaza la notificación
  /// anterior en vez de duplicarla. Nunca lanza una excepción: el fallo
  /// al programar una notificación push no debe impedir que el
  /// recordatorio se siga gestionando in-app.
  Future<void> _scheduleNotification(MealGlucoseReminder reminder) async {
    final notificationService = _notificationService;
    if (notificationService == null) {
      return;
    }
    await notificationService.schedule(
      id: reminder.id!,
      title: 'Hora de medir tu glucosa',
      body:
          'Han pasado ${reminder.offsetMinutes} minutos desde tu comida. '
          'Registra tu nivel de glucosa para completar el seguimiento.',
      scheduledAt: reminder.dueAt,
    );
  }

  /// Cancela la notificación push del sistema asociada a [reminder], si
  /// hay un [NotificationService] configurado. Debe llamarse cada vez
  /// que [reminder] deja de estar pendiente, sea por resolución
  /// automática, manual o descarte.
  Future<void> _cancelNotification(MealGlucoseReminder reminder) async {
    await _notificationService?.cancel(reminder.id!);
  }

  Future<void> _tryImportFromSensor() async {
    final importRepository = _importRepository;
    if (importRepository == null) {
      return;
    }
    if (!await importRepository.isAvailable()) {
      return;
    }
    try {
      await importRepository.importMeasurements(
        since: _now().subtract(const Duration(hours: 4)),
      );
    } on HealthImportException {
      // Si falla la lectura del sensor, se sigue con las mediciones ya
      // existentes en el historial local; el recordatorio simplemente
      // quedará para acción manual si no hay ninguna coincidencia.
    }
  }

  /// Busca, entre [candidates], la medición no usada aún más cercana a
  /// [dueAt] dentro de [_autoResolveTolerance], o `null` si no hay
  /// ninguna.
  GlucoseMeasurement? _closestUnusedMatch(
    List<GlucoseMeasurement> candidates,
    DateTime dueAt,
    Set<int> usedMeasurementIds,
  ) {
    GlucoseMeasurement? best;
    Duration? bestDifference;

    for (final candidate in candidates) {
      if (candidate.id == null || usedMeasurementIds.contains(candidate.id)) {
        continue;
      }
      final difference = candidate.measuredAt.difference(dueAt).abs();
      if (difference > _autoResolveTolerance) {
        continue;
      }
      if (bestDifference == null || difference < bestDifference) {
        best = candidate;
        bestDifference = difference;
      }
    }

    return best;
  }
}
