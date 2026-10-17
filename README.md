# Seguimiento Glucosa

Aplicación Flutter para registrar mediciones personales de glucosa junto con el momento de la medición, un comentario opcional y la fecha y hora automáticas.

> [!IMPORTANT]
> El proyecto se encuentra en una etapa inicial (MVP). No es un dispositivo médico ni sustituye el diagnóstico, tratamiento o asesoramiento de un profesional de la salud.

## Estado actual

La aplicación permite:

- Visualizar una pantalla principal con una tarjeta de glucosa.
- Abrir el formulario de registro desde la tarjeta.
- Ingresar una medición en `mg/dL`, validada en el rango 20–600.
- Seleccionar el contexto de la medición: al despertar, antes o después de una comida, antes de dormir, entre otros.
- Agregar un comentario opcional.
- Generar automáticamente la fecha y hora al pulsar **Guardar**.
- Al guardar, la medición se construye como un objeto `GlucoseMeasurement` y
  se retorna a la pantalla principal, que la persiste en SQLite (tabla
  `glucose_measurements`) y actualiza la tarjeta mostrando el valor y el
  momento registrado.
- Al reabrir la app, la pantalla principal carga automáticamente la última
  medición guardada (mostrando un indicador breve mientras se lee).
- Acceder al **Historial** desde la pantalla principal, con dos pestañas:
  - **Lista**: todas las mediciones registradas, ordenadas de la más
    reciente a la más antigua (valor, momento, fecha/hora y comentario si
    existe).
  - **Gráfico**: evolución de los valores de glucosa en el tiempo, con
    líneas de referencia en 70 y 180 mg/dL y tooltip táctil por medición
    (requiere al menos 2 mediciones registradas).
- Desde el **Historial**, importar manualmente mediciones de glucosa ya
  registradas en el sensor/CGM del dispositivo (Google Health Connect en
  Android, Apple Health en iOS), evitando duplicados por fecha/hora y
  valor con lo ya guardado en SQLite.

El historial completo de mediciones ahora sobrevive a reinicios de la app
gracias a la persistencia local en SQLite (`sqflite`).

Además, el módulo de **Comida** permite:

- Registrar una comida indicando su tipo (Desayuno, Almuerzo,
  Once/Merienda, Cena u Otro/Snack), agregando uno o más alimentos con su
  cantidad en texto libre (ej. "1 taza", "2 rebanadas") y un comentario
  opcional.
- Ver el **Historial** de comidas ya registradas (tipo, fecha/hora,
  alimentos y comentario), en su propia pestaña dentro de la pantalla de
  Comida.
- Reutilizar automáticamente un alimento ya registrado (por nombre) en
  lugar de duplicarlo en el catálogo interno.

Además, el módulo de **Medicamentos** permite:

- Registrar una toma indicando uno o más medicamentos, cada uno con una
  cantidad numérica y una unidad de dosis (mg, ml, Comprimido, Unidades,
  Gota u Otro con texto libre), y un comentario opcional.
- Ver el **Historial** de tomas ya registradas (medicamentos con su
  cantidad y unidad, fecha/hora y comentario), en su propia pestaña dentro
  de la pantalla de Medicamentos.
- Reutilizar automáticamente un medicamento ya registrado (por nombre) en
  lugar de duplicarlo en el catálogo interno.

Además, el módulo de **Biometría** permite:

- Registrar un peso corporal en kg (obligatorio, validado en el rango
  20–400), con presión arterial (sistólica/diastólica en mmHg, opcional
  pero deben completarse juntas) y frecuencia cardíaca (lpm, opcional)
  en el mismo registro, además de un comentario opcional.
- Ver el **Historial** de mediciones ya registradas (peso, presión y
  frecuencia cardíaca cuando existen, fecha/hora y comentario), en su
  propia pestaña dentro de la pantalla de Biometría. Cada registro del
  historial muestra además el **IMC** calculado a partir de ese peso y
  la altura guardada en el **Perfil**.
- Completar el **Perfil** (altura, fecha de nacimiento, sexo biológico
  y nombre a mostrar) en su propia pestaña dentro de la pantalla de
  Biometría; solo la altura es obligatoria para habilitar el cálculo
  de IMC.

Además, al guardar una comida se generan automáticamente dos
**recordatorios de medición post-comida** (a los 60 y 90 minutos). Al
vencer, se intentan resolver solos si hay una medición del
sensor/CGM cercana en el tiempo; si no, se muestra un diálogo al abrir
la app (registrar ahora o descartar). Por ahora esta lógica es
totalmente in-app (Fase A); todavía no dispara notificaciones ni
alarmas reales del sistema operativo (Fase B, pendiente).

Se integró **Firebase** (proyecto `seguimiento-glucosa`) como base para
pasos futuros del roadmap (autenticación, sincronización entre
dispositivos). SQLite sigue siendo el almacenamiento principal: por
ahora Firebase no mueve ningún dato ni usa Firestore/Realtime Database.

Además, se agregó **autenticación de usuarios opcional** (ícono
"Cuenta" en la pantalla principal), con correo/contraseña y con Google
(Firebase Auth). Es opcional: el resto de la app (Glucosa, Comida,
Medicamentos, Biometría, Historial) sigue funcionando sin iniciar
sesión, ya que SQLite es el almacenamiento principal.

Con una sesión iniciada, la pantalla de **Cuenta** también permite
**respaldar y restaurar manualmente** todo el historial (glucosa,
comidas, medicamentos, biometría) en Cloud Firestore. No es
sincronización automática: el usuario decide cuándo respaldar, y
"Restaurar" **reemplaza** los datos locales actuales (con un diálogo
de confirmación explícito, ya que la acción no se puede deshacer).

## Funcionalidades pendientes

- Sincronización automática/en tiempo real entre dispositivos (la
  versión actual es manual: respaldar/restaurar bajo demanda).
- Notificaciones/alarmas reales del sistema para los recordatorios de
  medición post-comida (Fase B); la Fase A (lógica, persistencia y
  diálogo in-app) ya está implementada.

**Historial**, **Comida**, **Medicamentos**, **Biometría** (con perfil de
usuario e IMC) e **importación manual desde sensores/CGM** ya están
implementados.

## Tecnologías y dependencias

- Flutter 3.44.8 (canal `stable`).
- Dart 3.12.2.
- Material Design.
- `cupertino_icons: ^1.0.8`.
- `sqflite: ^2.4.4+2` para persistir el historial completo de mediciones en
  SQLite.
- `path: ^1.9.1` para construir la ruta del archivo de base de datos.
- `intl: ^0.20.3` para formatear fechas en la pantalla de Historial.
- `fl_chart: ^1.2.0` para el gráfico de evolución de glucosa en la
  pestaña "Gráfico" del Historial.
- `firebase_core: ^5.0.0` para inicializar Firebase (proyecto
  `seguimiento-glucosa`) como base de pasos futuros (Auth, sincronización).
  No se usa todavía para almacenar datos de la app.
- `firebase_auth: ^7.0.0` para la autenticación opcional por
  correo/contraseña y por credenciales de Google.
- `google_sign_in: ^7.2.0` para el flujo nativo de inicio de sesión con
  Google (Android/iOS), usado junto con `firebase_auth`.
- `cloud_firestore: ^7.0.0` para el respaldo/restauración manual del
  historial completo en la nube (solo con sesión iniciada).
- `health: ^13.3.2` para la importación manual de glucosa desde
  Google Health Connect (Android) y Apple HealthKit (iOS). Solo lee
  datos ya existentes en la plataforma de salud, nunca escribe en ella.
- `flutter_lints: ^6.0.0` para análisis estático.
- `flutter_test` para pruebas de widgets.
- `sqflite_common_ffi: ^2.4.4` (dev) para probar `SqliteGlucoseRepository`
  sobre una base de datos en memoria, sin depender del plugin nativo.

El proyecto está enfocado actualmente en Android, aunque conserva las carpetas de plataforma generadas por Flutter para Android, iOS, Linux, macOS, web y Windows.

## Estructura principal

```text
lib/
├── main.dart
├── firebase_options.dart   (generado por `flutterfire configure`)
├── models/
│   ├── glucose_measurement.dart
│   ├── food.dart
│   ├── meal.dart
│   ├── medication.dart
│   ├── medication_intake.dart
│   ├── biometric_measurement.dart
│   ├── meal_glucose_reminder.dart
│   ├── user_profile.dart
│   └── app_user.dart
├── services/
│   ├── app_database.dart
│   ├── glucose_repository.dart
│   ├── glucose_import_repository.dart
│   ├── health_glucose_import_repository.dart
│   ├── meal_repository.dart
│   ├── meal_glucose_reminder_repository.dart
│   ├── meal_glucose_reminder_coordinator.dart
│   ├── medication_repository.dart
│   ├── biometric_repository.dart
│   ├── user_profile_repository.dart
│   ├── auth_repository.dart
│   ├── firebase_auth_repository.dart
│   ├── backup_repository.dart
│   └── firestore_backup_repository.dart
├── screens/
│   ├── home_screen.dart
│   ├── glucose_screen.dart
│   ├── history_screen.dart
│   ├── meal_screen.dart
│   ├── medication_screen.dart
│   ├── biometric_screen.dart
│   └── auth_screen.dart
└── widgets/
    └── glucose_line_chart.dart

test/
├── widget_test.dart
├── models/
│   └── user_profile_test.dart
└── services/
    ├── glucose_repository_test.dart
    ├── meal_repository_test.dart
    ├── meal_glucose_reminder_repository_test.dart
    ├── medication_repository_test.dart
    ├── biometric_repository_test.dart
    └── user_profile_repository_test.dart
```

- `lib/main.dart`: configura la aplicación, el tema y la pantalla
  inicial; inicializa Firebase (`Firebase.initializeApp`) y Google
  Sign-In (`initializeGoogleSignIn`) antes de `runApp`.
- `lib/firebase_options.dart`: generado por `flutterfire configure`;
  opciones de conexión (Android/iOS) del proyecto Firebase
  `seguimiento-glucosa`. No contiene secretos de servidor.
- `lib/models/glucose_measurement.dart`: modelo inmutable `GlucoseMeasurement` (con `id` opcional asignado por el almacenamiento) y enum `GlucoseMoment`.
- `lib/models/food.dart`: modelo inmutable `Food` (catálogo reutilizable de alimentos).
- `lib/models/meal.dart`: modelos inmutables `Meal` y `MealFoodItem`, y enum `MealType`.
- `lib/models/medication.dart`: modelo inmutable `Medication` (catálogo reutilizable de medicamentos) y enum `DoseUnit`.
- `lib/models/medication_intake.dart`: modelos inmutables `MedicationIntake` y `MedicationIntakeItem`.
- `lib/models/biometric_measurement.dart`: modelo inmutable `BiometricMeasurement` (peso corporal, con `id` opcional asignado por el almacenamiento).
- `lib/models/meal_glucose_reminder.dart`: modelo inmutable `MealGlucoseReminder` (id, mealId, offsetMinutes, dueAt, status, resolvedMeasurementId) y enum `MealGlucoseReminderStatus` (pending, resolvedAutomatically, resolvedManually, dismissed); representa un recordatorio de medir glucosa a los 60/90 minutos de una comida.
- `lib/models/user_profile.dart`: modelo inmutable `UserProfile` (heightCm, birthDate, biologicalSex, displayName), enum `BiologicalSex`, método `UserProfile.bmiFor(weightKg)` y enum/clasificación `BmiCategory` según rangos de la OMS.
- `lib/models/app_user.dart`: modelo inmutable `AppUser` (uid, email, displayName) del usuario autenticado, independiente del SDK de Firebase.
- `lib/services/app_database.dart`: `AppDatabase`, gestor único de la conexión SQLite compartida por todos los repositorios, con creación y migración de esquema.
- `lib/services/glucose_repository.dart`: interfaz `GlucoseRepository` (historial completo: última medición, listado, agregar, limpiar) y la implementación `SqliteGlucoseRepository` basada en `sqflite`.
- `lib/services/glucose_import_repository.dart`: interfaz `GlucoseImportRepository` (solo lectura) para importar manualmente mediciones ya registradas en la plataforma de salud del dispositivo (Health Connect/Apple Health) y `HealthImportException`.
- `lib/services/health_glucose_import_repository.dart`: implementación `HealthGlucoseImportRepository` de `GlucoseImportRepository` sobre el plugin `health`.
- `lib/services/meal_repository.dart`: interfaz `MealRepository` (listado, agregar, limpiar comidas; listar catálogo de alimentos) y la implementación `SqliteMealRepository`.
- `lib/services/meal_glucose_reminder_repository.dart`: interfaz `MealGlucoseReminderRepository` (agregar en lote, listar vencidos, actualizar estado) y la implementación `SqliteMealGlucoseReminderRepository`.
- `lib/services/meal_glucose_reminder_coordinator.dart`: `MealGlucoseReminderCoordinator`, lógica pura de aplicación (sin notificaciones del sistema todavía — Fase A) que genera los dos recordatorios por comida, revisa los vencidos intentando auto-resolución vía CGM, y expone `dismiss`/`resolveManually` para la acción del usuario.
- `lib/services/medication_repository.dart`: interfaz `MedicationRepository` (listado, agregar, limpiar tomas; listar catálogo de medicamentos) y la implementación `SqliteMedicationRepository`.
- `lib/services/biometric_repository.dart`: interfaz `BiometricRepository` (última medición, listado, agregar, limpiar) y la implementación `SqliteBiometricRepository`.
- `lib/services/user_profile_repository.dart`: interfaz `UserProfileRepository` (perfil único, sin listado ni multiusuario: `getProfile`, `saveProfile`, `clearProfile`) y la implementación `SqliteUserProfileRepository`.
- `lib/services/auth_repository.dart`: interfaz `AuthRepository` (estado de sesión, registro/inicio de sesión con correo, inicio de sesión con Google, recuperar contraseña, cerrar sesión) y `AuthException` (mensajes de error en español).
- `lib/services/firebase_auth_repository.dart`: implementación `FirebaseAuthRepository` sobre `firebase_auth` y `google_sign_in`.
- `lib/services/backup_repository.dart`: interfaz `BackupRepository` (`backup`, `restore`, `getLastBackupTime`) y `BackupException`. `restore` reemplaza los datos locales (no los fusiona), ya documentado en su propio docstring.
- `lib/services/firestore_backup_repository.dart`: implementación `FirestoreBackupRepository` sobre `cloud_firestore`, que serializa las cuatro colecciones de datos de salud a un único documento `backups/{uid}`.
- `lib/screens/home_screen.dart`: carga la última medición desde el repositorio al iniciar, presenta la tarjeta de glucosa y los accesos a los módulos, guarda cada nueva medición recibida, navega a `HistoryScreen`, `MealScreen`, `MedicationScreen`, `BiometricScreen` y (desde el ícono "Cuenta" del `AppBar`) a `AuthScreen`; al iniciar también revisa recordatorios post-comida vencidos vía `MealGlucoseReminderCoordinator` y muestra un diálogo (registrar ahora / descartar) por cada uno que no se resolvió automáticamente.
- `lib/screens/glucose_screen.dart`: contiene el formulario de captura de una medición, con validación, y retorna un `GlucoseMeasurement`.
- `lib/screens/history_screen.dart`: carga el historial completo de mediciones (`GlucoseRepository.getAllMeasurements`) y lo muestra en dos pestañas: **Lista** (de la más reciente a la más antigua) y **Gráfico** (evolución del valor en el tiempo, vía `GlucoseLineChart`).
- `lib/screens/meal_screen.dart`: pantalla del módulo de Comidas, con pestañas propias **Registrar** (formulario con alimentos y cantidades) e **Historial** (comidas guardadas).
- `lib/screens/medication_screen.dart`: pantalla del módulo de Medicamentos, con pestañas propias **Registrar** (formulario con medicamentos, cantidad y unidad) e **Historial** (tomas guardadas).
- `lib/screens/biometric_screen.dart`: pantalla del módulo de Biometría, con pestañas propias **Registrar** (peso corporal obligatorio; presión arterial y frecuencia cardíaca opcionales), **Perfil** (altura y otros datos personales) e **Historial** (mediciones guardadas, mostrando el IMC calculado a partir del peso de cada medición y la altura vigente del perfil vía `UserProfile.bmiFor`; si el perfil no tiene altura guardada, el IMC no se muestra).
- `lib/screens/auth_screen.dart`: pantalla de cuenta (opcional); muestra el formulario de inicio de sesión/registro o, si ya hay una sesión activa, el resumen de la cuenta con botones para respaldar/restaurar en la nube (con diálogo de confirmación antes de restaurar) y cerrar sesión.
- `lib/widgets/glucose_line_chart.dart`: widget reutilizable `GlucoseLineChart`, el gráfico de líneas (`fl_chart`) con la evolución de glucosa, líneas de referencia y tooltip táctil.
- `PROJECT_CONTEXT.md`: describe con mayor detalle las decisiones, el alcance y la evolución prevista del proyecto.
- `PROJECT_GRAPH.md`: grafo de dependencias, imports y navegación entre pantallas.

## Requisitos

- [Flutter SDK](https://docs.flutter.dev/get-started/install) compatible con Dart `^3.12.2`.
- Para Android: Android Studio o Android SDK y un emulador o dispositivo configurado.

Comprueba la instalación con:

```bash
flutter doctor
```

## Instalación y ejecución

Desde la raíz del proyecto (`seguimiento_glucosa`):

```bash
flutter pub get
flutter devices
flutter run
```

Para elegir un dispositivo concreto:

```bash
flutter run -d <device-id>
```

## Calidad y pruebas

Comandos de validación disponibles:

```bash
flutter analyze
flutter test
```

Estado actual de la revisión:

- `flutter analyze`: **No issues found!**
- `flutter test`: **All tests passed!** (91/91).
- `flutter build apk --debug`: compila correctamente (verificado tras
  integrar `firebase_auth`/`google_sign_in`/`cloud_firestore`).

Incidencias previamente conocidas y ya resueltas:

- El test referenciaba una clase inexistente `MyApp`; ahora valida `SeguimientoGlucosaApp`.
- `DropdownButtonFormField` usaba el parámetro deprecado `value`; ahora usa `initialValue`.
- Se eliminaron los cuatro usos de `print()` en el flujo de guardado.
- El almacenamiento solo conservaba el último valor (`shared_preferences`);
  ahora persiste el historial completo en SQLite (`sqflite`).

Nota sobre pruebas:

- Los widget tests inyectan fakes en memoria (ver `test/widget_test.dart`):
  `_FakeGlucoseRepository`, `_FakeMealRepository`,
  `_FakeMealGlucoseReminderRepository`, `_FakeMedicationRepository`,
  `_FakeBiometricRepository`, `_FakeUserProfileRepository`,
  `_FakeAuthRepository`, `_FakeBackupRepository` y
  `_FakeGlucoseImportRepository`, en lugar de usar las implementaciones
  `Sqlite*`/`HealthGlucoseImportRepository`/`FirebaseAuthRepository`/
  `FirestoreBackupRepository`, evitando depender del plugin real de
  `sqflite`, del plugin `health` ni del SDK de Firebase durante
  `flutter test`.
- `HomeScreen` solo construye un `FirestoreBackupRepository` real
  cuando se le pasa `enableCloudBackup: true` explícitamente (lo hace
  `main.dart` en producción); por defecto es `false`, para que los
  widget tests no intenten tocar Firestore real.
- `test/services/glucose_repository_test.dart`,
  `test/services/meal_repository_test.dart`,
  `test/services/meal_glucose_reminder_repository_test.dart`,
  `test/services/medication_repository_test.dart`,
  `test/services/biometric_repository_test.dart` y
  `test/services/user_profile_repository_test.dart` prueban sus
  implementaciones `Sqlite*` directamente contra una base de datos
  SQLite real en memoria, usando `sqflite_common_ffi` con
  `singleInstance: false` para aislar cada test.
- `test/services/meal_glucose_reminder_coordinator_test.dart` prueba
  `MealGlucoseReminderCoordinator` (lógica pura de aplicación) con un
  `_FakeMealGlucoseReminderRepository` en memoria, sin tocar SQLite.
- `test/models/user_profile_test.dart` prueba `UserProfile.bmiFor` y
  `bmiCategoryFor` como funciones puras, sin dependencias de
  plataforma.

## Próximos pasos recomendados

1. Implementar la Fase B de los recordatorios de medición post-comida:
   notificaciones/alarmas reales del sistema (`flutter_local_notifications`
   + `timezone`/`flutter_timezone`), manteniendo SQLite como fuente de
   verdad y con reconciliación al iniciar la app.
2. Evaluar si se necesita sincronización automática/en tiempo real
   (más allá del respaldo/restauración manual ya implementado), lo
   que requeriría introducir claves estables (p. ej. UUID) en los
   modelos de datos para poder fusionar sin duplicados.
3. Verificar en una Mac con Xcode que
   `ios/Runner/GoogleService-Info.plist` (generado vía
   `firebase apps:sdkconfig` y enlazado manualmente al proyecto Xcode,
   ya que `flutterfire configure` no pudo completarlo desde Windows)
   compila y se incluye correctamente al construir para iOS, y que el
   inicio de sesión con Google, el respaldo/restauración y la
   importación desde Apple Health funcionan en esa plataforma.
4. Probar el inicio de sesión con Google, el respaldo/restauración y
   la importación desde Health Connect en un dispositivo/emulador
   Android real (la validación actual cubrió `flutter analyze`,
   `flutter test` y una compilación exitosa del APK, pero no todas las
   ejecuciones interactivas).

## Licencia

El proyecto no declara actualmente una licencia de distribución.

