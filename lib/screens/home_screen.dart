import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/app_user.dart';
import '../models/glucose_measurement.dart';
import '../models/meal_glucose_reminder.dart';
import '../services/app_database.dart';
import '../services/auth_repository.dart';
import '../services/biometric_repository.dart';
import '../services/cloud_sync_repository.dart';
import '../services/firebase_auth_repository.dart';
import '../services/firestore_cloud_sync_repository.dart';
import '../services/glucose_import_repository.dart';
import '../services/glucose_repository.dart';
import '../services/health_glucose_import_repository.dart';
import '../services/meal_glucose_reminder_coordinator.dart';
import '../services/meal_glucose_reminder_repository.dart';
import '../services/meal_repository.dart';
import '../services/medication_repository.dart';
import '../services/notification_service.dart';
import '../services/syncing_repositories.dart';
import '../services/user_profile_repository.dart';
import 'auth_screen.dart';
import 'biometric_screen.dart';
import 'glucose_screen.dart';
import 'history_screen.dart';
import 'meal_screen.dart';
import 'medication_screen.dart';

/// Pantalla principal de la aplicación.
///
/// Muestra la tarjeta con la última medición de glucosa registrada (cargada
/// desde [GlucoseRepository] al iniciar) y los accesos a los módulos de
/// comida, medicamentos, biometría e historial. El título del `AppBar`
/// saluda por nombre cuando el perfil de usuario (módulo de Biometría,
/// pestaña Perfil) ya tiene un nombre a mostrar guardado.
class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    this.repository,
    this.mealRepository,
    this.medicationRepository,
    this.biometricRepository,
    this.profileRepository,
    this.authRepository,
    this.syncRepository,
    this.enableCloudSync = false,
    this.importRepository,
    this.enableHealthImport = false,
    this.reminderRepository,
    this.enableMealReminders = false,
    this.notificationService,
  });

  /// Repositorio de mediciones de glucosa. Si es `null`, se usa
  /// [SqliteGlucoseRepository] sobre la base de datos compartida. Permite
  /// inyectar una implementación de prueba (por ejemplo, un fake en
  /// memoria) en tests de widgets sin depender del plugin real de
  /// `sqflite`.
  final GlucoseRepository? repository;

  /// Repositorio de comidas. Si es `null`, se usa [SqliteMealRepository]
  /// sobre la misma base de datos compartida que [repository].
  final MealRepository? mealRepository;

  /// Repositorio de tomas de medicamentos. Si es `null`, se usa
  /// [SqliteMedicationRepository] sobre la misma base de datos compartida
  /// que [repository].
  final MedicationRepository? medicationRepository;

  /// Repositorio de mediciones biométricas. Si es `null`, se usa
  /// [SqliteBiometricRepository] sobre la misma base de datos compartida
  /// que [repository].
  final BiometricRepository? biometricRepository;

  /// Repositorio del perfil de usuario (altura, fecha de nacimiento,
  /// sexo biológico, nombre a mostrar). Si es `null`, se usa
  /// [SqliteUserProfileRepository] sobre la misma base de datos
  /// compartida que [repository].
  final UserProfileRepository? profileRepository;

  /// Repositorio de autenticación. Si es `null`, se usa
  /// [FirebaseAuthRepository]. Permite inyectar una implementación de
  /// prueba en tests de widgets sin depender de Firebase.
  final AuthRepository? authRepository;

  /// Repositorio de sincronización automática en la nube
  /// ("Sincronización en tiempo real"). Si es `null`, se usa
  /// [FirestoreCloudSyncRepository] (construido sobre los mismos
  /// repositorios de datos de salud que el resto de la pantalla).
  /// Permite inyectar un fake en tests sin tocar Firestore real.
  final CloudSyncRepository? syncRepository;

  /// Habilita la construcción automática de
  /// [FirestoreCloudSyncRepository] cuando [syncRepository] es `null`,
  /// y con ella: (1) que cada registro nuevo (glucosa, comida,
  /// medicamento, biometría) se suba solo a la nube al guardarlo en
  /// SQLite (ver `lib/services/syncing_repositories.dart`), y (2) que
  /// al detectar una sesión recién iniciada se traigan automáticamente
  /// los registros de la nube que falten en este dispositivo (ver
  /// [CloudSyncRepository.pullMissingFromCloud], pensado para migrar
  /// de un celular viejo a uno nuevo). Por defecto es `false` para no
  /// tocar Firestore real en los widget tests; `main.dart` lo activa
  /// explícitamente una vez que Firebase ya está inicializado.
  final bool enableCloudSync;

  /// Repositorio de importación manual de glucosa desde sensores/CGM
  /// (Health Connect/Apple Health). Si es `null`, se usa
  /// [HealthGlucoseImportRepository] (construido sobre [repository])
  /// cuando [enableHealthImport] es `true`; en caso contrario, no se
  /// muestra el botón de importar en `HistoryScreen`.
  final GlucoseImportRepository? importRepository;

  /// Habilita la construcción automática de
  /// [HealthGlucoseImportRepository] cuando [importRepository] es
  /// `null`. Por defecto es `false` para no tocar el plugin `health`
  /// real en los widget tests; `main.dart` lo activa explícitamente.
  final bool enableHealthImport;

  /// Repositorio de recordatorios de glucosa post-comida. Si es `null`,
  /// se usa [SqliteMealGlucoseReminderRepository] sobre la misma base de
  /// datos compartida que [repository].
  final MealGlucoseReminderRepository? reminderRepository;

  /// Habilita la revisión automática de recordatorios de glucosa
  /// post-comida al abrir esta pantalla (ver
  /// [MealGlucoseReminderCoordinator.reviewPending]), mostrando un
  /// diálogo por cada uno que siga pendiente tras intentar resolverlo
  /// vía sensores/CGM. Por defecto es `false` para que los widget tests
  /// no deban lidiar con diálogos inesperados; `main.dart` lo activa
  /// explícitamente.
  final bool enableMealReminders;

  /// Servicio de notificaciones push locales para los recordatorios de
  /// glucosa post-comida (roadmap punto 17, Fase B). Si es `null`, los
  /// recordatorios siguen funcionando solo in-app (diálogo al abrir la
  /// app), sin ningún aviso del sistema operativo; es el valor usado
  /// por defecto en los widget tests. `main.dart` inyecta
  /// `AndroidNotificationService` o `DarwinNotificationService` según
  /// la plataforma en dispositivos reales.
  final NotificationService? notificationService;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  // Base de datos compartida por los repositorios por defecto, para evitar
  // abrir dos conexiones (y aplicar las migraciones dos veces) cuando
  // ninguno de los dos repositorios se inyecta explícitamente.
  //
  // Debe ser `late` (inicialización perezosa): si se inyectan ambos
  // repositorios (como en los tests de widgets, con fakes en memoria),
  // esta instancia nunca debe construirse, porque `AppDatabase()` sin
  // `factory` accede de inmediato a `databaseFactory` de `sqflite`, que
  // lanza una excepción fuera de un entorno Android/iOS real.
  late final AppDatabase _sharedDatabase = AppDatabase();

  // Repositorios SQLite "base" (sin sincronización), usados tanto
  // directamente como fuente para los decoradores `Syncing*Repository`
  // de más abajo.
  late final GlucoseRepository _baseGlucoseRepository =
      widget.repository ??
      SqliteGlucoseRepository.withDatabase(_sharedDatabase);
  late final MealRepository _baseMealRepository =
      widget.mealRepository ??
      SqliteMealRepository.withDatabase(_sharedDatabase);
  late final MedicationRepository _baseMedicationRepository =
      widget.medicationRepository ??
      SqliteMedicationRepository.withDatabase(_sharedDatabase);
  late final BiometricRepository _baseBiometricRepository =
      widget.biometricRepository ??
      SqliteBiometricRepository.withDatabase(_sharedDatabase);
  late final UserProfileRepository _profileRepository =
      widget.profileRepository ??
      SqliteUserProfileRepository.withDatabase(_sharedDatabase);
  late final AuthRepository _authRepository =
      widget.authRepository ?? FirebaseAuthRepository();
  // No usa `??` porque, a diferencia de los demás repositorios, el valor
  // por defecto de `CloudSyncRepository` es `null` (no una
  // implementación real): esta funcionalidad requiere Firebase ya
  // inicializado (`enableCloudSync`), y los tests de widgets no deben
  // tocar Firestore real por defecto.
  late final CloudSyncRepository? _syncRepository =
      widget.syncRepository ??
      (widget.enableCloudSync
          ? FirestoreCloudSyncRepository(
              glucoseRepository: _baseGlucoseRepository,
              mealRepository: _baseMealRepository,
              medicationRepository: _baseMedicationRepository,
              biometricRepository: _baseBiometricRepository,
            )
          : null);

  // Repositorios que de verdad consumen el resto de esta pantalla y las
  // que abre: si hay sincronización habilitada, son los repositorios
  // base envueltos en su decorador `Syncing*Repository` (ver
  // `lib/services/syncing_repositories.dart`); si no, son los propios
  // repositorios base, sin ningún cambio de comportamiento.
  late final GlucoseRepository _repository = _makeRepository(
    _baseGlucoseRepository,
    (sync) => SyncingGlucoseRepository(
      delegate: _baseGlucoseRepository,
      syncRepository: sync,
    ),
  );
  late final MealRepository _mealRepository = _makeRepository(
    _baseMealRepository,
    (sync) => SyncingMealRepository(
      delegate: _baseMealRepository,
      syncRepository: sync,
    ),
  );
  late final MedicationRepository _medicationRepository = _makeRepository(
    _baseMedicationRepository,
    (sync) => SyncingMedicationRepository(
      delegate: _baseMedicationRepository,
      syncRepository: sync,
    ),
  );
  late final BiometricRepository _biometricRepository = _makeRepository(
    _baseBiometricRepository,
    (sync) => SyncingBiometricRepository(
      delegate: _baseBiometricRepository,
      syncRepository: sync,
    ),
  );

  /// Devuelve [base] sin cambios si no hay sincronización habilitada
  /// ([_syncRepository] es `null`), o el resultado de [wrap] con el
  /// [CloudSyncRepository] ya no nulo en caso contrario. Evita repetir
  /// el mismo `_syncRepository == null ? ... : ...` (con una
  /// aserción `!` redundante para el analizador) en cada repositorio.
  T _makeRepository<T>(T base, T Function(CloudSyncRepository sync) wrap) {
    final sync = _syncRepository;
    return sync == null ? base : wrap(sync);
  }
  // No usa `??` por la misma razón que `_syncRepository`: el valor
  // por defecto de `GlucoseImportRepository` es `null` (no una
  // implementación real), ya que esta funcionalidad depende del plugin
  // `health` real (`enableHealthImport`), y los tests de widgets no
  // deben tocar Health Connect/Apple Health reales por defecto.
  late final GlucoseImportRepository? _importRepository =
      widget.importRepository ??
      (widget.enableHealthImport
          ? HealthGlucoseImportRepository(glucoseRepository: _repository)
          : null);
  late final MealGlucoseReminderRepository _reminderRepository =
      widget.reminderRepository ??
      SqliteMealGlucoseReminderRepository.withDatabase(_sharedDatabase);
  late final MealGlucoseReminderCoordinator _reminderCoordinator =
      MealGlucoseReminderCoordinator(
        reminderRepository: _reminderRepository,
        glucoseRepository: _repository,
        importRepository: _importRepository,
        notificationService: widget.notificationService,
      );

  GlucoseMeasurement? _lastMeasurement;
  bool _isLoading = true;
  StreamSubscription<void>? _notificationTapSubscription;
  StreamSubscription<AppUser?>? _authStateSubscription;
  bool _wasSignedIn = false;

  @override
  void initState() {
    super.initState();
    _loadLastMeasurement();
    if (widget.enableMealReminders) {
      _reviewPendingReminders();
      _setUpNotificationTapHandling();
    }
    if (_syncRepository != null) {
      _setUpCloudSyncPullOnSignIn();
    }
  }

  /// Dispara [CloudSyncRepository.pullMissingFromCloud] automáticamente
  /// cada vez que se detecta una sesión recién iniciada (incluida la
  /// restauración automática de sesión al abrir la app), pensado para
  /// que un dispositivo nuevo (por ejemplo, tras cambiar de celular)
  /// recupere en silencio el historial completo sin ninguna acción
  /// manual. No se dispara al cerrar sesión, ni se repite mientras la
  /// sesión siga iniciada.
  void _setUpCloudSyncPullOnSignIn() {
    _wasSignedIn = _authRepository.currentUser != null;
    if (_wasSignedIn) {
      unawaited(_pullMissingFromCloudSilently());
    }
    _authStateSubscription = _authRepository.authStateChanges().listen((
      user,
    ) {
      final isSignedIn = user != null;
      if (isSignedIn && !_wasSignedIn) {
        unawaited(_pullMissingFromCloudSilently());
      }
      _wasSignedIn = isSignedIn;
    });
  }

  /// Ejecuta la fusión automática desde la nube sin interrumpir a quien
  /// use la app: cualquier falla (por ejemplo, sin conexión) se
  /// descarta en silencio, porque esta operación no la inició el
  /// usuario explícitamente. Si trae registros nuevos, refresca la
  /// tarjeta de glucosa para reflejarlos de inmediato.
  Future<void> _pullMissingFromCloudSilently() async {
    final syncRepository = _syncRepository;
    if (syncRepository == null) {
      return;
    }
    try {
      final summary = await syncRepository.pullMissingFromCloud();
      if (summary.addedGlucoseMeasurements > 0) {
        await _loadLastMeasurement();
      }
    } on CloudSyncException {
      // Falla silenciosa: ver documentación de este método.
    }
  }

  @override
  void dispose() {
    _notificationTapSubscription?.cancel();
    _authStateSubscription?.cancel();
    super.dispose();
  }

  /// Prepara el servicio de notificaciones push (permiso + red de
  /// seguridad de reprogramación) y se suscribe a los toques sobre
  /// notificaciones ya mostradas, para volver a revisar los
  /// recordatorios pendientes en ese caso (roadmap punto 17, Fase B).
  void _setUpNotificationTapHandling() {
    final notificationService = widget.notificationService;
    if (notificationService == null) {
      return;
    }

    unawaited(
      notificationService.requestPermission().then((_) {
        return _reminderCoordinator.rescheduleAllPending();
      }),
    );

    _notificationTapSubscription = notificationService.onNotificationTapped
        .listen((_) {
          _reviewPendingReminders();
        });
  }

  /// Revisa los recordatorios de glucosa post-comida vencidos: los que se
  /// resuelven solos (vía CGM) quedan registrados sin interrumpir al
  /// usuario; los que requieren acción manual se muestran uno por uno en
  /// un diálogo (alarma sonora de día, popup silencioso de noche).
  Future<void> _reviewPendingReminders() async {
    final result = await _reminderCoordinator.reviewPending();
    if (!mounted || result.needsManualAction.isEmpty) {
      return;
    }

    for (final pending in result.needsManualAction) {
      if (!mounted) {
        return;
      }
      if (pending.isDaytime) {
        // El sonido es un complemento best-effort: si la plataforma no
        // puede reproducirlo (por ejemplo, el canal no está disponible
        // en un entorno de pruebas), el diálogo debe mostrarse igual. Se
        // evita bloquear el flujo esperando su resultado.
        unawaited(SystemSound.play(SystemSoundType.alert).catchError((_) {}));
      }
      await _showReminderDialog(pending);
    }
  }

  Future<void> _showReminderDialog(PendingMealGlucoseReminder pending) async {
    final reminder = pending.reminder;
    final action = await showDialog<_ReminderDialogAction>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        icon: Icon(
          pending.isDaytime ? Icons.alarm : Icons.nightlight_round,
          color: Colors.deepPurple,
        ),
        title: const Text('Hora de medir tu glucosa'),
        content: Text(
          'Han pasado ${reminder.offsetMinutes} minutos desde tu comida. '
          'Registra tu nivel de glucosa para completar el seguimiento.',
        ),
        actions: [
          TextButton(
            onPressed: () =>
                Navigator.pop(context, _ReminderDialogAction.dismiss),
            child: const Text('Descartar'),
          ),
          FilledButton(
            onPressed: () =>
                Navigator.pop(context, _ReminderDialogAction.register),
            child: const Text('Registrar ahora'),
          ),
        ],
      ),
    );

    if (action == _ReminderDialogAction.register) {
      await _registerReminderMeasurement(reminder);
    } else {
      await _reminderCoordinator.dismiss(reminder);
    }
  }

  Future<void> _registerReminderMeasurement(
    MealGlucoseReminder reminder,
  ) async {
    final result = await Navigator.push<GlucoseMeasurement>(
      context,
      MaterialPageRoute(builder: (context) => const GlucoseScreen()),
    );

    if (result == null) {
      await _reminderCoordinator.dismiss(reminder);
      return;
    }

    final saved = await _reminderCoordinator.resolveManually(reminder, result);
    if (!mounted) {
      return;
    }
    setState(() {
      _lastMeasurement = saved;
    });
  }

  Future<void> _loadLastMeasurement() async {
    final stored = await _repository.getLastMeasurement();
    if (!mounted) {
      return;
    }
    setState(() {
      _lastMeasurement = stored;
      _isLoading = false;
    });
  }

  Future<void> _openGlucoseScreen() async {
    final result = await Navigator.push<GlucoseMeasurement>(
      context,
      MaterialPageRoute(builder: (context) => const GlucoseScreen()),
    );

    if (result == null) {
      return;
    }

    final saved = await _repository.addMeasurement(result);
    if (!mounted) {
      return;
    }

    setState(() {
      _lastMeasurement = saved;
    });
  }

  void _openHistoryScreen() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => HistoryScreen(
          repository: _repository,
          importRepository: _importRepository,
        ),
      ),
    );
  }

  void _openMealScreen() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => MealScreen(
          repository: _mealRepository,
          reminderCoordinator: _reminderCoordinator,
        ),
      ),
    );
  }

  void _openMedicationScreen() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) =>
            MedicationScreen(repository: _medicationRepository),
      ),
    );
  }

  void _openBiometricScreen() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => BiometricScreen(
          repository: _biometricRepository,
          profileRepository: _profileRepository,
        ),
      ),
    );
  }

  void _openAuthScreen() {
    Navigator.push(
      context,
      MaterialPageRoute<void>(
        builder: (context) => AuthScreen(repository: _authRepository),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[100],
      appBar: AppBar(
        title: const Text(
          'Seguimiento Glucosa',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.account_circle_outlined),
            tooltip: 'Cuenta',
            onPressed: _openAuthScreen,
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            _GlucoseCard(
              measurement: _lastMeasurement,
              isLoading: _isLoading,
              onTap: _openGlucoseScreen,
            ),
            const SizedBox(height: 20),
            MenuButton(
              icon: Icons.restaurant,
              title: 'Comida',
              onTap: _openMealScreen,
            ),
            MenuButton(
              icon: Icons.medication,
              title: 'Medicamentos',
              onTap: _openMedicationScreen,
            ),
            MenuButton(
              icon: Icons.favorite,
              title: 'Biometría',
              onTap: _openBiometricScreen,
            ),
            MenuButton(
              icon: Icons.show_chart,
              title: 'Historial',
              onTap: _openHistoryScreen,
            ),
          ],
        ),
      ),
    );
  }
}

/// Tarjeta que muestra la última medición de glucosa registrada, o un
/// marcador `--` cuando todavía no hay ninguna (o está cargando).
class _GlucoseCard extends StatelessWidget {
  const _GlucoseCard({
    required this.measurement,
    required this.isLoading,
    required this.onTap,
  });

  final GlucoseMeasurement? measurement;
  final bool isLoading;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final displayValue = measurement == null
        ? '-- mg/dL'
        : '${measurement!.value} mg/dL';

    return GestureDetector(
      onTap: onTap,
      child: Card(
        elevation: 4,
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            children: [
              const Icon(Icons.bloodtype, size: 45, color: Colors.red),
              const SizedBox(height: 10),
              const Text(
                'Glucosa actual',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 10),
              if (isLoading)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 8),
                  child: SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2.5),
                  ),
                )
              else
                Text(
                  displayValue,
                  style: const TextStyle(
                    fontSize: 38,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              if (!isLoading && measurement != null) ...[
                const SizedBox(height: 6),
                Text(
                  measurement!.moment.label,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Botón de menú reutilizable para los accesos de la pantalla principal.
///
/// [onTap] es opcional: los módulos aún no implementados (por ejemplo,
/// Comida o Medicamentos) se muestran sin acción asociada.
class MenuButton extends StatelessWidget {
  const MenuButton({
    super.key,
    required this.icon,
    required this.title,
    this.onTap,
  });

  final IconData icon;
  final String title;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: Icon(icon),
        title: Text(title, style: const TextStyle(fontSize: 18)),
        trailing: const Icon(Icons.arrow_forward_ios, size: 16),
        onTap: onTap,
      ),
    );
  }
}

/// Acción elegida por el usuario en el diálogo de un recordatorio de
/// glucosa post-comida.
enum _ReminderDialogAction { register, dismiss }
