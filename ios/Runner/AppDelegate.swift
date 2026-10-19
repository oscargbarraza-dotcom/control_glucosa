import Flutter
import UIKit
import flutter_local_notifications

@main
@objc class AppDelegate: FlutterAppDelegate, FlutterImplicitEngineDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    // Requerido por `flutter_local_notifications` (recordatorios de
    // glucosa post-comida, roadmap punto 17, Fase B) para poder recibir
    // el toque del usuario sobre una notificación y decidir cómo
    // mostrarla mientras la app está en primer plano.
    UNUserNotificationCenter.current().delegate = self as UNUserNotificationCenterDelegate
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  func didInitializeImplicitFlutterEngine(_ engineBridge: FlutterImplicitEngineBridge) {
    // Requerido por `flutter_local_notifications` para que el callback
    // de toque de notificación (`onDidReceiveNotificationResponse`)
    // tenga acceso al registro de plugins también cuando se ejecuta en
    // el isolate de background.
    FlutterLocalNotificationsPlugin.setPluginRegistrantCallback { registry in
      GeneratedPluginRegistrant.register(with: registry)
    }
    GeneratedPluginRegistrant.register(with: engineBridge.pluginRegistry)
  }
}

