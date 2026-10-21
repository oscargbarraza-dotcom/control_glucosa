import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';

import 'firebase_options.dart';
import 'screens/cloud_viewer_screen.dart';
import 'screens/home_screen.dart';
import 'screens/splash_screen.dart';
import 'services/android_notification_service.dart';
import 'services/darwin_notification_service.dart';
import 'services/firebase_auth_repository.dart';
import 'services/firestore_cloud_sync_viewer.dart';
import 'services/notification_service.dart';

/// Web Client ID del proyecto Firebase `seguimiento-glucosa`, generado
/// automáticamente al habilitar el proveedor Google en Firebase Auth
/// (visible en `android/app/google-services.json`, bloque `oauth_client`
/// con `client_type: 3`). Es el mismo valor para Android e iOS: Google
/// Sign-In lo usa para emitir un ID token verificable por Firebase,
/// independientemente del cliente nativo (Android/iOS) que inició el
/// flujo de autenticación. No es un secreto: es un identificador público
/// de cliente OAuth, al igual que el resto de `firebase_options.dart`.
const String _googleSignInServerClientId =
    '371154041496-p2aekm10mkqjvpitmof0pvo3rkc7m8cs.apps.googleusercontent.com';

/// `google_sign_in` solo tiene implementación de plataforma para Android,
/// iOS, macOS y Web (ver https://pub.dev/packages/google_sign_in): en
/// Windows y Linux no hay ningún `GoogleSignInPlatform` registrado, por lo
/// que `GoogleSignIn.instance.initialize()` lanza `UnimplementedError` en
/// esas plataformas. Evitamos llamarlo ahí para no crashear la app al
/// arrancar. Además, [FirebaseAuthRepository.supportsGoogleSignIn] permite
/// a [AuthScreen] ocultar el botón en plataformas no compatibles; la guarda
/// defensiva de `signInWithGoogle` conserva un error legible si el método se
/// invoca directamente de todas formas.
bool get _supportsGoogleSignIn =>
    Platform.isAndroid || Platform.isIOS || Platform.isMacOS;

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);

  final authRepository = FirebaseAuthRepository();
  if (_supportsGoogleSignIn) {
    await authRepository.initializeGoogleSignIn(
      serverClientId: _googleSignInServerClientId,
    );
  }

  runApp(
    SeguimientoGlucosaApp(
      authRepository: authRepository,
      notificationService: _createNotificationService(),
    ),
  );
}

/// Elige la implementación de [NotificationService] correspondiente a
/// la plataforma en ejecución (roadmap punto 17, Fase B).
///
/// `flutter_local_notifications` es la misma dependencia en ambos
/// casos; lo que cambia es la API nativa que envuelve cada
/// implementación (`AndroidNotificationService` vs
/// `DarwinNotificationService`, esta última también válida para
/// macOS). En cualquier otra plataforma (web, desktop no soportado)
/// devuelve `null`: la app sigue funcionando solo con el diálogo
/// in-app de la Fase A.
NotificationService? _createNotificationService() {
  if (Platform.isAndroid) {
    return AndroidNotificationService();
  }
  if (Platform.isIOS) {
    return DarwinNotificationService();
  }
  return null;
}

/// Punto de entrada de la aplicación Seguimiento Glucosa.
///
/// Configura el [MaterialApp] y carga [HomeScreen] como pantalla inicial.
class SeguimientoGlucosaApp extends StatelessWidget {
  const SeguimientoGlucosaApp({
    super.key,
    this.authRepository,
    this.notificationService,
  });

  /// Repositorio de autenticación ya inicializado (con Google Sign-In
  /// configurado). Si es `null`, [HomeScreen] crea el suyo por defecto;
  /// se usa `null` en los widget tests que inyectan un fake propio.
  final FirebaseAuthRepository? authRepository;

  /// Servicio de notificaciones push locales para los recordatorios de
  /// glucosa post-comida (roadmap punto 17, Fase B). Se usa `null` en
  /// los widget tests, que no deben tocar el plugin nativo
  /// `flutter_local_notifications`.
  final NotificationService? notificationService;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Seguimiento Glucosa',
      theme: _buildTheme(),
      home: SplashScreen(
        nextScreenBuilder: (context) => _homeForCurrentPlatform(),
      ),
    );
  }

  /// Tema de la app: azul "concienciación de diabetes" como color base
  /// (coherente con el icono y el splash, ver
  /// `tool/generate_icon_assets.py`), con rojo como color secundario
  /// reservado para la gota/alertas de glucosa.
  ThemeData _buildTheme() {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: const Color(0xFF0D47A1),
      secondary: Colors.red,
    );
    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: const Color(0xFFF2F6FC),
      appBarTheme: AppBarTheme(
        backgroundColor: colorScheme.primary,
        foregroundColor: Colors.white,
        centerTitle: true,
        elevation: 0,
      ),
      cardTheme: CardThemeData(
        elevation: 3,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: colorScheme.primary,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
    );
  }

  /// En Windows y macOS la app es un visor de **solo lectura** del
  /// historial sincronizado en la nube (ver "Sincronización en tiempo
  /// real" en `PROJECT_CONTEXT.md`): no hay ningún formulario de
  /// registro, ni almacenamiento local, en esas plataformas. En
  /// Android/iOS se mantiene [HomeScreen] completo, con sincronización
  /// automática habilitada (`enableCloudSync`).
  ///
  /// Linux queda fuera de ambos casos (cae en la rama de [HomeScreen])
  /// porque ni `firebase_auth` ni `cloud_firestore` tienen soporte
  /// oficial ahí: seguirá funcionando sobre SQLite local, pero sin
  /// sincronización en la nube.
  Widget _homeForCurrentPlatform() {
    if (Platform.isWindows || Platform.isMacOS) {
      return CloudViewerScreen(
        authRepository: authRepository ?? FirebaseAuthRepository(),
        syncViewer: FirestoreCloudSyncViewer(),
      );
    }
    return HomeScreen(
      authRepository: authRepository,
      enableCloudSync: true,
      enableHealthImport: true,
      enableMealReminders: true,
      notificationService: notificationService,
    );
  }
}
