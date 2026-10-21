import 'package:health/health.dart';

import '../models/glucose_measurement.dart';
import 'glucose_import_repository.dart';
import 'glucose_repository.dart';

/// Implementación de [GlucoseImportRepository] basada en el plugin
/// `health`, que envuelve Google Health Connect (Android) y Apple
/// Health (iOS).
///
/// Es de solo lectura: únicamente llama a métodos de lectura del
/// plugin (`hasPermissions`, `requestAuthorization` con acceso
/// `READ`, `getHealthDataFromTypes`), nunca a `writeHealthData` ni
/// similares.
class HealthGlucoseImportRepository implements GlucoseImportRepository {
  HealthGlucoseImportRepository({
    required GlucoseRepository glucoseRepository,
    Health? health,
  }) : // Se requiere un parámetro con nombre explícito
       // (`glucoseRepository: ...`) para legibilidad en el sitio de
       // construcción, por lo que no se usa un initializing formal
       // aquí, igual que en `FirestoreCloudSyncRepository`.
       // ignore: prefer_initializing_formals
       _glucoseRepository = glucoseRepository,
       _health = health ?? Health();

  static const _type = HealthDataType.BLOOD_GLUCOSE;
  static const _permissions = [HealthDataAccess.READ];

  final GlucoseRepository _glucoseRepository;
  final Health _health;

  bool _configured = false;

  Future<void> _ensureConfigured() async {
    if (_configured) {
      return;
    }
    await _health.configure();
    _configured = true;
  }

  @override
  Future<bool> isAvailable() async {
    await _ensureConfigured();
    try {
      return await _health.isHealthConnectAvailable();
    } catch (e) {
      return false;
    }
  }

  @override
  Future<bool> requestPermission() async {
    await _ensureConfigured();
    try {
      final alreadyGranted = await _health.hasPermissions(const [
        _type,
      ], permissions: _permissions);
      if (alreadyGranted == true) {
        return true;
      }
      return await _health.requestAuthorization(const [
        _type,
      ], permissions: _permissions);
    } catch (e) {
      throw const HealthImportException(
        'No se pudo solicitar el permiso de lectura de glucosa. '
        'Verifica que Health Connect (o Salud) esté disponible e '
        'intenta nuevamente.',
      );
    }
  }

  @override
  Future<int> importMeasurements({required DateTime since}) async {
    await _ensureConfigured();

    List<HealthDataPoint> points;
    try {
      points = await _health.getHealthDataFromTypes(
        types: const [_type],
        preferredUnits: const {_type: HealthDataUnit.MILLIGRAM_PER_DECILITER},
        startTime: since,
        endTime: DateTime.now(),
      );
    } catch (e) {
      throw const HealthImportException(
        'No se pudieron leer las mediciones de glucosa. Verifica el '
        'permiso concedido e intenta nuevamente.',
      );
    }

    final existing = await _glucoseRepository.getAllMeasurements();
    final existingKeys = existing
        .map((m) => _dedupKey(m.measuredAt, m.value))
        .toSet();

    var imported = 0;
    for (final point in points) {
      final value = point.value;
      if (value is! NumericHealthValue) {
        continue;
      }
      final roundedValue = value.numericValue.round();
      final key = _dedupKey(point.dateFrom, roundedValue);
      if (existingKeys.contains(key)) {
        continue;
      }

      await _glucoseRepository.addMeasurement(
        GlucoseMeasurement(
          value: roundedValue,
          moment: GlucoseMoment.now,
          measuredAt: point.dateFrom,
          comment: 'Importado desde ${point.sourceName}.',
        ),
      );
      existingKeys.add(key);
      imported++;
    }

    return imported;
  }

  @override
  Future<GlucoseMeasurement?> fetchLatestMeasurement({
    Duration lookback = const Duration(hours: 4),
  }) async {
    await _ensureConfigured();

    List<HealthDataPoint> points;
    try {
      points = await _health.getHealthDataFromTypes(
        types: const [_type],
        preferredUnits: const {_type: HealthDataUnit.MILLIGRAM_PER_DECILITER},
        startTime: DateTime.now().subtract(lookback),
        endTime: DateTime.now(),
      );
    } catch (e) {
      throw const HealthImportException(
        'No se pudieron leer las mediciones de glucosa. Verifica el '
        'permiso concedido e intenta nuevamente.',
      );
    }

    HealthDataPoint? latest;
    for (final point in points) {
      if (point.value is! NumericHealthValue) {
        continue;
      }
      if (latest == null || point.dateFrom.isAfter(latest.dateFrom)) {
        latest = point;
      }
    }
    if (latest == null) {
      return null;
    }

    final value = latest.value as NumericHealthValue;
    return GlucoseMeasurement(
      value: value.numericValue.round(),
      moment: GlucoseMoment.now,
      measuredAt: latest.dateFrom,
      comment: 'Tomado desde ${latest.sourceName}.',
    );
  }

  /// Clave de deduplicación: no existe un identificador estable
  /// compartido entre el historial local (asignado por SQLite) y la
  /// plataforma de salud, así que se usa la combinación de fecha/hora
  /// exacta y valor para evitar importar la misma medición dos veces
  /// en importaciones repetidas.
  String _dedupKey(DateTime measuredAt, int value) =>
      '${measuredAt.toIso8601String()}|$value';
}
