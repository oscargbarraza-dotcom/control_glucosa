/// Excepción de respaldo/restauración con un mensaje ya listo para
/// mostrar al usuario (en español, sin exponer detalles internos del
/// SDK).
class BackupException implements Exception {
  const BackupException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Contrato para el respaldo y restauración manual en la nube de todos
/// los datos de salud (glucosa, comidas, medicamentos, biometría).
///
/// Requiere que el usuario tenga una sesión iniciada (ver
/// `AuthRepository` en `auth_repository.dart`). SQLite sigue siendo
/// el almacenamiento principal: esta capa solo sube/baja una copia de
/// respaldo bajo demanda explícita del usuario (nunca de forma
/// automática en segundo plano).
///
/// [restore] **reemplaza** todos los datos locales actuales por los de
/// la nube (no los fusiona), porque los identificadores de cada
/// registro los asigna SQLite de forma local y autoincremental: no hay
/// una clave estable entre dispositivos que permita distinguir de forma
/// confiable qué registros ya existen y evitar duplicados. Esta
/// decisión debe comunicarse con claridad en la interfaz antes de
/// ejecutar la restauración.
abstract class BackupRepository {
  /// Sube una copia de todos los datos locales actuales a la nube,
  /// sobrescribiendo el respaldo anterior de este usuario (si existía).
  ///
  /// Lanza [BackupException] si el usuario no tiene sesión iniciada o
  /// si falla la operación (por ejemplo, sin conexión).
  Future<void> backup();

  /// Reemplaza todos los datos locales actuales (glucosa, comidas,
  /// medicamentos, biometría) por la última copia guardada en la nube.
  ///
  /// Lanza [BackupException] si el usuario no tiene sesión iniciada, si
  /// no existe ningún respaldo guardado, o si falla la operación.
  Future<void> restore();

  /// Fecha y hora del último respaldo guardado en la nube para el
  /// usuario autenticado, o `null` si nunca se ha respaldado (o si no
  /// hay sesión iniciada).
  Future<DateTime?> getLastBackupTime();
}
