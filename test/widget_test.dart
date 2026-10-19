// Pruebas de widgets para la pantalla principal de Seguimiento Glucosa.
//
// Verifican que la app arranca mostrando la tarjeta de glucosa sin valor
// registrado, que al tocarla se navega al formulario de registro, que una
// medición guardada se persiste a través de [GlucoseRepository], que la
// pantalla de Historial muestra correctamente sus pestañas de Lista y
// Gráfico (incluyendo el caso con menos de 2 mediciones), que el módulo
// de Comidas permite registrar una comida con alimentos y verla reflejada
// en su propio historial, y que el módulo de Medicamentos permite
// registrar una toma con medicamentos (incluyendo unidad personalizada) y
// verla reflejada en su propio historial.
//
// Se inyectan repositorios fake en memoria para no depender del plugin
// real de `sqflite` (que requiere mocks de plataforma aparte).

import 'dart:async';

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:seguimiento_glucosa/models/app_user.dart';
import 'package:seguimiento_glucosa/models/biometric_measurement.dart';
import 'package:seguimiento_glucosa/models/food.dart';
import 'package:seguimiento_glucosa/models/glucose_measurement.dart';
import 'package:seguimiento_glucosa/models/meal.dart';
import 'package:seguimiento_glucosa/models/meal_glucose_reminder.dart';
import 'package:seguimiento_glucosa/models/medication.dart';
import 'package:seguimiento_glucosa/models/medication_intake.dart';
import 'package:seguimiento_glucosa/models/user_profile.dart';
import 'package:seguimiento_glucosa/screens/home_screen.dart';
import 'package:seguimiento_glucosa/services/auth_repository.dart';
import 'package:seguimiento_glucosa/services/backup_repository.dart';
import 'package:seguimiento_glucosa/services/biometric_repository.dart';
import 'package:seguimiento_glucosa/services/glucose_import_repository.dart';
import 'package:seguimiento_glucosa/services/glucose_repository.dart';
import 'package:seguimiento_glucosa/services/meal_glucose_reminder_repository.dart';
import 'package:seguimiento_glucosa/services/meal_repository.dart';
import 'package:seguimiento_glucosa/services/medication_repository.dart';
import 'package:seguimiento_glucosa/services/notification_service.dart';
import 'package:seguimiento_glucosa/services/user_profile_repository.dart';

/// Repositorio en memoria usado solo en pruebas, para evitar llamadas al
/// plugin real de `sqflite` durante los widget tests.
class _FakeGlucoseRepository implements GlucoseRepository {
  final List<GlucoseMeasurement> _measurements = [];
  int _nextId = 1;

  /// Última medición agregada mediante [addMeasurement], expuesta para
  /// aserciones directas en los tests.
  GlucoseMeasurement? get stored =>
      _measurements.isEmpty ? null : _measurements.first;

  @override
  Future<GlucoseMeasurement?> getLastMeasurement() async => stored;

  @override
  Future<List<GlucoseMeasurement>> getAllMeasurements() async =>
      List.unmodifiable(_measurements);

  @override
  Future<GlucoseMeasurement> addMeasurement(
    GlucoseMeasurement measurement,
  ) async {
    final saved = measurement.copyWith(id: _nextId++);
    _measurements.insert(0, saved);
    return saved;
  }

  @override
  Future<void> clearMeasurements() async {
    _measurements.clear();
  }
}

/// Repositorio de comidas en memoria usado solo en pruebas, para evitar
/// llamadas al plugin real de `sqflite` durante los widget tests.
class _FakeMealRepository implements MealRepository {
  final List<Meal> _meals = [];
  final List<Food> _foods = [];
  int _nextMealId = 1;
  int _nextItemId = 1;
  int _nextFoodId = 1;

  /// Comidas agregadas mediante [addMeal], expuestas para aserciones
  /// directas en los tests.
  List<Meal> get stored => List.unmodifiable(_meals);

  @override
  Future<List<Meal>> getAllMeals() async => List.unmodifiable(_meals);

  @override
  Future<Meal> addMeal(Meal meal) async {
    final savedItems = meal.items.map((item) {
      var food = _foods.firstWhere(
        (f) => f.name == item.food.name,
        orElse: () => Food(id: _nextFoodId++, name: item.food.name),
      );
      if (!_foods.contains(food)) {
        _foods.add(food);
      }
      return MealFoodItem(
        id: _nextItemId++,
        food: food,
        quantity: item.quantity,
      );
    }).toList();

    final saved = meal.copyWith(id: _nextMealId++, items: savedItems);
    _meals.insert(0, saved);
    return saved;
  }

  @override
  Future<void> clearMeals() async {
    _meals.clear();
  }

  @override
  Future<List<Food>> getAllFoods() async => List.unmodifiable(_foods);
}

/// Repositorio de recordatorios de glucosa post-comida en memoria usado
/// solo en pruebas, para evitar llamadas al plugin real de `sqflite`
/// durante los widget tests.
class _FakeMealGlucoseReminderRepository
    implements MealGlucoseReminderRepository {
  final List<MealGlucoseReminder> _reminders = [];
  int _nextId = 1;

  @override
  Future<List<MealGlucoseReminder>> addReminders(
    List<MealGlucoseReminder> reminders,
  ) async {
    final saved = reminders.map((r) => r.copyWith(id: _nextId++)).toList();
    _reminders.addAll(saved);
    return saved;
  }

  @override
  Future<List<MealGlucoseReminder>> getPendingDueBy(DateTime now) async {
    return _reminders
        .where(
          (r) =>
              r.status == MealGlucoseReminderStatus.pending &&
              !r.dueAt.isAfter(now),
        )
        .toList();
  }

  @override
  Future<List<MealGlucoseReminder>> getAllPending() async {
    return _reminders
        .where((r) => r.status == MealGlucoseReminderStatus.pending)
        .toList();
  }

  @override
  Future<void> updateStatus(
    int id, {
    required MealGlucoseReminderStatus status,
    int? resolvedMeasurementId,
  }) async {
    final index = _reminders.indexWhere((r) => r.id == id);
    _reminders[index] = _reminders[index].copyWith(
      status: status,
      resolvedMeasurementId: resolvedMeasurementId,
    );
  }
}

/// Repositorio de medicamentos en memoria usado solo en pruebas, para
/// evitar llamadas al plugin real de `sqflite` durante los widget tests.
class _FakeMedicationRepository implements MedicationRepository {
  final List<MedicationIntake> _intakes = [];
  final List<Medication> _medications = [];
  int _nextIntakeId = 1;
  int _nextItemId = 1;
  int _nextMedicationId = 1;

  /// Tomas agregadas mediante [addIntake], expuestas para aserciones
  /// directas en los tests.
  List<MedicationIntake> get stored => List.unmodifiable(_intakes);

  @override
  Future<List<MedicationIntake>> getAllIntakes() async =>
      List.unmodifiable(_intakes);

  @override
  Future<MedicationIntake> addIntake(MedicationIntake intake) async {
    final savedItems = intake.items.map((item) {
      var medication = _medications.firstWhere(
        (m) => m.name == item.medication.name,
        orElse: () => Medication(
          id: _nextMedicationId++,
          name: item.medication.name,
          defaultUnit: item.medication.defaultUnit,
        ),
      );
      if (!_medications.contains(medication)) {
        _medications.add(medication);
      }
      return MedicationIntakeItem(
        id: _nextItemId++,
        medication: medication,
        quantity: item.quantity,
        unit: item.unit,
        customUnitLabel: item.customUnitLabel,
      );
    }).toList();

    final saved = intake.copyWith(id: _nextIntakeId++, items: savedItems);
    _intakes.insert(0, saved);
    return saved;
  }

  @override
  Future<void> clearIntakes() async {
    _intakes.clear();
  }

  @override
  Future<List<Medication>> getAllMedications() async =>
      List.unmodifiable(_medications);
}

/// Repositorio de biometría en memoria usado solo en pruebas, para evitar
/// llamadas al plugin real de `sqflite` durante los widget tests.
class _FakeBiometricRepository implements BiometricRepository {
  final List<BiometricMeasurement> _measurements = [];
  int _nextId = 1;

  /// Mediciones agregadas mediante [addMeasurement], expuestas para
  /// aserciones directas en los tests.
  List<BiometricMeasurement> get stored => List.unmodifiable(_measurements);

  @override
  Future<BiometricMeasurement?> getLastMeasurement() async =>
      _measurements.isEmpty ? null : _measurements.first;

  @override
  Future<List<BiometricMeasurement>> getAllMeasurements() async =>
      List.unmodifiable(_measurements);

  @override
  Future<BiometricMeasurement> addMeasurement(
    BiometricMeasurement measurement,
  ) async {
    final saved = measurement.copyWith(id: _nextId++);
    _measurements.insert(0, saved);
    return saved;
  }

  @override
  Future<void> clearMeasurements() async {
    _measurements.clear();
  }
}

/// Repositorio de perfil de usuario en memoria usado solo en pruebas,
/// para evitar llamadas al plugin real de `sqflite` durante los widget
/// tests.
class _FakeUserProfileRepository implements UserProfileRepository {
  UserProfile? _profile;

  @override
  Future<UserProfile?> getProfile() async => _profile;

  @override
  Future<void> saveProfile(UserProfile profile) async {
    _profile = profile;
  }

  @override
  Future<void> clearProfile() async {
    _profile = null;
  }
}

/// Repositorio de autenticación en memoria usado solo en pruebas, para
/// evitar llamadas al SDK real de Firebase durante los widget tests. No
/// valida credenciales: cualquier correo/contraseña "inicia sesión"
/// exitosamente, salvo que se pida simular un error mediante
/// [failWith].
class _FakeAuthRepository implements AuthRepository {
  final _controller = StreamController<AppUser?>.broadcast();
  AppUser? _currentUser;

  /// Si no es `null`, el próximo método de inicio de sesión/registro
  /// lanzará esta excepción en lugar de "autenticar" al usuario.
  AuthException? failWith;

  @override
  Stream<AppUser?> authStateChanges() => _controller.stream;

  @override
  AppUser? get currentUser => _currentUser;

  void _setUser(AppUser? user) {
    _currentUser = user;
    _controller.add(user);
  }

  @override
  Future<AppUser> registerWithEmail({
    required String email,
    required String password,
  }) async {
    if (failWith != null) {
      throw failWith!;
    }
    final user = AppUser(uid: 'uid-$email', email: email);
    _setUser(user);
    return user;
  }

  @override
  Future<AppUser> signInWithEmail({
    required String email,
    required String password,
  }) async {
    if (failWith != null) {
      throw failWith!;
    }
    final user = AppUser(uid: 'uid-$email', email: email);
    _setUser(user);
    return user;
  }

  @override
  Future<AppUser?> signInWithGoogle() async {
    if (failWith != null) {
      throw failWith!;
    }
    const user = AppUser(
      uid: 'uid-google',
      email: 'persona@gmail.com',
      displayName: 'Persona de Prueba',
    );
    _setUser(user);
    return user;
  }

  @override
  Future<void> sendPasswordResetEmail(String email) async {
    if (failWith != null) {
      throw failWith!;
    }
  }

  @override
  Future<void> signOut() async {
    _setUser(null);
  }
}

/// Repositorio de respaldo/restauración en memoria usado solo en
/// pruebas, para evitar llamadas reales a Cloud Firestore durante los
/// widget tests. Un flag [failWith] permite simular un error en la
/// próxima operación.
class _FakeBackupRepository implements BackupRepository {
  bool hasBackup = false;
  int backupCallCount = 0;
  int restoreCallCount = 0;
  BackupException? failWith;

  @override
  Future<void> backup() async {
    if (failWith != null) {
      throw failWith!;
    }
    backupCallCount++;
    hasBackup = true;
  }

  @override
  Future<void> restore() async {
    if (failWith != null) {
      throw failWith!;
    }
    if (!hasBackup) {
      throw const BackupException(
        'Todavía no tienes ningún respaldo guardado en la nube.',
      );
    }
    restoreCallCount++;
  }

  @override
  Future<DateTime?> getLastBackupTime() async =>
      hasBackup ? DateTime(2026, 1, 1) : null;
}

/// Repositorio de importación desde sensores/CGM en memoria usado solo
/// en pruebas, para evitar llamadas al plugin real `health`.
///
/// [importMeasurements] agrega las mediciones de [pending] a
/// [glucoseRepository], imitando lo que hace la implementación real al
/// encontrar datos nuevos en Health Connect/Apple Health.
class _FakeGlucoseImportRepository implements GlucoseImportRepository {
  _FakeGlucoseImportRepository(this.glucoseRepository);

  final GlucoseRepository glucoseRepository;
  bool available = true;
  bool permissionGranted = true;
  List<GlucoseMeasurement> pending = const [];
  HealthImportException? failWith;
  int importCallCount = 0;

  @override
  Future<bool> isAvailable() async => available;

  @override
  Future<bool> requestPermission() async => permissionGranted;

  @override
  Future<int> importMeasurements({required DateTime since}) async {
    if (failWith != null) {
      throw failWith!;
    }
    importCallCount++;
    final toImport = pending;
    pending = const [];
    for (final measurement in toImport) {
      await glucoseRepository.addMeasurement(measurement);
    }
    return toImport.length;
  }
}

/// Servicio de notificaciones en memoria usado solo en pruebas, para
/// evitar llamadas al plugin real `flutter_local_notifications`.
class _FakeNotificationService implements NotificationService {
  final Set<int> scheduledIds = {};
  bool permissionGranted = true;
  int requestPermissionCallCount = 0;
  final _tapController = StreamController<void>.broadcast();

  /// Simula que el usuario tocó una notificación ya mostrada.
  void simulateTap() => _tapController.add(null);

  @override
  Future<void> initialize() async {}

  @override
  Future<bool> requestPermission() async {
    requestPermissionCallCount++;
    return permissionGranted;
  }

  @override
  Future<void> schedule({
    required int id,
    required String title,
    required String body,
    required DateTime scheduledAt,
  }) async {
    scheduledIds.add(id);
  }

  @override
  Future<void> cancel(int id) async {
    scheduledIds.remove(id);
  }

  @override
  Stream<void> get onNotificationTapped => _tapController.stream;
}

void main() {
  testWidgets('HomeScreen muestra la tarjeta de glucosa sin valor inicial', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(home: HomeScreen(repository: _FakeGlucoseRepository())),
    );
    await tester.pumpAndSettle();

    expect(find.text('Seguimiento Glucosa'), findsOneWidget);
    expect(find.text('-- mg/dL'), findsOneWidget);
  });

  testWidgets('Tocar la tarjeta de glucosa navega a GlucoseScreen', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(home: HomeScreen(repository: _FakeGlucoseRepository())),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Glucosa actual'));
    await tester.pumpAndSettle();

    expect(find.text('Registrar glucosa'), findsOneWidget);
  });

  testWidgets('Guardar una medición la persiste y actualiza la tarjeta', (
    WidgetTester tester,
  ) async {
    final repository = _FakeGlucoseRepository();
    await tester.pumpWidget(
      MaterialApp(home: HomeScreen(repository: repository)),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Glucosa actual'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextFormField), '120');
    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(find.text('Seguimiento Glucosa'), findsOneWidget);
    expect(find.text('120 mg/dL'), findsOneWidget);
    expect(repository.stored?.value, 120);
  });

  testWidgets('Tocar Historial navega a HistoryScreen y lista las mediciones', (
    WidgetTester tester,
  ) async {
    final repository = _FakeGlucoseRepository();
    await repository.addMeasurement(
      GlucoseMeasurement(
        value: 95,
        moment: GlucoseMoment.beforeBreakfast,
        measuredAt: DateTime(2026, 1, 1, 8),
      ),
    );

    await tester.pumpWidget(
      MaterialApp(home: HomeScreen(repository: repository)),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Historial'));
    await tester.pumpAndSettle();

    expect(find.text('Historial'), findsOneWidget);
    expect(find.textContaining('95 mg/dL'), findsOneWidget);
  });

  testWidgets(
    'La pestaña Gráfico muestra un mensaje con menos de 2 mediciones',
    (WidgetTester tester) async {
      final repository = _FakeGlucoseRepository();
      await repository.addMeasurement(
        GlucoseMeasurement(
          value: 95,
          moment: GlucoseMoment.beforeBreakfast,
          measuredAt: DateTime(2026, 1, 1, 8),
        ),
      );

      await tester.pumpWidget(
        MaterialApp(home: HomeScreen(repository: repository)),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Historial'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Gráfico'));
      await tester.pumpAndSettle();

      expect(
        find.textContaining('Registra al menos dos mediciones'),
        findsOneWidget,
      );
    },
  );

  testWidgets('La pestaña Gráfico dibuja un LineChart con 2 o más mediciones', (
    WidgetTester tester,
  ) async {
    final repository = _FakeGlucoseRepository();
    await repository.addMeasurement(
      GlucoseMeasurement(
        value: 95,
        moment: GlucoseMoment.beforeBreakfast,
        measuredAt: DateTime(2026, 1, 1, 8),
      ),
    );
    await repository.addMeasurement(
      GlucoseMeasurement(
        value: 110,
        moment: GlucoseMoment.afterBreakfast,
        measuredAt: DateTime(2026, 1, 1, 10),
      ),
    );

    await tester.pumpWidget(
      MaterialApp(home: HomeScreen(repository: repository)),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Historial'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Gráfico'));
    await tester.pumpAndSettle();

    expect(find.byType(LineChart), findsOneWidget);
  });

  testWidgets('Tocar Comida navega a MealScreen con sus pestañas', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: _FakeGlucoseRepository(),
          mealRepository: _FakeMealRepository(),
          reminderRepository: _FakeMealGlucoseReminderRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Comida'));
    await tester.pumpAndSettle();

    expect(find.text('Registrar'), findsOneWidget);
    expect(find.text('Historial'), findsOneWidget);

    // TabBarView no construye páginas fuera del viewport por defecto: hay
    // que tocar la pestaña "Historial" para que su FutureBuilder se arme.
    await tester.tap(find.text('Historial'));
    await tester.pumpAndSettle();

    expect(find.text('Todavía no hay comidas registradas.'), findsOneWidget);
  });

  testWidgets(
    'Registrar una comida con alimentos la persiste y la muestra en el '
    'historial',
    (WidgetTester tester) async {
      final mealRepository = _FakeMealRepository();
      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            repository: _FakeGlucoseRepository(),
            mealRepository: mealRepository,
            reminderRepository: _FakeMealGlucoseReminderRepository(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Comida'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.widgetWithText(TextFormField, 'Alimento'),
        'Arroz',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Cantidad'),
        '1 taza',
      );
      await tester.tap(find.byTooltip('Agregar alimento'));
      await tester.pumpAndSettle();

      expect(find.text('Arroz'), findsOneWidget);

      await tester.tap(find.text('Guardar'));
      await tester.pumpAndSettle();

      expect(find.text('Comida guardada.'), findsOneWidget);
      expect(mealRepository.stored, hasLength(1));
      expect(mealRepository.stored.single.items.single.food.name, 'Arroz');

      // Tras guardar, la pestaña cambia automáticamente a "Historial".
      expect(find.text('Desayuno'), findsOneWidget);
      expect(find.textContaining('Arroz (1 taza)'), findsOneWidget);
    },
  );

  testWidgets('Tocar Medicamentos navega a MedicationScreen con sus pestañas', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: _FakeGlucoseRepository(),
          medicationRepository: _FakeMedicationRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Medicamentos'));
    await tester.pumpAndSettle();

    expect(find.text('Registrar'), findsOneWidget);
    expect(find.text('Historial'), findsOneWidget);

    // TabBarView no construye páginas fuera del viewport por defecto: hay
    // que tocar la pestaña "Historial" para que su FutureBuilder se arme.
    await tester.tap(find.text('Historial'));
    await tester.pumpAndSettle();

    expect(find.text('Todavía no hay tomas registradas.'), findsOneWidget);
  });

  testWidgets('Registrar una toma con unidad personalizada la persiste y la '
      'muestra en el historial', (WidgetTester tester) async {
    final medicationRepository = _FakeMedicationRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: _FakeGlucoseRepository(),
          medicationRepository: medicationRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Medicamentos'));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.widgetWithText(TextFormField, 'Medicamento'),
      'Parche de nicotina',
    );
    await tester.enterText(find.widgetWithText(TextFormField, 'Cantidad'), '1');
    await tester.tap(find.byType(DropdownButtonFormField<DoseUnit>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Otro').last);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Unidad personalizada'),
      'parche',
    );
    await tester.tap(find.byTooltip('Agregar medicamento'));
    await tester.pumpAndSettle();

    expect(find.text('Parche de nicotina'), findsOneWidget);

    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(find.text('Toma guardada.'), findsOneWidget);
    expect(medicationRepository.stored, hasLength(1));
    expect(
      medicationRepository.stored.single.items.single.medication.name,
      'Parche de nicotina',
    );
    expect(
      medicationRepository.stored.single.items.single.customUnitLabel,
      'parche',
    );

    // Tras guardar, la pestaña cambia automáticamente a "Historial".
    expect(
      find.textContaining('Parche de nicotina (1.0 parche)'),
      findsOneWidget,
    );
  });

  testWidgets(
    'Agregar un medicamento con coma decimal en la cantidad lo persiste '
    '(regresión: el teclado en español usa coma, no punto)',
    (WidgetTester tester) async {
      final medicationRepository = _FakeMedicationRepository();
      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            repository: _FakeGlucoseRepository(),
            medicationRepository: medicationRepository,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Medicamentos'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.widgetWithText(TextFormField, 'Medicamento'),
        'Metformina',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Cantidad'),
        '5,5',
      );
      await tester.tap(find.byTooltip('Agregar medicamento'));
      await tester.pumpAndSettle();

      // El medicamento se agregó a la lista (no quedó bloqueado en
      // silencio por un `double.tryParse` que no entendía la coma).
      expect(find.text('Metformina'), findsOneWidget);
      expect(find.textContaining('5.5'), findsOneWidget);

      await tester.tap(find.text('Guardar'));
      await tester.pumpAndSettle();

      expect(find.text('Toma guardada.'), findsOneWidget);
      expect(medicationRepository.stored, hasLength(1));
      expect(medicationRepository.stored.single.items.single.quantity, 5.5);
    },
  );

  testWidgets(
    'Intentar agregar un medicamento con cantidad inválida muestra un '
    'mensaje claro en vez de fallar en silencio',
    (WidgetTester tester) async {
      final medicationRepository = _FakeMedicationRepository();
      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            repository: _FakeGlucoseRepository(),
            medicationRepository: medicationRepository,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Medicamentos'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.widgetWithText(TextFormField, 'Medicamento'),
        'Metformina',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Cantidad'),
        'abc',
      );
      await tester.tap(find.byTooltip('Agregar medicamento'));
      await tester.pumpAndSettle();

      expect(
        find.text('Ingresa una cantidad numérica válida.'),
        findsOneWidget,
      );
      // El nombre permanece en el campo (no se borra en un error), pero el
      // medicamento no se agregó a la lista de la toma en construcción.
      expect(
        find.text('Todavía no agregaste medicamentos a esta toma.'),
        findsOneWidget,
      );
    },
  );

  testWidgets('Tocar Biometría navega a BiometricScreen con sus pestañas', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: _FakeGlucoseRepository(),
          biometricRepository: _FakeBiometricRepository(),
          profileRepository: _FakeUserProfileRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Biometría'));
    await tester.pumpAndSettle();

    expect(find.text('Registrar'), findsOneWidget);
    expect(find.text('Perfil'), findsOneWidget);
    expect(find.text('Historial'), findsOneWidget);

    // TabBarView no construye páginas fuera del viewport por defecto: hay
    // que tocar la pestaña "Historial" para que su FutureBuilder se arme.
    await tester.tap(find.text('Historial'));
    await tester.pumpAndSettle();

    expect(find.text('Todavía no hay mediciones registradas.'), findsOneWidget);
  });

  testWidgets('Registrar un peso lo persiste y lo muestra en el historial', (
    WidgetTester tester,
  ) async {
    // El formulario de Biometría tiene más campos de los que entran en el
    // tamaño de superficie por defecto de los tests; se agranda para que
    // el botón "Guardar" quede visible sin necesidad de hacer scroll.
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final biometricRepository = _FakeBiometricRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: _FakeGlucoseRepository(),
          biometricRepository: biometricRepository,
          profileRepository: _FakeUserProfileRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Biometría'));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.widgetWithText(TextFormField, 'Peso corporal (kg)'),
      '70.5',
    );
    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(find.text('Medición guardada.'), findsOneWidget);
    expect(biometricRepository.stored, hasLength(1));
    expect(biometricRepository.stored.single.weightKg, 70.5);

    // Tras guardar, la pestaña cambia automáticamente a "Historial".
    expect(find.text('70.5 kg'), findsOneWidget);
  });

  testWidgets(
    'Registrar un peso con presión y frecuencia cardíaca las persiste',
    (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      final biometricRepository = _FakeBiometricRepository();
      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            repository: _FakeGlucoseRepository(),
            biometricRepository: biometricRepository,
            profileRepository: _FakeUserProfileRepository(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Biometría'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.widgetWithText(TextFormField, 'Peso corporal (kg)'),
        '80',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Sistólica (mmHg)'),
        '120',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Diastólica (mmHg)'),
        '80',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Frecuencia cardíaca (lpm)'),
        '70',
      );
      await tester.tap(find.text('Guardar'));
      await tester.pumpAndSettle();

      expect(find.text('Medición guardada.'), findsOneWidget);
      expect(biometricRepository.stored, hasLength(1));
      final saved = biometricRepository.stored.single;
      expect(saved.systolicPressure, 120);
      expect(saved.diastolicPressure, 80);
      expect(saved.heartRateBpm, 70);

      expect(find.textContaining('Presión: 120/80 mmHg'), findsOneWidget);
      expect(
        find.textContaining('Frecuencia cardíaca: 70 lpm'),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'Completar solo la presión sistólica muestra un error de validación',
    (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            repository: _FakeGlucoseRepository(),
            biometricRepository: _FakeBiometricRepository(),
            profileRepository: _FakeUserProfileRepository(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Biometría'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.widgetWithText(TextFormField, 'Peso corporal (kg)'),
        '80',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Sistólica (mmHg)'),
        '120',
      );
      await tester.tap(find.text('Guardar'));
      await tester.pumpAndSettle();

      expect(
        find.text('Completa ambos valores de presión, o ninguno.'),
        findsOneWidget,
      );
    },
  );

  testWidgets('Guardar el perfil con altura lo persiste', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final profileRepository = _FakeUserProfileRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: _FakeGlucoseRepository(),
          biometricRepository: _FakeBiometricRepository(),
          profileRepository: profileRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Biometría'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Perfil'));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.widgetWithText(TextFormField, 'Altura (cm)'),
      '170',
    );
    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(find.text('Perfil guardado.'), findsOneWidget);
    expect((await profileRepository.getProfile())?.heightCm, 170);
  });

  testWidgets(
    'Con el perfil ya guardado, el historial de Biometría muestra el IMC',
    (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      final biometricRepository = _FakeBiometricRepository();
      final profileRepository = _FakeUserProfileRepository();
      await profileRepository.saveProfile(const UserProfile(heightCm: 170));

      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            repository: _FakeGlucoseRepository(),
            biometricRepository: biometricRepository,
            profileRepository: profileRepository,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Biometría'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.widgetWithText(TextFormField, 'Peso corporal (kg)'),
        '72.25',
      );
      await tester.tap(find.text('Guardar'));
      await tester.pumpAndSettle();

      // IMC = 72.25 / (1.70 ^ 2) = 25.0 → categoría "Sobrepeso".
      expect(find.textContaining('IMC: 25.0 (Sobrepeso)'), findsOneWidget);
    },
  );

  testWidgets('Tocar el ícono de Cuenta navega a AuthScreen', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: _FakeGlucoseRepository(),
          authRepository: _FakeAuthRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Cuenta'));
    await tester.pumpAndSettle();

    expect(find.text('Iniciar sesión'), findsWidgets);
    expect(find.text('Continuar con Google'), findsOneWidget);
  });

  testWidgets(
    'Registrarse con correo y contraseña muestra la cuenta autenticada',
    (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            repository: _FakeGlucoseRepository(),
            authRepository: _FakeAuthRepository(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byTooltip('Cuenta'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('¿No tienes cuenta? Regístrate'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.widgetWithText(TextFormField, 'Correo electrónico'),
        'nueva@example.com',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Contraseña'),
        'secreta123',
      );
      await tester.tap(find.text('Registrarse'));
      await tester.pumpAndSettle();

      expect(find.text('nueva@example.com'), findsOneWidget);
      expect(find.text('Cerrar sesión'), findsOneWidget);
    },
  );

  testWidgets('Iniciar sesión con Google muestra la cuenta autenticada', (
    WidgetTester tester,
  ) async {
    // El formulario de Cuenta es más largo que el tamaño de superficie
    // por defecto de los tests; se agranda para que el botón "Continuar
    // con Google" quede visible sin necesidad de hacer scroll.
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: _FakeGlucoseRepository(),
          authRepository: _FakeAuthRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Cuenta'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Continuar con Google'));
    await tester.pumpAndSettle();

    expect(find.text('Persona de Prueba'), findsOneWidget);
    expect(find.text('persona@gmail.com'), findsOneWidget);
  });

  testWidgets('Cerrar sesión vuelve a mostrar el formulario de inicio', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: _FakeGlucoseRepository(),
          authRepository: _FakeAuthRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Cuenta'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Continuar con Google'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Cerrar sesión'));
    await tester.pumpAndSettle();

    expect(find.text('Iniciar sesión'), findsWidgets);
  });

  testWidgets('Un error de autenticación muestra un mensaje legible', (
    WidgetTester tester,
  ) async {
    final authRepository = _FakeAuthRepository()
      ..failWith = const AuthException('Correo o contraseña incorrectos.');

    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: _FakeGlucoseRepository(),
          authRepository: authRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Cuenta'));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.widgetWithText(TextFormField, 'Correo electrónico'),
      'alguien@example.com',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Contraseña'),
      'secreta123',
    );
    await tester.tap(find.text('Iniciar sesión').last);
    await tester.pumpAndSettle();

    expect(find.text('Correo o contraseña incorrectos.'), findsOneWidget);
  });

  testWidgets(
    'Con sesión iniciada y backupRepository, se muestran los botones de '
    'respaldo',
    (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            repository: _FakeGlucoseRepository(),
            authRepository: _FakeAuthRepository(),
            backupRepository: _FakeBackupRepository(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byTooltip('Cuenta'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Continuar con Google'));
      await tester.pumpAndSettle();

      expect(find.text('Respaldar en la nube'), findsOneWidget);
      expect(find.text('Restaurar desde la nube'), findsOneWidget);
    },
  );

  testWidgets('Respaldar en la nube muestra un mensaje de éxito', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final backupRepository = _FakeBackupRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: _FakeGlucoseRepository(),
          authRepository: _FakeAuthRepository(),
          backupRepository: backupRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Cuenta'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Continuar con Google'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Respaldar en la nube'));
    await tester.pumpAndSettle();

    expect(find.text('Respaldo guardado correctamente.'), findsOneWidget);
    expect(backupRepository.backupCallCount, 1);
  });

  testWidgets('Restaurar desde la nube pide confirmación y luego restaura', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final backupRepository = _FakeBackupRepository()..hasBackup = true;
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: _FakeGlucoseRepository(),
          authRepository: _FakeAuthRepository(),
          backupRepository: backupRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Cuenta'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Continuar con Google'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Restaurar desde la nube'));
    await tester.pumpAndSettle();

    expect(find.text('Restaurar'), findsWidgets);
    expect(
      find.textContaining('reemplazará todos tus datos locales'),
      findsOneWidget,
    );

    await tester.tap(find.text('Restaurar').last);
    await tester.pumpAndSettle();

    expect(find.text('Datos restaurados correctamente.'), findsOneWidget);
    expect(backupRepository.restoreCallCount, 1);
  });

  testWidgets('Cancelar el diálogo de restaurar no ejecuta la restauración', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final backupRepository = _FakeBackupRepository()..hasBackup = true;
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: _FakeGlucoseRepository(),
          authRepository: _FakeAuthRepository(),
          backupRepository: backupRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Cuenta'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Continuar con Google'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Restaurar desde la nube'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Cancelar'));
    await tester.pumpAndSettle();

    expect(backupRepository.restoreCallCount, 0);
  });

  testWidgets('Un error de respaldo muestra un mensaje legible', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final backupRepository = _FakeBackupRepository()
      ..failWith = const BackupException(
        'No se pudo respaldar en la nube. Verifica tu conexión e '
        'intenta nuevamente.',
      );
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: _FakeGlucoseRepository(),
          authRepository: _FakeAuthRepository(),
          backupRepository: backupRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Cuenta'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Continuar con Google'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Respaldar en la nube'));
    await tester.pumpAndSettle();

    expect(
      find.text(
        'No se pudo respaldar en la nube. Verifica tu conexión e '
        'intenta nuevamente.',
      ),
      findsOneWidget,
    );
  });

  testWidgets(
    'Sin importRepository, HistoryScreen no muestra el botón de importar',
    (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(home: HomeScreen(repository: _FakeGlucoseRepository())),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Historial'));
      await tester.pumpAndSettle();

      expect(find.byTooltip('Importar desde sensor'), findsNothing);
    },
  );

  testWidgets(
    'Importar desde sensor agrega las mediciones nuevas al historial',
    (WidgetTester tester) async {
      final glucoseRepository = _FakeGlucoseRepository();
      final importRepository = _FakeGlucoseImportRepository(glucoseRepository)
        ..pending = [
          GlucoseMeasurement(
            value: 123,
            moment: GlucoseMoment.now,
            measuredAt: DateTime(2026, 1, 1, 8),
            comment: 'Importado desde Health Connect.',
          ),
        ];

      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            repository: glucoseRepository,
            importRepository: importRepository,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Historial'));
      await tester.pumpAndSettle();

      await tester.tap(find.byTooltip('Importar desde sensor'));
      await tester.pumpAndSettle();

      expect(importRepository.importCallCount, 1);
      expect(
        find.text('Se importaron 1 medición(es) nueva(s).'),
        findsOneWidget,
      );
      expect(find.textContaining('123 mg/dL'), findsOneWidget);
    },
  );

  testWidgets('Importar desde sensor sin mediciones nuevas muestra el mensaje '
      'correspondiente', (WidgetTester tester) async {
    final glucoseRepository = _FakeGlucoseRepository();
    final importRepository = _FakeGlucoseImportRepository(glucoseRepository);

    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: glucoseRepository,
          importRepository: importRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Historial'));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Importar desde sensor'));
    await tester.pumpAndSettle();

    expect(
      find.text('No hay mediciones nuevas para importar.'),
      findsOneWidget,
    );
  });

  testWidgets('Si Health Connect no está disponible, se informa sin intentar '
      'importar', (WidgetTester tester) async {
    final glucoseRepository = _FakeGlucoseRepository();
    final importRepository = _FakeGlucoseImportRepository(glucoseRepository)
      ..available = false;

    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: glucoseRepository,
          importRepository: importRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Historial'));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Importar desde sensor'));
    await tester.pumpAndSettle();

    expect(importRepository.importCallCount, 0);
    expect(
      find.textContaining('Health Connect no está disponible'),
      findsOneWidget,
    );
  });

  testWidgets('Si se deniega el permiso de lectura, se informa sin importar', (
    WidgetTester tester,
  ) async {
    final glucoseRepository = _FakeGlucoseRepository();
    final importRepository = _FakeGlucoseImportRepository(glucoseRepository)
      ..permissionGranted = false;

    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: glucoseRepository,
          importRepository: importRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Historial'));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Importar desde sensor'));
    await tester.pumpAndSettle();

    expect(importRepository.importCallCount, 0);
    expect(
      find.text('Permiso de lectura de glucosa denegado.'),
      findsOneWidget,
    );
  });

  testWidgets('Un error de importación muestra un mensaje legible', (
    WidgetTester tester,
  ) async {
    final glucoseRepository = _FakeGlucoseRepository();
    final importRepository = _FakeGlucoseImportRepository(glucoseRepository)
      ..failWith = const HealthImportException(
        'No se pudieron leer las mediciones de glucosa. Verifica el '
        'permiso concedido e intenta nuevamente.',
      );

    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: glucoseRepository,
          importRepository: importRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Historial'));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Importar desde sensor'));
    await tester.pumpAndSettle();

    expect(
      find.text(
        'No se pudieron leer las mediciones de glucosa. Verifica el '
        'permiso concedido e intenta nuevamente.',
      ),
      findsOneWidget,
    );
  });

  testWidgets(
    'Con un recordatorio post-comida vencido, se muestra un diálogo al '
    'abrir HomeScreen',
    (WidgetTester tester) async {
      final reminderRepository = _FakeMealGlucoseReminderRepository();
      await reminderRepository.addReminders([
        MealGlucoseReminder(
          mealId: 1,
          offsetMinutes: 60,
          dueAt: DateTime.now().subtract(const Duration(minutes: 5)),
        ),
      ]);

      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            repository: _FakeGlucoseRepository(),
            reminderRepository: reminderRepository,
            enableMealReminders: true,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Hora de medir tu glucosa'), findsOneWidget);
      expect(find.text('Registrar ahora'), findsOneWidget);
      expect(find.text('Descartar'), findsOneWidget);
    },
  );

  testWidgets(
    'Descartar el diálogo del recordatorio lo marca como descartado',
    (WidgetTester tester) async {
      final reminderRepository = _FakeMealGlucoseReminderRepository();
      await reminderRepository.addReminders([
        MealGlucoseReminder(
          mealId: 1,
          offsetMinutes: 60,
          dueAt: DateTime.now().subtract(const Duration(minutes: 5)),
        ),
      ]);

      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            repository: _FakeGlucoseRepository(),
            reminderRepository: reminderRepository,
            enableMealReminders: true,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Descartar'));
      await tester.pumpAndSettle();

      expect(find.text('Hora de medir tu glucosa'), findsNothing);
      expect(
        reminderRepository._reminders.single.status,
        MealGlucoseReminderStatus.dismissed,
      );
    },
  );

  testWidgets(
    'Registrar ahora desde el diálogo navega a GlucoseScreen y resuelve '
    'el recordatorio',
    (WidgetTester tester) async {
      final reminderRepository = _FakeMealGlucoseReminderRepository();
      await reminderRepository.addReminders([
        MealGlucoseReminder(
          mealId: 1,
          offsetMinutes: 60,
          dueAt: DateTime.now().subtract(const Duration(minutes: 5)),
        ),
      ]);
      final glucoseRepository = _FakeGlucoseRepository();

      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            repository: glucoseRepository,
            reminderRepository: reminderRepository,
            enableMealReminders: true,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Registrar ahora'));
      await tester.pumpAndSettle();

      expect(find.text('Registrar glucosa'), findsOneWidget);

      await tester.enterText(
        find.widgetWithText(TextFormField, 'Glucosa mg/dL'),
        '150',
      );
      await tester.tap(find.text('Guardar'));
      await tester.pumpAndSettle();

      expect(glucoseRepository.stored?.value, 150);
      expect(
        glucoseRepository.stored?.comment,
        'Medición post-comida (+60 min).',
      );
      expect(
        reminderRepository._reminders.single.status,
        MealGlucoseReminderStatus.resolvedManually,
      );
    },
  );

  testWidgets('Con CGM disponible y una medición cercana, el recordatorio se '
      'resuelve sin mostrar diálogo', (WidgetTester tester) async {
    final reminderRepository = _FakeMealGlucoseReminderRepository();
    final dueAt = DateTime.now().subtract(const Duration(minutes: 5));
    await reminderRepository.addReminders([
      MealGlucoseReminder(mealId: 1, offsetMinutes: 60, dueAt: dueAt),
    ]);
    final glucoseRepository = _FakeGlucoseRepository();
    final importRepository = _FakeGlucoseImportRepository(glucoseRepository)
      ..pending = [
        GlucoseMeasurement(
          value: 145,
          moment: GlucoseMoment.now,
          measuredAt: dueAt.add(const Duration(minutes: 2)),
        ),
      ];

    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: glucoseRepository,
          reminderRepository: reminderRepository,
          importRepository: importRepository,
          enableMealReminders: true,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Hora de medir tu glucosa'), findsNothing);
    expect(importRepository.importCallCount, 1);
    expect(
      reminderRepository._reminders.single.status,
      MealGlucoseReminderStatus.resolvedAutomatically,
    );
  });

  group('NotificationService (Fase B)', () {
    testWidgets(
      'Al abrir HomeScreen con un NotificationService, solicita permiso y '
      'reprograma los recordatorios pendientes',
      (WidgetTester tester) async {
        final reminderRepository = _FakeMealGlucoseReminderRepository();
        final saved = await reminderRepository.addReminders([
          MealGlucoseReminder(
            mealId: 1,
            offsetMinutes: 60,
            dueAt: DateTime.now().add(const Duration(minutes: 30)),
          ),
        ]);
        final notificationService = _FakeNotificationService();

        await tester.pumpWidget(
          MaterialApp(
            home: HomeScreen(
              repository: _FakeGlucoseRepository(),
              reminderRepository: reminderRepository,
              enableMealReminders: true,
              notificationService: notificationService,
            ),
          ),
        );
        await tester.pumpAndSettle();

        expect(notificationService.requestPermissionCallCount, 1);
        expect(notificationService.scheduledIds, {saved.single.id});
      },
    );

    testWidgets('Tocar una notificación vuelve a revisar los recordatorios '
        'pendientes y muestra el diálogo correspondiente', (
      WidgetTester tester,
    ) async {
      final reminderRepository = _FakeMealGlucoseReminderRepository();
      await reminderRepository.addReminders([
        MealGlucoseReminder(
          mealId: 1,
          offsetMinutes: 60,
          dueAt: DateTime.now().subtract(const Duration(minutes: 5)),
        ),
      ]);
      final notificationService = _FakeNotificationService();

      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            repository: _FakeGlucoseRepository(),
            reminderRepository: reminderRepository,
            enableMealReminders: true,
            notificationService: notificationService,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // El primer `reviewPending` (en `initState`) ya mostró el diálogo;
      // se descarta para simular que el usuario lo ignoró y, en cambio,
      // tocó la notificación del sistema más tarde.
      await tester.tap(find.text('Descartar'));
      await tester.pumpAndSettle();
      expect(find.text('Hora de medir tu glucosa'), findsNothing);

      // Se agrega un segundo recordatorio pendiente para verificar que
      // el toque efectivamente dispara una nueva revisión.
      await reminderRepository.addReminders([
        MealGlucoseReminder(
          mealId: 1,
          offsetMinutes: 90,
          dueAt: DateTime.now().subtract(const Duration(minutes: 1)),
        ),
      ]);

      notificationService.simulateTap();
      await tester.pumpAndSettle();

      expect(find.text('Hora de medir tu glucosa'), findsOneWidget);
    });
  });
}
