import 'dart:async';

import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_timezone/flutter_timezone.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

import 'notification_service.dart';

/// Implementación de [NotificationService] basada en
/// `flutter_local_notifications`, para los recordatorios de medición de
/// glucosa post-comida (roadmap punto 17, Fase B).
///
/// Intenta programar cada notificación con precisión exacta
/// ([AndroidScheduleMode.exactAllowWhileIdle]); si el permiso de
/// alarmas exactas no está concedido (`SCHEDULE_EXACT_ALARM`, revocable
/// por el usuario en Ajustes desde Android 12), hace *fallback*
/// automático a [AndroidScheduleMode.inexactAllowWhileIdle] en lugar de
/// fallar, ya que el sistema puede retrasar unos minutos la entrega
/// pero la notificación sigue llegando.
class AndroidNotificationService implements NotificationService {
  AndroidNotificationService({FlutterLocalNotificationsPlugin? plugin})
    : _plugin = plugin ?? FlutterLocalNotificationsPlugin();

  /// Identificador y nombre del canal usado por todos los recordatorios
  /// de glucosa post-comida. Un solo canal es suficiente: todas estas
  /// notificaciones comparten la misma importancia y comportamiento, y
  /// el usuario puede silenciarlas/personalizarlas en bloque desde los
  /// ajustes nativos de Android.
  static const _channelId = 'meal_glucose_reminders';
  static const _channelName = 'Recordatorios de glucosa post-comida';
  static const _channelDescription =
      'Avisos para medir tu glucosa 60 y 90 minutos después de comer.';

  final FlutterLocalNotificationsPlugin _plugin;

  final StreamController<void> _tapController =
      StreamController<void>.broadcast();

  bool _initialized = false;

  @override
  Stream<void> get onNotificationTapped => _tapController.stream;

  AndroidFlutterLocalNotificationsPlugin? get _androidPlugin => _plugin
      .resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin
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
        android: AndroidInitializationSettings('@mipmap/ic_launcher'),
      ),
      onDidReceiveNotificationResponse: (_) => _tapController.add(null),
    );

    await _androidPlugin?.createNotificationChannel(
      const AndroidNotificationChannel(
        _channelId,
        _channelName,
        description: _channelDescription,
        importance: Importance.high,
      ),
    );

    _initialized = true;
  }

  @override
  Future<bool> requestPermission() async {
    try {
      final granted = await _androidPlugin?.requestNotificationsPermission();
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
      android: AndroidNotificationDetails(
        _channelId,
        _channelName,
        channelDescription: _channelDescription,
        importance: Importance.high,
        priority: Priority.high,
      ),
    );

    try {
      await _plugin.zonedSchedule(
        id: id,
        title: title,
        body: body,
        scheduledDate: zonedDate,
        notificationDetails: details,
        androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
      );
    } catch (_) {
      // Falla típica: permiso de alarma exacta no concedido. Se
      // reintenta con precisión relajada en vez de perder el
      // recordatorio por completo.
      try {
        await _plugin.zonedSchedule(
          id: id,
          title: title,
          body: body,
          scheduledDate: zonedDate,
          notificationDetails: details,
          androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
        );
      } catch (_) {
        // Best-effort: si ni siquiera la programación inexacta
        // funciona, el diálogo in-app sigue siendo el respaldo.
      }
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
