import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/app_user.dart';
import '../services/auth_repository.dart';

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
  const AuthScreen({super.key, required this.repository});

  final AuthRepository repository;

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
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
            return _AccountView(user: user, repository: widget.repository);
          }
          return _AuthForm(repository: widget.repository);
        },
      ),
    );
  }
}

/// Resumen de la cuenta autenticada, con opción de cerrar sesión.
class _AccountView extends StatelessWidget {
  const _AccountView({required this.user, required this.repository});

  final AppUser user;
  final AuthRepository repository;

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
            user.displayName ?? 'Sesión iniciada',
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            textAlign: TextAlign.center,
          ),
          if (user.email != null) ...[
            const SizedBox(height: 4),
            Text(
              user.email!,
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
              onPressed: () => repository.signOut(),
              child: const Text('Cerrar sesión'),
            ),
          ),
          const SizedBox(height: 8),
          TextButton(
            onPressed: _openPrivacyPolicy,
            child: const Text('Política de privacidad'),
          ),
        ],
      ),
    );
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
