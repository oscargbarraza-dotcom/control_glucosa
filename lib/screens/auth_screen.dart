import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/app_user.dart';
import '../services/auth_repository.dart';
import '../services/cloud_sync_repository.dart';

/// URL pública de la política de privacidad (checklist de producción,
/// bloqueante #4), publicada vía Firebase Hosting a partir de
/// `public/privacy-policy/index.html`. Ver también `PRIVACY_POLICY.md`
/// en la raíz del repo (misma fuente de contenido, en Markdown).
const String privacyPolicyUrl =
    'https://seguimiento-glucosa.web.app/privacy-policy/';

/// Pantalla de cuenta: inicio de sesión, registro, o resumen de la
/// cuenta ya autenticada (con opción de cerrar sesión).
///
/// El inicio de sesión es opcional en la app: esta pantalla se abre
/// desde un acceso en `HomeScreen`, sin bloquear el uso del resto de
/// módulos (Glucosa, Comida, Medicamentos, Biometría, Historial), que
/// siguen funcionando sobre SQLite sin necesidad de una cuenta.
///
/// Mientras haya sesión iniciada, cada registro nuevo (en Android/iOS)
/// se sincroniza solo con la nube en segundo plano —ver
/// `SyncingGlucoseRepository` y equivalentes en
/// `lib/services/syncing_repositories.dart`—, sin que esta pantalla
/// deba ofrecer ningún botón manual de respaldo o restauración.
class AuthScreen extends StatefulWidget {
  const AuthScreen({
    super.key,
    required this.repository,
    this.cloudDataDeletionRepository,
    this.deleteLocalData,
  });

  final AuthRepository repository;

  /// Repositorio capaz de borrar las cuatro subcolecciones del usuario
  /// en Firestore. Si es `null`, el botón de eliminación de cuenta no se
  /// muestra, porque no sería seguro eliminar Firebase Auth dejando
  /// datos de salud huérfanos en la nube.
  final CloudDataDeletionRepository? cloudDataDeletionRepository;

  /// Callback opcional para borrar también los datos locales del
  /// dispositivo (SQLite, perfil, recordatorios y catálogos). En el
  /// visor de escritorio es `null` porque no existe almacenamiento
  /// local; la eliminación de cuenta y nube sigue disponible.
  final Future<void> Function()? deleteLocalData;

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  bool _isDeleting = false;

  /// Ejecuta la eliminación en el único orden seguro:
  /// 1) datos Firestore (todavía autenticado), 2) cuenta Firebase Auth,
  /// 3) datos SQLite opcionales. Si falla 1 o 2, los datos locales no
  /// se tocan; si falla 2, tampoco se pierde la sesión necesaria para
  /// reintentar o completar el borrado en la nube.
  Future<void> _deleteAccountAndData({required bool deleteLocalData}) async {
    final cloudRepository = widget.cloudDataDeletionRepository;
    if (cloudRepository == null || _isDeleting) {
      return;
    }

    setState(() => _isDeleting = true);
    var accountDeleted = false;
    try {
      await cloudRepository.deleteAllCloudData();
      await widget.repository.deleteAccount();
      accountDeleted = true;
      if (deleteLocalData) {
        await widget.deleteLocalData?.call();
      }
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Tu cuenta y tus datos fueron eliminados.'),
        ),
      );
      Navigator.of(context).pop(deleteLocalData);
    } on AuthException catch (e) {
      _showDeleteError(e.message);
    } on CloudSyncException catch (e) {
      _showDeleteError(e.message);
    } catch (_) {
      if (accountDeleted) {
        _showDeleteError(
          'La cuenta y los datos en la nube se eliminaron, pero no se '
          'pudieron borrar todos los datos de este dispositivo. Puedes '
          'eliminarlos desde los ajustes del sistema o desinstalando la app.',
        );
        if (mounted) {
          Navigator.of(context).pop(false);
        }
      } else {
        _showDeleteError(
          'No se pudo completar la eliminación. Intenta nuevamente.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isDeleting = false);
      }
    }
  }

  void _showDeleteError(String message) {
    if (!mounted) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.red),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Cuenta')),
      body: StreamBuilder<AppUser?>(
        stream: widget.repository.authStateChanges(),
        initialData: widget.repository.currentUser,
        builder: (context, snapshot) {
          final user = snapshot.data;
          if (user != null) {
            return _AccountView(
              user: user,
              repository: widget.repository,
              canDeleteLocalData: widget.deleteLocalData != null,
              isDeleting: _isDeleting,
              onDeleteAccountAndData: _deleteAccountAndData,
            );
          }
          return _AuthForm(repository: widget.repository);
        },
      ),
    );
  }
}

/// Resumen de la cuenta autenticada, con opciones para cerrar sesión o
/// eliminar permanentemente la cuenta y sus datos en la nube.
class _AccountView extends StatefulWidget {
  const _AccountView({
    required this.user,
    required this.repository,
    required this.canDeleteLocalData,
    required this.isDeleting,
    required this.onDeleteAccountAndData,
  });

  final AppUser user;
  final AuthRepository repository;
  final bool canDeleteLocalData;
  final bool isDeleting;
  final Future<void> Function({required bool deleteLocalData})
  onDeleteAccountAndData;

  @override
  State<_AccountView> createState() => _AccountViewState();
}

class _AccountViewState extends State<_AccountView> {
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.account_circle, size: 80, color: Colors.deepPurple),
          const SizedBox(height: 16),
          Text(
            widget.user.displayName ?? 'Sesión iniciada',
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            textAlign: TextAlign.center,
          ),
          if (widget.user.email != null) ...[
            const SizedBox(height: 4),
            Text(
              widget.user.email!,
              style: const TextStyle(color: Colors.black54),
              textAlign: TextAlign.center,
            ),
          ],
          const SizedBox(height: 24),
          const Divider(),
          const SizedBox(height: 8),
          const Icon(Icons.cloud_sync, color: Colors.black54),
          const SizedBox(height: 4),
          const Text(
            'Tu historial (glucosa, comidas, medicamentos, biometría) se '
            'sincroniza solo con la nube mientras tengas sesión iniciada, '
            'sin ninguna acción adicional.',
            style: TextStyle(color: Colors.black54, fontSize: 13),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: widget.isDeleting
                  ? null
                  : () => widget.repository.signOut(),
              child: const Text('Cerrar sesión'),
            ),
          ),
          const SizedBox(height: 8),
          TextButton.icon(
            onPressed: widget.isDeleting ? null : _confirmDeleteAccount,
            icon: widget.isDeleting
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.delete_forever_outlined),
            label: Text(
              widget.isDeleting
                  ? 'Eliminando cuenta y datos…'
                  : 'Eliminar cuenta y datos',
            ),
            style: TextButton.styleFrom(
              foregroundColor: Theme.of(context).colorScheme.error,
            ),
          ),
          const SizedBox(height: 8),
          TextButton(
            onPressed: widget.isDeleting ? null : _openPrivacyPolicy,
            child: const Text('Política de privacidad'),
          ),
        ],
      ),
    );
  }

  Future<void> _confirmDeleteAccount() async {
    var deleteLocalData = widget.canDeleteLocalData;
    final confirmed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          icon: Icon(
            Icons.warning_amber_rounded,
            color: Theme.of(context).colorScheme.error,
          ),
          title: const Text('¿Eliminar cuenta y datos?'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Esta acción es permanente. Se eliminarán tu cuenta de '
                'acceso y todos tus datos de salud guardados en la nube.',
              ),
              if (widget.canDeleteLocalData) ...[
                const SizedBox(height: 12),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: deleteLocalData,
                  onChanged: (value) =>
                      setDialogState(() => deleteLocalData = value ?? true),
                  title: const Text(
                    'Eliminar también los datos de este dispositivo',
                  ),
                  subtitle: const Text(
                    'Incluye glucosa, comidas, medicamentos, biometría, '
                    'perfil y recordatorios locales.',
                  ),
                  controlAffinity: ListTileControlAffinity.leading,
                ),
              ],
              const SizedBox(height: 12),
              const Text(
                'No podrás deshacer esta acción.',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              style: FilledButton.styleFrom(
                backgroundColor: Theme.of(context).colorScheme.error,
              ),
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Eliminar permanentemente'),
            ),
          ],
        ),
      ),
    );
    if (confirmed != true || !mounted) {
      return;
    }

    await widget.onDeleteAccountAndData(deleteLocalData: deleteLocalData);
  }

  Future<void> _openPrivacyPolicy() async {
    final uri = Uri.parse(privacyPolicyUrl);
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }
}

/// Formulario de inicio de sesión/registro con correo y contraseña, más
/// el acceso a inicio de sesión con Google.
class _AuthForm extends StatefulWidget {
  const _AuthForm({required this.repository});

  final AuthRepository repository;

  @override
  State<_AuthForm> createState() => _AuthFormState();
}

enum _AuthMode { signIn, register }

class _AuthFormState extends State<_AuthForm> {
  final _formKey = GlobalKey<FormState>();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();

  _AuthMode _mode = _AuthMode.signIn;
  bool _isSubmitting = false;
  String? _errorMessage;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  String? _validateEmail(String? input) {
    final value = input?.trim() ?? '';
    if (value.isEmpty) {
      return 'Ingresa tu correo.';
    }
    if (!value.contains('@') || !value.contains('.')) {
      return 'Ingresa un correo válido.';
    }
    return null;
  }

  String? _validatePassword(String? input) {
    final value = input ?? '';
    if (value.isEmpty) {
      return 'Ingresa tu contraseña.';
    }
    if (value.length < 6) {
      return 'La contraseña debe tener al menos 6 caracteres.';
    }
    return null;
  }

  Future<void> _submitEmailForm() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    setState(() {
      _isSubmitting = true;
      _errorMessage = null;
    });

    final email = _emailController.text.trim();
    final password = _passwordController.text;

    try {
      if (_mode == _AuthMode.register) {
        await widget.repository.registerWithEmail(
          email: email,
          password: password,
        );
      } else {
        await widget.repository.signInWithEmail(
          email: email,
          password: password,
        );
      }
    } on AuthException catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _errorMessage = e.message;
      });
    } finally {
      if (mounted) {
        setState(() {
          _isSubmitting = false;
        });
      }
    }
  }

  Future<void> _submitGoogleSignIn() async {
    setState(() {
      _isSubmitting = true;
      _errorMessage = null;
    });

    try {
      await widget.repository.signInWithGoogle();
    } on AuthException catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _errorMessage = e.message;
      });
    } finally {
      if (mounted) {
        setState(() {
          _isSubmitting = false;
        });
      }
    }
  }

  Future<void> _sendPasswordReset() async {
    final email = _emailController.text.trim();
    if (_validateEmail(email) != null) {
      setState(() {
        _errorMessage = 'Ingresa tu correo para recuperar la contraseña.';
      });
      return;
    }

    try {
      await widget.repository.sendPasswordResetEmail(email);
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Te enviamos un correo para restablecer tu contraseña.',
          ),
        ),
      );
    } on AuthException catch (e) {
      setState(() {
        _errorMessage = e.message;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final isRegister = _mode == _AuthMode.register;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Icon(
              Icons.account_circle,
              size: 70,
              color: Colors.deepPurple,
            ),
            const SizedBox(height: 10),
            Text(
              isRegister ? 'Crear cuenta' : 'Iniciar sesión',
              style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 4),
            const Text(
              'Opcional: tus datos siguen guardados en este dispositivo '
              'aunque no inicies sesión.',
              style: TextStyle(color: Colors.black54, fontSize: 13),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 20),
            TextFormField(
              controller: _emailController,
              keyboardType: TextInputType.emailAddress,
              decoration: const InputDecoration(
                labelText: 'Correo electrónico',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.email_outlined),
              ),
              validator: _validateEmail,
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _passwordController,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'Contraseña',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.lock_outline),
              ),
              validator: _validatePassword,
            ),
            if (_errorMessage != null) ...[
              const SizedBox(height: 12),
              Text(
                _errorMessage!,
                style: const TextStyle(color: Colors.red),
                textAlign: TextAlign.center,
              ),
            ],
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: _isSubmitting ? null : _submitEmailForm,
              child: _isSubmitting
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2.5),
                    )
                  : Text(isRegister ? 'Registrarse' : 'Iniciar sesión'),
            ),
            const SizedBox(height: 8),
            TextButton(
              onPressed: _isSubmitting
                  ? null
                  : () {
                      setState(() {
                        _mode = isRegister
                            ? _AuthMode.signIn
                            : _AuthMode.register;
                        _errorMessage = null;
                      });
                    },
              child: Text(
                isRegister
                    ? '¿Ya tienes cuenta? Inicia sesión'
                    : '¿No tienes cuenta? Regístrate',
              ),
            ),
            if (!isRegister)
              TextButton(
                onPressed: _isSubmitting ? null : _sendPasswordReset,
                child: const Text('¿Olvidaste tu contraseña?'),
              ),
            if (widget.repository.supportsGoogleSignIn) ...[
              const SizedBox(height: 10),
              const Row(
                children: [
                  Expanded(child: Divider()),
                  Padding(
                    padding: EdgeInsets.symmetric(horizontal: 8),
                    child: Text('o', style: TextStyle(color: Colors.black54)),
                  ),
                  Expanded(child: Divider()),
                ],
              ),
              const SizedBox(height: 10),
              OutlinedButton.icon(
                onPressed: _isSubmitting ? null : _submitGoogleSignIn,
                icon: const Icon(Icons.g_mobiledata, size: 28),
                label: const Text('Continuar con Google'),
              ),
            ],
            const SizedBox(height: 16),
            TextButton(
              onPressed: _openPrivacyPolicy,
              child: const Text('Política de privacidad'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _openPrivacyPolicy() async {
    final uri = Uri.parse(privacyPolicyUrl);
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }
}
