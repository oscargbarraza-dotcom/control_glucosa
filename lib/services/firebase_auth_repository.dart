import 'package:firebase_auth/firebase_auth.dart' as fb_auth;
import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';

import '../models/app_user.dart';
import 'auth_repository.dart';

/// Implementación de [AuthRepository] basada en Firebase Auth, con
/// inicio de sesión por correo/contraseña y por Google (`google_sign_in`).
///
/// El `serverClientId`/`clientId` de Google (el "Web client ID" generado
/// por Firebase al habilitar el proveedor Google) se recibe por
/// constructor en lugar de leerse de un archivo, para no acoplar esta
/// clase a `google-services.json` y poder probarla con un
/// [GoogleSignIn] inyectado en tests de integración manuales.
class FirebaseAuthRepository implements AuthRepository {
  FirebaseAuthRepository({
    fb_auth.FirebaseAuth? firebaseAuth,
    GoogleSignIn? googleSignIn,
  }) : _firebaseAuth = firebaseAuth ?? fb_auth.FirebaseAuth.instance,
       _googleSignIn = googleSignIn ?? GoogleSignIn.instance;

  final fb_auth.FirebaseAuth _firebaseAuth;
  final GoogleSignIn _googleSignIn;

  bool _googleSignInInitialized = false;

  /// Inicializa el SDK de Google Sign-In una sola vez, con el
  /// `serverClientId` (Web client ID) del proyecto Firebase. En una
  /// plataforma no compatible no realiza ninguna operación. Debe llamarse
  /// antes del primer [signInWithGoogle]; ver `lib/main.dart`, donde se
  /// invoca junto con `Firebase.initializeApp`.
  Future<void> initializeGoogleSignIn({required String serverClientId}) async {
    if (!supportsGoogleSignIn || _googleSignInInitialized) {
      return;
    }
    await _googleSignIn.initialize(serverClientId: serverClientId);
    _googleSignInInitialized = true;
  }

  @override
  Stream<AppUser?> authStateChanges() {
    return _firebaseAuth.authStateChanges().map(_toAppUser);
  }

  @override
  AppUser? get currentUser => _toAppUser(_firebaseAuth.currentUser);

  @override
  bool get supportsGoogleSignIn =>
      kIsWeb ||
      defaultTargetPlatform == TargetPlatform.android ||
      defaultTargetPlatform == TargetPlatform.iOS ||
      defaultTargetPlatform == TargetPlatform.macOS;

  @override
  Future<AppUser> registerWithEmail({
    required String email,
    required String password,
  }) async {
    try {
      final credential = await _firebaseAuth.createUserWithEmailAndPassword(
        email: email,
        password: password,
      );
      return _requireAppUser(credential.user);
    } on fb_auth.FirebaseAuthException catch (e) {
      throw AuthException(_messageForCode(e.code));
    }
  }

  @override
  Future<AppUser> signInWithEmail({
    required String email,
    required String password,
  }) async {
    try {
      final credential = await _firebaseAuth.signInWithEmailAndPassword(
        email: email,
        password: password,
      );
      return _requireAppUser(credential.user);
    } on fb_auth.FirebaseAuthException catch (e) {
      throw AuthException(_messageForCode(e.code));
    }
  }

  @override
  Future<AppUser?> signInWithGoogle() async {
    if (!supportsGoogleSignIn) {
      throw const AuthException(
        'Iniciar sesión con Google no está disponible en esta plataforma. '
        'Usa correo y contraseña.',
      );
    }

    GoogleSignInAccount account;
    try {
      account = await _googleSignIn.authenticate();
    } on GoogleSignInException catch (e) {
      if (e.code == GoogleSignInExceptionCode.canceled) {
        return null;
      }
      throw const AuthException(
        'No se pudo iniciar sesión con Google. Intenta nuevamente.',
      );
    } on UnimplementedError {
      // `google_sign_in` no tiene implementación de plataforma en
      // Windows ni Linux (ver `main.dart`, `_supportsGoogleSignIn`):
      // ahí ni siquiera se llamó `initialize()`, así que `authenticate()`
      // lanza este error en lugar de uno de `GoogleSignInException`.
      throw const AuthException(
        'Iniciar sesión con Google no está disponible en esta plataforma. '
        'Usa correo y contraseña.',
      );
    }

    final idToken = account.authentication.idToken;
    if (idToken == null) {
      throw const AuthException(
        'No se pudo iniciar sesión con Google. Intenta nuevamente.',
      );
    }

    try {
      final googleCredential = fb_auth.GoogleAuthProvider.credential(
        idToken: idToken,
      );
      final credential = await _firebaseAuth.signInWithCredential(
        googleCredential,
      );
      return _requireAppUser(credential.user);
    } on fb_auth.FirebaseAuthException catch (e) {
      throw AuthException(_messageForCode(e.code));
    }
  }

  @override
  Future<void> sendPasswordResetEmail(String email) async {
    try {
      await _firebaseAuth.sendPasswordResetEmail(email: email);
    } on fb_auth.FirebaseAuthException catch (e) {
      throw AuthException(_messageForCode(e.code));
    }
  }

  @override
  Future<void> signOut() async {
    await _firebaseAuth.signOut();
    if (!supportsGoogleSignIn) {
      return;
    }
    try {
      await _googleSignIn.signOut();
    } on UnimplementedError {
      // Guarda defensiva por si falla el registro de la implementación
      // federada en una plataforma que nominalmente declara soporte.
    }
  }

  @override
  Future<void> deleteAccount() async {
    final user = _firebaseAuth.currentUser;
    if (user == null) {
      throw const AuthException(
        'No hay ninguna sesión iniciada para eliminar.',
      );
    }
    try {
      await user.delete();
    } on fb_auth.FirebaseAuthException catch (e) {
      if (e.code == 'requires-recent-login') {
        throw const AuthException(
          'Por seguridad, cierra sesión, vuelve a iniciarla y luego '
          'intenta eliminar tu cuenta nuevamente.',
        );
      }
      throw AuthException(_messageForCode(e.code));
    }
    if (supportsGoogleSignIn) {
      try {
        await _googleSignIn.signOut();
      } catch (_) {
        // La cuenta de Firebase ya fue eliminada de forma irreversible.
        // Cerrar la sesión local del proveedor es best-effort: un fallo
        // del plugin no debe convertir una eliminación exitosa en un
        // error ni impedir que continúe el borrado local opcional.
      }
    }
  }

  AppUser _requireAppUser(fb_auth.User? user) {
    final appUser = _toAppUser(user);
    if (appUser == null) {
      throw const AuthException(
        'No se pudo completar la autenticación. Intenta nuevamente.',
      );
    }
    return appUser;
  }

  AppUser? _toAppUser(fb_auth.User? user) {
    if (user == null) {
      return null;
    }
    return AppUser(
      uid: user.uid,
      email: user.email,
      displayName: user.displayName,
    );
  }

  /// Traduce los códigos de [fb_auth.FirebaseAuthException] a mensajes en
  /// español, legibles para el usuario final, sin exponer detalles
  /// internos del SDK.
  String _messageForCode(String code) {
    switch (code) {
      case 'email-already-in-use':
        return 'Ya existe una cuenta registrada con ese correo.';
      case 'invalid-email':
        return 'El correo ingresado no es válido.';
      case 'weak-password':
        return 'La contraseña debe tener al menos 6 caracteres.';
      case 'user-not-found':
      case 'wrong-password':
      case 'invalid-credential':
        return 'Correo o contraseña incorrectos.';
      case 'user-disabled':
        return 'Esta cuenta fue deshabilitada.';
      case 'too-many-requests':
        return 'Demasiados intentos. Espera un momento e inténtalo de nuevo.';
      case 'network-request-failed':
        return 'Sin conexión a internet. Verifica tu red e inténtalo de nuevo.';
      default:
        return 'No se pudo completar la operación. Intenta nuevamente.';
    }
  }
}
