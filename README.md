# _glucosa

Aplicación local para Windows que **consulta y analiza, solo en lectura**, los datos de salud que la app
Android *SeguimientoGlucosa* sincroniza en Firebase Firestore: glucosa, comidas, medicamentos y biometría.

> **Aviso:** las comparaciones y los indicadores son descriptivos. No son un dispositivo médico ni
> sustituyen el consejo de un profesional de la salud.

## Estado

- **Hecho:** base del proyecto, validación de datos, cliente de Firestore de solo lectura, almacenamiento
  local cifrado, **inicio de sesión con Google (OAuth + PKCE) verificado con la cuenta real** y auditoría de
  calidad de datos (`python -m glucosa.audit`).
- **Fase 4 (Glucosa): COMPLETADA (2026-10-27).** Importador de LibreView, base local cifrada, cobertura y TIR
  estimado, y dashboard de Glucosa (filtros, indicadores por fuente, procedencia de las mediciones de Firebase,
  gráfico, distribuciones y tabla), con acceso local protegido y diseño compacto en tema oscuro.
- **Fase D (Alimentación): D2 y D3 cerradas; D4 (interfaz) implementada (2026-10-27)** y a la espera de revisión.
  Datos e indicadores de comidas (D2), asociación de cada comida con la glucosa de sus ventanas, referencia y previa,
  hitos +60/+90 min con tolerancia configurable y coincidencias probables manual ↔ LibreView (D3), y la página
  **Alimentación** (D4): filtros de período, tipo, alimento y fuente, filtros de visualización (disponibilidad y comidas
  aisladas), indicadores de comidas y de mediciones manuales cercanas a +60/+90 (elegibles y pendientes por separado),
  distribuciones, selector de comida individual con su gráfico de −60 a +180 min y tablas detalladas. Es descriptivo:
  no calcula cumplimiento de recordatorios ni atribuye efectos de alimentos sobre la glucosa. Medicamentos, Biometría y
  Configuración son por ahora marcadores. Pendientes para fases posteriores: optimización de gráficos grandes (M-4),
  empaquetado Windows y otros ajustes técnicos. El detalle de decisiones y avance está en
  [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).

## Desarrollo y aplicación final

- **Hoy (desarrollo):** Python + Streamlit + Plotly, ejecutándose en local (`python -m glucosa`) y mostrada en el
  navegador, escuchando solo en `127.0.0.1`. Es la arquitectura válida y vigente.
- **Versión final (requisito definitivo):** aplicación de escritorio para **Windows 11**: acceso directo, ventana
  propia sin barra de direcciones, sin comandos de Python, servidor local que se inicia y se detiene solo, sin
  privilegios de administrador, acceso restringido al equipo local y datos/credenciales fuera de OneDrive.
- El contenedor de escritorio (p. ej. WebView2) **aún no está implementado**: se evaluará y validará después de
  los módulos de datos. No cambia la arquitectura actual. Detalle en la sección 11d de
  [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).

## Requisitos

- Windows 10/11 y Python 3.12 o superior (probado con 3.14).
- Una cuenta que ya use SeguimientoGlucosa en el celular (mismo proyecto Firebase).

## Instalación

El entorno virtual se crea **fuera de OneDrive** (el proyecto vive en OneDrive y sincronizaría miles de
archivos innecesarios):

```powershell
$env:GLUCOSA_VENV = "$env:LOCALAPPDATA\glucosa\venv"
python -m venv $env:GLUCOSA_VENV
& "$env:GLUCOSA_VENV\Scripts\python" -m pip install -r requirements-dev.txt
& "$env:GLUCOSA_VENV\Scripts\python" -m pip install -e .
```

## Configuración

1. Copia `.env.example` a `%LOCALAPPDATA%\glucosa\.env` (crea la carpeta si no existe). Esa carpeta
   está fuera de OneDrive; durante el desarrollo también se lee un `.env` en la raíz del proyecto, pero
   ese archivo se sincronizaría a OneDrive, así que evítalo para valores reales. `.env` está en
   `.gitignore`.
2. Completa `GLUCOSA_FIREBASE_API_KEY` con la API key de la **app web de Windows** del proyecto Firebase
   (Consola de Firebase → Configuración del proyecto → Tus apps). Es un identificador de cliente
   público, no una credencial de administrador.
3. Guarda el JSON del cliente OAuth de escritorio (descargado de Google Cloud) en una carpeta privada
   **fuera de OneDrive**, por ejemplo `%LOCALAPPDATA%\glucosa\secrets\oauth_client.json`, y pon solo su
   **ruta** en `GLUCOSA_OAUTH_CLIENT_FILE`. No copies `client_id` ni `client_secret` a ningún otro archivo.
4. Comprueba la configuración (no muestra secretos):

   ```powershell
   & "$env:LOCALAPPDATA\glucosa\venv\Scripts\python" -m glucosa.check
   ```

### Qué no hacer

- No copies a este proyecto `google-services.json`, claves de servicio ni nada del proyecto Android.
- No uses Firebase Admin SDK ni credenciales de administrador: se saltan las reglas de seguridad.
- No guardes datos de salud ni credenciales dentro de esta carpeta: está en OneDrive. Los datos locales
  se guardan, cifrados, en `%LOCALAPPDATA%\glucosa`.
- Úsala en un equipo de un solo usuario: la interfaz local no tiene contraseña propia.

## Sesión con Google

```powershell
$py = "$env:LOCALAPPDATA\glucosa\venv\Scripts\python"
& $py -m glucosa.login login    # abre el navegador, inicia sesión y verifica la lectura de Firestore
& $py -m glucosa.login status   # restaura la sesión guardada (sin navegador) y repite la verificación
& $py -m glucosa.login logout   # borra la sesión guardada
& $py -m glucosa.login compare-uid   # compara el UID de la sesión con el de Firebase Console (pide el UID)
```

La verificación solo **cuenta** documentos por colección (consultas de agregación, solo lectura); no
descarga ni muestra datos de salud. En el Administrador de credenciales de Windows se guarda únicamente el
`uid` y el refresh token de Firebase; los tokens de Google no se almacenan.

## Importar un CSV de LibreView

Descarga el CSV desde LibreView (español) y, desde la carpeta del proyecto:

```powershell
& "$env:LOCALAPPDATA\glucosa\venv\Scripts\python" -m glucosa.libre_import "C:\ruta\al\archivo.csv"
```

- Lee el CSV (nunca lo modifica ni lo borra) y consolida las lecturas en una base **cifrada** en
  `%LOCALAPPDATA%\glucosa\data\libre.db.enc` (fuera de OneDrive; la ruta dentro de OneDrive se rechaza).
- Es **incremental e idempotente**: puedes importar exportaciones que se solapen y repetir el mismo archivo sin
  duplicar nada. Muestra un resumen con nuevos, repetidos, inválidos (con motivo, p. ej. `HI`/`LO`) y conflictos.
- Solo se guardan las lecturas de glucosa (historial y escaneos). Alimentos, notas, el nombre del paciente y el
  número de serie del dispositivo **no** se guardan.
- Guarda tus CSV originales: son la fuente de verdad.

### Si pierdes la clave o la base se daña

La base se puede reconstruir siempre: cierra la aplicación, borra `libre.db.enc` de
`%LOCALAPPDATA%\glucosa\data` y vuelve a importar tus CSV de LibreView. Si el mensaje dice que el archivo está
«en uso», solo reintenta en unos segundos (no borres nada).

## Uso

```powershell
& "$env:LOCALAPPDATA\glucosa\venv\Scripts\python" -m glucosa
```

Abre la interfaz en el navegador, escuchando solo en `127.0.0.1` (no accesible desde la red).
Antes, inicia sesión una vez con `python -m glucosa.login login`.

**Acceso protegido:** el lanzador elige un puerto libre al azar, genera un token nuevo en cada ejecución, abre tu
navegador con un enlace que lo incluye y, al cerrarlo (Ctrl+C), detiene el servidor y sus procesos. Quien abra el
puerto sin ese token (otro programa o usuario del equipo) ve solo «Acceso no autorizado»: no se lee ningún dato
ni se puede importar nada. No abras la aplicación con `streamlit run` directamente (queda bloqueada a propósito).
Sigue siendo para un equipo de un solo usuario; ver las amenazas que quedan fuera en la sección 11e.3 de
[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).

### Página Glucosa

- **Diseño:** tema oscuro compacto, pensado para Full HD y que se adapta a ventanas menores. Arriba, una línea con
  el período, el rango objetivo y el estado y la última actualización de Firebase (consulta) y LibreView
  (importación); el detalle está en «Detalle de las fuentes».
- **Filtros** (barra lateral): período (hoy, 7/30 días, 3/6/12 meses o rango personalizado), fuente, momento
  declarado (un selector compacto con «Seleccionar todos» y «Limpiar selección», incluida la opción «Sin momento
  declarado»), clasificación y rango objetivo (70–180 mg/dL por defecto; se puede guardar).
- **Indicadores:** una fila de tarjetas por fuente (violeta = Firebase, azul = LibreView) y, debajo, las dos
  distribuciones por rango lado a lado. La tabla de detalle muestra «Registros mostrados: N de M».
- **Dos bloques separados:** 🟣 mediciones manuales (Firebase) y 🔵 sensor FreeStyle Libre (LibreView). El
  porcentaje de las manuales es «porcentaje de mediciones», no tiempo en rango. El tiempo en rango del sensor
  es **estimado** a partir del CSV y siempre muestra su cobertura; con menos de 70 % de cobertura se informa
  «datos insuficientes».
- **Gráfico:** rombos violeta (manuales), línea azul (historial del sensor, cortada donde hay más de 30 min sin
  datos) y círculos grises opcionales (escaneos, apagados por defecto).
- **Procedencia en Firebase:** las mediciones manuales y las marcadas «Importado desde otra aplicación» se
  muestran en bloques separados; las importadas nunca se mezclan con las manuales ni se tratan como lecturas del
  sensor.
- **Frescura:** «Última consulta exitosa a Firebase» (cuándo leyó la aplicación) es distinta de «Última medición
  disponible» y no confirma una sincronización desde el teléfono.
- **Escaneos:** ocultos por defecto en el gráfico y la tabla; un solo control los muestra. No entran al TIR.
- **Sin descargas:** la interfaz no ofrece exportar tablas ni imágenes (evita dejar datos de salud en Descargas,
  que puede sincronizarse con OneDrive).
- **Importar un CSV de LibreView:** también se puede hacer desde la propia página (sección «Importar un CSV de
  LibreView»).
- Los filtros de clasificación y momento afectan al gráfico y la tabla; los indicadores describen siempre el
  período completo.

## Pruebas

```powershell
& "$env:LOCALAPPDATA\glucosa\venv\Scripts\python" -m pytest --cov=src/glucosa --cov-report=term-missing
& "$env:LOCALAPPDATA\glucosa\venv\Scripts\python" -m ruff check src tests
```

Las pruebas no usan red, credenciales ni datos reales.

## Seguridad y privacidad

- Solo lectura: no hay código que escriba en Firestore ni en la base de Android.
- La lectura usa el token del propio usuario, por lo que aplican las reglas de Firestore existentes
  (cada usuario solo accede a `users/{su-uid}/...`).
- El refresh token vive en el Administrador de credenciales de Windows; los datos locales y los ajustes
  (rango objetivo, altura) están cifrados.

## Estructura

Ver la sección "Arquitectura" de [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).
