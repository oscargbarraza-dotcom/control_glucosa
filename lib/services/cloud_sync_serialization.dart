// Funciones de (de)serialización usadas por [FirestoreCloudSyncRepository]
// para convertir cada modelo de salud al/del formato de documento de
// Firestore, en un único lugar.

import '../models/biometric_measurement.dart';
import '../models/food.dart';
import '../models/glucose_measurement.dart';
import '../models/meal.dart';
import '../models/medication.dart';
import '../models/medication_intake.dart';

// ---- GlucoseMeasurement ----

Map<String, Object?> glucoseToMap(GlucoseMeasurement m) => {
  'uuid': m.uuid,
  'value': m.value,
  'moment': m.moment.name,
  'measuredAt': m.measuredAt.toIso8601String(),
  'comment': m.comment,
};

GlucoseMeasurement glucoseFromMap(Map<String, Object?> map) {
  return GlucoseMeasurement(
    uuid: map['uuid'] as String?,
    value: map['value'] as int,
    moment:
        GlucoseMoment.values.asNameMap()[map['moment'] as String] ??
        GlucoseMoment.now,
    measuredAt: DateTime.parse(map['measuredAt'] as String),
    comment: map['comment'] as String?,
  );
}

// ---- Meal ----

Map<String, Object?> mealToMap(Meal m) => {
  'uuid': m.uuid,
  'type': m.type.name,
  'eatenAt': m.eatenAt.toIso8601String(),
  'comment': m.comment,
  'items': m.items
      .map((item) => {'foodName': item.food.name, 'quantity': item.quantity})
      .toList(),
};

Meal mealFromMap(Map<String, Object?> map) {
  final items = ((map['items'] as List?) ?? const [])
      .cast<Map<String, Object?>>()
      .map(
        (item) => MealFoodItem(
          food: Food(name: item['foodName'] as String),
          quantity: item['quantity'] as String,
        ),
      )
      .toList();
  return Meal(
    uuid: map['uuid'] as String?,
    type: MealType.values.asNameMap()[map['type'] as String] ?? MealType.other,
    eatenAt: DateTime.parse(map['eatenAt'] as String),
    comment: map['comment'] as String?,
    items: items,
  );
}

// ---- MedicationIntake ----

Map<String, Object?> intakeToMap(MedicationIntake intake) => {
  'uuid': intake.uuid,
  'takenAt': intake.takenAt.toIso8601String(),
  'comment': intake.comment,
  'items': intake.items
      .map(
        (item) => {
          'medicationName': item.medication.name,
          'defaultUnit': item.medication.defaultUnit.name,
          'quantity': item.quantity,
          'unit': item.unit.name,
          'customUnitLabel': item.customUnitLabel,
        },
      )
      .toList(),
};

MedicationIntake intakeFromMap(Map<String, Object?> map) {
  final items = ((map['items'] as List?) ?? const [])
      .cast<Map<String, Object?>>()
      .map((item) {
        final defaultUnit =
            DoseUnit.values.asNameMap()[item['defaultUnit'] as String] ??
            DoseUnit.other;
        final unit =
            DoseUnit.values.asNameMap()[item['unit'] as String] ??
            DoseUnit.other;
        return MedicationIntakeItem(
          medication: Medication(
            name: item['medicationName'] as String,
            defaultUnit: defaultUnit,
          ),
          quantity: (item['quantity'] as num).toDouble(),
          unit: unit,
          customUnitLabel: item['customUnitLabel'] as String?,
        );
      })
      .toList();
  return MedicationIntake(
    uuid: map['uuid'] as String?,
    takenAt: DateTime.parse(map['takenAt'] as String),
    comment: map['comment'] as String?,
    items: items,
  );
}

// ---- BiometricMeasurement ----

Map<String, Object?> biometricToMap(BiometricMeasurement m) => {
  'uuid': m.uuid,
  'weightKg': m.weightKg,
  'systolicPressure': m.systolicPressure,
  'diastolicPressure': m.diastolicPressure,
  'heartRateBpm': m.heartRateBpm,
  'measuredAt': m.measuredAt.toIso8601String(),
  'comment': m.comment,
};

BiometricMeasurement biometricFromMap(Map<String, Object?> map) {
  return BiometricMeasurement(
    uuid: map['uuid'] as String?,
    weightKg: (map['weightKg'] as num).toDouble(),
    systolicPressure: map['systolicPressure'] as int?,
    diastolicPressure: map['diastolicPressure'] as int?,
    heartRateBpm: map['heartRateBpm'] as int?,
    measuredAt: DateTime.parse(map['measuredAt'] as String),
    comment: map['comment'] as String?,
  );
}
