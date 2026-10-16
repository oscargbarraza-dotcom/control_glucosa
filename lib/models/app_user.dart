/// Representa al usuario autenticado de la aplicación.
///
/// Es un modelo propio (no depende de `firebase_auth.User` directamente)
/// para que las pantallas y los tests no se acoplen al SDK de Firebase,
/// siguiendo el mismo patrón de abstracción usado por [AuthRepository].
///
/// Es inmutable: cualquier cambio debe producir una nueva instancia.
class AppUser {
  const AppUser({required this.uid, required this.email, this.displayName});

  /// Identificador único del usuario, asignado por Firebase Auth.
  final String uid;

  /// Correo electrónico del usuario. Puede ser `null` para proveedores
  /// que no lo exponen, aunque email/contraseña y Google siempre lo
  /// incluyen.
  final String? email;

  /// Nombre a mostrar, si el proveedor lo entrega (por ejemplo, Google).
  final String? displayName;

  @override
  String toString() =>
      'AppUser(uid: $uid, email: $email, displayName: $displayName)';

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) {
      return true;
    }
    return other is AppUser &&
        other.uid == uid &&
        other.email == email &&
        other.displayName == displayName;
  }

  @override
  int get hashCode => Object.hash(uid, email, displayName);
}
