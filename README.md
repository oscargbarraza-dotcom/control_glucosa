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
la app (registrar ahora o descartar) (Fase A, lógica in-app). Además,
tanto en Android como en iOS, cada recordatorio programa una
**notificación push local** (`flutter_local_notifications`) que avisa
aunque la app esté cerrada o en background; se solicita el permiso de
notificaciones al abrir la app y, al tocar una notificación, se vuelve
a revisar los recordatorios pendientes (Fase B).

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
**respaldar** todo el historial (glucosa, comidas, medicamentos,
biometría) en Cloud Firestore, y traerlo de vuelta de dos formas
distintas:

- **Restaurar desde la nube**: **reemplaza** todos los datos locales
  actuales por la última copia guardada (con un diálogo de
  confirmación explícito, ya que la acción no se puede deshacer).
- **Fusionar desde la nube**: **agrega** los registros de la nube que
  todavía no existan en este dispositivo (identificados por su `uuid`
  estable), sin tocar ni borrar nada de lo que ya hay localmente. No
  pide confirmación porque nunca es destructiva; pensada para traer a
  este dispositivo lo registrado en otro, sin perder nada.

Ninguna de las dos es sincronización automática: el usuario decide
cuándo respaldar y cuál de las dos formas de traer datos usar.

Cada registro de glucosa, comida, toma de medicamentos y medición
biométrica tiene, además de su `id` autoincremental de SQLite, un
identificador estable (**UUID v4**) independiente del almacenamiento
local, que es justamente la clave que usa "Fusionar desde la nube"
para decidir qué registros ya existen y evitar duplicados.

## Funcionalidades pendientes

- Sincronización automática/en tiempo real entre dispositivos (la
  versión actual sigue siendo manual: respaldar, y luego elegir
  restaurar o fusionar bajo demanda).

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
- `flutter_local_notifications: ^22.3.2` para las notificaciones push
  locales de los recordatorios de glucosa post-comida (Fase B, en
  Android e iOS).
- `timezone: ^0.11.2` y `flutter_timezone: ^5.1.1` para programar esas
  notificaciones respetando la zona horaria local del dispositivo.
- `uuid: ^4.6.0` para generar el identificador estable (UUID v4) de
  cada registro de glucosa, comida, toma de medicamentos y medición
  biométrica, independiente del `id` autoincremental de SQLite.
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
- `lib/services/meal_glucose_reminder_repository.dart`: interfaz `MealGlucoseReminderRepository` (agregar en lote, listar vencidos con `getPendingDueBy`, listar **todos** los pendientes con `getAllPending`, actualizar estado) y la implementación `SqliteMealGlucoseReminderRepository`.
- `lib/services/notification_service.dart`: interfaz `NotificationService` (`initialize`, `requestPermission`, `schedule`, `cancel`, `onNotificationTapped`), independiente de plataforma, para las notificaciones push locales de los recordatorios de glucosa post-comida (Fase B).
- `lib/services/android_notification_service.dart`: implementación `AndroidNotificationService` de `NotificationService` sobre `flutter_local_notifications`/`timezone`/`flutter_timezone`; programa cada notificación con precisión exacta (`AndroidScheduleMode.exactAllowWhileIdle`) y, si el permiso de alarma exacta no está concedido, hace *fallback* automático a precisión inexacta en vez de perder el recordatorio.
- `lib/services/darwin_notification_service.dart`: implementación `DarwinNotificationService` de `NotificationService` para iOS/macOS sobre `flutter_local_notifications`/`timezone`/`flutter_timezone`; solicita el permiso (`alert`/`badge`/`sound`) desde `requestPermission` en vez de durante `initialize`, y no necesita el *fallback* de precisión que sí requiere Android, ya que iOS no tiene un permiso equivalente a `SCHEDULE_EXACT_ALARM`.
- `lib/services/meal_glucose_reminder_coordinator.dart`: `MealGlucoseReminderCoordinator`, lógica pura de aplicación que genera los dos recordatorios por comida (programando su notificación push si hay un `NotificationService` configurado — Fase B), revisa los vencidos intentando auto-resolución vía CGM, expone `dismiss`/`resolveManually` para la acción del usuario (cancelando la notificación correspondiente) y `rescheduleAllPending` como red de seguridad al iniciar la app.
- `lib/services/medication_repository.dart`: interfaz `MedicationRepository` (listado, agregar, limpiar tomas; listar catálogo de medicamentos) y la implementación `SqliteMedicationRepository`.
- `lib/services/biometric_repository.dart`: interfaz `BiometricRepository` (última medición, listado, agregar, limpiar) y la implementación `SqliteBiometricRepository`.
- `lib/services/user_profile_repository.dart`: interfaz `UserProfileRepository` (perfil único, sin listado ni multiusuario: `getProfile`, `saveProfile`, `clearProfile`) y la implementación `SqliteUserProfileRepository`.
- `lib/services/auth_repository.dart`: interfaz `AuthRepository` (estado de sesión, registro/inicio de sesión con correo, inicio de sesión con Google, recuperar contraseña, cerrar sesión) y `AuthException` (mensajes de error en español).
- `lib/services/firebase_auth_repository.dart`: implementación `FirebaseAuthRepository` sobre `firebase_auth` y `google_sign_in`.
- `lib/services/backup_repository.dart`: interfaz `BackupRepository` (`backup`, `restore`, `getLastBackupTime`) y `BackupException`. `restore` reemplaza los datos locales (no los fusiona), ya documentado en su propio docstring.
- `lib/services/firestore_backup_repository.dart`: implementación `FirestoreBackupRepository` sobre `cloud_firestore`, que serializa las cuatro colecciones de datos de salud a un único documento `backups/{uid}`.
- `lib/screens/home_screen.dart`: carga la última medición desde el repositorio al iniciar, presenta la tarjeta de glucosa y los accesos a los módulos, guarda cada nueva medición recibida, navega a `HistoryScreen`, `MealScreen`, `MedicationScreen`, `BiometricScreen` y (desde el ícono "Cuenta" del `AppBar`) a `AuthScreen`; al iniciar también revisa recordatorios post-comida vencidos vía `MealGlucoseReminderCoordinator` y muestra un diálogo (registrar ahora / descartar) por cada uno que no se resolvió automáticamente. Si se inyecta un `NotificationService` (Fase B), al iniciar también solicita el permiso de notificaciones, reprograma los recordatorios pendientes (`rescheduleAllPending`) y vuelve a revisarlos cada vez que el usuario toca una notificación mostrada por el sistema.
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
- `flutter test`: **All tests passed!** (122/122).
- `flutter build apk --debug`: compila correctamente (verificado tras
  integrar `firebase_auth`/`google_sign_in`/`cloud_firestore` y, más
  recientemente, `flutter_local_notifications`/`timezone`/
  `flutter_timezone`).
- `flutter build apk --release`: compila correctamente (verificado
  2026-10-21; genera
  `build/app/outputs/flutter-apk/app-release.apk`, ≈55 MB, firmado con
  las claves de **debug** —ver `TODO` en
  `android/app/build.gradle.kts`—, por lo que sirve para instalar en
  dispositivos propios pero no para publicar en Google Play sin
  configurar antes un keystore de release propio).

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
- `test/services/app_database_test.dart` prueba específicamente la
  migración de esquema (versión 7 a 8) que agrega la columna `uuid` a
  las cuatro tablas de datos de salud, usando un archivo temporal real
  (no en memoria) para poder cerrar y reabrir la base de datos
  simulando una instalación existente.
- `test/services/meal_glucose_reminder_coordinator_test.dart` prueba
  `MealGlucoseReminderCoordinator` (lógica pura de aplicación) con un
  `_FakeReminderRepository` en memoria, sin tocar SQLite, incluyendo un
  `_FakeNotificationService` (Fase B) para verificar que se programa y
  cancela la notificación de cada recordatorio en el momento correcto,
  y que `rescheduleAllPending` reprograma solo los que siguen
  pendientes.
- `test/widget_test.dart` incluye, en el grupo `NotificationService
  (Fase B)`, un `_FakeNotificationService` para verificar que
  `HomeScreen` solicita el permiso de notificaciones y reprograma los
  recordatorios pendientes al abrir, y que tocar una notificación
  dispara una nueva revisión de recordatorios. Estas pruebas cubren
  `MealGlucoseReminderCoordinator`/`HomeScreen` contra la interfaz
  `NotificationService`, por lo que validan por igual el uso de
  `AndroidNotificationService` y `DarwinNotificationService`: ninguna
  de las dos implementaciones concretas tiene pruebas unitarias propias
  (requerirían un entorno Android/iOS real para el plugin nativo
  `flutter_local_notifications`), ver punto 1 de "Próximos pasos".
- `test/models/user_profile_test.dart` prueba `UserProfile.bmiFor` y
  `bmiCategoryFor` como funciones puras, sin dependencias de
  plataforma.

## Próximos pasos recomendados

> **Nota (2026-10-22):** la versión 1.0 se publica solo en Google
> Play/Android (ver "Decisión: alcance de la versión 1.0 limitado a
> Android" en `PROJECT_CONTEXT.md`). Los puntos 1 y 4 (validación/
> verificación en iOS/macOS con Xcode) quedan **pospuestos** para una
> versión futura; los puntos 2 y 5 (validación interactiva en Android
> real) ya se completaron el 2026-10-22, ver "Validación manual en
> dispositivo Android físico real" en `PROJECT_CONTEXT.md`.

1. ⏸️ (Pospuesto) Validar en una Mac con Xcode el flujo completo de
   notificaciones en iOS (`DarwinNotificationService`): concesión/
   denegación del permiso de notificaciones, entrega con la app
   cerrada o en background, comportamiento al reiniciar el
   dispositivo y toque de la notificación. La validación actual en
   este entorno Windows solo cubrió `flutter analyze` y `flutter
   test` (no requieren compilar para iOS); no fue posible ejecutar
   `flutter build ios` ni abrir el proyecto en Xcode para confirmar
   que `ios/Runner/AppDelegate.swift` (registro de
   `UNUserNotificationCenterDelegate` y
   `FlutterLocalNotificationsPlugin.setPluginRegistrantCallback`)
   compila sin errores.
2. ✅ (2026-10-22) Validado en un dispositivo Android real (Honor
   `ELI-NX9`) el flujo completo de notificaciones: alarmas reales
   (`dumpsys alarm`, 60/90 min), notificación disparada adelantando
   la hora del dispositivo, e ícono renderizado correctamente
   (`dumpsys notification`, verificación visual).
3. Evaluar si se necesita sincronización automática/en tiempo real
   (más allá del respaldo/restauración manual ya implementado). Ya se
   agregó la clave estable (`uuid`) y la fusión manual
   ("Fusionar desde la nube", ver más abajo); queda pendiente decidir
   si además se necesita que ocurra automáticamente/en tiempo real,
   sin que el usuario tenga que abrir la pantalla de Cuenta y
   presionar un botón.
4. ⏸️ (Pospuesto) Verificar en una Mac con Xcode que
   `ios/Runner/GoogleService-Info.plist` (generado vía
   `firebase apps:sdkconfig` y enlazado manualmente al proyecto Xcode,
   ya que `flutterfire configure` no pudo completarlo desde Windows)
   compila y se incluye correctamente al construir para iOS, y que el
   inicio de sesión con Google, el respaldo/restauración y la
   importación desde Apple Health funcionan en esa plataforma.
5. ✅ (2026-10-22) Probados en un dispositivo Android real el inicio
   de sesión con Google (contra Firebase Auth de producción), la
   sincronización automática a Firestore (confirmada en la consola de
   Firebase) y el botón "Importar desde sensor" (Health Connect, con
   el resultado esperado de "permiso denegado" en ese dispositivo).

## Política de privacidad

Disponible en [`PRIVACY_POLICY.md`](PRIVACY_POLICY.md) y publicada
públicamente en <https://seguimiento-glucosa.web.app/privacy-policy/>
(exigido por Play Store/App Store), también accesible desde la
pantalla **Cuenta** de la app. Resume qué datos se recopilan, dónde se
almacenan (SQLite local vs. Firestore opcional), qué permisos de
salud se solicitan y por qué, y cómo ejercer tus derechos sobre tus
datos. La pantalla **Cuenta** también permite eliminar
permanentemente la cuenta de Firebase y todos sus datos en la nube;
en móvil, el mismo diálogo permite borrar además el historial, perfil
y recordatorios locales del dispositivo.

## Licencia

Software propietario. Copyright (c) 2026 OGB. Todos los derechos
reservados. Ver el archivo [`LICENSE`](LICENSE) para el texto
completo; queda prohibida la copia, modificación o redistribución del
código sin autorización previa y por escrito del titular.

