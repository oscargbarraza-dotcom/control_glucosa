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
import 'package:seguimiento_glucosa/screens/auth_screen.dart';
import 'package:seguimiento_glucosa/screens/home_screen.dart';
import 'package:seguimiento_glucosa/services/auth_repository.dart';
import 'package:seguimiento_glucosa/services/biometric_repository.dart';
import 'package:seguimiento_glucosa/services/cloud_sync_repository.dart';
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
  _FakeAuthRepository({this.supportsGoogleSignIn = true});

  final _controller = StreamController<AppUser?>.broadcast();
  AppUser? _currentUser;

  @override
  final bool supportsGoogleSignIn;

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

  /// Autentica el fake directamente para tests que ejercitan solo la
  /// vista de cuenta (sin pasar por el formulario de login).
  void authenticateForTest() {
    const user = AppUser(
      uid: 'uid-test',
      email: 'persona@example.com',
      displayName: 'Persona de Prueba',
    );
    _setUser(user);
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

  /// Si no es `null`, la próxima llamada a [deleteAccount] lanzará
  /// esta excepción en lugar de eliminar la cuenta.
  AuthException? failDeleteWith;
  int deleteAccountCallCount = 0;
  void Function()? onDeleteAccount;

  @override
  Future<void> deleteAccount() async {
    if (failDeleteWith != null) {
      throw failDeleteWith!;
    }
    deleteAccountCallCount++;
    onDeleteAccount?.call();
    _setUser(null);
  }
}

/// Repositorio de sincronización en la nube en memoria usado solo en
/// pruebas, para evitar llamadas reales a Cloud Firestore durante los
/// widget tests. Un flag [failPullWith] permite simular un error en la
/// próxima llamada a [pullMissingFromCloud]; los métodos `push*` nunca
/// lanzan excepciones, igual que la implementación real.
class _FakeCloudSyncRepository implements CloudSyncRepository {
  int pushGlucoseCallCount = 0;
  int pushMealCallCount = 0;
  int pushMedicationIntakeCallCount = 0;
  int pushBiometricCallCount = 0;
  int pullCallCount = 0;
  CloudSyncException? failPullWith;

  /// Resultado que devolverá la próxima llamada a
  /// [pullMissingFromCloud].
  CloudSyncPullSummary pullResult = const CloudSyncPullSummary(
    addedGlucoseMeasurements: 0,
    addedMeals: 0,
    addedMedicationIntakes: 0,
    addedBiometricMeasurements: 0,
  );

  @override
  Future<void> pushGlucoseMeasurement(GlucoseMeasurement measurement) async {
    pushGlucoseCallCount++;
  }

  @override
  Future<void> pushMeal(Meal meal) async {
    pushMealCallCount++;
  }

  @override
  Future<void> pushMedicationIntake(MedicationIntake intake) async {
    pushMedicationIntakeCallCount++;
  }

  @override
  Future<void> pushBiometricMeasurement(
    BiometricMeasurement measurement,
  ) async {
    pushBiometricCallCount++;
  }

  @override
  Future<CloudSyncPullSummary> pullMissingFromCloud() async {
    if (failPullWith != null) {
      throw failPullWith!;
    }
    pullCallCount++;
    return pullResult;
  }

  @override
  Stream<List<GlucoseMeasurement>> watchGlucoseMeasurements() =>
      Stream.value(const []);

  @override
  Stream<List<Meal>> watchMeals() => Stream.value(const []);

  @override
  Stream<List<MedicationIntake>> watchMedicationIntakes() =>
      Stream.value(const []);

  @override
  Stream<List<BiometricMeasurement>> watchBiometricMeasurements() =>
      Stream.value(const []);

  /// Si no es `null`, la próxima llamada a [deleteAllCloudData]
  /// lanzará esta excepción en lugar de "eliminar" los datos.
  CloudSyncException? failDeleteWith;
  int deleteAllCloudDataCallCount = 0;
  void Function()? onDeleteAllCloudData;

  @override
  Future<void> deleteAllCloudData() async {
    if (failDeleteWith != null) {
      throw failDeleteWith!;
    }
    deleteAllCloudDataCallCount++;
    onDeleteAllCloudData?.call();
  }
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

  /// Medición que devolverá [fetchLatestMeasurement], imitando una
  /// lectura puntual disponible en el sensor/CGM para el botón "Tomar
  /// desde sensor" de `GlucoseScreen`.
  GlucoseMeasurement? latestMeasurement;
  int fetchLatestCallCount = 0;

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

  @override
  Future<GlucoseMeasurement?> fetchLatestMeasurement({
    Duration lookback = const Duration(hours: 4),
  }) async {
    if (failWith != null) {
      throw failWith!;
    }
    fetchLatestCallCount++;
    return latestMeasurement;
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

  testWidgets(
    'Sin importRepository, GlucoseScreen no muestra el botón de tomar '
    'desde sensor',
    (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(home: HomeScreen(repository: _FakeGlucoseRepository())),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Glucosa actual'));
      await tester.pumpAndSettle();

      expect(find.byTooltip('Tomar desde sensor'), findsNothing);
    },
  );

  testWidgets('Tomar desde sensor prellena el formulario con el valor leído', (
    WidgetTester tester,
  ) async {
    final glucoseRepository = _FakeGlucoseRepository();
    final importRepository = _FakeGlucoseImportRepository(glucoseRepository)
      ..latestMeasurement = GlucoseMeasurement(
        value: 110,
        moment: GlucoseMoment.now,
        measuredAt: DateTime.now(),
        comment: 'Tomado desde Health Connect.',
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

    await tester.tap(find.text('Glucosa actual'));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Tomar desde sensor'));
    await tester.pumpAndSettle();

    expect(importRepository.fetchLatestCallCount, 1);
    expect(find.text('110'), findsOneWidget);
    expect(find.text('Tomado desde Health Connect.'), findsOneWidget);

    // El valor prellenado se puede guardar igual que uno manual.
    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(glucoseRepository.stored?.value, 110);
  });

  testWidgets(
    'Tomar desde sensor sin mediciones recientes muestra un mensaje',
    (WidgetTester tester) async {
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

      await tester.tap(find.text('Glucosa actual'));
      await tester.pumpAndSettle();

      await tester.tap(find.byTooltip('Tomar desde sensor'));
      await tester.pumpAndSettle();

      expect(
        find.text('El sensor no tiene mediciones recientes.'),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'Si Health Connect no está disponible, "Tomar desde sensor" informa '
    'sin leer el sensor',
    (WidgetTester tester) async {
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

      await tester.tap(find.text('Glucosa actual'));
      await tester.pumpAndSettle();

      await tester.tap(find.byTooltip('Tomar desde sensor'));
      await tester.pumpAndSettle();

      expect(importRepository.fetchLatestCallCount, 0);
      expect(
        find.textContaining('Health Connect no está disponible'),
        findsOneWidget,
      );
    },
  );

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
    'Se puede registrar una comida de tipo "Once", distinta de "Colación"',
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

      // El selector de tipo de comida ofrece "Once" y "Colación" como
      // opciones distintas (ver MealType.once vs. MealType.snack).
      await tester.tap(find.byType(DropdownButtonFormField<MealType>));
      await tester.pumpAndSettle();
      expect(find.text('Once'), findsOneWidget);
      expect(find.text('Colación'), findsOneWidget);

      await tester.tap(find.text('Once').last);
      await tester.pumpAndSettle();

      await tester.enterText(
        find.widgetWithText(TextFormField, 'Alimento'),
        'Té',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Cantidad'),
        '1 taza',
      );
      await tester.tap(find.byTooltip('Agregar alimento'));
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Guardar'),
        200,
        scrollable: find
            .descendant(
              of: find.byKey(const Key('mealFormListView')),
              matching: find.byType(Scrollable),
            )
            .first,
      );
      await tester.pump();
      await tester.tap(find.text('Guardar'));
      await tester.pumpAndSettle();

      expect(mealRepository.stored.single.type, MealType.once);
      // Tras guardar, la pestaña cambia automáticamente a "Historial".
      expect(find.text('Once'), findsOneWidget);
    },
  );

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

      // El ícono de cabecera del formulario empuja el botón "Guardar"
      // fuera del viewport fijo de prueba, demasiado lejos para que el
      // `ListView` ya lo haya construido (`ensureVisible` no sirve
      // aquí: no puede desplazarse hacia un widget que todavía no
      // existe). `scrollUntilVisible` desplaza el scroll en pasos
      // pequeños, dejando que se vayan construyendo los widgets de más
      // abajo, hasta encontrar el botón. Hay que indicar explícitamente
      // el `ListView` del formulario (identificado por su `Key`): por
      // defecto busca cualquier `Scrollable`, y aquí hay varios (el
      // `PageView` interno del `TabBarView`, uno por cada
      // `TextFormField` que envuelve su texto en un `Scrollable`
      // horizontal, etc.).
      await tester.scrollUntilVisible(
        find.text('Guardar'),
        200,
        // `.first`: dentro del `ListView` también hay un `Scrollable`
        // por cada `TextFormField` (para el scroll horizontal de su
        // texto); el del propio `ListView` es el primero en el árbol.
        scrollable: find
            .descendant(
              of: find.byKey(const Key('mealFormListView')),
              matching: find.byType(Scrollable),
            )
            .first,
      );
      // `scrollUntilVisible` termina con un ajuste fino vía
      // `Scrollable.ensureVisible` que no incluye un `pump`; sin este
      // paso extra, el `tap` puede calcular el centro del botón con el
      // layout todavía desactualizado (ver el mismo ajuste en los
      // tests equivalentes de Medicamentos).
      await tester.pump();
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

  testWidgets('Tras guardar una comida, se ofrece registrar una medición de '
      'glucosa', (WidgetTester tester) async {
    final mealRepository = _FakeMealRepository();
    final glucoseRepository = _FakeGlucoseRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: glucoseRepository,
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

    await tester.scrollUntilVisible(
      find.text('Guardar'),
      200,
      scrollable: find
          .descendant(
            of: find.byKey(const Key('mealFormListView')),
            matching: find.byType(Scrollable),
          )
          .first,
    );
    await tester.pump();
    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(find.text('Comida guardada.'), findsOneWidget);

    // Además del snackbar de confirmación, se ofrece registrar de
    // inmediato una medición de glucosa asociada a la comida.
    expect(find.text('¿Registrar tu glucosa?'), findsOneWidget);

    await tester.tap(find.text('Ahora no'));
    await tester.pumpAndSettle();

    expect(find.text('¿Registrar tu glucosa?'), findsNothing);
    expect(glucoseRepository.stored, isNull);
  });

  testWidgets('Elegir "Medir glucosa" tras guardar una comida navega a '
      'GlucoseScreen y guarda la medición', (WidgetTester tester) async {
    final mealRepository = _FakeMealRepository();
    final glucoseRepository = _FakeGlucoseRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: glucoseRepository,
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

    await tester.scrollUntilVisible(
      find.text('Guardar'),
      200,
      scrollable: find
          .descendant(
            of: find.byKey(const Key('mealFormListView')),
            matching: find.byType(Scrollable),
          )
          .first,
    );
    await tester.pump();
    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Medir glucosa'));
    await tester.pumpAndSettle();

    expect(find.text('Registrar glucosa'), findsOneWidget);

    await tester.enterText(find.byType(TextFormField), '130');
    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(glucoseRepository.stored?.value, 130);

    // `GlucoseScreen` solo retorna a `MealScreen` (de donde se abrió);
    // al volver manualmente desde ahí a `HomeScreen`, la tarjeta
    // principal refleja la medición recién guardada.
    await tester.pageBack();
    await tester.pumpAndSettle();

    expect(find.text('130 mg/dL'), findsOneWidget);
  });

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

    // El ícono de cabecera del formulario empuja el botón "Guardar"
    // fuera del viewport fijo de prueba, demasiado lejos para que el
    // `ListView` ya lo haya construido; ver el mismo ajuste (y su
    // motivo) en el test equivalente de Comida.
    await tester.scrollUntilVisible(
      find.text('Guardar'),
      200,
      // `.first`: dentro del `ListView` también hay un `Scrollable` por
      // cada `TextFormField` (para el scroll horizontal de su texto);
      // el del propio `ListView` es el primero en el árbol.
      scrollable: find
          .descendant(
            of: find.byKey(const Key('medicationFormListView')),
            matching: find.byType(Scrollable),
          )
          .first,
    );
    // `scrollUntilVisible` termina con un ajuste fino vía
    // `Scrollable.ensureVisible` que no incluye un `pump`; sin este
    // paso extra, el `tap` calcula el centro del botón con el layout
    // todavía desactualizado y falla el hit test.
    await tester.pump();
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

      // El ícono de cabecera del formulario empuja el botón "Guardar"
      // fuera del viewport fijo de prueba, demasiado lejos para que el
      // `ListView` ya lo haya construido; ver el mismo ajuste (y su
      // motivo) en el test equivalente de Comida.
      await tester.scrollUntilVisible(
        find.text('Guardar'),
        200,
        // `.first`: dentro del `ListView` también hay un `Scrollable`
        // por cada `TextFormField` (para el scroll horizontal de su
        // texto); el del propio `ListView` es el primero en el árbol.
        scrollable: find
            .descendant(
              of: find.byKey(const Key('medicationFormListView')),
              matching: find.byType(Scrollable),
            )
            .first,
      );
      // `scrollUntilVisible` termina con un ajuste fino vía
      // `Scrollable.ensureVisible` que no incluye un `pump`; sin este
      // paso extra, el `tap` calcula el centro del botón con el layout
      // todavía desactualizado y falla el hit test.
      await tester.pump();
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

  testWidgets(
    'Dejar el peso en blanco reutiliza el peso de la última medición',
    (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      final biometricRepository = _FakeBiometricRepository();
      await biometricRepository.addMeasurement(
        BiometricMeasurement(weightKg: 68.5, measuredAt: DateTime(2026, 1, 1)),
      );

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

      // El campo de peso queda en blanco a propósito: solo se registra
      // la frecuencia cardíaca ese día.
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Frecuencia cardíaca (lpm)'),
        '72',
      );
      await tester.tap(find.text('Guardar'));
      await tester.pumpAndSettle();

      expect(find.text('Medición guardada.'), findsOneWidget);
      expect(biometricRepository.stored, hasLength(2));
      expect(biometricRepository.stored.first.weightKg, 68.5);
      expect(biometricRepository.stored.first.heartRateBpm, 72);
    },
  );

  testWidgets(
    'Sin ningún peso previo registrado, dejar el peso en blanco muestra '
    'un error de validación',
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

      await tester.tap(find.text('Guardar'));
      await tester.pumpAndSettle();

      expect(
        find.text(
          'Ingresa el peso corporal (no hay un peso previo registrado).',
        ),
        findsOneWidget,
      );
      expect(biometricRepository.stored, isEmpty);
    },
  );

  testWidgets('Tras guardar una medición de Biometría, se ofrece registrar una '
      'medición de glucosa', (WidgetTester tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final biometricRepository = _FakeBiometricRepository();
    final glucoseRepository = _FakeGlucoseRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: glucoseRepository,
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
      '70',
    );
    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(find.text('¿Registrar tu glucosa?'), findsOneWidget);

    await tester.tap(find.text('Medir glucosa'));
    await tester.pumpAndSettle();

    expect(find.text('Registrar glucosa'), findsOneWidget);

    await tester.enterText(
      find.widgetWithText(TextFormField, 'Glucosa mg/dL'),
      '110',
    );
    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(glucoseRepository.stored?.value, 110);
  });

  testWidgets('Tras guardar una toma de Medicamentos, se ofrece registrar una '
      'medición de glucosa', (WidgetTester tester) async {
    final medicationRepository = _FakeMedicationRepository();
    final glucoseRepository = _FakeGlucoseRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: glucoseRepository,
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
      '500',
    );
    await tester.tap(find.byTooltip('Agregar medicamento'));
    await tester.pumpAndSettle();

    await tester.scrollUntilVisible(
      find.text('Guardar'),
      200,
      scrollable: find
          .descendant(
            of: find.byKey(const Key('medicationFormListView')),
            matching: find.byType(Scrollable),
          )
          .first,
    );
    await tester.pump();
    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(find.text('¿Registrar tu glucosa?'), findsOneWidget);

    await tester.tap(find.text('Ahora no'));
    await tester.pumpAndSettle();

    expect(find.text('¿Registrar tu glucosa?'), findsNothing);
    expect(glucoseRepository.stored, isNull);
  });

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

  testWidgets('Oculta Google Sign-In cuando el repositorio no lo soporta', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: _FakeGlucoseRepository(),
          authRepository: _FakeAuthRepository(supportsGoogleSignIn: false),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Cuenta'));
    await tester.pumpAndSettle();

    expect(find.text('Iniciar sesión'), findsWidgets);
    expect(find.text('Continuar con Google'), findsNothing);
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
    'Eliminar cuenta borra primero nube, luego Auth y también datos locales',
    (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1080, 2600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      final events = <String>[];
      final authRepository = _FakeAuthRepository()
        ..onDeleteAccount = () => events.add('auth');
      final syncRepository = _FakeCloudSyncRepository()
        ..onDeleteAllCloudData = () => events.add('cloud');
      var localDeleteCallCount = 0;

      await tester.pumpWidget(
        MaterialApp(
          home: AuthScreen(
            repository: authRepository,
            cloudDataDeletionRepository: syncRepository,
            deleteLocalData: () async {
              events.add('local');
              localDeleteCallCount++;
            },
          ),
        ),
      );
      authRepository.authenticateForTest();
      await tester.pumpAndSettle();

      await tester.tap(find.text('Eliminar cuenta y datos'));
      await tester.pumpAndSettle();

      expect(find.text('¿Eliminar cuenta y datos?'), findsOneWidget);
      expect(
        find.text('Eliminar también los datos de este dispositivo'),
        findsOneWidget,
      );

      await tester.tap(find.text('Eliminar permanentemente'));
      await tester.pumpAndSettle();

      expect(events, equals(['cloud', 'auth', 'local']));
      expect(syncRepository.deleteAllCloudDataCallCount, 1);
      expect(authRepository.deleteAccountCallCount, 1);
      expect(localDeleteCallCount, 1);
      expect(find.byType(AuthScreen), findsNothing);
    },
  );

  testWidgets(
    'Si falla borrar la nube, conserva la cuenta y los datos locales',
    (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1080, 2600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      final authRepository = _FakeAuthRepository();
      final syncRepository = _FakeCloudSyncRepository()
        ..failDeleteWith = const CloudSyncException(
          'No se pudieron eliminar tus datos de la nube.',
        );
      var localDeleteCallCount = 0;

      await tester.pumpWidget(
        MaterialApp(
          home: AuthScreen(
            repository: authRepository,
            cloudDataDeletionRepository: syncRepository,
            deleteLocalData: () async => localDeleteCallCount++,
          ),
        ),
      );
      authRepository.authenticateForTest();
      await tester.pumpAndSettle();

      await tester.tap(find.text('Eliminar cuenta y datos'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Eliminar permanentemente'));
      await tester.pumpAndSettle();

      expect(authRepository.deleteAccountCallCount, 0);
      expect(localDeleteCallCount, 0);
      expect(find.byType(AuthScreen), findsOneWidget);
      expect(
        find.text('No se pudieron eliminar tus datos de la nube.'),
        findsOneWidget,
      );
    },
  );

  testWidgets('Cancelar el diálogo no elimina cuenta ni datos', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 2600);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final authRepository = _FakeAuthRepository();
    final syncRepository = _FakeCloudSyncRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: AuthScreen(
          repository: authRepository,
          cloudDataDeletionRepository: syncRepository,
        ),
      ),
    );
    authRepository.authenticateForTest();
    await tester.pumpAndSettle();

    await tester.tap(find.text('Eliminar cuenta y datos'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancelar'));
    await tester.pumpAndSettle();

    expect(syncRepository.deleteAllCloudDataCallCount, 0);
    expect(authRepository.deleteAccountCallCount, 0);
    expect(find.text('¿Eliminar cuenta y datos?'), findsNothing);
  });

  testWidgets(
    'Con sesión iniciada y syncRepository, Cuenta muestra el aviso de '
    'sincronización automática (sin botones manuales de respaldo)',
    (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            repository: _FakeGlucoseRepository(),
            authRepository: _FakeAuthRepository(),
            syncRepository: _FakeCloudSyncRepository(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byTooltip('Cuenta'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Continuar con Google'));
      await tester.pumpAndSettle();

      expect(
        find.textContaining('se sincroniza solo con la nube'),
        findsOneWidget,
      );
      expect(find.text('Respaldar en la nube'), findsNothing);
      expect(find.text('Restaurar desde la nube'), findsNothing);
      expect(find.text('Fusionar desde la nube'), findsNothing);
    },
  );

  testWidgets('Guardar una medición la sincroniza automáticamente', (
    WidgetTester tester,
  ) async {
    final syncRepository = _FakeCloudSyncRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: _FakeGlucoseRepository(),
          authRepository: _FakeAuthRepository(),
          syncRepository: syncRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Glucosa actual'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextFormField), '120');
    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(syncRepository.pushGlucoseCallCount, 1);
  });

  testWidgets('Con sesión ya iniciada al abrir la app, se dispara la fusión '
      'automática desde la nube', (WidgetTester tester) async {
    final authRepository = _FakeAuthRepository();
    // Simula una sesión ya restaurada automáticamente por Firebase al
    // abrir la app (p. ej. al migrar a un celular nuevo).
    await authRepository.signInWithGoogle();
    final syncRepository = _FakeCloudSyncRepository()
      ..pullResult = const CloudSyncPullSummary(
        addedGlucoseMeasurements: 1,
        addedMeals: 0,
        addedMedicationIntakes: 0,
        addedBiometricMeasurements: 0,
      );

    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: _FakeGlucoseRepository(),
          authRepository: authRepository,
          syncRepository: syncRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(syncRepository.pullCallCount, 1);
  });

  testWidgets('Iniciar sesión mientras la app está abierta dispara la fusión '
      'automática desde la nube', (WidgetTester tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final authRepository = _FakeAuthRepository();
    final syncRepository = _FakeCloudSyncRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(
          repository: _FakeGlucoseRepository(),
          authRepository: authRepository,
          syncRepository: syncRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(syncRepository.pullCallCount, 0);

    await tester.tap(find.byTooltip('Cuenta'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Continuar con Google'));
    await tester.pumpAndSettle();

    expect(syncRepository.pullCallCount, 1);
  });

  testWidgets(
    'Un error al fusionar automáticamente desde la nube no interrumpe '
    'la app (falla en silencio)',
    (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);

      final authRepository = _FakeAuthRepository();
      final syncRepository = _FakeCloudSyncRepository()
        ..failPullWith = const CloudSyncException(
          'No se pudo sincronizar con la nube. Verifica tu conexión e '
          'intenta nuevamente.',
        );

      await tester.pumpWidget(
        MaterialApp(
          home: HomeScreen(
            repository: _FakeGlucoseRepository(),
            authRepository: authRepository,
            syncRepository: syncRepository,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byTooltip('Cuenta'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Continuar con Google'));
      await tester.pumpAndSettle();

      // No debe mostrarse ningún mensaje de error ni romperse la app:
      // la fusión automática es silenciosa (ver documentación de
      // `CloudSyncRepository.pullMissingFromCloud`). La pantalla de
      // Cuenta sigue mostrando la sesión ya iniciada con normalidad.
      expect(find.text('Persona de Prueba'), findsOneWidget);
    },
  );

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

  testWidgets('Registrar ahora desde el diálogo navega a GlucoseScreen con el '
      'comentario "60 minutos" precargado (pero editable) y resuelve el '
      'recordatorio', (WidgetTester tester) async {
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
    // El comentario viene precargado con los minutos del recordatorio,
    // pero el campo sigue siendo editable (no es de solo lectura).
    expect(find.text('60 minutos'), findsOneWidget);

    await tester.enterText(
      find.widgetWithText(TextFormField, 'Glucosa mg/dL'),
      '150',
    );
    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(glucoseRepository.stored?.value, 150);
    // Al guardar sin editar el comentario precargado, se conserva tal
    // cual (el comentario autogenerado de respaldo solo se aplica
    // cuando el usuario deja el campo vacío).
    expect(glucoseRepository.stored?.comment, '60 minutos');
    expect(
      reminderRepository._reminders.single.status,
      MealGlucoseReminderStatus.resolvedManually,
    );
  });

  testWidgets(
    'Si se borra el comentario precargado "90 minutos" antes de guardar, '
    'se aplica el comentario autogenerado de respaldo',
    (WidgetTester tester) async {
      final reminderRepository = _FakeMealGlucoseReminderRepository();
      await reminderRepository.addReminders([
        MealGlucoseReminder(
          mealId: 1,
          offsetMinutes: 90,
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

      expect(find.text('90 minutos'), findsOneWidget);

      // El campo "Comentario" en GlucoseScreen es un TextField (no un
      // TextFormField, a diferencia de "Glucosa mg/dL").
      await tester.enterText(find.widgetWithText(TextField, 'Comentario'), '');
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Glucosa mg/dL'),
        '160',
      );
      await tester.tap(find.text('Guardar'));
      await tester.pumpAndSettle();

      expect(glucoseRepository.stored?.value, 160);
      expect(
        glucoseRepository.stored?.comment,
        'Medición post-comida (+90 min).',
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
