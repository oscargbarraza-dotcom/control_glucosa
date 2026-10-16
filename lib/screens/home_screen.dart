import 'package:flutter/material.dart';

import '../models/glucose_measurement.dart';
import '../services/app_database.dart';
import '../services/auth_repository.dart';
import '../services/backup_repository.dart';
import '../services/biometric_repository.dart';
import '../services/firebase_auth_repository.dart';
import '../services/firestore_backup_repository.dart';
import '../services/glucose_import_repository.dart';
import '../services/glucose_repository.dart';
import '../services/health_glucose_import_repository.dart';
import '../services/meal_repository.dart';
import '../services/medication_repository.dart';
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
    this.backupRepository,
    this.enableCloudBackup = false,
    this.importRepository,
    this.enableHealthImport = false,
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

  /// Repositorio de respaldo/restauración en la nube. Si es `null`, se
  /// usa [FirestoreBackupRepository] (construido sobre los mismos
  /// repositorios de datos de salud que el resto de la pantalla).
  /// Permite inyectar `null` explícitamente en tests que no necesitan
  /// probar esta funcionalidad, para que `AuthScreen` no muestre los
  /// botones de respaldo.
  final BackupRepository? backupRepository;

  /// Habilita la construcción automática de [FirestoreBackupRepository]
  /// cuando [backupRepository] es `null`. Por defecto es `false` para
  /// no tocar Firestore real en los widget tests; `main.dart` lo activa
  /// explícitamente una vez que Firebase ya está inicializado.
  final bool enableCloudBackup;

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

  late final GlucoseRepository _repository =
      widget.repository ??
      SqliteGlucoseRepository.withDatabase(_sharedDatabase);
  late final MealRepository _mealRepository =
      widget.mealRepository ??
      SqliteMealRepository.withDatabase(_sharedDatabase);
  late final MedicationRepository _medicationRepository =
      widget.medicationRepository ??
      SqliteMedicationRepository.withDatabase(_sharedDatabase);
  late final BiometricRepository _biometricRepository =
      widget.biometricRepository ??
      SqliteBiometricRepository.withDatabase(_sharedDatabase);
  late final UserProfileRepository _profileRepository =
      widget.profileRepository ??
      SqliteUserProfileRepository.withDatabase(_sharedDatabase);
  late final AuthRepository _authRepository =
      widget.authRepository ?? FirebaseAuthRepository();
  // No usa `??` porque, a diferencia de los demás repositorios, el valor
  // por defecto de `BackupRepository` es `null` (no una implementación
  // real): esta funcionalidad requiere Firebase ya inicializado
  // (`enableCloudBackup`), y los tests de widgets no deben tocar
  // Firestore real por defecto.
  late final BackupRepository? _backupRepository =
      widget.backupRepository ??
      (widget.enableCloudBackup
          ? FirestoreBackupRepository(
              glucoseRepository: _repository,
              mealRepository: _mealRepository,
              medicationRepository: _medicationRepository,
              biometricRepository: _biometricRepository,
            )
          : null);
  // No usa `??` por la misma razón que `_backupRepository`: el valor
  // por defecto de `GlucoseImportRepository` es `null` (no una
  // implementación real), ya que esta funcionalidad depende del plugin
  // `health` real (`enableHealthImport`), y los tests de widgets no
  // deben tocar Health Connect/Apple Health reales por defecto.
  late final GlucoseImportRepository? _importRepository =
      widget.importRepository ??
      (widget.enableHealthImport
          ? HealthGlucoseImportRepository(glucoseRepository: _repository)
          : null);

  GlucoseMeasurement? _lastMeasurement;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadLastMeasurement();
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
        builder: (context) => MealScreen(repository: _mealRepository),
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
        builder: (context) => AuthScreen(
          repository: _authRepository,
          backupRepository: _backupRepository,
        ),
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
