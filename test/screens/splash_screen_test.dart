import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:seguimiento_glucosa/screens/splash_screen.dart';

void main() {
  testWidgets('Muestra el nombre de la app mientras se anima', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: SplashScreen(
          duration: const Duration(milliseconds: 50),
          nextScreenBuilder: (context) =>
              const Scaffold(body: Text('Siguiente pantalla')),
        ),
      ),
    );

    expect(find.text('Seguimiento Glucosa'), findsOneWidget);
    expect(find.byIcon(Icons.bloodtype), findsOneWidget);

    // El binding de test exige que no queden timers pendientes al
    // terminar: se agota aquí el `Future.delayed` de navegación (y la
    // animación de entrada) para no dejar nada colgado.
    await tester.pumpAndSettle();
  });

  testWidgets('Navega automáticamente a la pantalla siguiente tras el delay', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: SplashScreen(
          duration: const Duration(milliseconds: 50),
          nextScreenBuilder: (context) =>
              const Scaffold(body: Text('Siguiente pantalla')),
        ),
      ),
    );

    // `pumpAndSettle` agota tanto la animación de entrada del logo como
    // el `Future.delayed` que dispara la navegación.
    await tester.pumpAndSettle();

    expect(find.text('Siguiente pantalla'), findsOneWidget);
    expect(find.text('Seguimiento Glucosa'), findsNothing);
  });
}
