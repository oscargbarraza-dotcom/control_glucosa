/// Excepción de importación desde sensores/CGM con un mensaje ya listo
/// para mostrar al usuario (en español, sin exponer detalles internos
/// del SDK).
class HealthImportException implements Exception {
  const HealthImportException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Contrato para importar, de forma manual, las mediciones de glucosa
/// ya registradas en la plataforma de salud del dispositivo (Google
/// Health Connect en Android, Apple Health en iOS).
///
/// Es de **solo lectura**: ninguna implementación de esta interfaz debe
/// escribir datos en la plataforma de salud, solo leerlos e
/// incorporarlos al historial local ([GlucoseRepository]). La
/// importación ocurre bajo pedido explícito del usuario (un botón), no
/// de forma automática ni en segundo plano, siguiendo el mismo patrón
/// manual bajo pedido del usuario, distinto de la sincronización
/// automática en segundo plano de `CloudSyncRepository`.
///
/// Se define como interfaz abstracta para permitir sustituir la
/// implementación (por ejemplo, en pruebas) sin acoplar las pantallas
/// al plugin `health`, siguiendo el mismo patrón ya usado por el resto
/// de repositorios del proyecto.
abstract class GlucoseImportRepository {
  /// Indica si la plataforma de salud del dispositivo (Health Connect
  /// en Android, Apple Health en iOS) está disponible para leer datos.
  ///
  /// En Android, `false` normalmente significa que la app Health
  /// Connect no está instalada. En iOS siempre es `true` (Apple Health
  /// es parte del sistema).
  Future<bool> isAvailable();

  /// Solicita al usuario el permiso de lectura de mediciones de
  /// glucosa. Devuelve `true` si el permiso quedó concedido (o ya lo
  /// estaba).
  ///
  /// Lanza [HealthImportException] si la plataforma de salud no está
  /// disponible o si falla la solicitud.
  Future<bool> requestPermission();

  /// Importa al historial local las mediciones de glucosa registradas
  /// en la plataforma de salud desde [since] hasta ahora que todavía no
  /// existan en [GlucoseRepository].
  ///
  /// Devuelve la cantidad de mediciones nuevas agregadas (puede ser 0).
  /// Lanza [HealthImportException] si la plataforma de salud no está
  /// disponible, si el permiso fue denegado, o si falla la lectura.
  Future<int> importMeasurements({required DateTime since});
}
