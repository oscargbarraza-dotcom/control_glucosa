# Política de privacidad — Seguimiento Glucosa

**Última actualización: 22 de octubre de 2026**

Esta política describe qué datos recopila, almacena y comparte la
aplicación **Seguimiento Glucosa** (desarrollada por OGB), y qué
opciones tienes sobre esos datos.

> **Aviso importante:** Seguimiento Glucosa no es un dispositivo
> médico ni sustituye el diagnóstico, tratamiento o asesoramiento de
> un profesional de la salud. La información registrada es de uso
> personal y bajo tu propia responsabilidad.

## 1. Quién trata tus datos

Responsable: OGB. Contacto para cualquier consulta sobre privacidad,
tus datos o esta política: **oscargbarraza@gmail.com**.

## 2. Qué datos recopila la app

La app está diseñada para que puedas usarla completamente **sin
crear una cuenta**. Los datos que recopila dependen de qué módulos
uses:

* **Datos de salud que tú ingresas manualmente**: mediciones de
  glucosa (valor, momento del día, fecha/hora, comentario opcional),
  comidas (tipo, alimentos, cantidad, comentario), tomas de
  medicamentos (medicamento, dosis, unidad, comentario) y mediciones
  biométricas (peso, presión arterial, frecuencia cardíaca,
  comentario).
* **Perfil de usuario (opcional)**: altura, fecha de nacimiento, sexo
  biológico y nombre a mostrar, usados únicamente para calcular tu
  IMC dentro de la app.
* **Datos de salud importados desde el sistema operativo
  (opcional)**: si lo autorizas explícitamente, la app puede leer
  mediciones de glucosa ya existentes en Google Health Connect
  (Android) o Apple Salud/HealthKit (iOS) para evitar que las
  registres dos veces. La app **solo lee** estos datos; nunca escribe
  ni modifica nada en Health Connect o en Salud de Apple.
* **Datos de cuenta (opcional)**: si decides iniciar sesión (con
  correo/contraseña o con Google), se usa tu correo electrónico y,
  si inicias sesión con Google, tu nombre y foto de perfil públicos
  de Google, únicamente para identificar tu cuenta.
* **Copia de respaldo en la nube (opcional)**: solo si tienes sesión
  iniciada, tu historial (glucosa, comidas, medicamentos, biometría)
  se guarda también en Cloud Firestore (Google Firebase), asociado
  exclusivamente a tu cuenta.

La app **no** recopila ubicación, contactos, identificadores
publicitarios, ni utiliza analítica de comportamiento o publicidad de
terceros.

## 3. Dónde se almacenan tus datos

* **Almacenamiento principal: tu dispositivo.** Todo lo que registras
  se guarda localmente en una base de datos SQLite dentro de tu
  teléfono. Si nunca inicias sesión, tus datos nunca salen de tu
  dispositivo.
* **Almacenamiento en la nube (opcional): Google Firebase
  (Firestore)**, solo si inicias sesión. Cada usuario solo puede leer
  y escribir sus propios datos (reglas de seguridad de Firestore
  aplicadas a nivel de servidor); nadie más, ni siquiera otro usuario
  autenticado, puede acceder a tus datos.
* La sincronización con la nube es manual (no en tiempo real):
  decides cuándo respaldar o fusionar tu historial desde la pantalla
  de Cuenta.

## 4. Con quién se comparten tus datos

* **No vendemos ni compartimos tus datos de salud con terceros** con
  fines comerciales o publicitarios.
* Usamos los siguientes proveedores únicamente como infraestructura
  técnica para hacer funcionar la app (encargados de tratamiento):
  * **Google Firebase** (Authentication y Cloud Firestore), para el
    inicio de sesión opcional y el respaldo en la nube opcional.
  * **Google Health Connect** / **Apple HealthKit**, solo si
    autorizas la importación de mediciones ya existentes en tu
    dispositivo; la app únicamente lee esos datos, no los envía a
    ningún servidor.
* No usamos ningún puente o integración no oficial de terceros para
  obtener datos de sensores de glucosa (CGM). Evaluamos
  explícitamente esa posibilidad y decidimos no incluirla en la app
  por razones de seguridad y de cumplimiento de los términos de
  servicio de los fabricantes de sensores (ver detalle técnico
  público en el repositorio del proyecto).

## 5. Permisos que solicita la app y para qué

* **Lectura de glucosa en Health Connect** (Android,
  `android.permission.health.READ_BLOOD_GLUCOSE`): para importar
  mediciones ya registradas por tu sensor/CGM compatible, evitando
  que las ingreses manualmente dos veces. Solo lectura.
* **Lectura de datos de Salud** (iOS,
  `NSHealthShareUsageDescription`): mismo propósito que el permiso
  anterior, en Apple Health. La app nunca escribe en Salud
  (`NSHealthUpdateUsageDescription` explica que no se escriben
  datos).
* **Notificaciones** (`POST_NOTIFICATIONS` en Android 13+): para
  mostrarte recordatorios locales de medir tu glucosa después de
  registrar una comida, si activas esa función. Las notificaciones se
  generan y procesan enteramente en tu dispositivo.
* **Alarmas exactas y reinicio** (`SCHEDULE_EXACT_ALARM`,
  `RECEIVE_BOOT_COMPLETED` en Android): para que los recordatorios de
  medición sigan funcionando con precisión y sobrevivan a un reinicio
  del teléfono.

Todos estos permisos son opcionales: puedes rechazarlos y seguir
usando el resto de la app con registro manual.

## 6. Cuánto tiempo conservamos tus datos

Tus datos se conservan mientras uses la app y, si tienes sesión
iniciada, mientras mantengas tu cuenta activa. Puedes eliminar tus
datos locales desinstalando la app, y puedes solicitar la eliminación
de tu cuenta y de tu copia en la nube escribiendo a
**oscargbarraza@gmail.com** (ver también la sección de derechos más
abajo).

## 7. Tus derechos

De acuerdo con la Ley N.° 19.628 sobre protección de la vida privada
(Chile) y como buena práctica general, puedes en cualquier momento:

* Acceder a los datos que tenemos sobre ti.
* Solicitar la corrección de datos inexactos.
* Solicitar la eliminación de tu cuenta y de todos tus datos
  almacenados en la nube.
* Retirar tu consentimiento para el uso de la nube en cualquier
  momento (cerrando sesión; tus datos locales no se ven afectados).

Para ejercer cualquiera de estos derechos, escribe a
**oscargbarraza@gmail.com**.

## 8. Menores de edad

La app no está dirigida específicamente a menores de edad y no
recopila a sabiendas datos de menores sin el consentimiento de un
adulto responsable.

## 9. Seguridad

Los datos en la nube se transmiten cifrados (HTTPS/TLS) y se
protegen mediante reglas de seguridad de Firestore que restringen el
acceso exclusivamente al propio usuario autenticado. Los datos
locales dependen de los mecanismos de seguridad propios de tu
dispositivo (bloqueo de pantalla, cifrado del sistema operativo).

## 10. Cambios a esta política

Si esta política cambia de forma relevante, actualizaremos la fecha
al inicio de este documento. Te recomendamos revisarla periódicamente.

## 11. Contacto

Para cualquier consulta sobre esta política o sobre tus datos:
**oscargbarraza@gmail.com**.
