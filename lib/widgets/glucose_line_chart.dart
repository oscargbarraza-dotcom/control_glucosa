import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/glucose_measurement.dart';

/// Gráfico de líneas con la evolución de los valores de glucosa (mg/dL) a
/// lo largo del tiempo.
///
/// Recibe [measurements] ya ordenadas (el orden de dibujo va de la más
/// antigua a la más reciente, de izquierda a derecha); internamente se
/// reordenan si es necesario.
class GlucoseLineChart extends StatelessWidget {
  const GlucoseLineChart({super.key, required this.measurements});

  /// Mediciones a graficar. Debe contener al menos 2 elementos; la pantalla
  /// que lo use es responsable de mostrar un mensaje alternativo si hay
  /// menos datos.
  final List<GlucoseMeasurement> measurements;

  /// Rango de referencia considerado normal, usado para las líneas guía
  /// horizontales (en mg/dL).
  static const double _lowReference = 70;
  static const double _highReference = 180;

  @override
  Widget build(BuildContext context) {
    final chronological = [...measurements]
      ..sort((a, b) => a.measuredAt.compareTo(b.measuredAt));

    final spots = <FlSpot>[
      for (var i = 0; i < chronological.length; i++)
        FlSpot(i.toDouble(), chronological[i].value.toDouble()),
    ];

    final values = chronological.map((m) => m.value.toDouble());
    final minValue = values.reduce((a, b) => a < b ? a : b);
    final maxValue = values.reduce((a, b) => a > b ? a : b);
    final minY = (minValue < _lowReference ? minValue : _lowReference) - 20;
    final maxY = (maxValue > _highReference ? maxValue : _highReference) + 20;

    return LineChart(
      LineChartData(
        minY: minY,
        maxY: maxY,
        minX: 0,
        maxX: (chronological.length - 1).toDouble(),
        gridData: const FlGridData(show: true, drawVerticalLine: false),
        borderData: FlBorderData(
          show: true,
          border: Border.all(color: Colors.grey.shade300),
        ),
        titlesData: FlTitlesData(
          topTitles: const AxisTitles(
            sideTitles: SideTitles(showTitles: false),
          ),
          rightTitles: const AxisTitles(
            sideTitles: SideTitles(showTitles: false),
          ),
          leftTitles: AxisTitles(
            sideTitles: SideTitles(showTitles: true, reservedSize: 40),
          ),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 32,
              interval: _bottomInterval(chronological.length),
              getTitlesWidget: (value, meta) =>
                  _bottomLabel(value: value, measurements: chronological),
            ),
          ),
        ),
        extraLinesData: ExtraLinesData(
          horizontalLines: [
            HorizontalLine(
              y: _lowReference,
              color: Colors.orange,
              strokeWidth: 1,
              dashArray: [6, 4],
            ),
            HorizontalLine(
              y: _highReference,
              color: Colors.orange,
              strokeWidth: 1,
              dashArray: [6, 4],
            ),
          ],
        ),
        lineTouchData: LineTouchData(
          touchTooltipData: LineTouchTooltipData(
            getTooltipItems: (touchedSpots) => touchedSpots.map((spot) {
              final measurement = chronological[spot.x.toInt()];
              final date = DateFormat(
                'dd/MM HH:mm',
              ).format(measurement.measuredAt);
              return LineTooltipItem(
                '${measurement.value} mg/dL\n$date',
                const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                ),
              );
            }).toList(),
          ),
        ),
        lineBarsData: [
          LineChartBarData(
            spots: spots,
            isCurved: true,
            color: Colors.red,
            barWidth: 3,
            dotData: const FlDotData(show: true),
            belowBarData: BarAreaData(
              show: true,
              color: Colors.red.withValues(alpha: 0.12),
            ),
          ),
        ],
      ),
    );
  }

  /// Calcula un intervalo de etiquetas del eje X que evite solapamientos
  /// cuando hay muchas mediciones.
  static double _bottomInterval(int pointCount) {
    if (pointCount <= 6) {
      return 1;
    }
    return (pointCount / 6).ceilToDouble();
  }

  /// Construye la etiqueta del eje X con la fecha corta (dd/MM) de la
  /// medición correspondiente al índice [value].
  static Widget _bottomLabel({
    required double value,
    required List<GlucoseMeasurement> measurements,
  }) {
    final index = value.round();
    if (index < 0 || index >= measurements.length) {
      return const SizedBox.shrink();
    }

    final label = DateFormat('dd/MM').format(measurements[index].measuredAt);
    return Text(label, style: const TextStyle(fontSize: 10));
  }
}
