import 'package:flutter/material.dart';

/// Pantalla de bienvenida mostrada brevemente al abrir la app, antes de
/// navegar automáticamente a [nextScreenBuilder].
///
/// Complementa (no reemplaza) el splash nativo generado por
/// `flutter_native_splash` (ver `pubspec.yaml`): el nativo cubre el
/// instante entre el toque del ícono y que el motor de Flutter esté
/// listo para dibujar; este widget ya corre dentro de Flutter y permite
/// una transición animada (fundido + escala) con el mismo logo antes de
/// entrar a la pantalla principal.
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key, required this.nextScreenBuilder, this.duration = const Duration(milliseconds: 1800)});

  /// Construye la pantalla a la que se navega automáticamente al
  /// terminar la animación. Es una función (no un [Widget] ya
  /// construido) para no instanciar la pantalla siguiente —y sus
  /// repositorios— sino hasta que realmente se necesite.
  final WidgetBuilder nextScreenBuilder;

  /// Tiempo total que se muestra el splash antes de navegar. Se puede
  /// acortar en tests para no esperar innecesariamente.
  final Duration duration;

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _scale;
  late final Animation<double> _opacity;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    );
    _scale = Tween<double>(begin: 0.7, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeOutBack),
    );
    _opacity = CurvedAnimation(parent: _controller, curve: Curves.easeIn);
    _controller.forward();
    _scheduleNavigation();
  }

  void _scheduleNavigation() {
    Future.delayed(widget.duration, () {
      if (!mounted) {
        return;
      }
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: widget.nextScreenBuilder),
      );
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFF42A5F5), Color(0xFF0D47A1)],
          ),
        ),
        child: Center(
          child: AnimatedBuilder(
            animation: _controller,
            builder: (context, child) {
              return Opacity(
                opacity: _opacity.value,
                child: Transform.scale(scale: _scale.value, child: child),
              );
            },
            child: const Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                _LogoBadge(),
                SizedBox(height: 24),
                Text(
                  'Seguimiento Glucosa',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 26,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 0.3,
                  ),
                ),
                SizedBox(height: 8),
                Text(
                  'Tu control de glucosa, siempre a mano',
                  style: TextStyle(
                    color: Colors.white70,
                    fontSize: 15,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Insignia circular blanca con la gota de glucosa, réplica en Dart del
/// icono de la app (ver `tool/generate_icon_assets.py`) para no depender
/// de cargar un asset de imagen en este widget.
class _LogoBadge extends StatelessWidget {
  const _LogoBadge();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 120,
      height: 120,
      decoration: const BoxDecoration(
        color: Colors.white,
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(color: Colors.black26, blurRadius: 20, spreadRadius: 2),
        ],
      ),
      child: const Icon(Icons.bloodtype, color: Colors.red, size: 64),
    );
  }
}
