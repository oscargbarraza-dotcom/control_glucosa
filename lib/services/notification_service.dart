/// Contrato para programar y cancelar las notificaciones push locales de
/// los recordatorios de medición de glucosa post-comida (roadmap punto
/// 17, Fase B).
///
/// A diferencia de [MealGlucoseReminderCoordinator] (lógica in-app, sin
/// depender de ningún plugin nativo), esta interfaz sí representa el
/// aviso real del sistema operativo: debe seguir mostrándose aunque la
/// app esté en background o cerrada. Se define como interfaz abstracta
/// para que [MealGlucoseReminderCoordinator] no quede acoplado al
/// plugin `flutter_local_notifications`, siguiendo el mismo patrón ya
/// usado por el resto de repositorios del proyecto (por ejemplo,
/// [GlucoseImportRepository]).
///
/// Todas las implementaciones deben ser "best-effort": si el sistema
/// operativo no puede programar o mostrar una notificación (por
/// ejemplo, el usuario revocó el permiso correspondiente), no deben
/// lanzar una excepción que interrumpa el resto del flujo de la app,
/// ya que el recordatorio in-app (diálogo de [MealGlucoseReminderCoordinator])
/// sigue funcionando como respaldo.
abstract class NotificationService {
  /// Prepara el servicio para poder programar notificaciones.
  ///
  /// Debe llamarse una sola vez, antes de cualquier otro método, y
  /// normalmente desde `main()`. Es seguro llamarlo varias veces: las
  /// llamadas adicionales deben ser no-op.
  Future<void> initialize();

  /// Solicita al usuario los permisos necesarios para mostrar
  /// notificaciones (por ejemplo, `POST_NOTIFICATIONS` en Android 13+).
  ///
  /// Devuelve `true` si el permiso quedó concedido (o ya lo estaba, o
  /// la plataforma no lo requiere). No lanza excepciones: si la
  /// solicitud falla, devuelve `false`.
  Future<bool> requestPermission();

  /// Programa una notificación con [id] único para mostrarse en
  /// [scheduledAt], con [title] y [body] como contenido.
  ///
  /// [id] debe ser estable y reutilizable: programar con el mismo [id]
  /// dos veces reemplaza la notificación anterior en vez de duplicarla
  /// (ver [cancel]). Es responsabilidad de quien llama elegir un [id]
  /// que no colisione con otros usos de la app.
  ///
  /// Si [scheduledAt] ya pasó, la implementación puede mostrar la
  /// notificación de inmediato o simplemente no programarla; ninguno
  /// de los dos comportamientos debe lanzar una excepción.
  Future<void> schedule({
    required int id,
    required String title,
    required String body,
    required DateTime scheduledAt,
  });

  /// Cancela la notificación programada con [id], si existe. No hace
  /// nada (sin lanzar excepciones) si no hay ninguna con ese [id].
  Future<void> cancel(int id);

  /// Emite un evento cada vez que el usuario toca una notificación
  /// mostrada por este servicio mientras la app está corriendo
  /// (foreground o background, no aplica si la app estaba cerrada).
  ///
  /// No identifica qué recordatorio en particular se tocó: quien
  /// escucha este stream (normalmente `HomeScreen`) debe simplemente
  /// volver a revisar todos los recordatorios pendientes (por ejemplo,
  /// con [MealGlucoseReminderCoordinator.reviewPending]), que ya
  /// incluirá el que motivó el toque. Esto evita duplicar la lógica de
  /// mostrar el diálogo de recordatorio en dos lugares distintos.
  ///
  /// Si la app estaba cerrada (terminated) y se abrió al tocar la
  /// notificación, este stream no emite nada para ese toque: el
  /// arranque normal de la app (`HomeScreen.initState`) ya revisa los
  /// recordatorios pendientes, por lo que no se necesita ninguna señal
  /// adicional en ese caso.
  Stream<void> get onNotificationTapped;
}
