// Pruebas unitarias para MealGlucoseReminderCoordinator.
//
// Usan fakes en memoria para los tres repositorios que coordina
// (recordatorios, glucosa e importación CGM), de forma que la lógica de
// día/noche y de auto-resolución se puede probar sin SQLite ni plugins
// reales.

import 'package:flutter_test/flutter_test.dart';

import 'package:seguimiento_glucosa/models/glucose_measurement.dart';
import 'package:seguimiento_glucosa/models/meal.dart';
import 'package:seguimiento_glucosa/models/meal_glucose_reminder.dart';
import 'package:seguimiento_glucosa/services/glucose_import_repository.dart';
import 'package:seguimiento_glucosa/services/glucose_repository.dart';
import 'package:seguimiento_glucosa/services/meal_glucose_reminder_coordinator.dart';
import 'package:seguimiento_glucosa/services/meal_glucose_reminder_repository.dart';
import 'package:seguimiento_glucosa/services/notification_service.dart';

class _FakeReminderRepository implements MealGlucoseReminderRepository {
  final List<MealGlucoseReminder> reminders = [];
  int _nextId = 1;

  @override
  Future<List<MealGlucoseReminder>> addReminders(
    List<MealGlucoseReminder> newReminders,
  ) async {
    final saved = newReminders.map((r) => r.copyWith(id: _nextId++)).toList();
    reminders.addAll(saved);
    return saved;
  }

  @override
  Future<List<MealGlucoseReminder>> getPendingDueBy(DateTime now) async {
    return reminders
        .where(
          (r) =>
              r.status == MealGlucoseReminderStatus.pending &&
              !r.dueAt.isAfter(now),
        )
        .toList();
  }

  @override
  Future<List<MealGlucoseReminder>> getAllPending() async {
    return reminders
        .where((r) => r.status == MealGlucoseReminderStatus.pending)
        .toList();
  }

  @override
  Future<void> updateStatus(
    int id, {
    required MealGlucoseReminderStatus status,
    int? resolvedMeasurementId,
  }) async {
    final index = reminders.indexWhere((r) => r.id == id);
    reminders[index] = reminders[index].copyWith(
      status: status,
      resolvedMeasurementId: resolvedMeasurementId,
    );
  }
}

class _FakeGlucoseRepository implements GlucoseRepository {
  final List<GlucoseMeasurement> measurements = [];
  int _nextId = 1;

  @override
  Future<GlucoseMeasurement?> getLastMeasurement() async =>
      measurements.isEmpty ? null : measurements.first;

  @override
  Future<List<GlucoseMeasurement>> getAllMeasurements() async =>
      List.unmodifiable(measurements);

  @override
  Future<GlucoseMeasurement> addMeasurement(
    GlucoseMeasurement measurement,
  ) async {
    final saved = measurement.copyWith(id: _nextId++);
    measurements.insert(0, saved);
    return saved;
  }

  @override
  Future<void> clearMeasurements() async => measurements.clear();
}

class _FakeImportRepository implements GlucoseImportRepository {
  _FakeImportRepository(this._glucoseRepository);

  final _FakeGlucoseRepository _glucoseRepository;
  bool available = true;

  /// Mediciones "descubiertas" en el sensor/CGM la próxima vez que se
  /// llame a [importMeasurements]; imita una lectura nueva disponible en
  /// Health Connect/Apple Health.
  List<GlucoseMeasurement> toDiscover = const [];
  int importCallCount = 0;

  @override
  Future<bool> isAvailable() async => available;

  @override
  Future<bool> requestPermission() async => true;

  @override
  Future<int> importMeasurements({required DateTime since}) async {
    importCallCount++;
    final discovered = toDiscover;
    toDiscover = const [];
    for (final measurement in discovered) {
      await _glucoseRepository.addMeasurement(measurement);
    }
    return discovered.length;
  }

  @override
  Future<GlucoseMeasurement?> fetchLatestMeasurement({
    Duration lookback = const Duration(hours: 4),
  }) async => null;
}

/// Fake de [NotificationService] en memoria: registra qué ids quedan
/// programados y cancelados, sin tocar ningún plugin nativo.
class _FakeNotificationService implements NotificationService {
  final Set<int> scheduledIds = {};
  final List<DateTime> scheduledAtByCall = [];

  @override
  Future<void> initialize() async {}

  @override
  Future<bool> requestPermission() async => true;

  @override
  Future<void> schedule({
    required int id,
    required String title,
    required String body,
    required DateTime scheduledAt,
  }) async {
    scheduledIds.add(id);
    scheduledAtByCall.add(scheduledAt);
  }

  @override
  Future<void> cancel(int id) async {
    scheduledIds.remove(id);
  }

  @override
  Stream<void> get onNotificationTapped => const Stream.empty();
}

void main() {
  group('isDaytime', () {
    test('07:00 es de día (límite inferior inclusive)', () {
      expect(
        MealGlucoseReminderCoordinator.isDaytime(DateTime(2026, 1, 1, 7)),
        isTrue,
      );
    });

    test('21:59 es de día', () {
      expect(
        MealGlucoseReminderCoordinator.isDaytime(DateTime(2026, 1, 1, 21, 59)),
        isTrue,
      );
    });

    test('22:00 es de noche (límite superior exclusive)', () {
      expect(
        MealGlucoseReminderCoordinator.isDaytime(DateTime(2026, 1, 1, 22)),
        isFalse,
      );
    });

    test('06:59 es de noche', () {
      expect(
        MealGlucoseReminderCoordinator.isDaytime(DateTime(2026, 1, 1, 6, 59)),
        isFalse,
      );
    });

    test('03:00 es de noche', () {
      expect(
        MealGlucoseReminderCoordinator.isDaytime(DateTime(2026, 1, 1, 3)),
        isFalse,
      );
    });
  });

  group('addRemindersForMeal', () {
    test('genera recordatorios a los 60 y 90 minutos de eatenAt', () async {
      final reminderRepository = _FakeReminderRepository();
      final coordinator = MealGlucoseReminderCoordinator(
        reminderRepository: reminderRepository,
        glucoseRepository: _FakeGlucoseRepository(),
      );

      final meal = Meal(
        id: 5,
        type: MealType.lunch,
        eatenAt: DateTime(2026, 1, 1, 13),
      );
      final created = await coordinator.addRemindersForMeal(meal);

      expect(created.length, 2);
      expect(created[0].mealId, 5);
      expect(created[0].offsetMinutes, 60);
      expect(created[0].dueAt, DateTime(2026, 1, 1, 14));
      expect(created[1].offsetMinutes, 90);
      expect(created[1].dueAt, DateTime(2026, 1, 1, 14, 30));
      expect(reminderRepository.reminders.length, 2);
    });

    test('programa una notificación por recordatorio cuando hay '
        'NotificationService', () async {
      final reminderRepository = _FakeReminderRepository();
      final notificationService = _FakeNotificationService();
      final coordinator = MealGlucoseReminderCoordinator(
        reminderRepository: reminderRepository,
        glucoseRepository: _FakeGlucoseRepository(),
        notificationService: notificationService,
      );

      final meal = Meal(
        id: 5,
        type: MealType.lunch,
        eatenAt: DateTime(2026, 1, 1, 13),
      );
      final created = await coordinator.addRemindersForMeal(meal);

      expect(notificationService.scheduledIds, {created[0].id, created[1].id});
    });
  });

  group('reviewPending', () {
    test(
      'sin importRepository, los vencidos quedan para acción manual',
      () async {
        final reminderRepository = _FakeReminderRepository();
        final glucoseRepository = _FakeGlucoseRepository();
        final coordinator = MealGlucoseReminderCoordinator(
          reminderRepository: reminderRepository,
          glucoseRepository: glucoseRepository,
          now: () => DateTime(2026, 1, 1, 10),
        );
        await reminderRepository.addReminders([
          MealGlucoseReminder(
            mealId: 1,
            offsetMinutes: 60,
            dueAt: DateTime(2026, 1, 1, 9),
          ),
        ]);

        final result = await coordinator.reviewPending();

        expect(result.resolvedAutomatically, isEmpty);
        expect(result.needsManualAction.length, 1);
        expect(result.needsManualAction.first.reminder.offsetMinutes, 60);
        expect(result.needsManualAction.first.isDaytime, isTrue);
      },
    );

    test(
      'de noche, el pendiente se marca como no diurno (popup silencioso)',
      () async {
        final reminderRepository = _FakeReminderRepository();
        final coordinator = MealGlucoseReminderCoordinator(
          reminderRepository: reminderRepository,
          glucoseRepository: _FakeGlucoseRepository(),
          now: () => DateTime(2026, 1, 1, 23),
        );
        await reminderRepository.addReminders([
          MealGlucoseReminder(
            mealId: 1,
            offsetMinutes: 60,
            dueAt: DateTime(2026, 1, 1, 22, 30),
          ),
        ]);

        final result = await coordinator.reviewPending();

        expect(result.needsManualAction.single.isDaytime, isFalse);
      },
    );

    test(
      'con CGM disponible y una medición cercana, resuelve automáticamente',
      () async {
        final reminderRepository = _FakeReminderRepository();
        final glucoseRepository = _FakeGlucoseRepository();
        final importRepository = _FakeImportRepository(glucoseRepository)
          ..toDiscover = [
            GlucoseMeasurement(
              value: 145,
              moment: GlucoseMoment.now,
              measuredAt: DateTime(2026, 1, 1, 9, 3),
              comment: 'Importado desde Health Connect.',
            ),
          ];
        final coordinator = MealGlucoseReminderCoordinator(
          reminderRepository: reminderRepository,
          glucoseRepository: glucoseRepository,
          importRepository: importRepository,
          now: () => DateTime(2026, 1, 1, 10),
        );
        await reminderRepository.addReminders([
          MealGlucoseReminder(
            mealId: 1,
            offsetMinutes: 60,
            dueAt: DateTime(2026, 1, 1, 9),
          ),
        ]);

        final result = await coordinator.reviewPending();

        expect(importRepository.importCallCount, 1);
        expect(result.needsManualAction, isEmpty);
        expect(result.resolvedAutomatically.length, 1);
        expect(
          result.resolvedAutomatically.first.resolvedMeasurementId,
          glucoseRepository.measurements.single.id,
        );
        expect(
          reminderRepository.reminders.single.status,
          MealGlucoseReminderStatus.resolvedAutomatically,
        );
      },
    );

    test('cancela la notificación programada al resolverse automáticamente '
        'vía CGM', () async {
      final reminderRepository = _FakeReminderRepository();
      final glucoseRepository = _FakeGlucoseRepository();
      final notificationService = _FakeNotificationService();
      final importRepository = _FakeImportRepository(glucoseRepository)
        ..toDiscover = [
          GlucoseMeasurement(
            value: 145,
            moment: GlucoseMoment.now,
            measuredAt: DateTime(2026, 1, 1, 9, 3),
          ),
        ];
      final coordinator = MealGlucoseReminderCoordinator(
        reminderRepository: reminderRepository,
        glucoseRepository: glucoseRepository,
        importRepository: importRepository,
        notificationService: notificationService,
        now: () => DateTime(2026, 1, 1, 10),
      );
      final saved = await reminderRepository.addReminders([
        MealGlucoseReminder(
          mealId: 1,
          offsetMinutes: 60,
          dueAt: DateTime(2026, 1, 1, 9),
        ),
      ]);
      notificationService.scheduledIds.add(saved.single.id!);

      await coordinator.reviewPending();

      expect(notificationService.scheduledIds, isEmpty);
    });

    test('con CGM disponible pero sin medición dentro de ±10 min, queda '
        'pendiente de acción manual', () async {
      final reminderRepository = _FakeReminderRepository();
      final glucoseRepository = _FakeGlucoseRepository();
      final importRepository = _FakeImportRepository(glucoseRepository)
        ..toDiscover = [
          GlucoseMeasurement(
            value: 145,
            moment: GlucoseMoment.now,
            // 15 minutos de diferencia: fuera de tolerancia.
            measuredAt: DateTime(2026, 1, 1, 9, 15),
          ),
        ];
      final coordinator = MealGlucoseReminderCoordinator(
        reminderRepository: reminderRepository,
        glucoseRepository: glucoseRepository,
        importRepository: importRepository,
        now: () => DateTime(2026, 1, 1, 10),
      );
      await reminderRepository.addReminders([
        MealGlucoseReminder(
          mealId: 1,
          offsetMinutes: 60,
          dueAt: DateTime(2026, 1, 1, 9),
        ),
      ]);

      final result = await coordinator.reviewPending();

      expect(result.resolvedAutomatically, isEmpty);
      expect(result.needsManualAction.length, 1);
    });

    test('cuando el CGM no está disponible, no intenta importar', () async {
      final reminderRepository = _FakeReminderRepository();
      final glucoseRepository = _FakeGlucoseRepository();
      final importRepository = _FakeImportRepository(glucoseRepository)
        ..available = false;
      final coordinator = MealGlucoseReminderCoordinator(
        reminderRepository: reminderRepository,
        glucoseRepository: glucoseRepository,
        importRepository: importRepository,
        now: () => DateTime(2026, 1, 1, 10),
      );
      await reminderRepository.addReminders([
        MealGlucoseReminder(
          mealId: 1,
          offsetMinutes: 60,
          dueAt: DateTime(2026, 1, 1, 9),
        ),
      ]);

      final result = await coordinator.reviewPending();

      expect(importRepository.importCallCount, 0);
      expect(result.needsManualAction.length, 1);
    });

    test(
      'una misma medición no resuelve dos recordatorios en la misma pasada',
      () async {
        final reminderRepository = _FakeReminderRepository();
        final glucoseRepository = _FakeGlucoseRepository();
        final importRepository = _FakeImportRepository(glucoseRepository)
          ..toDiscover = [
            GlucoseMeasurement(
              value: 150,
              moment: GlucoseMoment.now,
              measuredAt: DateTime(2026, 1, 1, 9, 2),
            ),
          ];
        final coordinator = MealGlucoseReminderCoordinator(
          reminderRepository: reminderRepository,
          glucoseRepository: glucoseRepository,
          importRepository: importRepository,
          now: () => DateTime(2026, 1, 1, 10),
        );
        await reminderRepository.addReminders([
          MealGlucoseReminder(
            mealId: 1,
            offsetMinutes: 60,
            dueAt: DateTime(2026, 1, 1, 9),
          ),
          MealGlucoseReminder(
            mealId: 1,
            offsetMinutes: 90,
            dueAt: DateTime(2026, 1, 1, 9, 5),
          ),
        ]);

        final result = await coordinator.reviewPending();

        expect(result.resolvedAutomatically.length, 1);
        expect(result.needsManualAction.length, 1);
      },
    );
  });

  group('dismiss', () {
    test('marca el recordatorio como descartado sin medición', () async {
      final reminderRepository = _FakeReminderRepository();
      final coordinator = MealGlucoseReminderCoordinator(
        reminderRepository: reminderRepository,
        glucoseRepository: _FakeGlucoseRepository(),
      );
      final saved = await reminderRepository.addReminders([
        MealGlucoseReminder(
          mealId: 1,
          offsetMinutes: 60,
          dueAt: DateTime(2026, 1, 1, 9),
        ),
      ]);

      await coordinator.dismiss(saved.single);

      expect(
        reminderRepository.reminders.single.status,
        MealGlucoseReminderStatus.dismissed,
      );
      expect(reminderRepository.reminders.single.resolvedMeasurementId, isNull);
    });

    test(
      'cancela la notificación programada cuando hay NotificationService',
      () async {
        final reminderRepository = _FakeReminderRepository();
        final notificationService = _FakeNotificationService();
        final coordinator = MealGlucoseReminderCoordinator(
          reminderRepository: reminderRepository,
          glucoseRepository: _FakeGlucoseRepository(),
          notificationService: notificationService,
        );
        final saved = await reminderRepository.addReminders([
          MealGlucoseReminder(
            mealId: 1,
            offsetMinutes: 60,
            dueAt: DateTime(2026, 1, 1, 9),
          ),
        ]);
        notificationService.scheduledIds.add(saved.single.id!);

        await coordinator.dismiss(saved.single);

        expect(notificationService.scheduledIds, isEmpty);
      },
    );
  });

  group('resolveManually', () {
    test('persiste la medición con comentario autogenerado cuando el '
        'usuario no escribió uno', () async {
      final reminderRepository = _FakeReminderRepository();
      final glucoseRepository = _FakeGlucoseRepository();
      final coordinator = MealGlucoseReminderCoordinator(
        reminderRepository: reminderRepository,
        glucoseRepository: glucoseRepository,
      );
      final saved = await reminderRepository.addReminders([
        MealGlucoseReminder(
          mealId: 1,
          offsetMinutes: 60,
          dueAt: DateTime(2026, 1, 1, 9),
        ),
      ]);

      final result = await coordinator.resolveManually(
        saved.single,
        GlucoseMeasurement(
          value: 160,
          moment: GlucoseMoment.afterLunch,
          measuredAt: DateTime(2026, 1, 1, 9, 1),
        ),
      );

      expect(result.comment, 'Medición post-comida (+60 min).');
      expect(
        reminderRepository.reminders.single.status,
        MealGlucoseReminderStatus.resolvedManually,
      );
      expect(
        reminderRepository.reminders.single.resolvedMeasurementId,
        result.id,
      );
    });

    test('conserva el comentario del usuario si ya escribió uno', () async {
      final reminderRepository = _FakeReminderRepository();
      final glucoseRepository = _FakeGlucoseRepository();
      final coordinator = MealGlucoseReminderCoordinator(
        reminderRepository: reminderRepository,
        glucoseRepository: glucoseRepository,
      );
      final saved = await reminderRepository.addReminders([
        MealGlucoseReminder(
          mealId: 1,
          offsetMinutes: 90,
          dueAt: DateTime(2026, 1, 1, 9, 30),
        ),
      ]);

      final result = await coordinator.resolveManually(
        saved.single,
        GlucoseMeasurement(
          value: 160,
          moment: GlucoseMoment.afterLunch,
          measuredAt: DateTime(2026, 1, 1, 9, 31),
          comment: 'Me sentí mareado',
        ),
      );

      expect(result.comment, 'Me sentí mareado');
    });

    test(
      'cancela la notificación programada cuando hay NotificationService',
      () async {
        final reminderRepository = _FakeReminderRepository();
        final glucoseRepository = _FakeGlucoseRepository();
        final notificationService = _FakeNotificationService();
        final coordinator = MealGlucoseReminderCoordinator(
          reminderRepository: reminderRepository,
          glucoseRepository: glucoseRepository,
          notificationService: notificationService,
        );
        final saved = await reminderRepository.addReminders([
          MealGlucoseReminder(
            mealId: 1,
            offsetMinutes: 60,
            dueAt: DateTime(2026, 1, 1, 9),
          ),
        ]);
        notificationService.scheduledIds.add(saved.single.id!);

        await coordinator.resolveManually(
          saved.single,
          GlucoseMeasurement(
            value: 160,
            moment: GlucoseMoment.afterLunch,
            measuredAt: DateTime(2026, 1, 1, 9, 1),
          ),
        );

        expect(notificationService.scheduledIds, isEmpty);
      },
    );
  });

  group('rescheduleAllPending', () {
    test('reprograma la notificación de cada recordatorio pendiente, '
        'vencido o no', () async {
      final reminderRepository = _FakeReminderRepository();
      final notificationService = _FakeNotificationService();
      final coordinator = MealGlucoseReminderCoordinator(
        reminderRepository: reminderRepository,
        glucoseRepository: _FakeGlucoseRepository(),
        notificationService: notificationService,
      );
      final saved = await reminderRepository.addReminders([
        MealGlucoseReminder(
          mealId: 1,
          offsetMinutes: 60,
          // Ya vencido.
          dueAt: DateTime(2020, 1, 1, 9),
        ),
        MealGlucoseReminder(
          mealId: 1,
          offsetMinutes: 90,
          // Todavía por vencer.
          dueAt: DateTime(2100, 1, 1, 9, 30),
        ),
      ]);

      await coordinator.rescheduleAllPending();

      expect(notificationService.scheduledIds, {saved[0].id, saved[1].id});
    });

    test('no reprograma recordatorios ya resueltos o descartados', () async {
      final reminderRepository = _FakeReminderRepository();
      final notificationService = _FakeNotificationService();
      final coordinator = MealGlucoseReminderCoordinator(
        reminderRepository: reminderRepository,
        glucoseRepository: _FakeGlucoseRepository(),
        notificationService: notificationService,
      );
      final saved = await reminderRepository.addReminders([
        MealGlucoseReminder(
          mealId: 1,
          offsetMinutes: 60,
          dueAt: DateTime(2100, 1, 1, 9),
        ),
      ]);
      await coordinator.dismiss(saved.single);

      await coordinator.rescheduleAllPending();

      expect(notificationService.scheduledIds, isEmpty);
    });
  });
}
