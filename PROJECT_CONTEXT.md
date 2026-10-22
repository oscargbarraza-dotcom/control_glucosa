# PROJECT_CONTEXT.md

# Nombre del proyecto

## Nombre actual de la aplicación

**Seguimiento Glucosa**

Nombre técnico actual del proyecto Flutter:

`seguimiento_glucosa`

## Descripción breve

Aplicación móvil orientada al seguimiento personal de glucosa. Permite registrar mediciones de glucosa junto con contexto adicional como momento del día, comentarios y fecha/hora automática.

El proyecto se encuentra en etapa inicial de desarrollo (MVP/V1), con la interfaz principal creada y el primer flujo de registro de glucosa implementado.

---

# Objetivo de la aplicación

## Problema que resuelve

La aplicación busca centralizar el seguimiento de mediciones de glucosa, permitiendo asociar valores medidos con información contextual:

* Momento de medición.
* Fecha y hora real del registro.
* Comentarios adicionales.
* Futuramente relación con comidas, medicamentos, actividad física y otros datos biométricos.

El objetivo es facilitar la identificación de patrones y evolución de glucosa mediante historial y análisis posteriores.

## Usuarios objetivo

Pendiente de confirmar formalmente.

El diseño actual está orientado principalmente a:

* Personas que realizan seguimiento frecuente de glucosa.
* Usuarios que desean registrar mediciones y contexto asociado.
* Personas que utilizan medición continua o controles manuales de glucosa.

## Flujo principal de uso

Flujo implementado actualmente:

1. Abrir aplicación.
2. Visualizar pantalla principal.
3. Seleccionar tarjeta "Glucosa actual".
4. Ingresar valor de glucosa.
5. Seleccionar momento de medición.
6. Agregar comentario opcional.
7. Guardar medición.

Flujo futuro esperado:

1. Guardar medición persistente.
2. Visualizar último valor registrado.
3. Consultar historial.
4. Generar gráficos y análisis.
5. Relacionar datos con comidas, medicamentos y otros eventos.

---

# Estado actual del desarrollo

## Funcionalidades implementadas

### Pantalla principal

Implementada:

* Título "Seguimiento Glucosa".
* Tarjeta visual de glucosa actual.
* Menús principales:

  * Comida.
  * Medicamentos.
  * Biometría.
  * Historial.

La tarjeta de glucosa funciona como botón y navega hacia la pantalla de registro.
El menú "Comida" navega hacia `MealScreen` (ver sección "Registro de
comidas"), el menú "Medicamentos" navega hacia `MedicationScreen` (ver
sección "Registro de medicamentos") y el menú "Biometría" navega hacia
`BiometricScreen` (ver sección "Registro de biometría").

---

### Registro de glucosa

Implementado:

* Campo numérico para ingreso de glucosa.
* Selector de momento de medición.
* Comentario libre.
* Generación automática de fecha/hora.
* Botón Guardar.
* Navegación de regreso.

Ejemplo de registro generado:

```text
Glucosa: 176
Momento: Antes cena
Comentario: prueba
Fecha: 2026-08-07 21:59:54
```

---

## Pantallas creadas

Actualmente existen:

### HomeScreen

Responsable de:

* Pantalla inicial.
* Navegación hacia módulos (Glucosa, Comida, Medicamentos, Biometría,
  Historial).
* Carga y visualización del último valor de glucosa.

### GlucoseScreen

Responsable de:

* Captura de medición.
* Selección de contexto.
* Preparación de datos de medición.

### MealScreen

Responsable de:

* Registro de una nueva comida (tipo, alimentos con cantidad, comentario).
* Historial de comidas ya guardadas.
* Ambas vistas conviven en pestañas propias (`Registrar`/`Historial`)
  dentro de la misma pantalla (ver sección "Registro de comidas").

### MedicationScreen

Responsable de:

* Registro de una nueva toma (uno o más medicamentos, cada uno con
  cantidad numérica y unidad, comentario).
* Historial de tomas ya guardadas.
* Ambas vistas conviven en pestañas propias (`Registrar`/`Historial`)
  dentro de la misma pantalla, igual patrón que `MealScreen` (ver sección
  "Registro de medicamentos").

### BiometricScreen

Responsable de:

* Registro de un nuevo peso corporal (valor numérico en kg, comentario).
* Historial de pesos ya guardados.
* Ambas vistas conviven en pestañas propias (`Registrar`/`Historial`)
  dentro de la misma pantalla, igual patrón que `MealScreen`/
  `MedicationScreen` (ver sección "Registro de biometría").

---

## Componentes terminados

* Estructura base Flutter.
* Navegación entre pantallas.
* Diseño inicial Material.
* Tarjeta de glucosa.
* Formulario de medición.
* Selector visual de momentos con iconos.

---

## Funcionalidades implementadas (continuación)

### Persistencia de datos

Implementado.

Se agregaron las dependencias `sqflite: ^2.4.4+2`, `path: ^1.9.1` e
`intl: ^0.20.3`, reemplazando la implementación previa basada en
`shared_preferences` (que solo guardaba "el último valor"). Se actualizó
`lib/services/glucose_repository.dart` con:

* `GlucoseRepository`: interfaz abstracta ampliada (`getLastMeasurement`,
  `getAllMeasurements`, `addMeasurement`, `clearMeasurements`) que
  desacopla las pantallas del mecanismo de almacenamiento concreto y ya
  soporta el historial completo, no solo la última medición.
* `SqliteGlucoseRepository`: implementación basada en `sqflite`, con una
  tabla `glucose_measurements` (`id` autoincremental, `value`, `moment`,
  `measured_at`, `comment`). Permite inyectar `factory`, `databasePath` y
  `singleInstance` para pruebas (vía `sqflite_common_ffi`), sin afectar el
  uso por defecto en Android/iOS.

`GlucoseMeasurement` ahora incluye un campo `id` opcional (`null` para
mediciones aún no persistidas), asignado por el repositorio al guardarlas.

`HomeScreen` recibe opcionalmente un `GlucoseRepository` por constructor
(para poder inyectar un fake en tests); si no se provee, usa
`SqliteGlucoseRepository` de forma perezosa. Al iniciar, `HomeScreen` carga
la última medición guardada (`initState` → `_loadLastMeasurement`) y, al
guardar una nueva medición desde `GlucoseScreen`, la persiste (ahora como
una fila nueva del historial, vía `addMeasurement`) antes de actualizar la
tarjeta.

No existe todavía:

* Firebase o sincronización remota (evaluado y descartado por ahora; el
  alcance actual se mantiene 100% local).

---

### Actualización de pantalla principal

Implementado.

`HomeScreen` es un `StatefulWidget` que:

1. Al iniciar, carga la última medición persistida (mostrando un
   `CircularProgressIndicator` pequeño mientras `_isLoading == true`).
2. Al volver de `GlucoseScreen` con un resultado, guarda la medición en el
   repositorio y actualiza la tarjeta mostrando:

```text
176 mg/dL
Antes cena
```

Si no hay ninguna medición guardada, se muestra `-- mg/dL`. El valor ahora
sobrevive a reinicios de la app gracias a la persistencia en
`shared_preferences`.

---

### Historial

Implementado.

Se creó `lib/screens/history_screen.dart`: una pantalla que carga
`GlucoseRepository.getAllMeasurements()` una sola vez (ordenado de la
medición más reciente a la más antigua) y lo muestra en dos pestañas
(`DefaultTabController` + `TabBar`/`TabBarView`):

* **Lista**: comportamiento original, una `ListView` con el valor,
  momento, fecha/hora formateada (`intl`) y comentario de cada medición
  (`_MeasurementTile`).
* **Gráfico**: evolución de los valores en el tiempo, usando
  `GlucoseLineChart` (ver sección "Gráficos"). Con menos de 2 mediciones
  muestra un mensaje explicativo en lugar del gráfico.

Se cubre con un estado de carga y un mensaje cuando no hay datos.

`HomeScreen` conecta el botón "Historial" (antes decorativo) a esta
pantalla mediante `_openHistoryScreen`, reutilizando el mismo
`GlucoseRepository` ya inyectado/instanciado.

Decisión registrada sobre el mecanismo de persistencia: se evaluó SQLite
(`sqflite`) contra una lista JSON en `shared_preferences`, y se eligió
SQLite por: (1) evitar una futura migración duplicada cuando se implementen
los módulos de Comida/Medicamentos/Biometría (que ya se prevén
relacionados entre sí), (2) mejor rendimiento a medida que crece el
historial (no se reserializa toda la lista en cada lectura/escritura), y
(3) soporte nativo de consultas SQL para los futuros gráficos y
estadísticas. Se descartó explícitamente, en esta decisión, usar una nube
(Firebase/Firestore) como almacenamiento principal: el alcance se mantiene
100% local por ahora.

---

### Gráficos

Implementado.

`HistoryScreen` ahora tiene dos pestañas (`TabBar`/`TabBarView` dentro de un
`DefaultTabController`): **Lista** (comportamiento anterior) y **Gráfico**.
La pestaña Gráfico usa el widget reutilizable
`lib/widgets/glucose_line_chart.dart` (`GlucoseLineChart`), basado en
`fl_chart` (`LineChart`), para dibujar la evolución cronológica de los
valores de glucosa (mg/dL) en el eje Y contra la fecha/hora en el eje X.

Incluye:

* Línea curva con el valor de cada medición, en orden cronológico
  (`measuredAt` ascendente, independientemente del orden recibido).
* Dos líneas de referencia horizontales punteadas en 70 y 180 mg/dL (rango
  considerado normal), vía `ExtraLinesData`.
* Tooltip táctil (`LineTouchTooltipData`) que muestra el valor y la
  fecha/hora exacta de la medición tocada.
* Etiquetas del eje X con la fecha corta (`dd/MM`), con un intervalo que se
  ajusta automáticamente para evitar solapamientos cuando hay muchas
  mediciones.
* Mensaje alternativo ("Registra al menos dos mediciones...") cuando el
  historial tiene menos de 2 mediciones, ya que una sola no permite trazar
  una línea.

---

### Registro de comidas

Implementado.

Se creó el módulo de Comidas, siguiendo el modelo relacional previsto
(`COMIDA` + `ALIMENTO` + `COMIDA_ALIMENTO`):

* `lib/models/food.dart`: modelo `Food` (id, name) — un alimento del
  catálogo reutilizable.
* `lib/models/meal.dart`: modelo `Meal` (id, type, eatenAt, comment, items)
  y `MealFoodItem` (id, food, quantity); enum `MealType` con 5 categorías
  (Desayuno, Almuerzo, Once/Merienda, Cena, Otro/Snack).
* `lib/services/meal_repository.dart`: interfaz `MealRepository`
  (`getAllMeals`, `addMeal`, `clearMeals`, `getAllFoods`) + implementación
  `SqliteMealRepository`, sobre tres tablas: `meals`, `foods` y
  `meal_food_items` (tabla intermedia).
* `lib/services/app_database.dart`: gestor único de la base de datos
  SQLite compartida (`AppDatabase`), con migraciones versionadas
  (`onCreate`/`onUpgrade`), usado tanto por `SqliteGlucoseRepository` como
  por `SqliteMealRepository` para evitar abrir conexiones duplicadas.
* `lib/screens/meal_screen.dart` (`MealScreen`): pantalla con pestañas
  **Registrar** (formulario: tipo de comida, alimentos con cantidad en
  texto libre, comentario opcional) e **Historial** (lista de comidas
  guardadas, de la más reciente a la más antigua). Tras guardar, cambia
  automáticamente a la pestaña Historial y muestra una confirmación
  (`SnackBar`).

Decisiones de diseño registradas:

* El catálogo de `Food` solo tiene `name` por ahora (sin información
  nutricional); se prevé agregar macros en una iteración futura.
* La cantidad de cada alimento en una comida (`MealFoodItem.quantity`) es
  texto libre (ej. "1 taza", "2 rebanadas"), priorizando flexibilidad del
  usuario sobre un valor numérico estandarizado (gramos).
* `MealScreen` es una pantalla autocontenida con sus propias pestañas
  Registrar/Historial, en lugar de integrarse como una pestaña adicional
  dentro de `HistoryScreen` (de glucosa) o de depender de ella: cada
  módulo de dominio (Comida, y luego Medicamentos/Biometría) queda
  aislado y testeable por separado, evitando que `HistoryScreen` termine
  mezclando dominios no relacionados en una jerarquía de pestañas
  anidadas.
* El catálogo de alimentos (`foods`) se reutiliza por nombre (comparación
  tras `trim()`): si una comida reutiliza un alimento ya registrado, no se
  duplica la fila, se reutiliza su `id`.

---

### Registro de medicamentos

Implementado.

Se creó el módulo de Medicamentos, siguiendo el mismo modelo relacional
que Comidas (`MEDICATION` + `MEDICATION_INTAKE` + `MEDICATION_INTAKE_ITEM`):

* `lib/models/medication.dart`: enum `DoseUnit` (`milligram`,
  `milliliter`, `tablet`, `unit`, `drop`, `other`, con extensión `label`)
  y modelo `Medication` (id, name, defaultUnit) — un medicamento del
  catálogo reutilizable.
* `lib/models/medication_intake.dart`: modelo `MedicationIntake` (id,
  takenAt, comment, items) y `MedicationIntakeItem` (id, medication,
  quantity numérica, unit, customUnitLabel opcional, getter
  `effectiveUnitLabel`).
* `lib/services/medication_repository.dart`: interfaz
  `MedicationRepository` (`getAllIntakes`, `addIntake`, `clearIntakes`,
  `getAllMedications`) + implementación `SqliteMedicationRepository`,
  sobre tres tablas: `medication_intakes`, `medications` y
  `medication_intake_items` (tabla intermedia).
* `lib/services/app_database.dart`: las tres tablas anteriores se
  agregaron a la misma `AppDatabase` compartida (versión de esquema 3),
  reutilizada también por `SqliteGlucoseRepository` y
  `SqliteMealRepository`.
* `lib/screens/medication_screen.dart` (`MedicationScreen`): pantalla con
  pestañas **Registrar** (formulario: medicamento, cantidad numérica,
  selector de unidad —con campo de texto adicional cuando la unidad es
  "Otro"—, comentario opcional) e **Historial** (lista de tomas
  guardadas, de la más reciente a la más antigua). Tras guardar, cambia
  automáticamente a la pestaña Historial y muestra una confirmación
  (`SnackBar`).

Decisiones de diseño registradas:

* Se eligió el modelo relacional completo (igual que Comidas) en lugar de
  un registro simple de un medicamento por toma, porque una toma real
  puede incluir varios medicamentos a la vez (ej. Metformina + Insulina a
  las 8am).
* La dosis es estructurada (cantidad numérica + unidad de un selector),
  no texto libre, a diferencia de la cantidad de alimentos en Comidas:
  esto permite validar el valor numérico y mantener consistencia de
  unidades entre tomas del mismo medicamento.
* El catálogo de `Medication` tiene `name` + `defaultUnit` (a diferencia
  de `Food`, que solo tiene `name`), para pre-rellenar el selector de
  unidad al elegir un medicamento ya conocido en una iteración futura de
  UX (actualmente el formulario no autocompleta `defaultUnit` al escribir
  el nombre; eso queda como mejora posterior, no bloqueante).
* `DoseUnit.other` es el único punto donde se admite texto libre para la
  unidad (`customUnitLabel`), como comodín para unidades no listadas
  (ej. "parche", "sobre").
* `MedicationScreen` es autocontenida con pestañas propias
  Registrar/Historial, mismo patrón que `MealScreen`, para mantener cada
  módulo de dominio aislado y testeable por separado.
* El catálogo de medicamentos (`medications`) se reutiliza por nombre
  (comparación tras `trim()`): si una toma reutiliza un medicamento ya
  registrado, no se duplica la fila, se reutiliza su `id`.

---

### Registro de biometría

Implementado (peso corporal obligatorio; presión arterial, frecuencia
cardíaca e IMC opcionales — el IMC se calcula a partir del perfil de
usuario).

Se creó el módulo de Biometría, siguiendo el modelo simple de
`GlucoseMeasurement` (no el modelo relacional catálogo+items de
Comidas/Medicamentos), porque no hay múltiples valores por registro:

* `lib/models/biometric_measurement.dart`: modelo inmutable
  `BiometricMeasurement` (`id`, `weightKg`, `systolicPressure`,
  `diastolicPressure`, `heartRateBpm`, `measuredAt`, `comment`), con
  `copyWith`/`==`/`hashCode` siguiendo el mismo patrón que
  `GlucoseMeasurement`. `weightKg` es obligatorio; `systolicPressure`,
  `diastolicPressure` y `heartRateBpm` son opcionales (`int?`), y
  `hasBloodPressure` indica si la presión se registró en esa medición.
* `lib/services/biometric_repository.dart`: interfaz
  `BiometricRepository` (`getLastMeasurement`, `getAllMeasurements`,
  `addMeasurement`, `clearMeasurements`) e implementación
  `SqliteBiometricRepository` (constructores normal y `.withDatabase`),
  sobre una única tabla `biometric_measurements`.
* `lib/services/app_database.dart`: la tabla anterior se agregó a la
  misma `AppDatabase` compartida (versión de esquema 4), reutilizada
  también por el resto de repositorios. En la versión de esquema 5 se
  agregaron las columnas `systolic_pressure`, `diastolic_pressure` y
  `heart_rate_bpm` (todas `INTEGER` nullable) mediante `ALTER TABLE`. En
  la versión de esquema 6 se agregó la tabla `user_profile` (perfil de
  usuario, ver más abajo).
* `lib/models/user_profile.dart`: modelo inmutable `UserProfile`
  (`heightCm` obligatorio; `birthDate`, `biologicalSex`, `displayName`
  opcionales), el enum `BiologicalSex` (`female`/`male`/
  `preferNotToSay`) con su extensión `label`, el método
  `UserProfile.bmiFor(weightKg)` que calcula el IMC
  (`peso / altura_m²`), el enum `BmiCategory`
  (`underweight`/`normal`/`overweight`/`obese`) con su extensión
  `label`, y la función `bmiCategoryFor(bmi)` que clasifica un IMC ya
  calculado según los rangos estándar de la OMS para adultos (sin
  diferenciar por edad/sexo).
* `lib/services/user_profile_repository.dart`: interfaz
  `UserProfileRepository` (`getProfile`, `saveProfile`, `clearProfile`)
  e implementación `SqliteUserProfileRepository` (constructores normal y
  `.withDatabase`), sobre la tabla `user_profile`. Al no haber soporte
  multiusuario, usa el patrón "singleton row" (`id = 1` fijo,
  `saveProfile` con `ConflictAlgorithm.replace`) en lugar de un
  `AUTOINCREMENT` como el resto de tablas.
* `lib/screens/biometric_screen.dart` (`BiometricScreen`): pantalla con
  pestañas **Registrar** (peso en kg obligatorio; presión sistólica y
  diastólica opcionales, completadas juntas o ninguna; frecuencia
  cardíaca opcional; comentario opcional), **Perfil** (altura en cm
  obligatoria; nombre a mostrar, sexo biológico y fecha de nacimiento —
  vía `showDatePicker` — opcionales) e **Historial** (lista de
  mediciones guardadas, de la más reciente a la más antigua, mostrando
  el IMC — calculado combinando cada peso con la altura del perfil
  vigente, si existe —, presión y frecuencia cardíaca cuando existen).
  Tras guardar un peso, cambia automáticamente a la pestaña Historial y
  muestra una confirmación (`SnackBar`), mismo patrón que
  `MedicationScreen`; guardar el perfil muestra su propia confirmación
  sin cambiar de pestaña.
* `lib/screens/home_screen.dart`: nuevo parámetro `profileRepository`
  (mismo patrón que `biometricRepository`: si es `null`, usa
  `SqliteUserProfileRepository` sobre la base de datos compartida), que
  se pasa a `BiometricScreen` al navegar a ella.

Decisiones de diseño registradas:

* Se amplió el alcance original (solo peso) con presión arterial y
  frecuencia cardíaca, ambas opcionales dentro del mismo registro de
  peso, en lugar de crear un tipo de medición separado: evita duplicar
  el concepto de "registro" y mantiene la migración de esquema simple
  (`ALTER TABLE ADD COLUMN`, sin tocar restricciones existentes).
* El IMC se calcula en tiempo de lectura (`UserProfile.bmiFor`) a partir
  del peso de cada `BiometricMeasurement` y la altura del perfil
  vigente, en lugar de guardarse como columna en
  `biometric_measurements`: evita que el IMC quede desactualizado si el
  usuario corrige su altura más adelante, y evita recalcular/migrar el
  historial existente al hacerlo.
* El perfil de usuario (`UserProfile`) es un registro único local
  (patrón "singleton row" en SQLite), no una entidad con historial como
  `BiometricMeasurement`: no tiene sentido guardar "versiones" de la
  altura de una persona de la misma forma que un historial de pesos.
* Se amplió el perfil más allá de la altura mínima necesaria para el
  IMC (roadmap: "altura, entre otros datos"), agregando fecha de
  nacimiento, sexo biológico y nombre a mostrar, como base para
  funcionalidades futuras (clasificación de IMC por edad/sexo, saludo
  personalizado) sin requerir otra migración de esquema a corto plazo.
* La validación de presión arterial exige que sistólica y diastólica se
  completen juntas (ambas vacías, o ambas con valor): no tiene sentido
  guardar solo una de las dos.
* Se usó el modelo simple (un valor de peso por registro, análogo a
  `GlucoseMeasurement`) en lugar del modelo relacional catálogo+items de
  Comidas/Medicamentos, porque un registro de peso no agrupa múltiples
  mediciones a la vez.
* `BiometricScreen` es autocontenida con pestañas propias
  Registrar/Perfil/Historial, mismo patrón que
  `MealScreen`/`MedicationScreen`, para mantener cada módulo de dominio
  aislado y testeable por separado.

---

### Alertas

Parcialmente implementado.

* Recordatorios de medición post-comida (60 y 90 minutos tras guardar
  una comida): **Fase A hecha** — lógica, persistencia y diálogo
  in-app (`MealGlucoseReminder`/`MealGlucoseReminderRepository`/
  `MealGlucoseReminderCoordinator`). **Fase B hecha para Android e
  iOS** — notificaciones push locales reales del sistema
  (`NotificationService`/`AndroidNotificationService`/
  `DarwinNotificationService`, vía `flutter_local_notifications`),
  que avisan aunque la app esté cerrada o en background, con permiso
  solicitado al abrir la app, reconciliación
  (`rescheduleAllPending`) y revisión al tocar una notificación.
  `main.dart` elige la implementación según `Platform.isAndroid`/
  `Platform.isIOS`. Ver roadmap punto 17 y la entrada correspondiente
  en Historial de cambios.

Pendiente:

* Alertas por valores altos/bajos de glucosa.

---

## Errores conocidos o pendientes

No existen errores críticos actualmente.

Problemas menores observados:

* Mensajes Android relacionados con `InteractionJankMonitor` e IME del emulador. No afectan funcionamiento.
* Hubo problemas temporales de caché/build solucionados mediante:

  * `flutter clean`
  * recompilación completa.

---

# Stack tecnológico

## Lenguaje

Dart.

## Framework/UI

Flutter.

No se utiliza Jetpack Compose ni XML.

## Plataforma

Android.

## Versión Flutter conocida

Flutter:

```text
3.44.8 stable
```

Dart:

```text
3.12.2
```

## Android

Emulador utilizado:

```text
Pixel 7
Android 17
API 37
```

Versión exacta de Kotlin pendiente de confirmar.

---

## Arquitectura actual

Arquitectura Flutter simple basada en separación por pantallas, con un
patrón Repository para la persistencia.

Actualmente:

* Widgets de pantalla (`lib/screens/`).
* Modelos inmutables (`lib/models/`).
* Repositorios (`lib/services/`), patrón Repository:
  * `glucose_repository.dart`: interfaz `GlucoseRepository` +
    implementación `SqliteGlucoseRepository`.
  * `meal_repository.dart`: interfaz `MealRepository` + implementación
    `SqliteMealRepository`.
  * `app_database.dart`: gestor único (`AppDatabase`) de la conexión
    SQLite compartida por ambos repositorios, con migraciones
    versionadas. Cada repositorio puede instanciar su propia
    `AppDatabase` (uso por defecto) o reutilizar una ya creada
    (`SqliteGlucoseRepository.withDatabase`/
    `SqliteMealRepository.withDatabase`/
    `SqliteMedicationRepository.withDatabase`/
    `SqliteBiometricRepository.withDatabase`), como hace `HomeScreen`
    para evitar abrir dos conexiones.
* Navegación directa (`Navigator.push`/`pop`).
* Estado local mediante `StatefulWidget`.

Arquitectura futura pendiente de definir:

* IMC en el módulo de Biometría, una vez exista un perfil de usuario con
  altura (presión arterial y frecuencia cardíaca ya están implementadas).
* Manejo de estado global (si la complejidad lo justifica).

---

## Librerías principales

Actualmente:

```dart
import 'package:flutter/material.dart';
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';
import 'package:intl/intl.dart';
import 'package:fl_chart/fl_chart.dart';
```

Librerías externas confirmadas: `sqflite` (persistencia del historial de
mediciones en SQLite), `path` (construcción de la ruta del archivo de base
de datos), `intl` (formateo de fechas en `HistoryScreen`) y `fl_chart`
(gráfico de evolución de glucosa en la pestaña "Gráfico" de
`HistoryScreen`; librería 100% Dart, sin dependencias nativas). En tests,
`sqflite_common_ffi` permite ejercitar `SqliteGlucoseRepository` sin el
plugin nativo.

---

## Herramientas utilizadas

* Flutter SDK.
* Android Studio.
* Android Emulator.
* Visual Studio Code.
* Terminal PowerShell.

---

## Servicios externos

Sin integraciones externas. El almacenamiento es 100% local (SQLite vía
`sqflite`); se evaluó y descartó Firebase/nube como almacenamiento
principal (ver "Formato de almacenamiento").

No existe todavía integración con:

* Firebase.
* APIs.
* Bluetooth.
* Sensores.
* Dispositivos CGM.

---

# Arquitectura del proyecto

## Estructura actual

```text
seguimiento_glucosa
│
├── android
├── ios
├── web
├── windows
│
└── lib
    │
    ├── main.dart
    │
    ├── models
    │   ├── glucose_measurement.dart
    │   ├── food.dart
    │   └── meal.dart
    │
    ├── services
    │   ├── app_database.dart
    │   ├── glucose_repository.dart
    │   └── meal_repository.dart
    │
    ├── screens
    │   ├── home_screen.dart
    │   ├── glucose_screen.dart
    │   ├── history_screen.dart
    │   └── meal_screen.dart
    │
    └── widgets
        └── glucose_line_chart.dart
```

---

## Responsabilidad de carpetas

### lib/

Código principal Flutter.

### models/

Modelos de datos inmutables: `GlucoseMeasurement`/`GlucoseMoment`
(glucosa) y `Food`/`Meal`/`MealFoodItem`/`MealType` (comidas).

### services/

Capa de persistencia (patrón Repository): `GlucoseRepository` +
`SqliteGlucoseRepository`, `MealRepository` + `SqliteMealRepository`, y
`AppDatabase` como gestor único de la conexión SQLite compartida
(creación y migración de esquema para todas las tablas).

### screens/

Pantallas completas de la aplicación.

### widgets/

Componentes reutilizables.

Contiene `glucose_line_chart.dart` (`GlucoseLineChart`), el gráfico de
evolución de glucosa basado en `fl_chart` usado por `HistoryScreen`.

---

## Flujo de datos actual

Actualmente:

```text
Usuario
  |
  v
GlucoseScreen
  |
  ├── valor glucosa
  ├── momento
  ├── comentario
  └── fecha/hora automática
  |
  v
print() consola
```

---

# Modelo de datos

## Modelo conceptual definido para V1

El modelo conceptual inicial considerado fue:

* USUARIO — pendiente.
* COMIDA — ✅ implementada (tabla `meals`).
* ALIMENTO — ✅ implementada (tabla `foods`).
* COMIDA_ALIMENTO — ✅ implementada (tabla `meal_food_items`).
* SEGUIMIENTO — pendiente.
* SEGUIMIENTO_MEDICION — pendiente.
* MEDICION_GLUCOSA — ✅ implementada (tabla `glucose_measurements`).
* MEDICAMENTO — ✅ implementada (tabla `medications`).
* MEDICATION_INTAKE (toma de medicamentos) — ✅ implementada (tabla
  `medication_intakes`).
* MEDICATION_INTAKE_ITEM — ✅ implementada (tabla
  `medication_intake_items`).
* BIOMETRIA — ✅ implementada parcialmente (tabla
  `biometric_measurements`: peso corporal obligatorio, presión arterial
  y frecuencia cardíaca opcionales; IMC queda pendiente).
* RECORDATORIO_MEDICION — ✅ implementada, Fase A (tabla
  `meal_glucose_reminders`) y Fase B para Android e iOS
  (notificaciones push locales reales vía
  `flutter_local_notifications`).
* CONTROL — pendiente.

---

## Entidad: Comida y alimentos

Implementado formalmente como tres tablas SQLite relacionadas:

```text
meals

id              INTEGER PRIMARY KEY AUTOINCREMENT
type            TEXT NOT NULL      -- nombre del enum MealType
eaten_at        TEXT NOT NULL      -- fecha/hora en formato ISO 8601
comment         TEXT               -- comentario opcional

foods

id              INTEGER PRIMARY KEY AUTOINCREMENT
name            TEXT NOT NULL UNIQUE

meal_food_items

id              INTEGER PRIMARY KEY AUTOINCREMENT
meal_id         INTEGER NOT NULL REFERENCES meals (id) ON DELETE CASCADE
food_id         INTEGER NOT NULL REFERENCES foods (id)
quantity        TEXT NOT NULL      -- cantidad en texto libre, ej. "1 taza"
```

Estructura conceptual equivalente a `COMIDA` + `ALIMENTO` +
`COMIDA_ALIMENTO` anticipadas en V1. `foods` actúa como catálogo
reutilizable: `SqliteMealRepository` reutiliza la fila existente por
nombre en lugar de duplicarla.

Ejemplo:

```text
tipo: Desayuno
alimentos:
  - Pan (2 rebanadas)
  - Huevo (1 unidad)
comentario: null
fechaHora: 2026-08-19 08:15:00
```

---

## Entidad: Medicamentos y tomas

Implementado formalmente como tres tablas SQLite relacionadas:

```text
medications

id              INTEGER PRIMARY KEY AUTOINCREMENT
name            TEXT NOT NULL UNIQUE
default_unit    TEXT NOT NULL      -- nombre del enum DoseUnit

medication_intakes

id              INTEGER PRIMARY KEY AUTOINCREMENT
taken_at        TEXT NOT NULL      -- fecha/hora en formato ISO 8601
comment         TEXT               -- comentario opcional

medication_intake_items

id                  INTEGER PRIMARY KEY AUTOINCREMENT
intake_id           INTEGER NOT NULL
                      REFERENCES medication_intakes (id) ON DELETE CASCADE
medication_id       INTEGER NOT NULL REFERENCES medications (id)
quantity            REAL NOT NULL      -- cantidad numérica de la dosis
unit                TEXT NOT NULL      -- nombre del enum DoseUnit
custom_unit_label   TEXT               -- solo cuando unit = 'other'
```

Estructura equivalente a `MEDICAMENTO` + `MEDICATION_INTAKE` +
`MEDICATION_INTAKE_ITEM`, siguiendo el mismo patrón que
`meals`/`foods`/`meal_food_items`. `medications` actúa como catálogo
reutilizable: `SqliteMedicationRepository` reutiliza la fila existente
por nombre en lugar de duplicarla.

Ejemplo:

```text
tomadoEn: 2026-08-19 08:00:00
medicamentos:
  - Metformina (500 mg)
  - Insulina (10 Unidades)
comentario: null
```

---

## Entidad actual: Medición de glucosa

Implementado formalmente como tabla SQLite `glucose_measurements`:

```text
glucose_measurements

id              INTEGER PRIMARY KEY AUTOINCREMENT
value           INTEGER NOT NULL   -- valor en mg/dL
moment          TEXT NOT NULL      -- nombre del enum GlucoseMoment
measured_at     TEXT NOT NULL      -- fecha/hora en formato ISO 8601
comment         TEXT               -- comentario opcional
```

Estructura conceptual equivalente (coincide con el modelo `MEDICION_GLUCOSA`
anticipado en V1):

```text
MEDICION_GLUCOSA

id
valor
fechaHora
momento
comentario
```

Ejemplo:

```text
valor:
176

momento:
Antes cena

comentario:
prueba

fechaHora:
2026-08-07 21:59:54
```

---

## Entidad: Recordatorio de medición post-comida

Implementado formalmente como tabla SQLite `meal_glucose_reminders`:

```text
meal_glucose_reminders

id                        INTEGER PRIMARY KEY AUTOINCREMENT
meal_id                   INTEGER NOT NULL
                            REFERENCES meals (id) ON DELETE CASCADE
offset_minutes            INTEGER NOT NULL   -- 60 o 90
due_at                    TEXT NOT NULL      -- fecha/hora en formato ISO 8601
status                    TEXT NOT NULL      -- nombre del enum MealGlucoseReminderStatus
resolved_measurement_id   INTEGER            -- id de glucose_measurements, si ya se resolvió
```

Cada `meals` insertada genera dos filas (60 y 90 minutos) cuando se
inyecta un `MealGlucoseReminderCoordinator` en `MealScreen`. Al
borrar la comida, sus recordatorios se eliminan en cascada.

---

## Formato de almacenamiento

Decidido e implementado: SQLite (`sqflite`), 100% local.

Se evaluaron tres opciones: Firebase/Firestore (nube), SQLite (local
relacional) y una lista JSON en `shared_preferences` (local clave-valor).
Se eligió SQLite por:

* Evitar una migración futura duplicada: los módulos de Comida,
  Medicamentos y Biometría (próximos en el roadmap) ya se prevén
  relacionados entre sí y con `MEDICION_GLUCOSA`; SQLite soporta ese
  modelo relacional de forma nativa, mientras que listas JSON
  independientes requerirían relaciones manuales frágiles.
* Rendimiento: con `shared_preferences` cada lectura/escritura del
  historial requeriría cargar y reserializar toda la lista; SQLite escala
  sin ese problema.
* Soporte de consultas SQL (`WHERE`, `AVG`, `GROUP BY`) para los futuros
  gráficos y estadísticas de evolución.

Se descartó explícitamente Firebase/nube como almacenamiento principal: el
alcance actual del proyecto se mantiene 100% local, sin sincronización
remota.

---

# Funcionalidades de la app

## Registro de glucosa

Implementado parcialmente.

Permite:

* Ingresar valor.
* Seleccionar contexto.
* Agregar comentario.
* Generar fecha/hora automática.

---

## Visualización de datos

Implementado.

La tarjeta principal consume datos reales: carga y muestra la última
medición persistida en SQLite al iniciar la app, y se actualiza al
guardar una nueva medición. El historial completo se visualiza en
`HistoryScreen`, en formato lista o gráfico de evolución.

---

## Gráficos

Implementado (ver sección "Gráficos" bajo "Funcionalidades de la app" más
arriba).

---

## Alertas

Parcialmente implementado: recordatorios de medición post-comida
(Fase A + Fase B para Android e iOS, ver sección "Alertas" bajo
"Pantallas creadas" y roadmap punto 17).

Ideas futuras:

* Alertas por valores altos/bajos de glucosa.

---

## Usuarios/perfiles

Parcialmente implementado.

* Autenticación (Firebase Auth, correo/contraseña y Google): hecha, ver
  roadmap punto 13.
* Perfil de usuario (`UserProfile`: altura, fecha de nacimiento, sexo
  biológico, nombre a mostrar): hecho, ver roadmap punto 16 y módulo de
  Biometría (pestaña Perfil). Es un único perfil local (patrón
  "singleton row" en SQLite), independiente de la cuenta de Firebase
  Auth: no está ligado al `uid` del usuario autenticado.

Pendiente:

* Datos separados por usuario (multiusuario real): el perfil de SQLite
  sigue siendo único por dispositivo, no por cuenta autenticada.

---

## Historial

Implementado.

`HistoryScreen` muestra el historial completo de mediciones guardadas en
SQLite (`GlucoseRepository.getAllMeasurements`), accesible desde el botón
"Historial" de la pantalla principal. El historial de comidas tiene su
propia vista: la pestaña "Historial" de `MealScreen`, accesible desde el
botón "Comida".

---

# Decisiones técnicas tomadas

## Fecha/hora automática

Decisión:

La fecha/hora nunca debe ser ingresada manualmente.

Motivo:

* Evita errores.
* Mantiene trazabilidad.
* Permite análisis temporal.

---

## Momento de medición separado de fecha/hora

Decisión:

El usuario selecciona contexto:

Ejemplos:

* Ahora.
* Al despertar.
* Antes desayuno.
* Después desayuno.
* Antes almuerzo.
* Después almuerzo.
* Antes cena.
* Después cena.
* Antes dormir.

La aplicación registra automáticamente el momento real.

---

## Comentario libre

Decisión:

Agregar comentario opcional para capturar contexto.

Ejemplos:

* Sensaciones.
* Ejercicio.
* Situaciones especiales.
* Eventos relevantes.

---

## Alternativas descartadas

Pendiente de confirmar formalmente.

---

# Archivos importantes

## lib/main.dart

Función:

Punto de entrada de la aplicación.

Actualmente:

* Inicializa MaterialApp.
* Carga HomeScreen.
* Configura tema.
* `_createNotificationService()` (roadmap punto 17, Fase B): elige
  `AndroidNotificationService` o `DarwinNotificationService` según
  `Platform.isAndroid`/`Platform.isIOS` (`null` en cualquier otra
  plataforma), y la inyecta en `SeguimientoGlucosaApp`/`HomeScreen`.

---

## lib/screens/home_screen.dart

Función:

Pantalla principal.

Contiene:

* Tarjeta glucosa (carga la última medición al iniciar y se actualiza al
  guardar una nueva).
* Menús principales.
* Navegación hacia `GlucoseScreen`, `HistoryScreen`, `MealScreen` y
  `MedicationScreen`.
* Una `AppDatabase` compartida (`_sharedDatabase`, `late final`), usada
  para construir todos los repositorios SQLite por defecto (glucosa,
  comidas, medicamentos, biometría, perfil, recordatorios) cuando no
  se inyectan explícitos; al ser `late`, nunca se construye si todos
  llegan inyectados (como en tests), evitando acceder a `sqflite`
  fuera de un entorno real.
* Flags `enable*` (`enableCloudBackup`, `enableHealthImport`,
  `enableMealReminders`), todos `false` por defecto: activan
  integraciones que dependen de plugins/servicios externos
  (Firestore, Health Connect/Apple Health, diálogo de recordatorios
  post-comida) solo cuando `main.dart` los pasa explícitamente en
  `true`, para que los widget tests no se vean afectados.
* `_reviewPendingReminders`/`_showReminderDialog`/
  `_registerReminderMeasurement`: revisión de recordatorios vencidos
  en `initState` (si `enableMealReminders` es `true`) y el
  `AlertDialog` secuencial que muestran (ver la entrada de Historial
  de cambios "Recordatorios de medición post-comida, Fase A").
* `notificationService`/`_setUpNotificationTapHandling`: si se
  inyecta un `NotificationService` (Fase B), al iniciar solicita el
  permiso de notificaciones, reprograma los pendientes
  (`rescheduleAllPending`) y se suscribe a
  `NotificationService.onNotificationTapped` para volver a llamar a
  `_reviewPendingReminders` cuando el usuario toca una notificación.
  La suscripción se cancela en `dispose`. `HomeScreen` no conoce la
  implementación concreta (`AndroidNotificationService` o
  `DarwinNotificationService`); es `main.dart` quien elige una u otra
  según `Platform.isAndroid`/`Platform.isIOS`.

---

## lib/screens/glucose_screen.dart

Función:

Pantalla de registro de glucosa.

Contiene:

* Campo glucosa (validado, rango 20–600 mg/dL).
* Selector momento (`DropdownButtonFormField<GlucoseMoment>`, usando
  `initialValue` en lugar del parámetro `value` deprecado).
* Comentario opcional.
* Captura fecha/hora.
* Botón guardar que construye un `GlucoseMeasurement` y lo retorna con
  `Navigator.pop(context, measurement)`.

---

## lib/screens/history_screen.dart

Función:

Pantalla de historial de mediciones, con dos pestañas.

Contiene:

* Carga de `GlucoseRepository.getAllMeasurements()` mediante
  `FutureBuilder` (una sola vez al abrir la pantalla).
* `DefaultTabController` + `TabBar`/`TabBarView` con dos pestañas:
  * **Lista** (`_MeasurementList`): `ListView` con una fila
    (`_MeasurementTile`) por medición: valor, momento, fecha/hora
    formateada (`intl`) y comentario si existe.
  * **Gráfico** (`_MeasurementChart`): renderiza `GlucoseLineChart` si hay
    2 o más mediciones; de lo contrario, muestra un mensaje explicativo.
* Estado de carga y mensaje para historial vacío.

---

## lib/widgets/glucose_line_chart.dart

Función:

Widget reutilizable `GlucoseLineChart`, el gráfico de evolución de
glucosa usado por la pestaña "Gráfico" de `HistoryScreen`.

Contiene:

* `LineChart` (`fl_chart`) con los valores de glucosa (mg/dL) ordenados
  cronológicamente en el eje X (independiente del orden recibido en
  `measurements`).
* Dos líneas de referencia horizontales punteadas (`ExtraLinesData`) en
  70 y 180 mg/dL (rango considerado normal).
* Tooltip táctil (`LineTouchTooltipData`/`LineTooltipItem`) con el valor y
  la fecha/hora exacta de la medición tocada.
* Etiquetas del eje X con fecha corta (`dd/MM`, vía `intl`), con un
  intervalo (`_bottomInterval`) que se ajusta según la cantidad de
  mediciones para evitar solapamientos.
* Requiere al menos 2 mediciones (la pantalla que lo usa es responsable de
  validarlo antes de instanciarlo).

---

## lib/screens/meal_screen.dart

Función:

Pantalla del módulo de Comidas, autocontenida (no depende de
`HistoryScreen`), con dos pestañas propias.

Contiene:

* `MealScreen`: `TabController` con pestañas **Registrar** (`_MealForm`) e
  **Historial** (`_MealHistoryList`).
* `_MealForm`: formulario con `DropdownButtonFormField<MealType>`, campos
  de alimento/cantidad con botón "Agregar" (`_FoodItemInputRow`), lista de
  alimentos ya agregados con opción de eliminar (`_FoodItemsList`) y
  comentario opcional. Valida que haya al menos un alimento antes de
  guardar.
* Al guardar (`_handleMealSaved` en `MealScreen`), persiste la comida vía
  `MealRepository.addMeal`, genera sus dos recordatorios de medición
  (60 y 90 minutos) si se inyectó un `reminderCoordinator`, recarga el
  historial, cambia automáticamente a la pestaña Historial y muestra
  un `SnackBar` de confirmación.
* `_MealHistoryList`/`_MealTile`: listan las comidas (más reciente a más
  antigua) con tipo, fecha/hora (`intl`), resumen de alimentos
  (`"Nombre (cantidad)"` separados por coma) y comentario si existe.

---

## lib/screens/medication_screen.dart

Función:

Pantalla del módulo de Medicamentos, autocontenida (no depende de
`HistoryScreen`), con dos pestañas propias, mismo patrón que
`meal_screen.dart`.

Contiene:

* `MedicationScreen`: `TabController` con pestañas **Registrar**
  (`_MedicationForm`) e **Historial** (`_MedicationHistoryList`).
* `_MedicationForm`: formulario con campo de medicamento, cantidad
  numérica y selector de unidad (`_MedicationItemInputRow`, con un campo
  de texto adicional cuando la unidad es "Otro"), lista de medicamentos ya
  agregados con opción de eliminar (`_MedicationItemsList`) y comentario
  opcional. Valida que haya al menos un medicamento, que la cantidad sea
  numérica y que la unidad personalizada no esté vacía cuando corresponde,
  antes de guardar.
* Al guardar (`_handleIntakeSaved` en `MedicationScreen`), persiste la
  toma vía `MedicationRepository.addIntake`, recarga el historial, cambia
  automáticamente a la pestaña Historial y muestra un `SnackBar` de
  confirmación.
* `_MedicationHistoryList`/`_MedicationTile`: listan las tomas (más
  reciente a más antigua) con fecha/hora (`intl`), resumen de medicamentos
  (`"Nombre (cantidad unidad)"` separados por coma, usando
  `MedicationIntakeItem.effectiveUnitLabel`) y comentario si existe.

---

## lib/services/glucose_repository.dart

Función:

Capa de persistencia del historial de mediciones.

Contiene:

* `GlucoseRepository`: interfaz abstracta (`getLastMeasurement`,
  `getAllMeasurements`, `addMeasurement`, `clearMeasurements`).
* `SqliteGlucoseRepository`: implementación basada en `sqflite`, con tabla
  `glucose_measurements`. Soporta inyección de `factory`, `databasePath` y
  `singleInstance` para pruebas aisladas en memoria, o reutilizar una
  `AppDatabase` ya creada (`SqliteGlucoseRepository.withDatabase`).

---

## lib/services/meal_repository.dart

Función:

Capa de persistencia del historial de comidas y su catálogo de alimentos.

Contiene:

* `MealRepository`: interfaz abstracta (`getAllMeals`, `addMeal`,
  `clearMeals`, `getAllFoods`).
* `SqliteMealRepository`: implementación basada en `sqflite`, sobre las
  tablas `meals`, `foods` y `meal_food_items`. `addMeal` usa una
  transacción (`db.transaction`) para insertar la comida y resolver/crear
  cada alimento del catálogo de forma atómica. Soporta los mismos
  parámetros de inyección que `SqliteGlucoseRepository`
  (`factory`/`databasePath`/`singleInstance`/`.withDatabase`).

---

## lib/services/medication_repository.dart

Función:

Capa de persistencia del historial de tomas de medicamentos y su catálogo
de medicamentos.

Contiene:

* `MedicationRepository`: interfaz abstracta (`getAllIntakes`,
  `addIntake`, `clearIntakes`, `getAllMedications`).
* `SqliteMedicationRepository`: implementación basada en `sqflite`, sobre
  las tablas `medication_intakes`, `medications` y
  `medication_intake_items`. `addIntake` usa una transacción
  (`db.transaction`) para insertar la toma y resolver/crear cada
  medicamento del catálogo (con su `defaultUnit`) de forma atómica.
  Soporta los mismos parámetros de inyección que
  `SqliteGlucoseRepository`/`SqliteMealRepository`
  (`factory`/`databasePath`/`singleInstance`/`.withDatabase`).

---

## lib/services/app_database.dart

Función:

Gestor único de la conexión SQLite compartida por todos los
repositorios, incluyendo creación y migración de esquema.

Contiene:

* `AppDatabase`: abre (de forma perezosa, vía el getter `database`) la
  base de datos `seguimiento_glucosa.db`, con `onCreate` (crea las 9
  tablas: `glucose_measurements`, `foods`, `meals`, `meal_food_items`,
  `medications`, `medication_intakes`, `medication_intake_items`,
  `biometric_measurements`, `user_profile`, `meal_glucose_reminders`)
  y `onUpgrade` (migración versionada; `_schemaVersion = 2` sumó las 3
  tablas de comidas sobre la versión 1 de solo glucosa,
  `_schemaVersion = 3` sumó las 3 tablas de medicamentos,
  `_schemaVersion = 4` sumó `biometric_measurements`,
  `_schemaVersion = 5` sumó presión/frecuencia cardíaca opcionales a
  esa tabla, `_schemaVersion = 6` sumó `user_profile`,
  `_schemaVersion = 7` sumó `meal_glucose_reminders`, y
  `_schemaVersion = 8` (actual) sumó la columna `uuid TEXT NOT NULL
  UNIQUE` a `glucose_measurements`, `meals`, `medication_intakes` y
  `biometric_measurements`, con backfill vía `_addUuidColumn` para las
  filas preexistentes — ver la entrada correspondiente en "Historial
  de cambios"). Activa `PRAGMA foreign_keys = ON` en `onConfigure`
  para que `ON DELETE CASCADE` funcione al borrar una comida (incluye
  sus recordatorios) o una toma de medicamentos.
* Centralizar esto evita que cada repositorio administre su propia
  versión de esquema de forma independiente (lo que se desincronizaría
  fácilmente al agregar más tablas).

---

## lib/models/glucose_measurement.dart

Función:

Modelo inmutable `GlucoseMeasurement` (id, uuid, value, moment,
measuredAt, comment) y el enum `GlucoseMoment` con su extensión `label`
para el texto legible de cada momento de medición. El campo `id` es
opcional y lo asigna el repositorio al persistir la medición. `uuid` es
un identificador estable (UUID v4), independiente de `id`: si no se
provee en el constructor, se genera automáticamente (`const
Uuid().v4()`); al reconstruir una medición ya persistida (por ejemplo,
desde una fila de SQLite), el repositorio pasa explícitamente el `uuid`
original para preservarlo. Por este generado automático, la clase ya
no es `const`-constructible (antes sí lo era). Ver la entrada
correspondiente en "Historial de cambios" para el detalle de por qué
se agregó.

---

## lib/models/food.dart

Función:

Modelo inmutable `Food` (id, name): un alimento del catálogo reutilizable
consumido por una o más comidas.

---

## lib/models/meal.dart

Función:

Modelo inmutable `Meal` (id, uuid, type, eatenAt, comment, items) y
`MealFoodItem` (id, food, quantity), más el enum `MealType` (breakfast,
lunch, snack, dinner, other) con su extensión `label`. Los campos `id`
son opcionales y los asigna el repositorio al persistir. `uuid` sigue
el mismo patrón que en `GlucoseMeasurement` (generado automáticamente
si no se provee).

---

## lib/models/medication.dart

Función:

Modelo inmutable `Medication` (id, name, defaultUnit): un medicamento del
catálogo reutilizable consumido por una o más tomas. Incluye también el
enum `DoseUnit` (milligram, milliliter, tablet, unit, drop, other) con su
extensión `label`.

---

## lib/models/medication_intake.dart

Función:

Modelo inmutable `MedicationIntake` (id, uuid, takenAt, comment, items) y
`MedicationIntakeItem` (id, medication, quantity, unit,
customUnitLabel), con el getter `effectiveUnitLabel` (devuelve
`customUnitLabel` cuando `unit` es `DoseUnit.other` y no está vacío, o
`unit.label` en cualquier otro caso). Los campos `id` son opcionales y
los asigna el repositorio al persistir. `uuid` sigue el mismo patrón
que en `GlucoseMeasurement` (generado automáticamente si no se
provee).

---

## lib/models/user_profile.dart

Función:

Modelo inmutable `UserProfile` (heightCm, birthDate, biologicalSex,
displayName; solo `heightCm` es obligatorio), el enum `BiologicalSex`
con su extensión `label`, el método `UserProfile.bmiFor(weightKg)` que
calcula el IMC, el enum `BmiCategory` con su extensión `label`, y la
función `bmiCategoryFor(bmi)` que clasifica un IMC ya calculado.

---

## lib/services/user_profile_repository.dart

Función:

Capa de persistencia del perfil de usuario (un único registro local,
sin soporte multiusuario).

Contiene:

* `UserProfileRepository`: interfaz abstracta (`getProfile`,
  `saveProfile`, `clearProfile`).
* `SqliteUserProfileRepository`: implementación basada en `sqflite`,
  sobre la tabla `user_profile`, usando el patrón "singleton row"
  (`id = 1` fijo; `saveProfile` usa `ConflictAlgorithm.replace` en
  lugar de distinguir entre crear y actualizar). Soporta los mismos
  parámetros de inyección que `SqliteBiometricRepository`
  (`factory`/`databasePath`/`singleInstance`/`.withDatabase`).

---

## lib/models/meal_glucose_reminder.dart

Función:

Modelo inmutable `MealGlucoseReminder` (id, mealId, offsetMinutes,
dueAt, status, resolvedMeasurementId) y el enum
`MealGlucoseReminderStatus` (pending, resolvedAutomatically,
resolvedManually, dismissed). Representa un recordatorio de medir
glucosa a los 60 o 90 minutos de una comida.

---

## lib/services/meal_glucose_reminder_repository.dart

Función:

Capa de persistencia de los recordatorios de medición post-comida.

Contiene:

* `MealGlucoseReminderRepository`: interfaz abstracta
  (`addReminders`, `getPendingDueBy`, `getAllPending`,
  `updateStatus`). `getAllPending` (Fase B) devuelve todos los
  pendientes sin filtrar por `dueAt`, usado para reprogramar
  notificaciones push al iniciar la app.
* `SqliteMealGlucoseReminderRepository`: implementación basada en
  `sqflite`, sobre la tabla `meal_glucose_reminders`. Soporta los
  mismos parámetros de inyección que `SqliteBiometricRepository`
  (`factory`/`databasePath`/`singleInstance`/`.withDatabase`).

---

## lib/services/notification_service.dart

Función:

Interfaz abstracta `NotificationService` (`initialize`,
`requestPermission`, `schedule`, `cancel`, `onNotificationTapped`),
independiente de plataforma, para las notificaciones push locales de
los recordatorios de glucosa post-comida (roadmap punto 17, Fase B).
Todas las implementaciones deben ser "best-effort": nunca lanzan
excepciones, ya que el diálogo in-app (Fase A) sigue funcionando como
respaldo si la notificación falla.

---

## lib/services/android_notification_service.dart

Función:

Implementación `AndroidNotificationService` de `NotificationService`
sobre `flutter_local_notifications`/`timezone`/`flutter_timezone`.

Contiene:

* Un único canal de notificación (`meal_glucose_reminders`) para
  todos los recordatorios.
* `initialize()`: inicializa la base de datos de zonas horarias y fija
  la zona horaria local del dispositivo (vía `flutter_timezone`), e
  inicializa el plugin con el callback de tap conectado a un
  `StreamController` (`onNotificationTapped`).
* `schedule()`: intenta programar con precisión exacta
  (`AndroidScheduleMode.exactAllowWhileIdle`) y, si falla (típicamente
  porque el permiso de alarma exacta no está concedido), hace
  *fallback* automático a precisión inexacta
  (`AndroidScheduleMode.inexactAllowWhileIdle`) en vez de perder el
  recordatorio. Omite programar si `scheduledAt` ya pasó.
* `cancel()`/`requestPermission()`: best-effort, nunca lanzan.

---

## lib/services/darwin_notification_service.dart

Función:

Implementación `DarwinNotificationService` de `NotificationService`
para iOS (y macOS, que comparte la misma API "Darwin" del plugin)
sobre `flutter_local_notifications`/`timezone`/`flutter_timezone`.

Contiene:

* `initialize()`: igual que `AndroidNotificationService` (zona
  horaria local vía `flutter_timezone`, callback de tap conectado a
  `onNotificationTapped`), pero con
  `DarwinInitializationSettings(requestAlertPermission: false,
  requestBadgePermission: false, requestSoundPermission: false)`: el
  permiso no se solicita durante `initialize`, sino explícitamente
  desde `requestPermission`, para que el prompt del sistema aparezca
  cuando `HomeScreen` lo pide (al abrir la app con recordatorios
  activados) y no antes.
* `requestPermission()`: resuelve
  `IOSFlutterLocalNotificationsPlugin.requestPermissions(alert: true,
  badge: true, sound: true)`.
* `schedule()`: a diferencia de Android, no necesita un *fallback* de
  precisión: iOS no tiene un permiso equivalente a
  `SCHEDULE_EXACT_ALARM`, así que un único intento con
  `DarwinNotificationDetails(interruptionLevel:
  InterruptionLevel.active)` es suficiente (best-effort: si falla, el
  diálogo in-app sigue de respaldo). Omite programar si `scheduledAt`
  ya pasó, igual que Android.
* `cancel()`: best-effort, nunca lanza.

---

## lib/services/meal_glucose_reminder_coordinator.dart

Función:

Lógica pura de aplicación (sin widgets) que orquesta el ciclo de vida
completo de los recordatorios: generación al guardar una comida,
intento de auto-resolución vía sensores/CGM al revisar pendientes, y
resolución o descarte manual. Ver la entrada correspondiente en
Historial de cambios para el detalle de cada método
(`addRemindersForMeal`, `reviewPending`, `dismiss`,
`resolveManually`, `isDaytime`).

Desde Fase B, acepta opcionalmente un `NotificationService`:

* `addRemindersForMeal` programa la notificación de cada recordatorio
  nuevo (usando `MealGlucoseReminder.id` como id de notificación).
* `dismiss`/`resolveManually`/`reviewPending` (al resolver
  automáticamente) cancelan la notificación correspondiente.
* `rescheduleAllPending` (nuevo método) reprograma la notificación de
  cada recordatorio todavía pendiente (vencido o no), como red de
  seguridad al iniciar la app.

---

# Estado de compilación

## Estado actual

El proyecto compila correctamente.

Última validación:

* APK generada.
* Instalada en emulador Pixel 7.
* Pantallas funcionando.

---

## Problemas de compilación conocidos

Problemas resueltos:

### NDK corrupto

Problema:

```text
NDK did not have a source.properties file
```

Solución:

Eliminar/reinstalar NDK.

---

### Espacio insuficiente

Problema:

```text
Espacio en disco insuficiente
```

Solución:

Liberación de espacio y recompilación.

---

### Errores Dart

Se corrigieron errores de:

* Paréntesis.
* Llaves.
* Estructura de widgets.

---

# Próximos pasos recomendados

Prioridad alta:

1. ~~Crear modelo `GlucoseMeasurement`.~~ ✅ Hecho.
2. ~~Reemplazar `print()` por objeto de medición.~~ ✅ Hecho.
3. ~~Pasar resultado desde `GlucoseScreen` hacia `HomeScreen`.~~ ✅ Hecho.
4. ~~Mostrar último valor registrado en tarjeta principal.~~ ✅ Hecho.
5. ~~Implementar almacenamiento persistente (`shared_preferences`) para que
   el último valor sobreviva a reinicios de la app.~~ ✅ Hecho.
6. ~~Crear historial de mediciones (migrado a SQLite/`sqflite`; pantalla
   `HistoryScreen` conectada al botón "Historial").~~ ✅ Hecho.

Prioridad media:

7. ~~Crear gráficos (gráfico de evolución de glucosa con `fl_chart`, en una
   nueva pestaña "Gráfico" de `HistoryScreen`).~~ ✅ Hecho.
8. ~~Crear módulo comidas (`Food`/`Meal`/`MealFoodItem`,
   `MealRepository`/`SqliteMealRepository`, pantalla `MealScreen` con
   pestañas Registrar/Historial).~~ ✅ Hecho.
9. ~~Crear módulo medicamentos (`Medication`/`MedicationIntake`/
   `MedicationIntakeItem`, `MedicationRepository`/
   `SqliteMedicationRepository`, pantalla `MedicationScreen` con pestañas
   Registrar/Historial).~~ ✅ Hecho.
10. ~~Crear módulo de Biometría, alcance V1 solo peso corporal
    (`BiometricMeasurement`, `BiometricRepository`/
    `SqliteBiometricRepository`, pantalla `BiometricScreen` con pestañas
    Registrar/Historial).~~ ✅ Hecho.
11. ~~Ampliar el módulo de Biometría con presión arterial y frecuencia
    cardíaca (opcionales, dentro del mismo registro de peso).~~ ✅ Hecho.
    El IMC se agregó en el punto 16, junto con el perfil de usuario.

Prioridad futura:

12. ✅ Integración Firebase (base de preparación; ver Historial de
    cambios). SQLite sigue siendo el almacenamiento principal.
13. ✅ Autenticación de usuarios (Firebase Auth: correo/contraseña y
    Google), opcional — no bloquea el uso de la app. Ver Historial de
    cambios.
14. ✅ Respaldo/restauración manual en la nube (Cloud Firestore),
    disponible solo con sesión iniciada. SQLite sigue siendo el
    almacenamiento principal; no hay sincronización automática ni
    bidireccional en tiempo real. Ver Historial de cambios.
15. ✅ Integración con sensores/CGM (importación manual, de solo lectura,
    desde Google Health Connect/Apple Health vía el plugin `health`).
    Ver Historial de cambios. **Nota (2026-10-22)**: para sensores sin
    integración oficial del fabricante con Health Connect (p. ej.
    FreeStyle Libre 2 Plus), se evaluó y **se descartó** integrar un
    puente no oficial (`HealthConnect-LibreLinkUp`) en la app
    distribuida, por riesgo de ToS de Abbott y responsabilidad legal
    (Ley 19.628) frente a terceros. El registro manual sigue siendo la
    vía soportada para esos casos. Ver entrada correspondiente en
    Historial de cambios.
16. ✅ Perfil de usuario (`UserProfile`: altura obligatoria; fecha de
    nacimiento, sexo biológico y nombre a mostrar opcionales), nueva
    pestaña Perfil en el módulo de Biometría, y cálculo de IMC
    (`UserProfile.bmiFor`) mostrado en el Historial de Biometría. Ver
    Historial de cambios.
17. ✅ Recordatorios de medición post-comida — Fase A: lógica,
    persistencia y diálogo in-app (`MealGlucoseReminder`,
    `MealGlucoseReminderRepository`/`SqliteMealGlucoseReminderRepository`,
    `MealGlucoseReminderCoordinator`). Fase B para Android e iOS:
    notificaciones push locales reales del sistema
    (`NotificationService`/`AndroidNotificationService`/
    `DarwinNotificationService`, vía
    `flutter_local_notifications`/`timezone`/`flutter_timezone`), con
    permiso solicitado al abrir la app, reconciliación al iniciar
    (`rescheduleAllPending`) y revisión al tocar una notificación. Ver
    Historial de cambios.
18. 🔶 Sincronización automática/en tiempo real entre dispositivos.
    Hecho hasta ahora: identificador estable `uuid` en los 4 modelos
    de datos de salud (migración `_schemaVersion = 8`) y fusión
    manual (`BackupRepository.mergeFromCloud()`, botón "Fusionar
    desde la nube" en `AuthScreen`, agrega por `uuid` sin reemplazar
    nada local, a diferencia de `restore()` que sigue intacto). Ver
    Historial de cambios. Pendiente para una iteración futura: decidir
    si además se necesita que la sincronización ocurra
    automáticamente/en tiempo real (sin que el usuario abra la
    pantalla de Cuenta y presione un botón).
19. 🔶 Checklist para llevar la app a producción (Play Store/App
    Store). Auditado el 2026-10-22; nada de esto está hecho todavía.

    Bloqueantes críticos:

    1. ✅ Firma de release real (2026-10-22). Generado
       `android/app/upload-keystore.jks` (RSA 2048, validez 10 000
       días, `CN=Seguimiento Glucosa, O=OGB, C=CL`) con contraseñas
       aleatorias en `android/key.properties` (no versionado, ya
       cubierto por `android/.gitignore`). `build.gradle.kts` ahora
       define `signingConfigs.release` leyendo ese archivo y cae de
       vuelta al keystore de debug solo si `key.properties` no existe
       en la máquina (para no romper `flutter run --release` en otros
       checkouts). Verificado con `flutter build apk --release` +
       `apksigner verify --print-certs`: el APK queda firmado con el
       certificado de release (SHA-1 `63:AE:F9:D7:EB:E7:55:80:94:97:
       92:BE:03:B7:40:91:CB:FD:A8:BC`), no con el de debug.
    2. ✅ `applicationId`/bundle ID definitivos (2026-10-22). Nuevo
       identificador `cl.ogb.seguimientoglucosa.app` en las 6
       plataformas Flutter: Android (`namespace` y `applicationId` en
       `android/app/build.gradle.kts`; paquete Kotlin de
       `MainActivity.kt` movido de `com/example/seguimiento_glucosa`
       a `cl/ogb/seguimientoglucosa/app`), iOS
       (`PRODUCT_BUNDLE_IDENTIFIER` en `ios/Runner.xcodeproj/
       project.pbxproj`, 5 ocurrencias incl. `RunnerTests`), macOS
       (mismo archivo en `macos/`, 4 ocurrencias, + `AppInfo.xcconfig`),
       Linux (`APPLICATION_ID` en `linux/CMakeLists.txt`) y metadata de
       Windows (`CompanyName`/`LegalCopyright` en
       `windows/runner/Runner.rc`, de `com.example` a `OGB`; Windows no
       tiene un `applicationId` real equivalente). Regenerados
       `google-services.json`, `GoogleService-Info.plist` (iOS) y
       `lib/firebase_options.dart` vía `flutterfire configure` contra
       el proyecto Firebase existente `seguimiento-glucosa`, que
       registró automáticamente nuevas apps Android/iOS/macOS con el
       id nuevo (las apps antiguas con `com.example.*` quedan huérfanas
       en la consola de Firebase, se pueden eliminar manualmente desde
       ahí si se desea). Huellas SHA-1 del keystore de **debug** y de
       **release** añadidas a la nueva app Android de Firebase
       (`firebase apps:android:sha:create`) para que el login con
       Google siga funcionando. Pendiente menor, no bloqueante: el
       nodo `services.appinvite_service` dentro de
       `android/app/google-services.json` conserva una referencia
       heredada a `com.example.seguimientoGlucosa` — es metadata del
       backend de Firebase para la función deprecada "App Invites"
       (no usada por esta app) y no afecta autenticación ni ninguna
       funcionalidad actual.
    3. ⬜ Desplegar las reglas de Firestore a producción
       (`firebase deploy --only firestore:rules`). Ya documentado como
       limitación conocida desde 2026-10-20; sin esto, el esquema
       `users/{uid}/...` puede no estar protegido/activo en el
       proyecto real.
    4. ⬜ Política de privacidad. No existe ningún documento de
       privacidad en el repo. Obligatoria para Play Store/App Store al
       tratar datos de salud, y recomendable bajo la Ley 19.628
       (Chile). Debe cubrir: qué se almacena (SQLite local vs.
       Firestore opcional), qué permisos de salud se piden y por qué
       (`NSHealthShareUsageDescription` en iOS, permisos Health
       Connect en Android) y que no hay sincronización con puentes no
       oficiales de terceros (ver decisión del 2026-10-22 arriba).
    5. ⬜ Eliminación de cuenta y datos desde la app. Play Store exige
       que, si hay cuentas (Firebase Auth), el usuario pueda eliminar
       su cuenta y sus datos desde un flujo claro. No se encontró
       ningún flujo de "eliminar cuenta" en el código actual
       (`AuthScreen` y repos relacionados no exponen esta acción).
    6. ⬜ Licencia del proyecto. El `README.md` declara explícitamente
       que el proyecto no tiene licencia de distribución definida.
       Hay que elegir una (o al menos términos de uso) antes de
       distribuir.

    Importantes, no bloqueantes pero de alto riesgo si se omiten:

    7. ⬜ Validación manual real en un dispositivo Android físico
       (Health Connect, notificaciones locales, login con Google,
       lectura/escritura en Firestore). Hasta ahora todo lo validado
       es `flutter analyze`/`flutter test`/build de APK, sin pruebas
       interactivas en hardware.
    8. ⬜ Validación manual real en iOS/macOS con Xcode (notificaciones
       Darwin, `GoogleService-Info.plist`, permisos HealthKit). No se
       puede hacer desde este entorno Windows.
    9. ⬜ Habilitar explícitamente `minifyEnabled`/R8 en el build
       `release` de Android y revisar/crear reglas ProGuard propias si
       corresponde (hoy el build release no declara minify ni
       `proguard-rules.pro` propio).
    10. ⬜ Ficha de la tienda: descripciones, capturas de pantalla
        (hay material preliminar en `Capturas/`), clasificación de
        contenido, y asegurar que el disclaimer "no es un dispositivo
        médico" del `README.md` también sea visible **dentro de la
        app** (no solo en el repo).
    11. ⬜ Revisar que el proyecto de Firebase (`seguimiento-glucosa`)
        esté en modo producción real y no en modo
        test/desarrollo por defecto para Firestore.

---

# Historial de cambios

## 2026-10-22 — Keystore de release real + `applicationId`/bundle ID definitivos

Primeros dos bloqueantes críticos del checklist de producción (punto 19
del roadmap), resueltos en la misma sesión:

* **Keystore de release**: generado `android/app/upload-keystore.jks`
  (RSA 2048, validez 10 000 días, alias `release`,
  `CN=Seguimiento Glucosa, OU=Mobile, O=OGB, L=Santiago, ST=RM, C=CL`)
  con `keytool`, usando contraseñas aleatorias de 24 bytes generadas
  con `RNGCryptoServiceProvider` (no reutiliza ninguna contraseña
  existente). Las contraseñas y la ruta del keystore quedan en
  `android/key.properties`, que **no se versiona** (ya cubierto por
  `key.properties` y `**/*.jks` en `android/.gitignore`).
  `android/app/build.gradle.kts` se actualizó para leer ese archivo y
  configurar `signingConfigs.release` dinámicamente; si
  `key.properties` no existe en la máquina (p. ej. un checkout nuevo
  sin el keystore), el build `release` cae de vuelta al keystore de
  debug para no romper `flutter run --release` en otros entornos de
  desarrollo. Verificado extremo a extremo: `flutter build apk
  --release` genera el APK correctamente y `apksigner verify
  --print-certs` confirma que está firmado con el certificado de
  release (no con el de debug).
* **`applicationId`/bundle ID definitivo**: `cl.ogb.seguimientoglucosa.app`
  en las 6 plataformas que genera `flutter create`, reemplazando los
  valores de ejemplo `com.example.seguimiento_glucosa`/
  `com.example.seguimientoGlucosa`/`com.example`:
  * Android: `namespace` y `applicationId` en
    `android/app/build.gradle.kts`; paquete Kotlin de `MainActivity.kt`
    movido físicamente de `android/app/src/main/kotlin/com/example/
    seguimiento_glucosa/` a `android/app/src/main/kotlin/cl/ogb/
    seguimientoglucosa/app/`.
  * iOS: `PRODUCT_BUNDLE_IDENTIFIER` en
    `ios/Runner.xcodeproj/project.pbxproj` (5 ocurrencias, incluye el
    target `RunnerTests`).
  * macOS: mismo archivo en `macos/Runner.xcodeproj/project.pbxproj`
    (4 ocurrencias) y `macos/Runner/Configs/AppInfo.xcconfig`
    (`PRODUCT_BUNDLE_IDENTIFIER` y `PRODUCT_COPYRIGHT`, de `com.example`
    a `OGB`).
  * Linux: `APPLICATION_ID` en `linux/CMakeLists.txt`.
  * Windows: no tiene un identificador de paquete real equivalente;
    se actualizó solo la metadata `CompanyName`/`LegalCopyright` en
    `windows/runner/Runner.rc` (de `com.example` a `OGB`).
  * Firebase: se ejecutó `flutterfire configure` contra el proyecto
    existente `seguimiento-glucosa` con
    `--android-package-name=cl.ogb.seguimientoglucosa.app
    --ios-bundle-id=cl.ogb.seguimientoglucosa.app
    --macos-bundle-id=cl.ogb.seguimientoglucosa.app`, lo que registró
    automáticamente nuevas apps Android/iOS/macOS con el id nuevo y
    regeneró `android/app/google-services.json`,
    `ios/Runner/GoogleService-Info.plist` y `lib/firebase_options.dart`.
    Las apps antiguas con `com.example.*` quedan huérfanas en la
    consola de Firebase (no se borran automáticamente); se pueden
    eliminar manualmente ahí si se desea, sin impacto en la app.
  * Se registraron las huellas SHA-1 del keystore de **debug**
    (`3b8c8ab35ae5b2d58aaa08667978820515fd65ae`) y del nuevo keystore
    de **release** (`63aef9d7ebe75580949792be03b74091cbfda8bc`) en la
    nueva app Android de Firebase vía `firebase apps:android:sha:create`,
    requisito para que el login con Google siga funcionando tanto en
    builds de desarrollo como de release.
  * Pendiente menor no bloqueante: el nodo `services.appinvite_service`
    dentro del `google-services.json` regenerado conserva una
    referencia heredada a `com.example.seguimientoGlucosa` — es
    metadata del backend de Firebase para la función deprecada
    "App Invites" (no usada por esta app) y no afecta autenticación ni
    ninguna otra funcionalidad.
* **Pendiente a cargo del usuario**: no se puede compilar/probar iOS
  ni macOS desde este entorno Windows; falta validar en Xcode que el
  nuevo bundle id y el `GoogleService-Info.plist` regenerado funcionan
  correctamente (ver puntos 7–8 del checklist de producción).

## 2026-10-22 — Decisión: no integrar el puente no oficial LibreLinkUp→Health Connect en la app distribuida

Contexto: el sensor del propio usuario (FreeStyle Libre 2 Plus, Chile)
no tiene integración oficial de Abbott con Google Health Connect — la
app oficial FreeStyle LibreLink no escribe ahí. La única forma de que
esos datos lleguen a Health Connect (y por lo tanto a la importación
genérica ya implementada en el punto 15 del roadmap) es mediante un
puente **no oficial** de terceros, p. ej.
`c99koder/HealthConnect-LibreLinkUp` (Kotlin/Java, licencia Apache
2.0), que inicia sesión contra la API no documentada de LibreView con
las credenciales Abbott del usuario y escribe las lecturas en Health
Connect mediante un `SyncWorker` periódico.

* Se realizó una auditoría de seguridad de solo lectura de ese repo
  externo (`LibreLinkUp.java`, `MainActivity.kt`, `SyncWorker.java`,
  `proguard-rules.pro`, manifiesto/permisos, endpoints regionales, y
  verificación vía API de GitHub de que el tag `1.5` es idéntico a
  `main`). Hallazgos relevantes:
  * **Alto**: (a) riesgo de incumplir los Términos de Servicio de
    Abbott al simular ser un cliente oficial de LibreView, con posible
    bloqueo de la cuenta; (b) sin manejo de errores al escribir en
    Health Connect; (c) sin `clientRecordId`, lo que puede producir
    duplicados en sincronizaciones repetidas.
  * **Medio**: permiso de lectura de glucosa solicitado de forma más
    amplia de lo necesario; sin build reproducible verificable contra
    el código fuente publicado.
  * **Bajo**: la contraseña de LibreView queda en memoria sin limpieza
    explícita; solo sincroniza la lectura más reciente (no el
    histórico completo).
  * Sin hallazgos de exfiltración de datos ni SDKs de terceros
    ocultos; las credenciales nunca se persisten en disco (solo un
    token cifrado vía Jetpack Security `EncryptedSharedPreferences`).
* **Decisión de producto/negocio** (no solo técnica): dado que
  **Seguimiento Glucosa** está destinada a **distribuirse** a
  terceros (no es exclusivamente para uso personal del desarrollador),
  **no se integra, empaqueta, ni se instruye a los usuarios
  distribuidos a instalar** `HealthConnect-LibreLinkUp` (ni ningún
  otro puente no oficial equivalente) como parte del flujo soportado
  de la app. El **registro manual** de glucosa sigue siendo la única
  vía **soportada** para todos los usuarios distribuidos. El botón
  "Importar desde sensor" (Health Connect/Apple Health, punto 15 del
  roadmap) se mantiene **sin cambios de código**: sigue siendo una
  importación genérica de solo lectura, agnóstica de fabricante, que
  simplemente no tendrá datos que importar para usuarios con Libre 2
  Plus a menos que ellos mismos instalen —bajo su propio riesgo y
  fuera del flujo soportado— un puente no oficial.
* Motivo legal señalado (**pendiente de validar formalmente con
  asesoría legal**, fuera del alcance de este asistente): la Ley
  19.628 sobre Protección de la Vida Privada (Chile) califica los
  datos de salud como datos sensibles; integrar o recomendar
  activamente un puente que depende de credenciales de un tercero
  (Abbott/LibreView) para una app distribuida a múltiples usuarios
  añade una capa de responsabilidad legal que no tiene sentido asumir
  sin asesoría legal explícita, frente al beneficio limitado (una
  integración no oficial y frágil).
* Para uso **personal** del propio desarrollador (no distribuido),
  instalar el APK oficial desde las *Releases* de
  `c99koder/HealthConnect-LibreLinkUp` (verificando el SHA-256
  publicado) sigue siendo razonable, bajo su propio riesgo y criterio.
* No hubo cambios de código en `seguimiento_glucosa` ni en el repo
  externo auditado; esta entrada es puramente una decisión de alcance
  y de producto, documentada para no repetir la evaluación más
  adelante.
* **Pendiente abierto**: monitorear si Abbott lanza una integración
  oficial de FreeStyle LibreLink con Google Health Connect/Apple
  Health en el futuro; si ocurre, reevaluar esta decisión.

## 2026-10-21 — Auto-resolución de recordatorios con la lectura más reciente del sensor

`MealGlucoseReminderCoordinator.reviewPending()` cambia su estrategia de
auto-resolución cuando hay un sensor/CGM disponible
(`GlucoseImportRepository.isAvailable()`): antes exigía que la lectura
estuviera dentro de ±10 minutos de `MealGlucoseReminder.dueAt`
(`_autoResolveTolerance`) para auto-resolver; ahora, con sensor
disponible, se toma siempre su lectura más reciente
(`fetchLatestMeasurement()`) y se usa para resolver de inmediato **todos**
los recordatorios vencidos de esa pasada, sin exigir ninguna cercanía
temporal al vencimiento. Motivación: en la práctica, revisar el sensor
justo en el minuto exacto del vencimiento es poco realista (el usuario
abre la app cuando puede), y antes eso dejaba el recordatorio varado
para acción manual aunque el sensor tuviera una lectura perfectamente
válida (solo que tomada, por ejemplo, 25 minutos después).

* `reminder.offsetMinutes` sigue viajando como metadato de cada
  recordatorio: el comentario autogenerado (p. ej. "Medición automática
  a los 60 minutos.") indica los minutos transcurridos desde la comida,
  no el origen de la lectura ni cuán cerca estuvo del vencimiento.
* Sin sensor disponible (`isAvailable()` devuelve `false`) o si
  `fetchLatestMeasurement()` no devuelve ninguna lectura (`null`) o
  lanza `HealthImportException`, `reviewPending()` cae al
  comportamiento de respaldo previo sin cambios: importar en bloque
  (`_tryImportFromSensor`, últimas 4 horas) y buscar, entre las
  mediciones ya existentes en el historial local, la más cercana a
  `dueAt` dentro de `_autoResolveTolerance` (±10 minutos), sin
  reutilizar la misma medición para más de un recordatorio
  (`usedMeasurementIds`).
* Nuevo método privado `_fetchLatestFromSensorSafely()`: encapsula
  `isAvailable()` + `fetchLatestMeasurement()`, devolviendo `null` en
  cualquier escenario donde no haya una lectura usable (sin sensor,
  sensor sin datos, o `HealthImportException`), para que
  `reviewPending()` no necesite distinguir esos tres casos.
* Nuevo método privado `_autoResolveWithSensor(reminder,
  sensorMeasurement)`: construye una `GlucoseMeasurement` **nueva**
  (no `copyWith` sobre `sensorMeasurement`) a partir del valor/momento/
  fecha de la lectura del sensor, con el comentario de minutos
  transcurridos, y la persiste con `GlucoseRepository.addMeasurement`.
  Se usa `GlucoseMeasurement` nueva en vez de `copyWith` a propósito:
  si varios recordatorios vencidos comparten la misma lectura del
  sensor en una misma pasada de `reviewPending()` (ej. los
  recordatorios de 60 y 90 minutos de la misma comida, revisados
  juntos), cada uno debe quedar como un registro independiente del
  historial, con su propio `uuid` — nunca se reutiliza el mismo
  registro para dos recordatorios.
* `reviewPending()` ahora separa los pendientes vencidos en dos listas
  intermedias: `resolved` (ya resueltos, sea por sensor o por el
  respaldo) y `fallbackPending` (sin lectura de sensor, deben pasar por
  el flujo de respaldo). Si `fallbackPending` queda vacío no se llama a
  `_tryImportFromSensor()` ni se consulta `getAllMeasurements()`, igual
  que antes cuando no había nada que resolver por respaldo.
* No hubo cambios en la firma pública de `MealGlucoseReminderCoordinator`
  ni en `MealGlucoseReminderReviewResult`/`PendingMealGlucoseReminder`:
  es un cambio interno de estrategia, transparente para `HomeScreen` y
  para cualquier otro consumidor.
* `test/services/meal_glucose_reminder_coordinator_test.dart` ganó
  casos para: auto-resolución con una lectura del sensor lejana al
  vencimiento (fuera de los ±10 minutos previos) cuando el sensor está
  disponible; dos recordatorios vencidos de la misma comida resueltos
  en la misma pasada con la misma lectura del sensor, verificando que
  cada uno obtiene un registro de medición distinto; y que, sin sensor
  disponible, se preserva el comportamiento de respaldo ±10 minutos
  anterior sin modificaciones.
* Validación: `flutter analyze` sin issues, `flutter test` 122/122 OK,
  y `flutter build apk --release` exitoso (ver sección "Generación e
  instalación manual de un APK release", más abajo en este mismo
  historial) para confirmar que el cambio funciona también compilado
  en modo release, no solo en los tests.

## 2026-10-21 — Generación e instalación manual de un APK release (sin cable USB)

Contexto: no había un celular Android conectado por USB visible desde
este entorno (`flutter devices`/`adb devices` sin dispositivos, `adb`
tampoco estaba en el `PATH` de la sesión). Se optó por generar un APK
de release y transferirlo manualmente (WhatsApp/Drive/etc.) en vez de
instalar por cable.

* Se confirmó antes de compilar que `android/app/build.gradle.kts` ya
  tiene el `release` firmado con las claves de **debug**
  (`signingConfig = signingConfigs.getByName("debug")`, con un `TODO`
  explícito para reemplazarlo por un keystore propio antes de publicar
  en Google Play). Esto significa que el flujo de este punto **no
  sirve para publicar en Play Store**, solo para instalar y probar en
  dispositivos propios.
* Comando usado: `flutter build apk --release`, con la salida
  redirigida a un archivo de log temporal en el escritorio (el build
  de Gradle tarda varios minutos y no conviene bloquear la sesión
  esperando sin poder inspeccionar el progreso).
* Duración real de este build (primera compilación de release de este
  proyecto en esta máquina, con Firebase + `health` + R8/minificación):
  **~7.2 minutos** (434.9 s reportados por Flutter) para la tarea
  Gradle `assembleRelease`. Builds posteriores deberían ser más rápidos
  gracias al cache de Gradle.
* Resultado: `build/app/outputs/flutter-apk/app-release.apk` (≈55.1 MB).
  Esa carpeta está excluida de git vía `.gitignore` (`/build/`), por lo
  que el APK generado no se versiona ni se sube al repositorio; cada
  quien debe generarlo localmente con el mismo comando cuando lo
  necesite.
* Instalación en el celular sin cable: subir el APK a un medio de
  transferencia (Drive, WhatsApp "Mensajes guardados", Telegram,
  etc.), descargarlo desde el celular, habilitar "Instalar apps
  desconocidas" para la app usada para abrirlo (Android lo solicita
  automáticamente la primera vez si no está activado) y abrir el
  archivo para instalar. Al compartir el mismo `applicationId` que una
  instalación previa, Android actualiza en vez de duplicar, preservando
  los datos locales (SQLite).
* Advertencias no bloqueantes observadas durante el build (no afectan
  el resultado, documentadas por si se repiten en builds futuros):
  * Warnings de Gradle sobre `System::load`/método restringido
    (`net.rubygrapefruit.platform`), relacionados con la versión del
    wrapper de Gradle, no con el código del proyecto.
  * Warning de Flutter: los plugins `firebase_auth`, `firebase_core` y
    `health` todavía aplican el Kotlin Gradle Plugin (KGP) de forma
    clásica en vez del "Built-in Kotlin" que Flutter planea exigir a
    futuro; no requiere acción mientras esos plugins no publiquen una
    versión compatible.
  * Warning del SDK de Android: "This version only understands SDK
    XML versions up to 3 but an SDK XML file of version 4 was
    encountered" (desalineación de versión entre Android Studio y las
    command-line tools instaladas); no impidió el build.
  * Nota del compilador Java sobre `PipelineStageHandlers.java` de
    `cloud_firestore` usando operaciones "unchecked or unsafe"; es
    código generado del plugin, no del proyecto.

## 2026-10-20 — Sincronización en tiempo real: push/pull automático en Android/iOS y visor de solo lectura en Windows/macOS

Reemplaza por completo el respaldo manual (botones "Respaldar"/
"Restaurar"/"Fusionar" de la entrada anterior) por sincronización
automática y silenciosa, más un visor de solo lectura en escritorio.
Decisiones de alcance acordadas antes de implementar:

* "Sincronizar entre dispositivos" se interpretó como dos casos
  distintos: (1) migrar de celular viejo a celular nuevo (debe quedar
  usable con todo el historial, sin acción manual), y (2) un panel de
  **solo lectura** en Windows/macOS (nunca puede crear/editar/borrar).
* En el celular, el push a la nube es automático y silencioso (al
  guardar un registro, se sube solo, sin botón). Al iniciar sesión
  (incluida la restauración automática de sesión al abrir la app), se
  trae automáticamente del servidor lo que falte localmente (por
  `uuid`) y se fusiona con lo ya guardado en el dispositivo, sin
  reemplazar nada.
* Linux queda explícitamente fuera del visor de escritorio: ni
  `firebase_auth` ni `cloud_firestore` tienen soporte oficial ahí en
  FlutterFire (ver tabla de plataformas de cada paquete en pub.dev).
  Sigue funcionando con SQLite local, sin sincronización.
* Los botones manuales de respaldo (`BackupRepository`,
  `FirestoreBackupRepository`, `backups/{uid}` en Firestore) se
  eliminaron por completo en vez de coexistir con el nuevo esquema,
  para no mantener dos formas distintas de sincronizar. No había datos
  reales en `backups/{uid}` que migrar.

**Infraestructura Firebase**: se ejecutó `flutterfire configure` para
registrar apps nuevas de macOS y Windows en el proyecto
`seguimiento-glucosa` (`lib/firebase_options.dart`, `firebase.json`).
macOS reutiliza la configuración de la app iOS (mismo
`GoogleService-Info.plist`); Windows usa el SDK web de Firebase bajo
el capó (no hay SDK nativo de Firebase para Windows). Se agregó el
entitlement `com.apple.security.network.client` a
`macos/Runner/{Debug,Release}.entitlements` (antes solo tenían
`network.server`, usado por el VM service de depuración, no por
llamadas salientes), necesario para que Firestore funcione bajo el
sandbox de macOS.

**Nuevo esquema de Firestore** (reemplaza `backups/{uid}`):

```text
users/{uid}/glucose_measurements/{uuid}
users/{uid}/meals/{uuid}
users/{uid}/medication_intakes/{uuid}
users/{uid}/biometric_measurements/{uuid}
```

Un documento por registro (no un array dentro de un documento único),
indexado por el `uuid` ya existente en cada modelo. Permite `set` por
`uuid` sin duplicar y `snapshots()` reactivo por subcolección, sin
acercarse al límite de 1 MiB por documento de Firestore.
`firestore.rules` se actualizó para este esquema: cada usuario
autenticado solo lee/escribe sus propias subcolecciones.

**Código nuevo**:

* `lib/services/cloud_sync_repository.dart`: `CloudSyncException`,
  `CloudSyncPullSummary` (`addedGlucoseMeasurements`, `addedMeals`,
  `addedMedicationIntakes`, `addedBiometricMeasurements`,
  `totalAdded`), `CloudSyncViewer` (contrato de solo lectura:
  `watchGlucoseMeasurements`/`watchMeals`/`watchMedicationIntakes`/
  `watchBiometricMeasurements`, cada uno un `Stream` con la lista
  completa actualizada en vivo) y `CloudSyncRepository` (extiende
  `CloudSyncViewer` y agrega `pushGlucoseMeasurement`/`pushMeal`/
  `pushMedicationIntake`/`pushBiometricMeasurement` —nunca lanzan
  excepciones, fallan en silencio— y `pullMissingFromCloud` —sí puede
  lanzar `CloudSyncException`, pensado para que quien lo invoque
  decida si informar el error o absorberlo—).
* `lib/services/cloud_sync_serialization.dart`: funciones de
  (de)serialización (`glucoseToMap`/`glucoseFromMap` y equivalentes
  para `Meal`, `MedicationIntake`, `BiometricMeasurement`), extraídas
  como funciones de nivel superior (no métodos) para compartirlas
  entre `FirestoreCloudSyncRepository` y `FirestoreCloudSyncViewer`
  sin duplicar el formato de cada documento.
* `lib/services/firestore_cloud_sync_repository.dart`:
  `FirestoreCloudSyncRepository`, implementación completa (push +
  pull + watch) usada en Android/iOS. Requiere los 4 repositorios
  SQLite por constructor (los necesita para `pullMissingFromCloud` y
  para comparar `uuid`s existentes).
* `lib/services/firestore_cloud_sync_viewer.dart`:
  `FirestoreCloudSyncViewer`, implementación **solo de los 4
  métodos `watch*`** (sin `push`/`pull`, sin ningún repositorio SQLite
  como dependencia), usada en el visor de Windows/macOS. Existe como
  clase separada de `FirestoreCloudSyncRepository` a propósito: en
  Windows no hay soporte nativo de `sqflite` sin configurar
  `sqflite_common_ffi` aparte, y el visor nunca necesita
  almacenamiento local, así que no debía arrastrar esa dependencia.
* `lib/services/syncing_repositories.dart`: `SyncingGlucoseRepository`,
  `SyncingMealRepository`, `SyncingMedicationRepository`,
  `SyncingBiometricRepository`. Decoradores que envuelven cada
  repositorio SQLite (`delegate`) delegando todos los métodos salvo
  `addX`: tras guardar localmente, llaman (con `unawaited`, sin
  esperar ni propagar errores) al `pushX` correspondiente de un
  `CloudSyncRepository` inyectado.
* `lib/screens/cloud_viewer_screen.dart`: `CloudViewerScreen`, pantalla
  de solo lectura para escritorio. Sin sesión iniciada, muestra un
  aviso con botón "Iniciar sesión" (abre `AuthScreen`, reutilizada tal
  cual: el formulario de email/Google no cambia). Con sesión iniciada,
  cuatro pestañas (Glucosa/Comida/Medicamentos/Biometría), cada una un
  `StreamBuilder` sobre el método `watch*` correspondiente de
  `CloudSyncViewer`, con los mismos `ListTile` que ya usaban
  `HistoryScreen`/`MealScreen`/etc. (reconstruidos aquí porque esos
  widgets de fila eran privados de sus pantallas de origen). Ningún
  botón de crear/editar/borrar en toda la pantalla.

**Código modificado**:

* `lib/screens/home_screen.dart`:
  * `HomeScreen` reemplaza `backupRepository`/`enableCloudBackup` por
    `syncRepository`/`enableCloudSync`.
  * `_HomeScreenState` ahora distingue repositorios "base" (SQLite
    puro: `_baseGlucoseRepository` y equivalentes) de los que de
    verdad usan el resto de la pantalla (`_repository` y equivalentes),
    estos últimos envueltos en su `Syncing*Repository` cuando
    `_syncRepository` no es `null` (ver método auxiliar
    `_makeRepository`, que evita repetir la misma rama en cada
    repositorio).
  * Nuevo método `_setUpCloudSyncPullOnSignIn`: se suscribe a
    `AuthRepository.authStateChanges()` y dispara
    `pullMissingFromCloud()` cada vez que detecta una transición de
    "sin sesión" a "con sesión" (incluida la sesión ya iniciada al
    construir el widget, p. ej. tras cambiar de celular). No se repite
    mientras la sesión siga iniciada ni se dispara al cerrar sesión.
    Cualquier `CloudSyncException` se descarta en silencio
    (`_pullMissingFromCloudSilently`): es una operación que el usuario
    no inició explícitamente, así que no debe interrumpirlo con un
    error.
  * `_openAuthScreen` ya no pasa `backupRepository` a `AuthScreen`.
* `lib/screens/auth_screen.dart`: se eliminaron `backupRepository`,
  los métodos `_backup`/`_confirmAndRestore`/`_merge` y los tres
  botones correspondientes. `_AccountView` pasó de `StatefulWidget` a
  `StatelessWidget` (ya no necesita estado propio: solo mostraba
  `_isBusy`/`_statusMessage` de las operaciones manuales eliminadas).
  En su lugar, un texto fijo explica que la sincronización ya es
  automática mientras haya sesión iniciada.
* `lib/main.dart`: nuevo método `_homeForCurrentPlatform` en
  `SeguimientoGlucosaApp.build`: en Windows/macOS construye
  `CloudViewerScreen` (con `FirestoreCloudSyncViewer`); en cualquier
  otra plataforma (Android/iOS, y Linux como excepción documentada)
  construye `HomeScreen` con `enableCloudSync: true`.
* `lib/services/glucose_import_repository.dart`,
  `health_glucose_import_repository.dart`,
  `meal_glucose_reminder_coordinator.dart`: comentarios actualizados
  (referenciaban a `BackupRepository`/`FirestoreBackupRepository`, ya
  eliminados) para seguir señalando un ejemplo válido del mismo patrón
  que describen.
* `firestore.rules`: reglas para el nuevo esquema `users/{uid}/...`
  (reemplaza las de `backups/{uid}`).
* `macos/Runner/DebugProfile.entitlements`,
  `macos/Runner/Release.entitlements`: agregado
  `com.apple.security.network.client`.

**Archivos eliminados**: `lib/services/backup_repository.dart`,
`lib/services/firestore_backup_repository.dart` (ver justificación de
alcance arriba).

**Tests** (`test/widget_test.dart`): `_FakeBackupRepository` se
reemplazó por `_FakeCloudSyncRepository` (implementa
`CloudSyncRepository` completo; los `push*` solo cuentan llamadas,
nunca lanzan; `pullMissingFromCloud` respeta `failPullWith`/
`pullResult`; los `watch*` devuelven streams vacíos de un solo valor,
suficiente para los tests de widgets que no ejercitan el visor de
escritorio). Los 7 tests antiguos de respaldar/restaurar/fusionar se
reemplazaron por 5 tests nuevos: aviso de sincronización automática en
Cuenta (sin botones de respaldo), push automático al guardar una
medición, pull automático con sesión ya iniciada al abrir la app, pull
automático al iniciar sesión con la app ya abierta, y que un error al
fusionar no interrumpe la app. `CloudViewerScreen` no tiene tests de
widgets propios en esta entrada (requeriría mockear
`cloud_firestore`/`firebase_auth`, fuera de alcance de este cambio;
queda como trabajo pendiente si se detectan regresiones ahí).

**Limitaciones conocidas**:

* No se pudo compilar un ejecutable de Windows en este entorno (sin
  Visual Studio/MSBuild instalado): la validación se limitó a
  `flutter analyze`/`flutter test` (ambos limpios). Falta una
  validación manual en una máquina Windows real con Visual Studio, y
  en una Mac real con Xcode, antes de considerar esto probado en
  dispositivo.
* `CloudViewerScreen` no se probó manualmente contra Firestore real
  (requiere las apps de escritorio ya compiladas). El esquema de
  Firestore y las reglas de seguridad tampoco se desplegaron a
  producción (`firebase deploy --only firestore:rules` queda
  pendiente antes de que el nuevo esquema funcione en producción).

## 2026-10-19 (3) — Fusión manual desde la nube por uuid (BackupRepository.mergeFromCloud)

* Segundo paso del roadmap punto 3, sobre la base de la entrada
  anterior (UUID estable). Decisión de diseño clave: **no** se
  modificó `restore()` (sigue reemplazando todo el historial local,
  igual que antes, con su mismo diálogo de confirmación
  "irreversible"); en vez de eso se agregó una acción nueva y
  separada, puramente aditiva, para no cambiar en silencio el
  comportamiento de un botón ya en producción que algunos usuarios
  pueden depender de que sea destructivo (p. ej. para limpiar datos
  corruptos/duplicados locales).
* `lib/services/backup_repository.dart`: nueva clase
  `BackupMergeSummary` (inmutable; `addedGlucoseMeasurements`,
  `addedMeals`, `addedMedicationIntakes`, `addedBiometricMeasurements`,
  y el getter `totalAdded`) y nuevo método abstracto
  `Future<BackupMergeSummary> mergeFromCloud()` en `BackupRepository`.
* `lib/services/firestore_backup_repository.dart`:
  * Las 4 funciones `_xToMap`/`_xFromMap` (glucose, meal, intake,
    biometric) ahora serializan/deserializan también `uuid`.
    `_xFromMap` pasa `uuid: map['uuid'] as String?`: si el campo no
    existe (respaldo creado antes de este cambio), el modelo genera
    uno nuevo automáticamente (mismo comportamiento ya descrito en la
    entrada anterior).
  * `mergeFromCloud()` (nuevo): lee el documento de respaldo (mismo
    manejo de errores que `restore()`), carga el `uuid` de todo lo
    que ya existe localmente en las 4 categorías (`Set<String>` por
    categoría), y recorre cada lista del respaldo agregando
    (`addMeasurement`/`addMeal`/`addIntake`) solo los elementos cuyo
    `uuid` no esté ya en el set correspondiente. Nunca llama a
    `clearMeasurements`/`clearMeals`/`clearIntakes`. Como la app no
    permite editar un registro ya guardado, un `uuid` ya existente
    nunca se actualiza: se omite sin más (se asume que la copia local
    es la vigente).
  * **Limitación conocida**: un respaldo subido con `backup()` antes
    de esta entrada no tiene `uuid` guardado en Firestore. Al
    fusionar ese respaldo, cada elemento genera un `uuid` aleatorio
    nuevo que nunca coincidirá con ningún `uuid` local, por lo que se
    re-agregaría como si fuera nuevo (duplicando lo que ya existía).
    No se intentó resolver esto automáticamente (no hay forma
    confiable de emparejar registros antiguos sin una clave común);
    el mitigante práctico es volver a ejecutar `backup()` una vez
    actualizada la app, antes de usar `mergeFromCloud()` por primera
    vez.
* `lib/screens/auth_screen.dart`: `_AccountViewState` gana el método
  `_merge()` (mismo patrón que `_backup()`: fija `_isBusy`, llama al
  repositorio, actualiza `_statusMessage` con el total agregado o
  "no había datos nuevos", maneja `BackupException`). A diferencia de
  `_confirmAndRestore()`, `_merge()` no pide confirmación (no hay nada
  que confirmar: nunca borra). Nuevo botón "Fusionar desde la nube"
  (`OutlinedButton`, debajo de "Restaurar desde la nube") y un texto
  explicativo corto aclarando la diferencia entre ambos botones.
* `test/widget_test.dart`: `_FakeBackupRepository` implementa
  `mergeFromCloud()` (cuenta llamadas en `mergeCallCount`, devuelve
  `mergeResult` configurable, respeta `failWith`/`hasBackup` igual que
  `restore()`). Dos pruebas nuevas: fusionar con un `BackupMergeSummary`
  que tiene conteos > 0 muestra el mensaje con el total y confirma que
  no aparece ningún `AlertDialog` (a diferencia de restaurar); fusionar
  con todo en cero muestra el mensaje de "no había datos nuevos".
* No se tocaron los tests de `restore()` existentes (siguen pasando
  sin cambios): el contrato de esa operación no cambió.

## 2026-10-19 (2) — Identificador estable (UUID) en los modelos de datos de salud

* Primer paso del roadmap punto 3 ("evaluar si se necesita
  sincronización automática/en tiempo real"): agrega la clave estable
  que una futura sincronización/fusión entre dispositivos necesitaría,
  sin tocar todavía `backup`/`restore` (`FirestoreBackupRepository`
  sigue reemplazando todo el historial local al restaurar, igual que
  antes). Alcance acotado deliberadamente a esto; fusionar por `uuid`
  en `restore()` queda para una iteración futura.
* `lib/models/glucose_measurement.dart`, `meal.dart`,
  `medication_intake.dart` y `biometric_measurement.dart`: cada uno
  gana un campo `uuid` (`String`, no nulo). Si no se provee en el
  constructor, se genera automáticamente un UUID v4 (`const
  Uuid().v4()`); al reconstruir un registro ya persistido (en los
  `_fromRow` de cada repositorio `Sqlite*`), se pasa explícitamente el
  `uuid` ya guardado para preservarlo. Por este valor por defecto
  calculado en el constructor, estas 4 clases dejan de ser
  `const`-constructibles (no había ningún sitio del código que las
  instanciara con `const`, así que no fue necesario tocar nada más por
  este cambio). `copyWith`/`==`/`hashCode`/`toString` de las 4 clases
  se actualizaron para incluir `uuid`.
* `lib/services/app_database.dart`: `_schemaVersion` 7 → 8. La
  migración (`oldVersion < 8`) agrega la columna `uuid` a
  `glucose_measurements`, `meals`, `medication_intakes` y
  `biometric_measurements` mediante el nuevo método privado
  `_addUuidColumn`, en tres pasos (SQLite no permite agregar una
  columna `NOT NULL UNIQUE` con `ALTER TABLE` sobre una tabla con
  filas existentes): 1) `ALTER TABLE ... ADD COLUMN uuid TEXT` sin
  restricciones, 2) una pasada rellenando un UUID v4 nuevo fila por
  fila (`db.update` por `id`), 3) `CREATE UNIQUE INDEX` sobre la
  columna ya rellena. Las instalaciones nuevas (`_createAll`) crean
  directamente `uuid TEXT NOT NULL UNIQUE` en las 4 tablas.
* `lib/services/glucose_repository.dart`, `meal_repository.dart`,
  `medication_repository.dart` y `biometric_repository.dart`: cada
  `_fromRow`/`_toRow` (o `_mealFromRow`/`_mealToRow`,
  `_intakeFromRow`/`_intakeToRow` según el archivo) ahora lee/escribe
  la columna `uuid`.
* `pubspec.yaml`: se agregó `uuid: ^4.6.0` (ya era dependencia
  transitiva de otros paquetes; ahora es dependencia directa).
* Pruebas nuevas: en cada `test/services/*_repository_test.dart`
  (glucose, meal, medication, biometric) se agregó un caso que
  verifica que `uuid` se genera distinto por cada registro nuevo y que
  persiste al recargar desde SQLite. `test/services/app_database_test.dart`
  (nuevo archivo) prueba específicamente la migración 7 → 8: que una
  instalación nueva crea el índice único desde el inicio, y que al
  migrar una base existente (simulada abriendo un esquema v7 manual
  sobre un archivo temporal real, no en memoria, para poder cerrar y
  reabrir con la versión actual) cada fila preexistente recibe un
  `uuid` propio y distinto, y el índice único rechaza duplicados desde
  ese momento en adelante.
* No se tocaron las pantallas (`glucose_screen.dart`,
  `meal_screen.dart`, `medication_screen.dart`, `biometric_screen.dart`)
  ni `firestore_backup_repository.dart`: siguen construyendo estos
  modelos sin pasar `uuid` explícitamente (se genera solo), y el
  respaldo/restauración en Firestore sigue serializando sin `uuid` (se
  genera uno nuevo en cada `addMeasurement`/`addMeal`/`addIntake` al
  restaurar, igual que ya ocurría con `id` antes de este cambio).

## 2026-10-19 — Recordatorios de medición post-comida, Fase B para iOS (notificaciones push locales)

* Extiende la Fase B (ver entrada del 2026-08-23) a iOS, siguiendo el
  mismo patrón que `AndroidNotificationService`: `main.dart` elige la
  implementación de `NotificationService` según la plataforma, en vez
  de instanciar siempre `AndroidNotificationService`.
* `lib/services/darwin_notification_service.dart` (nuevo):
  `DarwinNotificationService`, implementación de `NotificationService`
  para iOS/macOS sobre `flutter_local_notifications`/`timezone`/
  `flutter_timezone`. `initialize()` fija la zona horaria local del
  dispositivo (igual que Android) e inicializa el plugin con
  `DarwinInitializationSettings(requestAlertPermission: false,
  requestBadgePermission: false, requestSoundPermission: false)`, para
  no pedir el permiso automáticamente durante la inicialización;
  `requestPermission()` lo solicita explícitamente vía
  `IOSFlutterLocalNotificationsPlugin.requestPermissions(alert: true,
  badge: true, sound: true)`. A diferencia de Android, `schedule()` no
  necesita un *fallback* de precisión (iOS no tiene un permiso
  equivalente a `SCHEDULE_EXACT_ALARM`): un único intento con
  `DarwinNotificationDetails(interruptionLevel:
  InterruptionLevel.active)` es suficiente, y sigue siendo
  best-effort (nunca lanza) y omite programar si `scheduledAt` ya
  pasó. `cancel()` es best-effort, igual que en Android.
* `lib/main.dart`: nueva función privada `_createNotificationService()`
  que devuelve `AndroidNotificationService()` si `Platform.isAndroid`,
  `DarwinNotificationService()` si `Platform.isIOS`, o `null` en
  cualquier otra plataforma (web/desktop no soportados); `main()` la
  usa en vez de instanciar `AndroidNotificationService()` directamente.
  Requiere el nuevo import `dart:io` para `Platform`.
* `ios/Runner/AppDelegate.swift`: agrega `import
  flutter_local_notifications`; registra
  `UNUserNotificationCenter.current().delegate` en
  `application(_:didFinishLaunchingWithOptions:)` (requerido para que
  el plugin pueda recibir el toque de una notificación) y
  `FlutterLocalNotificationsPlugin.setPluginRegistrantCallback` en
  `didInitializeImplicitFlutterEngine` (requerido para que el callback
  de tap tenga acceso al registro de plugins también en el isolate de
  background), siguiendo el mismo patrón que la app de ejemplo oficial
  del plugin.
* No fue necesario modificar `ios/Runner/Info.plist`: a diferencia de
  Android (que requiere declarar receivers/permisos en el Manifest),
  `flutter_local_notifications` en iOS no necesita ninguna clave
  adicional en `Info.plist` para notificaciones locales (sí la
  requeriría para *remote push*, que no es el caso aquí).
* `lib/screens/home_screen.dart`: solo se actualizó el comentario de
  documentación de `notificationService` (ya mencionaba
  `AndroidNotificationService`; ahora menciona también
  `DarwinNotificationService`). No hubo cambios de lógica: `HomeScreen`
  ya dependía únicamente de la interfaz `NotificationService`, nunca
  de una implementación concreta.
* No se agregaron pruebas nuevas: las existentes en
  `test/services/meal_glucose_reminder_coordinator_test.dart` y
  `test/widget_test.dart` (grupo `NotificationService (Fase B)`) ya
  prueban `MealGlucoseReminderCoordinator`/`HomeScreen` contra la
  interfaz `NotificationService` con un fake en memoria, por lo que
  cubren por igual cualquier implementación concreta que la respete.
  `DarwinNotificationService` (igual que `AndroidNotificationService`)
  no tiene pruebas unitarias propias, ya que envuelve directamente el
  plugin nativo `flutter_local_notifications` y requeriría un entorno
  iOS/macOS real para probarse de forma significativa. Total: 99 tests
  (sin cambios), todos pasando.
* Validación: `flutter analyze` (sin issues) y `flutter test` (99/99).
  **No fue posible validar la compilación nativa para iOS**
  (`flutter build ios`/abrir el proyecto en Xcode) desde este entorno
  Windows, al no contar con una Mac disponible; ver punto 1 de
  "Próximos pasos recomendados" en `README.md`.

## 2026-08-23 — Recordatorios de medición post-comida, Fase B para Android (notificaciones push locales)

* Decisiones de alcance (confirmadas con el usuario antes de
  implementar):
  * Precisión de las alarmas en Android: enfoque **híbrido**. Se
    intenta programar con precisión exacta
    (`AndroidScheduleMode.exactAllowWhileIdle`, requiere el permiso
    `SCHEDULE_EXACT_ALARM`, que el usuario concede manualmente en
    Ajustes desde Android 12); si falla (permiso no concedido), se
    hace *fallback* automático a precisión inexacta
    (`AndroidScheduleMode.inexactAllowWhileIdle`, sin permisos extra,
    el sistema puede retrasar la entrega unos minutos). Ninguna rama
    bloquea el flujo ni requiere intervención del usuario para que el
    recordatorio exista de alguna forma.
  * Solo se implementó para **Android** en este turno; iOS sigue
    funcionando únicamente con el diálogo in-app de la Fase A (queda
    pendiente para una iteración futura).
* `pubspec.yaml`: se agregaron `flutter_local_notifications: ^22.3.2`,
  `timezone: ^0.11.2` y `flutter_timezone: ^5.1.1`.
* `android/app/build.gradle.kts`: se habilitó
  `isCoreLibraryDesugaringEnabled`/`multiDexEnabled` (exigidos por
  `flutter_local_notifications` desde su v10) y se agregó la
  dependencia `coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")`.
* `android/app/src/main/AndroidManifest.xml`: se agregaron los
  permisos `POST_NOTIFICATIONS`, `RECEIVE_BOOT_COMPLETED` y
  `SCHEDULE_EXACT_ALARM`, y los `<receiver>` exigidos por el plugin
  (`ScheduledNotificationReceiver`, `ScheduledNotificationBootReceiver`
  con sus `intent-filter` de reinicio) para mostrar y reprogramar
  notificaciones.
* `lib/services/notification_service.dart` (nuevo): interfaz
  abstracta `NotificationService` (`initialize`, `requestPermission`,
  `schedule`, `cancel`, `onNotificationTapped`), independiente de
  plataforma, para que `MealGlucoseReminderCoordinator` no quede
  acoplado al plugin nativo. Todas las implementaciones deben ser
  "best-effort" (nunca lanzan), ya que el diálogo in-app sigue
  funcionando como respaldo.
* `lib/services/android_notification_service.dart` (nuevo):
  `AndroidNotificationService`, implementación sobre
  `flutter_local_notifications`/`timezone`/`flutter_timezone`. Un
  único canal (`meal_glucose_reminders`); `initialize()` fija la zona
  horaria local del dispositivo vía `flutter_timezone` y conecta el
  callback de tap a un `StreamController` (`onNotificationTapped`);
  `schedule()` implementa el fallback exacta→inexacta descrito arriba
  y omite programar si la fecha ya pasó; `cancel()`/
  `requestPermission()` son best-effort.
* `lib/services/meal_glucose_reminder_repository.dart`: nuevo método
  `getAllPending()` (todos los pendientes, sin filtrar por `dueAt`),
  implementado en `SqliteMealGlucoseReminderRepository` con una
  consulta `status = 'pending'`.
* `lib/services/meal_glucose_reminder_coordinator.dart`: nuevo
  parámetro opcional `notificationService`. `addRemindersForMeal`
  programa la notificación de cada recordatorio nuevo (usando
  `MealGlucoseReminder.id` como id de notificación, estable y único);
  `dismiss`/`resolveManually`/`reviewPending` (al resolver vía CGM)
  cancelan la notificación correspondiente; nuevo método
  `rescheduleAllPending()` reprograma la notificación de cada
  recordatorio todavía pendiente (vencido o no), como red de
  seguridad al iniciar la app.
* `lib/screens/home_screen.dart`: nuevo parámetro opcional
  `notificationService`, pasado al `MealGlucoseReminderCoordinator`.
  Si no es `null` y `enableMealReminders` es `true`,
  `_setUpNotificationTapHandling` (llamado desde `initState`)
  solicita el permiso de notificaciones, llama a
  `rescheduleAllPending()`, y se suscribe a
  `NotificationService.onNotificationTapped` para volver a llamar
  `_reviewPendingReminders` cuando el usuario toca una notificación;
  la suscripción se cancela en el nuevo `dispose()`.
* `lib/main.dart`: `SeguimientoGlucosaApp` recibe un nuevo parámetro
  opcional `notificationService`, pasado a `HomeScreen`; `main()`
  inyecta `AndroidNotificationService()` en producción.
* Pruebas nuevas: `_FakeNotificationService` en
  `test/services/meal_glucose_reminder_coordinator_test.dart` (9 tests
  nuevos: programar/cancelar notificaciones en cada método del
  coordinador, y dos tests de `rescheduleAllPending`) y en
  `test/widget_test.dart` (grupo `NotificationService (Fase B)`, 2
  tests: solicitud de permiso + reprogramación al abrir `HomeScreen`,
  y revisión de pendientes al tocar una notificación). Total:
  91 → 99 tests, todos pasando.
* Validación: `dart format`, `flutter analyze` (sin issues) y
  `flutter build apk --debug` (compila correctamente con las nuevas
  dependencias nativas y la configuración de Gradle/Manifest).

## 2026-08-22 — Recordatorios de medición post-comida, Fase A (lógica/persistencia/diálogo in-app)

* Decisiones de alcance (confirmadas con el usuario antes de
  implementar):
  * Se dividió el trabajo en dos fases: **Fase A** (esta entrada) cubre
    la lógica de dominio, la persistencia y la interacción dentro de la
    app (sin notificaciones push ni alarmas del sistema operativo).
    **Fase B** (notificaciones/alarmas reales fuera de la app) se
    abordará en un turno separado.
  * No se creó una pantalla nueva: los recordatorios vencidos se
    muestran como un `AlertDialog` secuencial al abrir `HomeScreen`
    (uno por recordatorio pendiente), en lugar de una bandeja de
    notificaciones o pantalla dedicada.
  * De día (07:00 inclusive–22:00 exclusivo) el diálogo se acompaña de
    `SystemSound.play(SystemSoundType.alert)` ("alarma"); de noche es
    un popup silencioso. La franja horaria se calcula sobre la hora
    local del dispositivo en el momento de revisar los pendientes, no
    sobre la hora en que venció el recordatorio.
  * La medición registrada manualmente desde el diálogo se guarda como
    una `GlucoseMeasurement` normal del historial (sin ningún campo de
    vínculo en el modelo): solo se le autogenera el comentario
    `'Medición post-comida (+N min).'` cuando el usuario no escribió
    uno propio, siguiendo el mismo patrón que usa la importación CGM
    con "Importado desde...".
  * Tolerancia de auto-resolución vía sensor/CGM: ±10 minutos respecto
    a la hora exacta en que correspondía medir (`dueAt`). Si existe una
    medición del historial (incluida una recién importada del sensor)
    dentro de ese rango y no utilizada por otro recordatorio, el
    recordatorio se marca `resolvedAutomatically` sin interrumpir al
    usuario.
* `lib/models/meal_glucose_reminder.dart` (nuevo): modelo inmutable
  `MealGlucoseReminder` (`id`, `mealId`, `offsetMinutes`, `dueAt`,
  `status`, `resolvedMeasurementId`), con `copyWith`/`==`/`hashCode`/
  `toString` siguiendo el mismo patrón que los demás modelos. El enum
  `MealGlucoseReminderStatus` tiene cuatro valores: `pending`,
  `resolvedAutomatically`, `resolvedManually`, `dismissed`.
* `lib/services/app_database.dart`: `_schemaVersion` subido a `7`; se
  agregó la tabla `meal_glucose_reminders` (`meal_id` con
  `REFERENCES meals (id) ON DELETE CASCADE`, `offset_minutes`,
  `due_at`, `status`, `resolved_measurement_id`), creada tanto en
  `_createAll` como en `_upgrade` (rama `oldVersion < 7`).
* `lib/services/meal_glucose_reminder_repository.dart` (nuevo):
  interfaz `MealGlucoseReminderRepository` (`addReminders`,
  `getPendingDueBy`, `updateStatus`) e implementación
  `SqliteMealGlucoseReminderRepository` (constructores normal y
  `.withDatabase`, mismo patrón de inyección que
  `SqliteBiometricRepository`). `addReminders` inserta varios
  recordatorios de una sola comida en lote.
* `lib/services/meal_glucose_reminder_coordinator.dart` (nuevo):
  `MealGlucoseReminderCoordinator`, lógica pura de aplicación (sin
  widgets) que orquesta todo el ciclo de vida:
  * `isDaytime(DateTime)`: franja diurna 07:00 (inclusive)–22:00
    (exclusivo).
  * `addRemindersForMeal(Meal)`: genera los dos recordatorios (+60 y
    +90 minutos desde `Meal.eatenAt`) al guardar una comida.
  * `reviewPending()`: busca los recordatorios vencidos
    (`getPendingDueBy(now)`), intenta importar mediciones nuevas del
    sensor/CGM si hay un `GlucoseImportRepository` disponible, y por
    cada uno busca en el historial la medición no usada más cercana a
    `dueAt` dentro de ±10 minutos; si la encuentra, lo marca
    `resolvedAutomatically`; si no, lo devuelve como
    `PendingMealGlucoseReminder` (con su flag `isDaytime`) para que la
    UI lo muestre. Devuelve un `MealGlucoseReminderReviewResult`
    (separa resueltos automáticamente de los que necesitan acción
    manual).
  * `dismiss(reminder)`: marca `dismissed` sin asociar medición.
  * `resolveManually(reminder, measurement)`: guarda la medición
    tomada manualmente (autogenerando el comentario si falta, ver
    decisión de alcance arriba) y marca el recordatorio
    `resolvedManually` con el `id` de la medición guardada.
* `lib/screens/meal_screen.dart`: nuevo parámetro opcional
  `reminderCoordinator`; si no es `null`, `_handleMealSaved` llama a
  `reminderCoordinator.addRemindersForMeal(saved)` justo después de
  guardar la comida.
* `lib/screens/home_screen.dart`: nuevos parámetros `reminderRepository`
  y `enableMealReminders` (`false` por defecto, mismo patrón de flag
  que `enableHealthImport`/`enableCloudBackup`, para que los widget
  tests existentes no se vean afectados por diálogos inesperados).
  Construye `_reminderRepository`/`_reminderCoordinator` igual que los
  demás repositorios (reutilizando `_sharedDatabase` e
  `_importRepository` si existe). En `initState`, si
  `enableMealReminders` es `true`, llama a `_reviewPendingReminders()`,
  que muestra un `AlertDialog` por cada `needsManualAction` (ícono de
  alarma o luna según `isDaytime`, botones "Registrar ahora" y
  "Descartar"). "Registrar ahora" navega a `GlucoseScreen` y llama a
  `resolveManually`; "Descartar" (o cerrar sin guardar) llama a
  `dismiss`. El `SystemSound.play` de día se dispara con `unawaited`
  (no se espera su resultado) para no bloquear la aparición del
  diálogo si el canal de sonido de la plataforma no está disponible
  (por ejemplo, en el entorno de pruebas).
* `lib/main.dart`: pasa `enableMealReminders: true` al construir
  `HomeScreen`.
* Tests: `test/services/meal_glucose_reminder_repository_test.dart`
  (persistencia en lote, filtrado por vencimiento, actualización de
  estado) y `test/services/meal_glucose_reminder_coordinator_test.dart`
  (15 tests: franja horaria, generación de recordatorios, las
  distintas ramas de `reviewPending` incluyendo auto-resolución con
  tolerancia de ±10 minutos, `dismiss`, `resolveManually` con/sin
  comentario propio). En `test/widget_test.dart` se agregó
  `_FakeMealGlucoseReminderRepository` y 4 widget tests nuevos
  (mostrar el diálogo al abrir `HomeScreen` con un recordatorio
  vencido; descartar; registrar ahora y verificar comentario
  autogenerado + estado `resolvedManually`; auto-resolución vía CGM
  fake sin mostrar diálogo), además de inyectar
  `_FakeMealGlucoseReminderRepository` en los tests existentes que
  navegan a `MealScreen` para no activar `sqflite` real.
* Validación completa: `dart format` (sin cambios tras aplicarlo);
  `flutter analyze` (sin issues); `flutter test` (91/91 OK: 67
  anteriores + tests nuevos de modelo/repositorio/coordinador + 4
  widget tests nuevos).
* `PROJECT_CONTEXT.md` y `PROJECT_GRAPH.md` actualizados (paso #17 del
  roadmap marcado como hecho, sección "Alertas" actualizada, esquema
  de base de datos y archivos importantes documentados).

## 2026-08-21 — Perfil de usuario e IMC en el módulo de Biometría

* Decisión de alcance (confirmada con el usuario antes de implementar):
  se eligió un perfil "completo" (altura + fecha de nacimiento + sexo
  biológico + nombre a mostrar), en lugar del mínimo indispensable
  (solo altura), para sentar base a funcionalidades futuras
  (clasificación de IMC por edad/sexo, saludo personalizado) sin
  requerir otra migración de esquema a corto plazo.
* `lib/models/user_profile.dart` (nuevo): modelo inmutable `UserProfile`
  (`heightCm` obligatorio; `birthDate`, `biologicalSex`, `displayName`
  opcionales, con `copyWith`/`==`/`hashCode` y flags `clearBirthDate`/
  `clearBiologicalSex`/`clearDisplayName`), el enum `BiologicalSex`
  (`female`/`male`/`preferNotToSay`) con su extensión `label`, el
  método `UserProfile.bmiFor(weightKg)` (IMC = peso / altura_m²,
  `null` si la altura no es positiva), el enum `BmiCategory`
  (`underweight`/`normal`/`overweight`/`obese`) con su extensión
  `label`, y `bmiCategoryFor(bmi)` (rangos estándar de la OMS para
  adultos).
* `lib/services/user_profile_repository.dart` (nuevo): interfaz
  `UserProfileRepository` (`getProfile`, `saveProfile`, `clearProfile`)
  e implementación `SqliteUserProfileRepository` (constructores normal
  y `.withDatabase`, mismo patrón de inyección que
  `SqliteBiometricRepository`), sobre la tabla `user_profile` con
  patrón "singleton row" (`id = 1` fijo; `saveProfile` usa
  `ConflictAlgorithm.replace`), ya que la app no tiene soporte
  multiusuario.
* `lib/services/app_database.dart`: tabla `user_profile` (`id`,
  `height_cm REAL NOT NULL`, `birth_date`, `biological_sex`,
  `display_name`), sumada en la versión de esquema 6.
* `lib/screens/biometric_screen.dart`: nueva pestaña **Perfil** (entre
  Registrar e Historial) con el formulario de altura (obligatoria),
  nombre a mostrar, sexo biológico (`DropdownButtonFormField`) y fecha
  de nacimiento (`showDatePicker`), todos opcionales salvo la altura.
  Guardar el perfil muestra una confirmación (`SnackBar`) sin cambiar
  de pestaña. La pestaña Historial ahora muestra el IMC de cada peso
  (y su categoría, p. ej. "IMC: 25.0 (Sobrepeso)") cuando el perfil ya
  tiene altura guardada; si no, simplemente no se muestra. El IMC se
  calcula en tiempo de lectura (no se guarda en
  `biometric_measurements`), para que no quede desactualizado si el
  usuario corrige su altura más adelante.
* `lib/screens/home_screen.dart`: nuevo parámetro `profileRepository`
  (mismo patrón que `biometricRepository`: si es `null`, usa
  `SqliteUserProfileRepository` sobre la base de datos compartida),
  pasado a `BiometricScreen` al navegar a ella.
* Tests: 14 tests nuevos — 6 unitarios de `UserProfile` (cálculo de
  IMC, clasificación por rangos, `copyWith`) en
  `test/models/user_profile_test.dart`; 6 unitarios de
  `SqliteUserProfileRepository` (persistencia, patrón singleton row,
  `clearProfile`) en `test/services/user_profile_repository_test.dart`;
  2 de widgets en `test/widget_test.dart` (guardar el perfil lo
  persiste, el Historial de Biometría muestra el IMC combinando perfil
  + peso). Se agregó `_FakeUserProfileRepository` en memoria y se
  inyectó en los tests existentes de `BiometricScreen` para no tocar
  `sqflite` real. 67/67 tests OK, `flutter analyze` limpio, `dart
  format` aplicado, build APK debug exitoso.
* `PROJECT_CONTEXT.md` actualizado (paso #16 del roadmap marcado como
  hecho; secciones "Registro de biometría" y "Usuarios/perfiles"
  actualizadas).

## 2026-08-20 (1) — Importación manual de glucosa desde sensores/CGM (Health Connect/Apple Health)

* Decisiones de alcance (confirmadas con el usuario antes de
  implementar):
  * Se evaluaron 3 vías para integrar datos de sensores/CGM: (a) la
    capa de salud del sistema operativo (Google Health Connect en
    Android, Apple Health en iOS) vía el plugin `health`, agnóstica
    de fabricante y testeable con datos de prueba sin hardware real;
    (b) la API directa de un fabricante (p. ej. Dexcom), que exige
    cuenta developer, aprobación y OAuth2, y solo sirve para ese
    fabricante; (c) BLE directo al sensor, inviable sin el SDK
    propietario de cada fabricante. Se eligió la opción (a).
  * Alcance V1: solo **importación** (lectura), simétrico al patrón ya
    usado por el respaldo en la nube (botón manual, no sincronización
    automática ni bidireccional). La app nunca escribe en Health
    Connect/Apple Health, solo lee mediciones ya existentes.
  * Deduplicación: no existe un identificador estable compartido entre
    el historial local (IDs autoincrementales de SQLite) y la
    plataforma de salud, así que se usa la combinación de fecha/hora
    exacta + valor como clave para evitar importar la misma medición
    dos veces en importaciones repetidas (ventana de 30 días hacia
    atrás en cada importación).
* `pubspec.yaml`: dependencia `health: ^13.3.2` (wrapper de Health
  Connect/HealthKit). Requiere `minSdk 26` en Android (antes
  `flutter.minSdkVersion`), actualizado en
  `android/app/build.gradle.kts`.
* `android/app/src/main/AndroidManifest.xml`: permiso
  `android.permission.health.READ_BLOOD_GLUCOSE` (solo lectura), el
  `activity-alias` y los `intent-filter`/`<queries>` que exige Health
  Connect para la pantalla de permisos y para detectar si la app
  Health Connect está instalada.
* `ios/Runner/Info.plist`: `NSHealthShareUsageDescription` y
  `NSHealthUpdateUsageDescription` (HealthKit).
* `lib/services/glucose_import_repository.dart`: interfaz abstracta
  `GlucoseImportRepository` (`isAvailable`, `requestPermission`,
  `importMeasurements`) y `HealthImportException`, siguiendo el mismo
  patrón que `AuthRepository`/`BackupRepository`.
* `lib/services/health_glucose_import_repository.dart`:
  `HealthGlucoseImportRepository`, implementación basada en el plugin
  `health`. Lee `HealthDataType.BLOOD_GLUCOSE` (convertido a
  `MILLIGRAM_PER_DECILITER`) y agrega al `GlucoseRepository` las
  mediciones que no estén ya presentes según la clave de
  deduplicación. Solo llama a métodos de lectura del plugin
  (`configure`, `hasPermissions`, `requestAuthorization` con acceso
  `READ`, `getHealthDataFromTypes`), nunca a `writeHealthData`.
* `lib/screens/history_screen.dart`: nuevo botón "Importar desde
  sensor" (ícono `Icons.sync`) en el `AppBar`, visible solo si se
  inyecta un `importRepository`. Solicita disponibilidad y permiso
  antes de importar, y muestra el resultado (mediciones importadas,
  sin novedades, Health Connect no disponible, permiso denegado, o
  error) en un `SnackBar`.
* `lib/screens/home_screen.dart`: nuevos parámetros `importRepository`
  y `enableHealthImport` (mismo patrón que `backupRepository`/
  `enableCloudBackup`): por defecto `enableHealthImport` es `false`
  para no tocar el plugin `health` real en los widget tests;
  `main.dart` lo activa explícitamente.
* Tests: 6 tests nuevos en `test/widget_test.dart` con un
  `_FakeGlucoseImportRepository` en memoria (sin botón visible sin
  `importRepository`, importación exitosa reflejada en el historial,
  sin mediciones nuevas, Health Connect no disponible, permiso
  denegado, error de importación con mensaje legible). 53/53 tests
  OK, `flutter analyze` limpio, build APK debug exitoso.
* `PROJECT_CONTEXT.md` actualizado (paso #15 del roadmap marcado como
  hecho).
* Pendiente de verificación interactiva en un dispositivo/emulador
  Android real con Health Connect instalado (no disponible en este
  entorno); ver sección de deuda técnica.

## 2026-08-19 (9) — Respaldo/restauración manual en la nube (Cloud Firestore)

* Decisiones de alcance (confirmadas con el usuario antes de
  implementar):
  * Estrategia simple: botones manuales "Respaldar en la nube" y
    "Restaurar desde la nube" (no sincronización automática ni
    bidireccional en tiempo real, que requeriría resolución de
    conflictos fuera de alcance de esta iteración).
  * `restore()` **reemplaza** todos los datos locales (no los
    fusiona): los IDs de cada registro los asigna SQLite de forma
    local y autoincremental, sin una clave estable entre
    dispositivos que permita distinguir con confiabilidad qué
    registros ya existen; fusionar sin esa clave produciría
    duplicados silenciosos. Se muestra un diálogo de confirmación
    explícito antes de ejecutar la restauración, explicando que la
    acción no se puede deshacer.
  * Ubicación en la UI: dentro de `AuthScreen` → `_AccountView`
    (solo visible con sesión iniciada, ya que sin cuenta no hay a
    dónde respaldar), reutilizando la pantalla de Cuenta ya
    existente en lugar de crear una pantalla nueva.
* Firebase Console/CLI: habilitada la API de Cloud Firestore
  (requirió habilitación manual en Google Cloud Console antes de que
  el comando de Firebase CLI funcionara) y creada la base de datos
  `(default)` en `us-central1` vía
  `firebase firestore:databases:create`.
* `firestore.rules` (nuevo): reglas de seguridad que permiten a cada
  usuario autenticado leer/escribir únicamente su propio documento en
  `backups/{uid}` (`request.auth.uid == userId`); nadie accede al
  respaldo de otro usuario, y los usuarios no autenticados no acceden
  a ningún dato. Desplegadas con
  `firebase deploy --only firestore:rules`. `firebase.json` se
  actualizó para registrar `"firestore": {"rules": "firestore.rules"}`.
* `pubspec.yaml`: se agregó `cloud_firestore: ^7.0.0`.
* Arquitectura (mismo patrón Repository que el resto del proyecto):
  * `lib/services/backup_repository.dart`: interfaz `BackupRepository`
    (`backup`, `restore`, `getLastBackupTime`) y `BackupException`
    (mensajes en español). Documenta explícitamente la decisión de
    "reemplazar, no fusionar" directamente en el docstring de
    `restore`.
  * `lib/services/firestore_backup_repository.dart`:
    `FirestoreBackupRepository`, que serializa manualmente las cuatro
    colecciones de datos de salud (`GlucoseMeasurement`, `Meal`,
    `MedicationIntake`, `BiometricMeasurement`) a/desde `Map<String,
    Object?>` y las guarda en un único documento `backups/{uid}` (con
    `updatedAt: FieldValue.serverTimestamp()`). `restore()` primero
    lee y valida el documento remoto (lanzando `BackupException` si
    no existe ningún respaldo), y solo después limpia los
    repositorios locales (`clear*`) e inserta los registros
    recuperados (`add*`), para no borrar datos locales si la lectura
    remota falla.
  * `lib/screens/auth_screen.dart`: `AuthScreen` ganó un parámetro
    `backupRepository` opcional; `_AccountView` se convirtió de
    `StatelessWidget` a `StatefulWidget` para manejar el estado de
    carga/mensaje de las operaciones de respaldo. El botón "Restaurar
    desde la nube" abre un `AlertDialog` de confirmación explícito
    antes de llamar a `restore()`.
  * `lib/screens/home_screen.dart`: ganó un parámetro
    `backupRepository` inyectable y un flag `enableCloudBackup`
    (`false` por defecto). A diferencia de los demás repositorios
    (que siempre construyen una implementación real si no se
    inyectan), `BackupRepository` **no** se construye automáticamente
    salvo que `enableCloudBackup` sea `true` explícitamente, porque
    requiere Firebase ya inicializado y los widget tests no deben
    tocar Firestore real por defecto.
  * `lib/main.dart`: pasa `enableCloudBackup: true` a `HomeScreen`,
    ya que en producción Firebase ya está inicializado en ese punto.
* Tests: se agregó `_FakeBackupRepository` (en memoria, con flags
  `hasBackup`/`failWith` y contadores `backupCallCount`/
  `restoreCallCount`) en `test/widget_test.dart`, y 5 widget tests
  nuevos (botones visibles con `backupRepository` inyectado; respaldo
  exitoso; restauración con confirmación y posterior ejecución;
  cancelar el diálogo no restaura; mensaje de error legible).
* Validación completa: `flutter pub get` (agrega `cloud_firestore` y
  sus paquetes de plataforma); `dart format` (sin cambios tras
  corregir); `flutter analyze` (sin issues, tras resolver 4 avisos
  `prefer_initializing_formals` en el constructor de
  `FirestoreBackupRepository` con comentarios `// ignore:`
  justificados — los parámetros deben mantener nombres públicos para
  legibilidad en el sitio de construcción); `flutter test` (47/47 OK:
  42 anteriores + 5 nuevos, **sin ninguna regresión** gracias al flag
  `enableCloudBackup`); `flutter build apk --debug` compiló
  exitosamente (`√ Built build\app\outputs\flutter-apk\app-debug.apk`,
  108.1s), confirmando que la integración nativa de
  `cloud_firestore` funciona en la práctica.
* `PROJECT_CONTEXT.md`, `README.md` y `PROJECT_GRAPH.md` actualizados
  (paso #14 del roadmap marcado como hecho).

## 2026-08-19 (8) — Autenticación de usuarios (Firebase Auth)

* Decisión de alcance (confirmada con el usuario antes de implementar):
  inicio de sesión **opcional**, con correo/contraseña y con Google;
  no bloquea el uso del resto de la app (Glucosa, Comida, Medicamentos,
  Biometría, Historial siguen funcionando sin cuenta, sobre SQLite). El
  gate obligatorio, si se decide, queda para el punto 14 (sincronización
  real), que es lo que lo justificaría.
* Configuración en Firebase Console: habilitados los proveedores
  "Correo electrónico/contraseña" y "Google" (con correo de asistencia)
  en Authentication → Sign-in method.
* SHA-1 del keystore de debug obtenido (`keytool -list -v -alias
  androiddebugkey -keystore %USERPROFILE%\.android\debug.keystore`) y
  registrado en el proyecto Firebase vía
  `firebase apps:android:sha:create`, requisito para que Google
  Sign-In funcione en Android.
* `android/app/google-services.json` y `ios/Runner/GoogleService-Info.plist`
  regenerados (`firebase apps:sdkconfig`) tras habilitar Google, para
  incluir los nuevos `oauth_client` (Android client y **Web client ID**,
  este último usado como `serverClientId` de `google_sign_in`).
* `pubspec.yaml`: se agregaron `firebase_auth: ^7.0.0` y
  `google_sign_in: ^7.2.0`.
* Arquitectura (mismo patrón Repository ya usado por
  `GlucoseRepository`/`MealRepository`/etc., para no acoplar pantallas
  al SDK de Firebase y mantener los widget tests sin dependencias
  nativas):
  * `lib/models/app_user.dart`: modelo inmutable `AppUser` (uid, email,
    displayName), independiente de `firebase_auth.User`.
  * `lib/services/auth_repository.dart`: interfaz `AuthRepository`
    (`authStateChanges`, `currentUser`, `registerWithEmail`,
    `signInWithEmail`, `signInWithGoogle`, `sendPasswordResetEmail`,
    `signOut`) y `AuthException` (mensajes en español, sin exponer
    códigos internos del SDK).
  * `lib/services/firebase_auth_repository.dart`:
    `FirebaseAuthRepository`, implementación sobre `firebase_auth` y
    `google_sign_in` 7.x (API `GoogleSignIn.instance.initialize/
    authenticate`, con `GoogleSignInAccount.authentication.idToken` →
    `GoogleAuthProvider.credential` → `signInWithCredential`). El
    método `initializeGoogleSignIn` se invoca una sola vez desde
    `main()`. La cancelación del selector de cuentas de Google
    (`GoogleSignInExceptionCode.canceled`) devuelve `null` en lugar de
    lanzar una excepción, porque no es un error real.
  * `lib/screens/auth_screen.dart`: pantalla `AuthScreen`, con
    `StreamBuilder<AppUser?>` sobre `authStateChanges()` que alterna
    entre el formulario de login/registro (`_AuthForm`, con alternancia
    Iniciar sesión/Registrarse, botón "Continuar con Google",
    "¿Olvidaste tu contraseña?") y el resumen de cuenta autenticada
    (`_AccountView`, con botón "Cerrar sesión").
* `lib/screens/home_screen.dart`: ganó un parámetro inyectable
  `authRepository` (mismo patrón que los demás repositorios) y un
  ícono "Cuenta" (`Icons.account_circle_outlined`) en el `AppBar` que
  navega a `AuthScreen`, sin alterar la lista de módulos existente.
* `lib/main.dart`: crea un único `FirebaseAuthRepository`, llama a
  `initializeGoogleSignIn` con el Web Client ID del proyecto antes de
  `runApp`, y lo inyecta en `SeguimientoGlucosaApp`/`HomeScreen`.
* Tests: se agregó `_FakeAuthRepository` (en memoria, con
  `StreamController` propio y un flag `failWith` para simular errores)
  en `test/widget_test.dart`, y 5 widget tests nuevos (navegación al
  ícono de Cuenta, registro con correo, inicio de sesión con Google,
  cierre de sesión, mensaje de error legible). Dos de ellos requirieron
  agrandar el tamaño de superficie de la prueba
  (`tester.view.physicalSize`), igual que los tests de Biometría,
  porque el botón "Continuar con Google" queda fuera del viewport por
  defecto.
* Validación completa: `flutter pub get` (agrega `firebase_auth`,
  `google_sign_in` y sus paquetes de plataforma); `dart format` (sin
  cambios); `flutter analyze` (sin issues); `flutter test` (42/42 OK:
  37 anteriores + 5 nuevos); `flutter build apk --debug` compiló
  exitosamente (`√ Built build\app\outputs\flutter-apk\app-debug.apk`),
  confirmando que la integración nativa de Android (Kotlin, Gradle,
  `google-services.json`) funciona en la práctica y no solo en
  análisis estático.
* Nota técnica: el build mostró un warning no fatal de Flutter sobre
  `firebase_auth`/`firebase_core` aplicando su propio Kotlin Gradle
  Plugin (KGP) en lugar del "Built-in Kotlin" que Flutter irá
  exigiendo a futuro; no bloquea el build actual y se resolverá solo
  cuando el equipo de FlutterFire publique versiones compatibles.
* `PROJECT_CONTEXT.md`, `README.md` y `PROJECT_GRAPH.md` actualizados
  (paso #13 del roadmap marcado como hecho).

## 2026-08-19 (7) — Integración base de Firebase

* Decisión de alcance (confirmada con el usuario antes de implementar):
  SQLite sigue siendo el almacenamiento principal de los datos de salud
  (glucosa, comidas, medicamentos, biometría); Firebase se integra solo
  como base/preparación para pasos futuros del roadmap (punto 13,
  autenticación; punto 14, sincronización entre dispositivos). No se
  migra ningún dato ni se usa Firestore/Realtime Database todavía.
* Se creó el proyecto `seguimiento-glucosa` en Firebase Console y se
  ejecutó `flutterfire configure` (CLI `flutterfire_cli` v1.4.1) desde la
  raíz del proyecto, registrando las apps Android e iOS.
* Archivos generados por `flutterfire configure` (versionados
  intencionalmente; son identificadores de cliente, no secretos de
  backend — ver nota en `.gitignore`):
  * `lib/firebase_options.dart` (`DefaultFirebaseOptions`, con las
    opciones Android e iOS del proyecto `seguimiento-glucosa`).
  * `android/app/google-services.json`.
  * `firebase.json` (mapeo de apps FlutterFire).
  * `android/build.gradle.kts` y `android/app/build.gradle.kts`: la CLI
    agregó el plugin `com.google.gms.google-services` (classpath y
    aplicación en `app/build.gradle.kts`, bloque marcado con comentarios
    `START/END: FlutterFire Configuration`).
  * `ios/Runner/GoogleService-Info.plist`: no se generó durante
    `flutterfire configure` (limitación observada al correr la CLI desde
    Windows sin herramientas de Apple disponibles). Se completó aparte
    con `firebase apps:sdkconfig IOS <app-id> --out
    ios/Runner/GoogleService-Info.plist` (Firebase CLI), que descarga la
    configuración ya registrada para la app iOS existente del proyecto
    (mismo `BUNDLE_ID`/`GOOGLE_APP_ID` que en `firebase_options.dart`).
    Como el archivo no quedó automáticamente enlazado al proyecto Xcode
    (`ios/Runner.xcodeproj/project.pbxproj`, que normalmente lo hace
    Xcode o `flutterfire configure` en macOS), se añadió manualmente su
    `PBXFileReference`, `PBXBuildFile` y entrada en la fase de Resources
    del target `Runner`, siguiendo el mismo patrón que
    `Assets.xcassets`/`LaunchScreen.storyboard` ya presentes en el
    archivo. Esto no se pudo verificar abriendo Xcode real (no hay
    macOS disponible en este entorno); se recomienda confirmarlo al
    compilar por primera vez para iOS.
* `pubspec.yaml`: se agregó `firebase_core: ^5.0.0` (única dependencia de
  Firebase añadida en este paso; Auth/Firestore se agregarán en los
  puntos 13/14 del roadmap cuando correspondan).
* `lib/main.dart`: `main()` se convirtió en `Future<void> main() async`,
  con `WidgetsFlutterBinding.ensureInitialized()` y
  `await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform)`
  antes de `runApp`, siguiendo el patrón estándar de inicialización de
  FlutterFire.
* Se requirió activar el **Modo de programador (Developer Mode)** de
  Windows para que `flutter pub get` pudiera crear los symlinks de
  plugins nativos (`firebase_core` añade un plugin con código
  Android/iOS); sin este modo, `flutter pub get` fallaba con "Building
  with plugins requires symlink support."
* `.gitignore`: se agregó una nota explícita documentando que los
  archivos de configuración de Firebase (`firebase_options.dart`,
  `google-services.json`, `GoogleService-Info.plist`) se versionan a
  propósito, y se excluyeron patrones para futuras credenciales de
  servidor (`*serviceAccountKey.json`, `.firebase/`) que no deben
  versionarse si se usan Cloud Functions/Admin SDK más adelante.
* No se tocó ningún repositorio (`GlucoseRepository`, `MealRepository`,
  `MedicationRepository`, `BiometricRepository`) ni `AppDatabase`: la
  persistencia de datos de salud sigue siendo 100% SQLite local, sin
  cambios funcionales para el usuario final en este paso.
* Validación completa: `flutter pub get` (agrega `firebase_core`,
  `firebase_core_platform_interface`, `firebase_core_web`); `dart format`
  (sin cambios); `flutter analyze` (sin issues); `flutter test`
  (37/37 OK, sin cambios respecto al paso anterior — Firebase no afecta
  la lógica de dominio ni los repositorios existentes).
* `PROJECT_CONTEXT.md`, `README.md` y `PROJECT_GRAPH.md` actualizados
  (paso #12 del roadmap marcado como hecho).

## 2026-08-19 (6) — Biometría: presión arterial y frecuencia cardíaca opcionales

* Decisión de alcance (confirmada con el usuario antes de implementar):
  agregar presión arterial y frecuencia cardíaca como campos opcionales
  dentro del mismo registro de peso (no como un tipo de medición
  separado), dejando el IMC pendiente hasta que exista un perfil de
  usuario con altura (ver roadmap, punto 16).
* `lib/models/biometric_measurement.dart`: `BiometricMeasurement` ganó
  los campos opcionales `systolicPressure`, `diastolicPressure` y
  `heartRateBpm` (`int?`), y el getter `hasBloodPressure`. `copyWith`
  ganó parámetros `clearSystolicPressure`/`clearDiastolicPressure`/
  `clearHeartRateBpm` para poder limpiar explícitamente esos campos
  (distinto de "no tocar", que es el comportamiento por defecto al
  omitir el argumento).
* `lib/services/app_database.dart`: `_schemaVersion` subido a `5`; la
  migración (`oldVersion < 5`) agrega `systolic_pressure`,
  `diastolic_pressure` y `heart_rate_bpm` (todas `INTEGER` nullable) a
  `biometric_measurements` mediante `ALTER TABLE ADD COLUMN`; el
  `CREATE TABLE` usado en instalaciones nuevas también las incluye
  directamente.
* `lib/services/biometric_repository.dart`: `SqliteBiometricRepository`
  mapea las tres columnas nuevas en `_fromRow`/`_toRow`.
* `lib/screens/biometric_screen.dart`: el formulario de Registrar ganó
  dos campos opcionales de presión (sistólica/diastólica, en una fila,
  con validación de rango 60-250/30-150 mmHg y de que se completen
  juntas o ninguna) y un campo opcional de frecuencia cardíaca
  (validación 30-220 lpm). El historial muestra "Presión: X/Y mmHg" y
  "Frecuencia cardíaca: Z lpm" cuando existen. El mensaje de guardado
  cambió de "Peso guardado." a "Medición guardada." y el de historial
  vacío de "Todavía no hay pesos registrados." a "Todavía no hay
  mediciones registradas.", para reflejar que el registro ya no es solo
  peso.
* Tests: 2 tests nuevos en `test/services/biometric_repository_test.dart`
  (persistencia de presión/frecuencia cardíaca, y valores `null` cuando
  no se registran) y 2 widget tests nuevos en `test/widget_test.dart`
  (registro con presión y frecuencia cardíaca completas; validación de
  error al completar solo la presión sistólica). Los widget tests de
  Biometría agrandan el tamaño de superficie (`tester.view.physicalSize`)
  porque el formulario ampliado ya no cabe en el tamaño por defecto del
  entorno de pruebas.
* Validación completa: `dart format` (sin cambios); `flutter analyze`
  (sin issues); `flutter test` (37/37 OK: 33 anteriores + 2 del
  repositorio + 2 widget tests nuevos).
* `PROJECT_CONTEXT.md` y `README.md` actualizados (paso #11 del roadmap
  marcado como hecho, con el punto 16 añadido para el IMC pendiente).

## 2026-08-19 (5) — Módulo de Biometría (`BiometricMeasurement`), alcance V1: peso corporal

* Decisión de alcance (recomendada y confirmada con el usuario antes de
  implementar): limitar V1 a peso corporal, dejando presión arterial,
  frecuencia cardíaca e IMC para una iteración futura (IMC requiere
  altura/perfil de usuario, aún no existente). Se usó el modelo simple de
  `GlucoseMeasurement` (un valor por registro) en lugar del modelo
  relacional catálogo+items de Comidas/Medicamentos, porque un peso no
  agrupa múltiples mediciones a la vez.
* `lib/models/biometric_measurement.dart`: modelo inmutable
  `BiometricMeasurement` (`id`, `weightKg`, `measuredAt`, `comment`), con
  `copyWith`/`==`/`hashCode`/`toString` siguiendo el mismo patrón que
  `GlucoseMeasurement`.
* `lib/services/app_database.dart`: `_schemaVersion` subido a `4`; se
  agregó la tabla `biometric_measurements` (`weight_kg REAL`,
  `measured_at`, `comment`), creada tanto en `_createAll` (instalaciones
  nuevas) como en `_upgrade` (rama `oldVersion < 4`, instalaciones
  existentes).
* `lib/services/biometric_repository.dart`: interfaz
  `BiometricRepository` (`getLastMeasurement`, `getAllMeasurements`,
  `addMeasurement`, `clearMeasurements`) e implementación
  `SqliteBiometricRepository` (constructores normal y `.withDatabase`),
  mismo patrón que `SqliteGlucoseRepository`.
* `lib/screens/biometric_screen.dart`: pantalla `BiometricScreen` con
  pestañas Registrar/Historial (misma estructura que `MedicationScreen`);
  formulario con campo numérico "Peso corporal (kg)" (validado entre 20 y
  400 kg) y comentario opcional; historial con tarjetas que muestran el
  peso, fecha/hora y comentario.
* `lib/screens/home_screen.dart`: acepta `biometricRepository` opcional;
  `_biometricRepository` reutiliza la misma `AppDatabase` compartida
  (`.withDatabase`); el botón "Biometría" del menú pasó de decorativo a
  navegar hacia `BiometricScreen`.
* Tests: `test/services/biometric_repository_test.dart` (5 tests) + 2
  widget tests nuevos en `test/widget_test.dart` (navegación a
  `BiometricScreen` y registro de un peso que se refleja en el
  historial).
* Validación completa: `dart format` (sin cambios tras la corrección
  inicial); `flutter analyze` (sin issues); `flutter test` (33/33 OK: 26
  anteriores + 5 del nuevo repositorio + 2 widget tests nuevos).
* `PROJECT_CONTEXT.md` y `README.md` actualizados (paso #10 del roadmap
  marcado como hecho, estructura de carpetas, dependencias y sección de
  pruebas).

## 2026-08-19 (4) — Módulo de Medicamentos (`Medication`/`MedicationIntake`/`MedicationIntakeItem`)

* Decisiones de alcance (confirmadas con el usuario antes de implementar,
  siguiendo el mismo proceso de preguntas que en el módulo de Comidas):
  modelo relacional completo (`MEDICATION`+`MEDICATION_INTAKE`+
  `MEDICATION_INTAKE_ITEM`, análogo a `Food`/`Meal`/`MealFoodItem`, en
  lugar de un registro simple de un medicamento por toma); dosis
  estructurada (cantidad numérica + unidad de un selector), no texto
  libre; enum `DoseUnit` con `milligram`, `milliliter`, `tablet`, `unit`,
  `drop` y `other` (con texto libre complementario en
  `customUnitLabel`/`DoseUnit.other`, único punto donde se admite texto
  libre para la dosis); catálogo `Medication` con `name` +
  `defaultUnit` (a diferencia de `Food`, que solo tiene `name`);
  `MedicationScreen` autocontenida con pestañas propias
  Registrar/Historial, igual patrón que `MealScreen`.
* `lib/models/medication.dart`: enum `DoseUnit` (con extensión `label`) y
  modelo inmutable `Medication` (`id`, `name`, `defaultUnit`).
* `lib/models/medication_intake.dart`: modelos inmutables
  `MedicationIntakeItem` (`id`, `medication`, `quantity` numérica, `unit`,
  `customUnitLabel` opcional, getter `effectiveUnitLabel`) y
  `MedicationIntake` (`id`, `takenAt`, `comment`, `items`), con
  `copyWith`/`==`/`hashCode` siguiendo el mismo patrón que `Meal`.
* `lib/services/app_database.dart`: `_schemaVersion` subido a `3`; se
  agregaron las tablas `medications` (`name` único, `default_unit`),
  `medication_intakes` (`taken_at`, `comment`) y
  `medication_intake_items` (`intake_id` con `ON DELETE CASCADE`,
  `medication_id`, `quantity REAL`, `unit`, `custom_unit_label`), creadas
  tanto en `_createAll` (instalaciones nuevas) como en `_upgrade` (rama
  `oldVersion < 3`, instalaciones existentes).
* `lib/services/medication_repository.dart`: interfaz
  `MedicationRepository` (`getAllIntakes`, `addIntake`, `clearIntakes`,
  `getAllMedications`) e implementación `SqliteMedicationRepository`
  (constructores normal y `.withDatabase`), con el mismo patrón
  transaccional de `SqliteMealRepository`: el catálogo de `Medication` se
  resuelve por nombre (trim-normalizado) dentro de la transacción de
  `addIntake`, reutilizando la fila existente o creándola con su
  `defaultUnit`.
* `lib/screens/medication_screen.dart`: pantalla `MedicationScreen` con
  pestañas Registrar/Historial (idéntica estructura a `MealScreen`);
  formulario con campos Medicamento/Cantidad/selector de Unidad (y un
  campo adicional de texto cuando la unidad es `DoseUnit.other`) más
  comentario opcional; historial con tarjetas que muestran medicamentos,
  cantidad, unidad efectiva, fecha/hora y comentario.
* `lib/screens/home_screen.dart`: acepta `medicationRepository` opcional;
  `_medicationRepository` reutiliza la misma `AppDatabase` compartida
  (`.withDatabase`); el botón "Medicamentos" del menú pasó de decorativo a
  navegar hacia `MedicationScreen`.
* Tests: `test/services/medication_repository_test.dart` (6 tests,
  incluyendo el caso de unidad personalizada `DoseUnit.other`) + 2 widget
  tests nuevos en `test/widget_test.dart` (navegación a
  `MedicationScreen` y registro de una toma con unidad personalizada,
  verificando el selector de `DoseUnit` y el campo de unidad
  personalizada).
* Validación completa: `dart format` (3 archivos reformateados, luego 0
  cambios); `flutter analyze` (sin issues); `flutter test` (26/26 OK: 18
  anteriores + 6 del nuevo repositorio + 2 widget tests nuevos).
* `PROJECT_CONTEXT.md` y `README.md` actualizados (paso #9 del roadmap
  marcado como hecho, estructura de carpetas, dependencias y sección de
  pruebas).

## 2026-08-19 (3) — Módulo de Comidas (`Food`/`Meal`/`MealFoodItem`)

* Decisiones de alcance (confirmadas con el usuario antes de implementar):
  modelo relacional completo (`COMIDA`+`ALIMENTO`+`COMIDA_ALIMENTO`, no una
  versión simplificada); catálogo de `Food` sin información nutricional
  por ahora; cantidad por alimento en texto libre (no gramos
  estandarizados); `MealType` con 5 categorías (Desayuno, Almuerzo,
  Once/Merienda, Cena, Otro/Snack); `MealScreen` autocontenida con
  pestañas propias Registrar/Historial, en lugar de integrarse dentro de
  `HistoryScreen` o depender de una pantalla de historial separada — para
  mantener cada módulo de dominio aislado y testeable a medida que se
  agreguen Medicamentos/Biometría.
* Se creó `lib/services/app_database.dart` (`AppDatabase`): gestor único
  de la conexión SQLite compartida, con `_schemaVersion = 2` y migración
  (`onUpgrade`) que suma las tablas de comidas sobre instalaciones que ya
  tenían solo `glucose_measurements` (versión 1). Activa
  `PRAGMA foreign_keys = ON` para que `ON DELETE CASCADE` funcione.
* `lib/services/glucose_repository.dart` se refactorizó para delegar en
  `AppDatabase` (en lugar de abrir su propia conexión `sqflite`
  directamente), agregando el constructor
  `SqliteGlucoseRepository.withDatabase` para reutilizar una instancia ya
  creada.
* Se crearon `lib/models/food.dart` (`Food`) y `lib/models/meal.dart`
  (`Meal`, `MealFoodItem`, enum `MealType`).
* Se creó `lib/services/meal_repository.dart`: interfaz `MealRepository`
  + `SqliteMealRepository`, sobre las tablas `meals`, `foods` y
  `meal_food_items`; `addMeal` usa una transacción para persistir la
  comida y resolver/crear cada alimento del catálogo de forma atómica.
* Se creó `lib/screens/meal_screen.dart` (`MealScreen`): pestañas
  Registrar (`_MealForm`, con alta dinámica de alimentos+cantidad) e
  Historial (`_MealHistoryList`/`_MealTile`). Al guardar, cambia
  automáticamente a Historial y muestra un `SnackBar` de confirmación.
* `lib/screens/home_screen.dart`: ahora acepta también un
  `MealRepository?` inyectable; agrega una `AppDatabase` compartida
  (`late final`, para no construirse si ambos repositorios llegan
  inyectados en tests) y conecta el botón "Comida" a `MealScreen`.
* Se creó `test/services/meal_repository_test.dart` (5 tests) y se
  añadieron 2 widget tests nuevos en `test/widget_test.dart` (navegación a
  `MealScreen`; registrar una comida con alimentos y verla en su
  historial), con un fake `_FakeMealRepository` en memoria.
* Verificación: `dart format` → 0 cambios; `flutter analyze` → *No issues
  found!*; `flutter test` → *All tests passed!* (18/18: 8 widget tests +
  5 tests de `GlucoseRepository` + 5 tests de `MealRepository`).

## 2026-08-19 (2) — Gráfico de evolución de glucosa (`fl_chart`)

* Decisión: se evaluó la ubicación del gráfico (pantalla independiente,
  vista fija arriba de la lista, o pestañas dentro de `HistoryScreen`); se
  eligió el patrón de pestañas **Lista / Gráfico** dentro de
  `HistoryScreen` (`DefaultTabController` + `TabBar`/`TabBarView`) por ser
  el más usado en apps de salud (Google Fit, Fitbit) y por evitar
  fragmentar la navegación con una pantalla nueva, reutilizando los datos
  ya cargados por `FutureBuilder`.
* Se evaluó la librería de gráficos: se eligió `fl_chart` (`^1.2.0`) sobre
  alternativas por ser 100% Dart (sin dependencias nativas, por lo que es
  totalmente testeable en widget tests sin mocks de plataforma), muy
  madura (1.95M de descargas, 150 puntos en pub.dev) y con buen soporte
  para `LineChart`.
* Se agregó la dependencia `fl_chart: ^1.2.0` a `pubspec.yaml` (sin
  dependencias nativas transitivas: solo `equatable` y `vector_math`,
  ambas Dart puro).
* Se creó `lib/widgets/glucose_line_chart.dart` con el widget
  `GlucoseLineChart`: un `LineChart` que grafica los valores de glucosa
  (mg/dL) ordenados cronológicamente, con dos líneas de referencia
  horizontales punteadas en 70 y 180 mg/dL, tooltip táctil con valor y
  fecha/hora exacta, y etiquetas del eje X con fecha corta (`dd/MM`) con
  intervalo adaptativo para evitar solapamientos.
* `lib/screens/history_screen.dart` se reestructuró para usar
  `DefaultTabController` con dos pestañas: **Lista** (comportamiento
  anterior, extraído a `_MeasurementList`) y **Gráfico**
  (`_MeasurementChart`, que renderiza `GlucoseLineChart` con 2+ mediciones
  o un mensaje explicativo con menos).
* `test/widget_test.dart`: se añadieron 2 tests nuevos (mensaje con menos
  de 2 mediciones; `LineChart` presente con 2 o más), totalizando 6 widget
  tests.
* Verificación: `dart format` → 0 cambios; `flutter analyze` → *No issues
  found!*; `flutter test` → *All tests passed!* (11/11: 6 widget tests + 5
  tests de repositorio).

## 2026-08-19 — Historial de mediciones con SQLite (`sqflite`)

* Decisión: se evaluaron SQLite (`sqflite`) y una lista JSON en
  `shared_preferences` para el historial completo de mediciones; se
  descartó explícitamente usar una nube (Firebase/Firestore) como
  almacenamiento principal, manteniendo el alcance 100% local. Se eligió
  SQLite por rendimiento a largo plazo, soporte de consultas SQL para
  futuros gráficos, y porque evita una migración duplicada cuando se
  implementen los módulos de Comida/Medicamentos/Biometría (ya previstos
  como relacionados entre sí).
* Se reemplazó `shared_preferences` por `sqflite` (`^2.4.4+2`) + `path`
  (`^1.9.1`) en `pubspec.yaml`; se agregó `intl` (`^0.20.3`) para
  formateo de fechas y `sqflite_common_ffi` (`^2.4.4`, dev) para tests.
* `lib/models/glucose_measurement.dart`: se agregó el campo `id` opcional
  (`int?`), asignado por el repositorio al persistir.
* `lib/services/glucose_repository.dart`: se reescribió el contrato
  `GlucoseRepository` (ahora `getLastMeasurement`, `getAllMeasurements`,
  `addMeasurement`, `clearMeasurements`) y se creó
  `SqliteGlucoseRepository`, con una tabla `glucose_measurements` y
  soporte de inyección de `factory`/`databasePath`/`singleInstance` para
  pruebas aisladas en memoria.
* Se creó `lib/screens/history_screen.dart`: lista el historial completo
  vía `FutureBuilder`, con estado de carga, mensaje de "sin datos" y una
  fila por medición (valor, momento, fecha/hora, comentario).
* `HomeScreen` conecta el botón "Historial" (antes decorativo) a
  `HistoryScreen`, y usa `addMeasurement` en lugar de
  `saveLastMeasurement` al guardar.
* `test/widget_test.dart`: el fake en memoria se actualizó al nuevo
  contrato (lista interna en lugar de un único valor); se añadió un
  cuarto test que verifica la navegación a `HistoryScreen` y el listado
  de una medición.
* Se creó `test/services/glucose_repository_test.dart`: 5 tests unitarios
  de `SqliteGlucoseRepository` contra SQLite real en memoria
  (`sqflite_common_ffi`, `databasePath: inMemoryDatabasePath`,
  `singleInstance: false` para aislar cada test).
* Verificación: `dart format` → 0 cambios; `flutter analyze` → *No issues
  found!*; `flutter test` → *All tests passed!* (9/9: 4 widget tests + 5
  tests de repositorio).

## 2026-08-18 — Persistencia local con `shared_preferences`

* Se agregó la dependencia `shared_preferences: ^2.5.6` a `pubspec.yaml`
  (`flutter pub get` ejecutado y verificado en `pubspec.lock`).
* Se creó `lib/services/glucose_repository.dart` con la interfaz
  `GlucoseRepository` y la implementación `SharedPreferencesGlucoseRepository`,
  usando la API moderna `SharedPreferencesAsync` (no la legacy
  `SharedPreferences.getInstance()`).
* `HomeScreen` ahora acepta un `GlucoseRepository?` opcional por
  constructor (inyección de dependencias para tests), carga la última
  medición guardada en `initState` mostrando un indicador de carga breve, y
  persiste cada nueva medición antes de actualizar la tarjeta.
* `test/widget_test.dart` se actualizó para instanciar `HomeScreen`
  directamente con un `_FakeGlucoseRepository` en memoria (en lugar de
  `SeguimientoGlucosaApp`), evitando dependencias del plugin real de
  `shared_preferences` en los widget tests. Se añadió un tercer test que
  verifica que guardar una medición la persiste y actualiza la tarjeta.
* Verificación: `dart format --set-exit-if-changed` → 0 cambios;
  `flutter analyze` → *No issues found!*; `flutter test` →
  *All tests passed!* (3/3).

## 2026-08-17 — Refactor de arquitectura base

* Se corrigió `test/widget_test.dart`: ya no referencia la clase inexistente
  `MyApp`; ahora valida `SeguimientoGlucosaApp`, la tarjeta de glucosa sin
  valor inicial y la navegación hacia `GlucoseScreen`.
* Se creó `lib/models/glucose_measurement.dart` con el modelo inmutable
  `GlucoseMeasurement` y el enum `GlucoseMoment`.
* `GlucoseScreen` ahora usa `Form` + `TextFormField` con validación
  (rango 20–600 mg/dL), reemplazó `DropdownButtonFormField.value` (deprecado)
  por `initialValue`, eliminó las 4 llamadas a `print()` y retorna el
  `GlucoseMeasurement` vía `Navigator.pop(context, measurement)`.
* `HomeScreen` pasó de `StatelessWidget` a `StatefulWidget`: recibe la
  medición devuelta por `GlucoseScreen` y actualiza la tarjeta principal
  mostrando el valor y el momento registrado.
* Se aplicó `dart format` sobre `lib/` y `test/`.
* Verificación: `flutter analyze` → *No issues found!* y `flutter test` →
  *All tests passed!* (2/2).
* Se generó `PROJECT_GRAPH.md` con el grafo de dependencias e imports del
  proyecto.

---

# Instrucciones para Codex

Antes de modificar código:

1. Leer completamente este archivo `PROJECT_CONTEXT.md`.
2. Mantener la arquitectura Flutter existente.
3. No reemplazar la estructura actual sin justificación.
4. Evitar cambios grandes sin explicar impacto.
5. Continuar desde el estado actual del proyecto.
6. Priorizar cambios pequeños y verificables.
7. Mantener separación entre:

   * Pantallas.
   * Modelos.
   * Widgets.
   * Servicios.

El proyecto está en una etapa temprana pero funcional. La prioridad es evolucionar desde la captura actual de glucosa hacia una arquitectura con modelos, persistencia e historial sin perder las decisiones ya tomadas.
