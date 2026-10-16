// Pruebas unitarias para SqliteUserProfileRepository.
//
// Usan sqflite_common_ffi para ejecutar sobre una base de datos SQLite en
// memoria, sin depender del plugin nativo de Android/iOS.

import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'package:seguimiento_glucosa/models/user_profile.dart';
import 'package:seguimiento_glucosa/services/user_profile_repository.dart';

void main() {
  setUpAll(() {
    sqfliteFfiInit();
  });

  // singleInstance: false asegura que cada repositorio abra su propia base
  // de datos en memoria, completamente aislada de las demás pruebas.
  SqliteUserProfileRepository createRepository() {
    return SqliteUserProfileRepository(
      factory: databaseFactoryFfi,
      databasePath: inMemoryDatabasePath,
      singleInstance: false,
    );
  }

  test('getProfile devuelve null cuando no hay perfil guardado', () async {
    final repository = createRepository();
    expect(await repository.getProfile(), isNull);
  });

  test('saveProfile persiste el perfil y getProfile lo recupera', () async {
    final repository = createRepository();

    await repository.saveProfile(
      const UserProfile(
        heightCm: 170,
        biologicalSex: BiologicalSex.female,
        displayName: 'Persona de Prueba',
      ),
    );

    final loaded = await repository.getProfile();
    expect(loaded?.heightCm, 170);
    expect(loaded?.biologicalSex, BiologicalSex.female);
    expect(loaded?.displayName, 'Persona de Prueba');
    expect(loaded?.birthDate, isNull);
  });

  test('saveProfile persiste la fecha de nacimiento', () async {
    final repository = createRepository();

    await repository.saveProfile(
      UserProfile(heightCm: 180, birthDate: DateTime(1990, 5, 20)),
    );

    final loaded = await repository.getProfile();
    expect(loaded?.birthDate, DateTime(1990, 5, 20));
  });

  test(
    'saveProfile reemplaza cualquier perfil anterior (singleton row)',
    () async {
      final repository = createRepository();

      await repository.saveProfile(const UserProfile(heightCm: 160));
      await repository.saveProfile(const UserProfile(heightCm: 175));

      final loaded = await repository.getProfile();
      expect(loaded?.heightCm, 175);
    },
  );

  test('clearProfile elimina el perfil guardado', () async {
    final repository = createRepository();

    await repository.saveProfile(const UserProfile(heightCm: 165));
    await repository.clearProfile();

    expect(await repository.getProfile(), isNull);
  });
}
