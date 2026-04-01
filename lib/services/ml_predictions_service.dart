import 'package:flutter/services.dart';

class MlPrediction {
  final String subBasinId;
  final double probability;
  final String riskCategory;
  final bool predictedFlow;
  final bool? observed; // null for fires with no ground truth (Palisades)

  const MlPrediction({
    required this.subBasinId,
    required this.probability,
    required this.riskCategory,
    required this.predictedFlow,
    this.observed,
  });
}

class MlPredictionsService {
  static Future<Map<String, MlPrediction>> loadDolan() async {
    final csv = await rootBundle
        .loadString('assets/ml_predictions/dolan_ml_predictions.csv');
    return _parse(csv, hasObserved: true);
  }

  static Future<Map<String, MlPrediction>> loadPalisades() async {
    final csv = await rootBundle
        .loadString('assets/ml_predictions/palisades_ml_predictions.csv');
    return _parse(csv, hasObserved: false);
  }

  static Map<String, MlPrediction> _parse(String csv,
      {required bool hasObserved}) {
    final result = <String, MlPrediction>{};
    final lines = csv.split('\n');
    if (lines.length < 2) return result;

    final headers = lines[0].split(',').map((h) => h.trim()).toList();
    final idIdx = headers.indexOf('sub_basin_id');
    final probIdx = headers.indexOf('probability');
    final riskIdx = headers.indexOf('risk_category');
    final predIdx = headers.indexOf('predicted_flow');
    final obsIdx =
        hasObserved ? headers.indexOf('debris_flow_observed') : -1;

    if (idIdx < 0 || probIdx < 0 || riskIdx < 0 || predIdx < 0) return result;

    for (int i = 1; i < lines.length; i++) {
      final line = lines[i].trim();
      if (line.isEmpty) continue;
      final cols = line.split(',');
      if (cols.length <= idIdx) continue;

      final id = cols[idIdx].trim();
      final prob = double.tryParse(cols[probIdx].trim()) ?? 0.0;
      final risk = cols[riskIdx].trim();
      final pred = cols[predIdx].trim() == '1';
      final obs = (hasObserved && obsIdx >= 0 && obsIdx < cols.length)
          ? cols[obsIdx].trim() == '1'
          : null;

      result[id] = MlPrediction(
        subBasinId: id,
        probability: prob,
        riskCategory: risk,
        predictedFlow: pred,
        observed: obs,
      );
    }
    return result;
  }
}
