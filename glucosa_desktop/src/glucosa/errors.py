"""Errores de dominio con mensajes ya listos para mostrar al usuario (en español).

La UI distingue estos casos para mostrar claramente "sin conexión",
"sesión vencida", "sin permiso" o "configuración incompleta", y nunca debe
presentar datos parciales como si estuvieran completos.
"""


class GlucosaError(Exception):
    """Base de todos los errores esperables de la aplicación."""


class ConfigError(GlucosaError):
    """Falta configuración local (por ejemplo, la API key en ``.env``)."""


class ConnectionProblem(GlucosaError):
    """Sin red, tiempo agotado o servicio temporalmente no disponible."""


class SessionExpiredError(GlucosaError):
    """La sesión ya no es válida: hay que iniciar sesión de nuevo."""


class PermissionDeniedError(GlucosaError):
    """Las reglas de seguridad de Firestore rechazaron la lectura."""


class AuthError(GlucosaError):
    """Falla inesperada al autenticar o renovar la sesión."""


class SecureStoreError(GlucosaError):
    """No se pudo leer o descifrar un archivo local protegido."""


class OAuthDenied(AuthError):
    """El usuario canceló o Google rechazó la autorización en el navegador."""


class OAuthTimeout(AuthError):
    """No llegó la respuesta del navegador dentro del tiempo permitido."""


class LibreFormatError(GlucosaError):
    """El archivo no tiene el formato esperado de una exportación de LibreView."""


class LibreStoreError(GlucosaError):
    """Operación inválida sobre la base local de LibreView (p. ej. una clave repetida)."""


class SecureStoreBusyError(SecureStoreError):
    """El archivo protegido no se pudo leer ahora (en uso por otro programa); reintentar."""
