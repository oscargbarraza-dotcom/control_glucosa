import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:seguimiento_glucosa/screens/glucose_screen.dart';

/// Regresión para el `RenderFlex overflowed by 61 pixels` reportado en
/// [GlucoseScreen]: el `Row` interno del `DropdownButtonFormField` de
/// "Momento de medición" desbordaba horizontalmente con las etiquetas
/// más largas (p. ej. "Después desayuno") porque el botón solo medía
/// su contenido mínimo.
void main() {
  testWidgets(
    'el selector de "Momento de medición" no desborda con etiquetas largas',
    (WidgetTester tester) async {
      await tester.pumpWidget(const MaterialApp(home: GlucoseScreen()));

      // Recorre todas las opciones reabriendo el desplegable cada vez
      // (tras seleccionar una, el botón pasa a mostrar esa etiqueta).
      // Cualquier overflow -incluido el horizontal del Row ícono+texto-
      // queda como una excepción pendiente que `tester.takeException`
      // detecta tras el pump correspondiente.
      var currentLabel = 'Ahora';
      for (final nextLabel in const [
        'Al despertar',
        'Antes desayuno',
        'Después desayuno',
        'Antes almuerzo',
        'Después almuerzo',
        'Antes cena',
        'Después cena',
        'Antes dormir',
      ]) {
        await tester.tap(find.text(currentLabel));
        await tester.pumpAndSettle();
        expect(
          tester.takeException(),
          isNull,
          reason: 'Overflow al abrir el selector mostrando "$currentLabel"',
        );

        await tester.tap(find.text(nextLabel).last);
        await tester.pumpAndSettle();
        expect(
          tester.takeException(),
          isNull,
          reason: 'Overflow al seleccionar "$nextLabel"',
        );

        currentLabel = nextLabel;
      }
    },
  );
}
