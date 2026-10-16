import 'dart:math' as math;

/// Sexo biológico declarado por el usuario, usado como base para futuras
/// clasificaciones de referencia (por ejemplo, rangos de IMC
/// diferenciados). Es opcional: no es obligatorio para calcular el IMC.
enum BiologicalSex { female, male, preferNotToSay }

/// Extensión con el texto legible para cada [BiologicalSex].
extension BiologicalSexLabel on BiologicalSex {
  String get label {
    switch (this) {
      case BiologicalSex.female:
        return 'Femenino';
      case BiologicalSex.male:
        return 'Masculino';
      case BiologicalSex.preferNotToSay:
        return 'Prefiero no decir';
    }
  }
}

/// Categoría de índice de masa corporal (IMC), según los rangos estándar
/// para población adulta definidos por la OMS.
///
/// No considera variaciones por edad o sexo: es una clasificación general,
/// suficiente para el alcance actual de la app.
enum BmiCategory { underweight, normal, overweight, obese }

/// Extensión con el texto legible para cada [BmiCategory].
extension BmiCategoryLabel on BmiCategory {
  String get label {
    switch (this) {
      case BmiCategory.underweight:
        return 'Bajo peso';
      case BmiCategory.normal:
        return 'Normal';
      case BmiCategory.overweight:
        return 'Sobrepeso';
      case BmiCategory.obese:
        return 'Obesidad';
    }
  }
}

/// Clasifica un valor de IMC ya calculado en su [BmiCategory] correspondiente.
BmiCategory bmiCategoryFor(double bmi) {
  if (bmi < 18.5) {
    return BmiCategory.underweight;
  }
  if (bmi < 25) {
    return BmiCategory.normal;
  }
  if (bmi < 30) {
    return BmiCategory.overweight;
  }
  return BmiCategory.obese;
}

/// Perfil del usuario de la aplicación.
///
/// Existe como un único registro local (no hay soporte multiusuario
/// todavía, ver "Usuarios/perfiles" en `PROJECT_CONTEXT.md`), persistido
/// por `UserProfileRepository`. [heightCm] es el único dato obligatorio,
/// ya que es la pieza que faltaba para calcular el índice de masa
/// corporal (IMC) en el módulo de Biometría; el resto de los campos son
/// opcionales.
///
/// Es inmutable: cualquier cambio debe producir una nueva instancia
/// mediante [copyWith].
class UserProfile {
  const UserProfile({
    required this.heightCm,
    this.birthDate,
    this.biologicalSex,
    this.displayName,
  });

  /// Altura en centímetros. Es el dato mínimo necesario para calcular el
  /// IMC junto con el peso registrado en una `BiometricMeasurement`.
  final double heightCm;

  /// Fecha de nacimiento, si el usuario la ingresó.
  final DateTime? birthDate;

  /// Sexo biológico declarado, si el usuario lo ingresó.
  final BiologicalSex? biologicalSex;

  /// Nombre a mostrar en la interfaz (por ejemplo, el saludo de
  /// `HomeScreen`), si el usuario lo ingresó.
  final String? displayName;

  /// Calcula el IMC resultante de combinar [heightCm] con [weightKg].
  ///
  /// Devuelve `null` si [heightCm] no es un valor positivo (lo que no
  /// debería ocurrir en un perfil guardado válidamente, pero evita una
  /// división por cero si llegara a ocurrir).
  double? bmiFor(double weightKg) {
    if (heightCm <= 0) {
      return null;
    }
    final heightM = heightCm / 100;
    return weightKg / math.pow(heightM, 2);
  }

  /// Crea una copia de este perfil sustituyendo los campos indicados.
  ///
  /// Para limpiar explícitamente un campo opcional (dejarlo en `null`),
  /// usa [clearBirthDate], [clearBiologicalSex] o [clearDisplayName]; de
  /// lo contrario el valor actual se conserva.
  UserProfile copyWith({
    double? heightCm,
    DateTime? birthDate,
    bool clearBirthDate = false,
    BiologicalSex? biologicalSex,
    bool clearBiologicalSex = false,
    String? displayName,
    bool clearDisplayName = false,
  }) {
    return UserProfile(
      heightCm: heightCm ?? this.heightCm,
      birthDate: clearBirthDate ? null : (birthDate ?? this.birthDate),
      biologicalSex: clearBiologicalSex
          ? null
          : (biologicalSex ?? this.biologicalSex),
      displayName: clearDisplayName ? null : (displayName ?? this.displayName),
    );
  }

  @override
  String toString() {
    return 'UserProfile(heightCm: $heightCm, birthDate: $birthDate, '
        'biologicalSex: $biologicalSex, displayName: $displayName)';
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) {
      return true;
    }
    return other is UserProfile &&
        other.heightCm == heightCm &&
        other.birthDate == birthDate &&
        other.biologicalSex == biologicalSex &&
        other.displayName == displayName;
  }

  @override
  int get hashCode =>
      Object.hash(heightCm, birthDate, biologicalSex, displayName);
}
