# Ficha de Google Play — Seguimiento Glucosa

Contenido redactado para completar la ficha de la app en Google Play
Console (sección **Presencia en Play Store → Ficha principal del
listado** y **Contenido de la app → Clasificación de contenido**).
Este documento es el borrador fuente; la subida final a la consola es
manual (ver punto 10 del checklist de producción en
`PROJECT_CONTEXT.md`).

## 1. Categoría de la app

**Categoría:** Salud y forma física (*Health & Fitness*).

No se usa la categoría "Medicina" porque esa categoría está pensada
para apps de referencia médica/profesional (vademécums, diagnóstico,
etc.); esta app es un diario personal de seguimiento, no una
herramienta clínica ni de diagnóstico (consistente con el disclaimer
ya visible en la app y en `PRIVACY_POLICY.md`).

## 2. Descripción corta (máx. 80 caracteres)

```
Registra tu glucosa, comidas, medicamentos y biometría fácilmente.
```

66 caracteres (validado). Alternativas por si se prefiere otro tono,
todas bajo el límite de 80:

```
Controla tu diabetes: glucosa, comidas, medicamentos y biometría.   (65)
Registra y sigue tu glucosa, comidas, medicamentos y biometría.     (63)
```

## 3. Descripción larga (máx. 4000 caracteres)

```
Seguimiento Glucosa es tu diario personal de salud para registrar y
organizar, en un solo lugar, tus mediciones de glucosa, comidas,
medicamentos y datos biométricos (peso, presión arterial, frecuencia
cardíaca). Pensada para personas con diabetes o prediabetes, y para
quienes cuidan a alguien con esa condición, te ayuda a llevar un
registro ordenado sin depender de papel ni de varias apps distintas.

GLUCOSA
• Registra cada medición en mg/dL junto con el momento (en ayunas,
  antes/después de comer, antes de dormir, etc.) y un comentario
  opcional.
• Consulta tu historial en una lista ordenada por fecha o en un
  gráfico de evolución, con líneas de referencia (70-180 mg/dL) y
  detalle táctil por medición.
• Importa automáticamente mediciones ya registradas por tu sensor o
  CGM compatible a través de Google Health Connect, evitando
  duplicados.

COMIDAS
• Registra qué comiste (desayuno, almuerzo, once, cena o snack), con
  uno o más alimentos, su cantidad y un comentario opcional.
• Revisa el historial completo de comidas registradas.
• Recibe recordatorios automáticos para medir tu glucosa a los 60 y
  90 minutos después de comer, con notificación push incluso con la
  app cerrada.

MEDICAMENTOS
• Registra cada toma con uno o más medicamentos, su dosis y unidad
  (mg, ml, comprimidos, unidades, gotas u otra) y un comentario
  opcional.
• Consulta el historial completo de tomas registradas.

BIOMETRÍA
• Registra tu peso, presión arterial y frecuencia cardíaca en el
  mismo registro.
• Completa tu perfil (altura, fecha de nacimiento, sexo biológico)
  para calcular automáticamente tu IMC en cada registro.

TUS DATOS, BAJO TU CONTROL
• Toda la información se guarda primero en tu propio dispositivo; no
  necesitas crear una cuenta para usar la app.
• Si lo deseas, puedes iniciar sesión (con correo o con Google) para
  respaldar y sincronizar tu historial de forma privada en la nube, y
  recuperarlo en otro dispositivo.
• Puedes eliminar tu cuenta y todos tus datos cuando quieras, desde la
  pantalla Cuenta.
• No mostramos anuncios ni vendemos tus datos de salud a terceros.

Seguimiento Glucosa no es un dispositivo médico ni sustituye el
diagnóstico, tratamiento o consejo de un profesional de la salud. La
información registrada es de uso personal y bajo tu propia
responsabilidad.

Puedes consultar la política de privacidad completa dentro de la app,
desde la pantalla Cuenta.
```

(~2000 caracteres; muy por debajo del límite de 4000, deja margen
para ajustes futuros sin reescribir todo.)

## 4. Clasificación de contenido (cuestionario IARC)

Google Play calcula la clasificación final automáticamente a partir
de un cuestionario que **solo el titular de la cuenta puede
completar** dentro de Play Console (Contenido de la app →
Clasificación de contenido). No se puede subir como texto; estas son
las **respuestas recomendadas** para cada bloque del cuestionario,
según el contenido real de la app:

| Bloque del cuestionario | Respuesta recomendada | Motivo |
|---|---|---|
| Violencia | Ninguna | La app no tiene contenido visual/narrativo de violencia. |
| Sangre/gore | Ninguna | No aplica. |
| Contenido sexual/desnudez | Ninguno | No aplica. |
| Lenguaje soez/grosero | Ninguno | No aplica. |
| Sustancias controladas (alcohol, tabaco, drogas) | No | La app registra **medicamentos recetados** como dato de salud del usuario; no representa, promueve ni hace referencia a consumo de alcohol, tabaco o drogas recreativas/ilegales, que es lo que evalúa este bloque. |
| Apuestas/juego (real o simulado) | No | No aplica. |
| Contenido generado por el usuario compartido públicamente | No | Los registros son privados y, si hay sesión iniciada, solo visibles para el propio usuario autenticado (reglas de Firestore). |
| Interacción entre usuarios (chat, compartir ubicación) | No | La app no tiene chat, mensajería ni comparte ubicación; no hay interacción entre usuarios. |
| Compras digitales / dentro de la app | No | No hay anuncios, compras ni suscripciones (confirmado: no hay dependencias de `google_mobile_ads` ni `in_app_purchase` en `pubspec.yaml`). |
| Terror/temas perturbadores | No | No aplica. |

**Resultado esperado:** al no activarse ningún descriptor, el
cuestionario debería asignar la clasificación más baja disponible en
cada sistema regional (equivalente a **PEGI 3 / ESRB Everyone / USK 0
/ Clasificación general**, "apta para todo público").

## 5. Público objetivo (Target audience / Grupo de edad objetivo)

Recomendación: marcar el grupo de edad objetivo como **adultos (18 y
más)**, y responder **"No"** a si la app está dirigida/orientada a
niños o si puede resultar atractiva principalmente para niños, aunque
el contenido no tenga restricciones de clasificación.

Motivo: la app procesa datos de salud personales (glucosa,
medicamentos, biometría) y requiere registro manual consciente de
esos datos; no está diseñada, ilustrada ni comercializada para
público infantil. Marcarla como "no dirigida a niños" evita que quede
sujeta a las políticas de Google Play Families (diseño, publicidad y
APIs restringidas para apps infantiles), que no aplican ni tienen
sentido para este caso de uso.

## 6. Pendiente (acción manual del titular de la cuenta)

- [ ] Subir categoría, descripción corta y larga en Play Console.
- [ ] Completar el cuestionario de clasificación de contenido (IARC)
      con las respuestas de la sección 4 y confirmar el resultado
      emitido por el sistema.
- [ ] Configurar el público objetivo según la sección 5.
- [ ] Subir las 7 capturas definitivas desde `Capturas/` (no
      trackeadas por git, ver punto 10 del checklist en
      `PROJECT_CONTEXT.md`).
- [ ] Completar el formulario de "Seguridad de los datos" (Data
      safety) en Play Console con base en `PRIVACY_POLICY.md`
      (secciones 2-5): qué datos se recopilan, si se comparten
      (no se comparten con terceros con fines comerciales), si se
      cifran en tránsito (sí, HTTPS/TLS) y si el usuario puede
      solicitar su eliminación (sí, desde la pantalla Cuenta).
