import 'dart:async';

import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_timezone/flutter_timezone.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

import 'notification_service.dart';

/// Implementación de [NotificationService] para iOS (y macOS, que
/// comparte la misma API "Darwin" de `flutter_local_notifications`),
/// para los recordatorios de medición de glucosa post-comida (roadmap
/// punto 17, Fase B).
///
/// A diferencia de [AndroidNotificationService], iOS no distingue entre
/// precisión "exacta" e "inexacta" al programar una notificación: una
/// vez concedido el permiso correspondiente (ver [requestPermission]),
/// el sistema operativo se encarga de entregarla puntualmente aunque la
/// app esté en background o cerrada, sin ningún permiso adicional
/// equivalente a `SCHEDULE_EXACT_ALARM`. Por eso aquí no existe el
/// *fallback* de dos intentos que sí necesita la implementación de
/// Android.
///
/// El permiso de notificaciones en iOS se solicita explícitamente desde
/// [requestPermission] (no durante [initialize]), para que el aviso del
/// sistema aparezca en el momento en que `HomeScreen` lo solicita y no
/// antes; ver `requestAlertPermission`/`requestBadgePermission`/
/// `requestSoundPermission: false` en [DarwinInitializationSettings]
/// más abajo.
class DarwinNotificationService implements NotificationService {
  DarwinNotificationService({FlutterLocalNotificationsPlugin? plugin})
    : _plugin = plugin ?? FlutterLocalNotificationsPlugin();

  final FlutterLocalNotificationsPlugin _plugin;

  final StreamController<void> _tapController =
      StreamController<void>.broadcast();

  bool _initialized = false;

  @override
  Stream<void> get onNotificationTapped => _tapController.stream;

  IOSFlutterLocalNotificationsPlugin? get _iosPlugin => _plugin
      .resolvePlatformSpecificImplementation<
        IOSFlutterLocalNotificationsPlugin
      >();

  @override
  Future<void> initialize() async {
    if (_initialized) {
      return;
    }

    tz_data.initializeTimeZones();
    try {
      final timezoneInfo = await FlutterTimezone.getLocalTimezone();
      tz.setLocalLocation(tz.getLocation(timezoneInfo.identifier));
    } catch (_) {
      // Si no se puede determinar la zona horaria del dispositivo, se
      // sigue con la que `timezone` use por defecto (UTC). Es preferible
      // a dejar la app sin poder programar ninguna notificación.
    }

    await _plugin.initialize(
      settings: const InitializationSettings(
        iOS: DarwinInitializationSettings(
          requestAlertPermission: false,
          requestBadgePermission: false,
          requestSoundPermission: false,
        ),
      ),
      onDidReceiveNotificationResponse: (_) => _tapController.add(null),
    );

    _initialized = true;
  }

  @override
  Future<bool> requestPermission() async {
    await initialize();
    try {
      final granted = await _iosPlugin?.requestPermissions(
        alert: true,
        badge: true,
        sound: true,
      );
      return granted ?? true;
    } catch (_) {
      return false;
    }
  }

  @override
  Future<void> schedule({
    required int id,
    required String title,
    required String body,
    required DateTime scheduledAt,
  }) async {
    await initialize();

    final zonedDate = tz.TZDateTime.from(scheduledAt, tz.local);
    if (!zonedDate.isAfter(tz.TZDateTime.now(tz.local))) {
      // El sistema no permite programar notificaciones en el pasado;
      // si el recordatorio ya venció (por ejemplo, la app estuvo
      // cerrada más de 60/90 minutos), se omite: la reconciliación al
      // reabrir la app y el diálogo in-app siguen cubriendo este caso.
      return;
    }

    const details = NotificationDetails(
      iOS: DarwinNotificationDetails(
        presentAlert: true,
        presentBadge: true,
        presentSound: true,
        interruptionLevel: InterruptionLevel.active,
      ),
    );

    try {
      await _plugin.zonedSchedule(
        id: id,
        title: title,
        body: body,
        scheduledDate: zonedDate,
        notificationDetails: details,
        // Parámetro requerido por la firma multiplataforma de
        // `zonedSchedule`, pero ignorado en iOS (solo lo usa la
        // implementación Android internamente).
        androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
      );
    } catch (_) {
      // Best-effort: si el sistema rechaza la programación (por
      // ejemplo, permiso de notificaciones revocado), el diálogo
      // in-app sigue siendo el respaldo.
    }
  }

  @override
  Future<void> cancel(int id) async {
    try {
      await _plugin.cancel(id: id);
    } catch (_) {
      // Best-effort, ver documentación de la interfaz.
    }
  }
}
