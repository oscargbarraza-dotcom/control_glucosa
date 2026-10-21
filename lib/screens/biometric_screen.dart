import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/biometric_measurement.dart';
import '../models/user_profile.dart';
import '../services/biometric_repository.dart';
import '../services/user_profile_repository.dart';

/// Pantalla del módulo de Biometría, con tres pestañas: **Registrar**
/// (nueva medición), **Perfil** (altura y otros datos personales) e
/// **Historial** (mediciones ya guardadas).
///
/// El peso corporal es obligatorio en cada registro; la presión arterial
/// y la frecuencia cardíaca son opcionales. El IMC se calcula y muestra
/// en el Historial combinando cada peso registrado con la altura del
/// perfil (ver [UserProfile.bmiFor]); si el perfil todavía no tiene
/// altura guardada, el IMC simplemente no se muestra. Sigue el mismo
/// patrón que `MedicationScreen`: autocontenida, con pestañas propias en
/// lugar de depender de `HistoryScreen`, para mantener cada módulo de
/// dominio aislado y testeable.
class BiometricScreen extends StatefulWidget {
  const BiometricScreen({
    super.key,
    required this.repository,
    required this.profileRepository,
  });

  /// Repositorio desde el que se cargan y guardan las mediciones.
  final BiometricRepository repository;

  /// Repositorio desde el que se carga y guarda el perfil de usuario.
  final UserProfileRepository profileRepository;

  @override
  State<BiometricScreen> createState() => _BiometricScreenState();
}

/// Datos combinados que necesita la pestaña Historial: el listado de
/// mediciones y el perfil vigente (para calcular el IMC de cada una).
typedef _HistoryData = ({
  List<BiometricMeasurement> measurements,
  UserProfile? profile,
});

class _BiometricScreenState extends State<BiometricScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController = TabController(
    length: 3,
    vsync: this,
  );
  late Future<UserProfile?> _profileFuture;
  late Future<_HistoryData> _historyDataFuture;

  @override
  void initState() {
    super.initState();
    _profileFuture = widget.profileRepository.getProfile();
    _historyDataFuture = _loadHistoryData();
  }

  Future<_HistoryData> _loadHistoryData() async {
    final measurements = await widget.repository.getAllMeasurements();
    final profile = await widget.profileRepository.getProfile();
    return (measurements: measurements, profile: profile);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _handleMeasurementSaved(BiometricMeasurement measurement) async {
    await widget.repository.addMeasurement(measurement);
    if (!mounted) {
      return;
    }

    setState(() {
      _historyDataFuture = _loadHistoryData();
    });
    _tabController.animateTo(2);

    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('Medición guardada.')));
  }

  Future<void> _handleProfileSaved(UserProfile profile) async {
    await widget.profileRepository.saveProfile(profile);
    if (!mounted) {
      return;
    }

    setState(() {
      _profileFuture = widget.profileRepository.getProfile();
      _historyDataFuture = _loadHistoryData();
    });

    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('Perfil guardado.')));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Biometría'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Registrar', icon: Icon(Icons.add_circle_outline)),
            Tab(text: 'Perfil', icon: Icon(Icons.badge_outlined)),
            Tab(text: 'Historial', icon: Icon(Icons.list)),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _BiometricForm(onSave: _handleMeasurementSaved),
          _ProfileSection(
            profileFuture: _profileFuture,
            onSave: _handleProfileSaved,
          ),
          _BiometricHistoryList(historyDataFuture: _historyDataFuture),
        ],
      ),
    );
  }
}

/// Formulario de registro de una nueva medición: peso corporal
/// (obligatorio), presión arterial y frecuencia cardíaca (opcionales), y
/// comentario (opcional).
class _BiometricForm extends StatefulWidget {
  const _BiometricForm({required this.onSave});

  /// Invocado con la [BiometricMeasurement] construida al pulsar
  /// "Guardar".
  final Future<void> Function(BiometricMeasurement measurement) onSave;

  @override
  State<_BiometricForm> createState() => _BiometricFormState();
}

class _BiometricFormState extends State<_BiometricForm> {
  final _formKey = GlobalKey<FormState>();
  final TextEditingController _weightController = TextEditingController();
  final TextEditingController _systolicController = TextEditingController();
  final TextEditingController _diastolicController = TextEditingController();
  final TextEditingController _heartRateController = TextEditingController();
  final TextEditingController _commentController = TextEditingController();

  bool _isSaving = false;

  @override
  void dispose() {
    _weightController.dispose();
    _systolicController.dispose();
    _diastolicController.dispose();
    _heartRateController.dispose();
    _commentController.dispose();
    super.dispose();
  }

  String? _validateWeight(String? input) {
    if (input == null || input.trim().isEmpty) {
      return 'Ingresa el peso corporal.';
    }
    final parsed = double.tryParse(input.trim());
    if (parsed == null) {
      return 'Ingresa solo números.';
    }
    if (parsed < 20 || parsed > 400) {
      return 'El peso debe estar entre 20 y 400 kg.';
    }
    return null;
  }

  /// Valida un campo de presión arterial (sistólica o diastólica).
  ///
  /// Es opcional, pero si se completa uno de los dos campos del par, el
  /// otro también debe completarse: [partnerText] es el texto actual del
  /// campo complementario.
  String? _validatePressure(
    String? input, {
    required int min,
    required int max,
    required String partnerText,
  }) {
    final ownEmpty = input == null || input.trim().isEmpty;
    final partnerEmpty = partnerText.trim().isEmpty;
    if (ownEmpty) {
      return partnerEmpty
          ? null
          : 'Completa ambos valores de presión, o ninguno.';
    }
    final parsed = int.tryParse(input.trim());
    if (parsed == null) {
      return 'Ingresa solo números.';
    }
    if (parsed < min || parsed > max) {
      return 'Debe estar entre $min y $max mmHg.';
    }
    return null;
  }

  String? _validateHeartRate(String? input) {
    if (input == null || input.trim().isEmpty) {
      return null;
    }
    final parsed = int.tryParse(input.trim());
    if (parsed == null) {
      return 'Ingresa solo números.';
    }
    if (parsed < 30 || parsed > 220) {
      return 'Debe estar entre 30 y 220 lpm.';
    }
    return null;
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() => _isSaving = true);

    final systolicText = _systolicController.text.trim();
    final diastolicText = _diastolicController.text.trim();
    final heartRateText = _heartRateController.text.trim();

    final measurement = BiometricMeasurement(
      weightKg: double.parse(_weightController.text.trim()),
      systolicPressure: systolicText.isEmpty ? null : int.parse(systolicText),
      diastolicPressure: diastolicText.isEmpty
          ? null
          : int.parse(diastolicText),
      heartRateBpm: heartRateText.isEmpty ? null : int.parse(heartRateText),
      measuredAt: DateTime.now(),
      comment: _commentController.text.trim().isEmpty
          ? null
          : _commentController.text.trim(),
    );

    await widget.onSave(measurement);

    if (!mounted) {
      return;
    }
    setState(() {
      _weightController.clear();
      _systolicController.clear();
      _diastolicController.clear();
      _heartRateController.clear();
      _commentController.clear();
      _isSaving = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Icon(Icons.monitor_weight, color: Colors.teal, size: 70),
          const SizedBox(height: 20),
          TextFormField(
            controller: _weightController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(
              labelText: 'Peso corporal (kg)',
              border: OutlineInputBorder(),
            ),
            validator: _validateWeight,
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: TextFormField(
                  controller: _systolicController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Sistólica (mmHg)',
                    hintText: 'Opcional',
                    border: OutlineInputBorder(),
                  ),
                  validator: (input) => _validatePressure(
                    input,
                    min: 60,
                    max: 250,
                    partnerText: _diastolicController.text,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextFormField(
                  controller: _diastolicController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Diastólica (mmHg)',
                    hintText: 'Opcional',
                    border: OutlineInputBorder(),
                  ),
                  validator: (input) => _validatePressure(
                    input,
                    min: 30,
                    max: 150,
                    partnerText: _systolicController.text,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          TextFormField(
            controller: _heartRateController,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: 'Frecuencia cardíaca (lpm)',
              hintText: 'Opcional',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.favorite),
            ),
            validator: _validateHeartRate,
          ),
          const SizedBox(height: 20),
          TextField(
            controller: _commentController,
            maxLines: 3,
            decoration: const InputDecoration(
              labelText: 'Comentario',
              hintText: 'Opcional',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.note_alt),
            ),
          ),
          const SizedBox(height: 30),
          ElevatedButton(
            onPressed: _isSaving ? null : _save,
            child: _isSaving
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2.5),
                  )
                : const Text('Guardar'),
          ),
        ],
      ),
    );
  }
}

/// Vista de historial: pesos de la más reciente a la más antigua, con el
/// IMC de cada uno cuando el perfil ya tiene altura guardada.
///
/// Carga su contenido desde [historyDataFuture], resuelto una vez por
/// [BiometricScreen] y actualizado tras guardar un nuevo peso o un nuevo
/// perfil.
class _BiometricHistoryList extends StatelessWidget {
  const _BiometricHistoryList({required this.historyDataFuture});

  final Future<_HistoryData> historyDataFuture;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_HistoryData>(
      future: historyDataFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }

        final measurements = snapshot.data?.measurements ?? const [];
        if (measurements.isEmpty) {
          return const Center(
            child: Text('Todavía no hay mediciones registradas.'),
          );
        }
        final profile = snapshot.data?.profile;

        return ListView.separated(
          padding: const EdgeInsets.symmetric(vertical: 8),
          itemCount: measurements.length,
          separatorBuilder: (context, index) => const Divider(height: 1),
          itemBuilder: (context, index) => _BiometricTile(
            measurement: measurements[index],
            profile: profile,
          ),
        );
      },
    );
  }
}

/// Fila individual del historial con el peso, el IMC (si hay altura en
/// el perfil), fecha/hora y comentario (si existe) de una medición.
class _BiometricTile extends StatelessWidget {
  const _BiometricTile({required this.measurement, required this.profile});

  final BiometricMeasurement measurement;
  final UserProfile? profile;

  @override
  Widget build(BuildContext context) {
    final formattedDate = DateFormat(
      'dd/MM/yyyy HH:mm',
    ).format(measurement.measuredAt);

    final lines = <String>[formattedDate];
    final bmi = profile?.bmiFor(measurement.weightKg);
    if (bmi != null) {
      lines.add(
        'IMC: ${bmi.toStringAsFixed(1)} (${bmiCategoryFor(bmi).label})',
      );
    }
    if (measurement.hasBloodPressure) {
      lines.add(
        'Presión: ${measurement.systolicPressure}/'
        '${measurement.diastolicPressure} mmHg',
      );
    }
    if (measurement.heartRateBpm != null) {
      lines.add('Frecuencia cardíaca: ${measurement.heartRateBpm} lpm');
    }
    if (measurement.comment != null) {
      lines.add(measurement.comment!);
    }

    return ListTile(
      leading: const Icon(Icons.monitor_weight, color: Colors.teal),
      title: Text(
        '${measurement.weightKg} kg',
        style: const TextStyle(fontWeight: FontWeight.bold),
      ),
      subtitle: Text(lines.join('\n')),
      isThreeLine: lines.length > 2,
    );
  }
}

/// Pestaña Perfil: carga el perfil guardado (si existe) y muestra el
/// formulario de edición ([_ProfileForm]) ya pre-rellenado con sus
/// valores.
class _ProfileSection extends StatelessWidget {
  const _ProfileSection({required this.profileFuture, required this.onSave});

  final Future<UserProfile?> profileFuture;
  final Future<void> Function(UserProfile profile) onSave;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<UserProfile?>(
      future: profileFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        return _ProfileForm(profile: snapshot.data, onSave: onSave);
      },
    );
  }
}

/// Formulario de perfil de usuario: altura (obligatoria), fecha de
/// nacimiento, sexo biológico y nombre a mostrar (todos opcionales).
class _ProfileForm extends StatefulWidget {
  const _ProfileForm({required this.profile, required this.onSave});

  /// Perfil ya guardado, usado para pre-rellenar el formulario. `null`
  /// si el usuario todavía no ha completado su perfil.
  final UserProfile? profile;

  /// Invocado con el [UserProfile] construido al pulsar "Guardar".
  final Future<void> Function(UserProfile profile) onSave;

  @override
  State<_ProfileForm> createState() => _ProfileFormState();
}

class _ProfileFormState extends State<_ProfileForm> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _heightController = TextEditingController(
    text: widget.profile == null ? '' : widget.profile!.heightCm.toString(),
  );
  late final TextEditingController _displayNameController =
      TextEditingController(text: widget.profile?.displayName ?? '');
  late DateTime? _birthDate = widget.profile?.birthDate;
  late BiologicalSex? _biologicalSex = widget.profile?.biologicalSex;

  bool _isSaving = false;

  @override
  void dispose() {
    _heightController.dispose();
    _displayNameController.dispose();
    super.dispose();
  }

  String? _validateHeight(String? input) {
    if (input == null || input.trim().isEmpty) {
      return 'Ingresa tu altura.';
    }
    final parsed = double.tryParse(input.trim());
    if (parsed == null) {
      return 'Ingresa solo números.';
    }
    if (parsed < 50 || parsed > 250) {
      return 'La altura debe estar entre 50 y 250 cm.';
    }
    return null;
  }

  Future<void> _pickBirthDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _birthDate ?? DateTime(now.year - 30),
      firstDate: DateTime(now.year - 120),
      lastDate: now,
    );
    if (picked != null) {
      setState(() => _birthDate = picked);
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() => _isSaving = true);

    final displayNameText = _displayNameController.text.trim();
    final profile = UserProfile(
      heightCm: double.parse(_heightController.text.trim()),
      birthDate: _birthDate,
      biologicalSex: _biologicalSex,
      displayName: displayNameText.isEmpty ? null : displayNameText,
    );

    await widget.onSave(profile);

    if (!mounted) {
      return;
    }
    setState(() => _isSaving = false);
  }

  @override
  Widget build(BuildContext context) {
    final formattedBirthDate = _birthDate == null
        ? 'No especificada'
        : DateFormat('dd/MM/yyyy').format(_birthDate!);

    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Icon(Icons.badge_outlined, color: Colors.teal, size: 70),
          const SizedBox(height: 20),
          TextFormField(
            controller: _heightController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(
              labelText: 'Altura (cm)',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.height),
            ),
            validator: _validateHeight,
          ),
          const SizedBox(height: 20),
          TextFormField(
            controller: _displayNameController,
            decoration: const InputDecoration(
              labelText: 'Nombre a mostrar',
              hintText: 'Opcional',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.person_outline),
            ),
          ),
          const SizedBox(height: 20),
          DropdownButtonFormField<BiologicalSex>(
            initialValue: _biologicalSex,
            // Evita que el botón se reduzca a su contenido mínimo; ver
            // el mismo ajuste (y su motivo) en GlucoseScreen.
            isExpanded: true,
            decoration: const InputDecoration(
              labelText: 'Sexo biológico',
              hintText: 'Opcional',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.wc),
            ),
            items: BiologicalSex.values
                .map(
                  (sex) => DropdownMenuItem(value: sex, child: Text(sex.label)),
                )
                .toList(),
            onChanged: (sex) => setState(() => _biologicalSex = sex),
          ),
          const SizedBox(height: 20),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.cake_outlined),
            title: const Text('Fecha de nacimiento'),
            subtitle: Text(formattedBirthDate),
            trailing: const Icon(Icons.edit_calendar_outlined),
            onTap: _pickBirthDate,
          ),
          const SizedBox(height: 30),
          ElevatedButton(
            onPressed: _isSaving ? null : _save,
            child: _isSaving
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2.5),
                  )
                : const Text('Guardar'),
          ),
        ],
      ),
    );
  }
}
