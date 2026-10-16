import 'package:sqflite/sqflite.dart';

import '../models/user_profile.dart';
import 'app_database.dart';

/// Contrato de persistencia para el perfil del usuario.
///
/// La app no tiene soporte multiusuario (ver "Usuarios/perfiles" en
/// `PROJECT_CONTEXT.md`): existe un único perfil local, por lo que no
/// hay operaciones de listado ni de identificación por id, a diferencia
/// del resto de repositorios de datos de salud.
///
/// Se define como interfaz abstracta para permitir sustituir la
/// implementación (por ejemplo, en pruebas) sin acoplar las pantallas a
/// `sqflite`.
abstract class UserProfileRepository {
  /// Recupera el perfil guardado, o `null` si el usuario todavía no lo
  /// ha completado.
  Future<UserProfile?> getProfile();

  /// Guarda [profile], sustituyendo cualquier perfil anterior.
  Future<void> saveProfile(UserProfile profile);

  /// Elimina el perfil guardado, si existe.
  Future<void> clearProfile();
}

/// Implementación de [UserProfileRepository] basada en SQLite (`sqflite`).
///
/// Consume la tabla `user_profile` de la base de datos compartida
/// ([AppDatabase]). Al existir un único perfil, se persiste siempre en
/// la fila con `id = 1` (patrón "singleton row"): [saveProfile] usa
/// `ConflictAlgorithm.replace` en lugar de distinguir entre crear y
/// actualizar.
class SqliteUserProfileRepository implements UserProfileRepository {
  /// Crea el repositorio usando [factory] como fábrica de la base de datos
  /// y, opcionalmente, [databasePath] como ruta explícita del archivo.
  ///
  /// Si [factory] no se provee, usa la fábrica por defecto de `sqflite`
  /// ([databaseFactory]), válida en Android/iOS.
  ///
  /// En tests se puede inyectar `databaseFactoryFfi` de
  /// `sqflite_common_ffi` junto con `inMemoryDatabasePath` como
  /// [databasePath] y [singleInstance] en `false`, para que cada instancia
  /// de este repositorio abra una base de datos en memoria propia y
  /// completamente aislada de otras pruebas.
  SqliteUserProfileRepository({
    DatabaseFactory? factory,
    String? databasePath,
    bool singleInstance = true,
  }) : _appDatabase = AppDatabase(
         factory: factory,
         databasePath: databasePath,
         singleInstance: singleInstance,
       );

  /// Permite reutilizar una [AppDatabase] ya creada (por ejemplo, la misma
  /// instancia compartida con [SqliteGlucoseRepository]), en lugar de
  /// abrir una conexión nueva.
  SqliteUserProfileRepository.withDatabase(AppDatabase appDatabase)
    : _appDatabase = appDatabase;

  static const _table = 'user_profile';
  static const _singletonId = 1;

  final AppDatabase _appDatabase;

  Future<Database> get _db => _appDatabase.database;

  @override
  Future<UserProfile?> getProfile() async {
    final db = await _db;
    final rows = await db.query(
      _table,
      where: 'id = ?',
      whereArgs: [_singletonId],
      limit: 1,
    );
    if (rows.isEmpty) {
      return null;
    }
    return _fromRow(rows.first);
  }

  @override
  Future<void> saveProfile(UserProfile profile) async {
    final db = await _db;
    await db.insert(
      _table,
      _toRow(profile),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  @override
  Future<void> clearProfile() async {
    final db = await _db;
    await db.delete(_table, where: 'id = ?', whereArgs: [_singletonId]);
  }

  UserProfile _fromRow(Map<String, Object?> row) {
    final birthDateText = row['birth_date'] as String?;
    final biologicalSexName = row['biological_sex'] as String?;
    return UserProfile(
      heightCm: (row['height_cm'] as num).toDouble(),
      birthDate: birthDateText == null ? null : DateTime.parse(birthDateText),
      biologicalSex: biologicalSexName == null
          ? null
          : BiologicalSex.values.asNameMap()[biologicalSexName],
      displayName: row['display_name'] as String?,
    );
  }

  Map<String, Object?> _toRow(UserProfile profile) {
    return {
      'id': _singletonId,
      'height_cm': profile.heightCm,
      'birth_date': profile.birthDate?.toIso8601String(),
      'biological_sex': profile.biologicalSex?.name,
      'display_name': profile.displayName,
    };
  }
}
