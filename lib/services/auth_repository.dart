import '../models/app_user.dart';

/// Excepción de autenticación con un mensaje ya listo para mostrar al
/// usuario (en español, sin exponer códigos internos del SDK).
class AuthException implements Exception {
  const AuthException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Contrato de autenticación de usuarios.
///
/// Se define como interfaz abstracta para permitir sustituir la
/// implementación (por ejemplo, en pruebas) sin acoplar las pantallas al
/// SDK de Firebase, siguiendo el mismo patrón ya usado por
/// [GlucoseRepository] y el resto de repositorios del proyecto.
///
/// El inicio de sesión es opcional: la app sigue siendo usable sin
/// autenticarse, ya que SQLite es el almacenamiento principal. Esta
/// capa es la base para pasos futuros del roadmap (sincronización).
abstract class AuthRepository {
  /// Emite el usuario actual cada vez que cambia el estado de sesión
  /// (inicio de sesión, cierre de sesión, o restauración automática al
  /// abrir la app). Emite `null` cuando no hay nadie autenticado.
  Stream<AppUser?> authStateChanges();

  /// Usuario autenticado en este momento, o `null` si no hay ninguno.
  AppUser? get currentUser;

  /// Indica si Google Sign-In está implementado en la plataforma actual.
  ///
  /// Permite que la interfaz oculte el flujo en Linux sin acoplar
  /// las pantallas al sistema operativo ni al plugin `google_sign_in`.
  bool get supportsGoogleSignIn;

  /// Crea una cuenta nueva con correo y contraseña, y deja al usuario
  /// autenticado. Lanza [AuthException] con un mensaje legible si falla
  /// (por ejemplo, correo ya registrado o contraseña débil).
  Future<AppUser> registerWithEmail({
    required String email,
    required String password,
  });

  /// Inicia sesión con correo y contraseña. Lanza [AuthException] con un
  /// mensaje legible si falla (por ejemplo, credenciales inválidas).
  Future<AppUser> signInWithEmail({
    required String email,
    required String password,
  });

  /// Inicia sesión con una cuenta de Google.
  ///
  /// Devuelve `null` si el usuario cancela el selector de cuentas (no se
  /// considera un error). Lanza [AuthException] con un mensaje legible
  /// ante cualquier otra falla.
  Future<AppUser?> signInWithGoogle();

  /// Envía un correo de restablecimiento de contraseña. Lanza
  /// [AuthException] con un mensaje legible si falla.
  Future<void> sendPasswordResetEmail(String email);

  /// Cierra la sesión actual (de email/contraseña o de Google).
  Future<void> signOut();

  /// Elimina permanentemente la cuenta del usuario autenticado
  /// (checklist de producción, bloqueante #5: "eliminación de cuenta
  /// y datos"). No elimina los datos locales en SQLite de este
  /// dispositivo (son independientes de la cuenta); quien llama a
  /// este método es responsable de borrar también los datos en la
  /// nube (ver `CloudSyncRepository.deleteAllCloudData`) **antes** de
  /// invocarlo, porque las reglas de seguridad de Firestore exigen
  /// estar autenticado para poder borrar los propios documentos.
  ///
  /// Lanza [AuthException] si no hay sesión iniciada o si falla la
  /// operación. En particular, si Firebase exige una autenticación
  /// reciente por motivos de seguridad (código
  /// `requires-recent-login`), el mensaje le indica al usuario que
  /// debe cerrar sesión, volver a iniciarla y reintentar.
  Future<void> deleteAccount();
}
