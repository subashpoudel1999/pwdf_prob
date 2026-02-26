import 'package:flutter/material.dart';
import '../utils/geojson_parser.dart';

// ---------------------------------------------------------------------------
// Descriptive labels for Wildcat output parameters
// Sources: Staley et al. (2017) M1 logistic regression model,
//          Gartner et al. (2014) OLS volume regression,
//          Cannon et al. (2010) combined hazard classification.
// I15 = 15-minute peak rainfall intensity (mm/hr)
// ---------------------------------------------------------------------------
const _kParamMeta = {
  'Area_km2': _ParamMeta(
    label: 'Sub-basin Drainage Area',
    unit: 'km²',
    description:
        'Total contributing drainage area of the sub-basin delineated by D8 '
        'flow routing on the 10 m DEM.',
  ),
  'BurnRatio': _ParamMeta(
    label: 'Burned Area Fraction',
    unit: '0–1',
    description:
        'Proportion of the sub-basin burned at any severity level, '
        'derived from Sentinel-2 dNBR (pixels with dNBR > 100).',
  ),
  'Slope': _ParamMeta(
    label: 'Mean Sub-basin Slope',
    unit: 'rad',
    description:
        'Mean slope of the sub-basin terrain in radians (gradient), '
        'computed from the hydrologically conditioned 10 m DEM.',
  ),
  'P_0': _ParamMeta(
    label: 'Debris-flow Probability — I15 = 16 mm/hr',
    unit: '0–1',
    description:
        'Estimated probability of a post-fire debris flow when the '
        '15-minute peak rainfall intensity is 16 mm/hr (~2-year storm). '
        'Computed using the Staley et al. (2017) M1 logistic model.',
  ),
  'P_1': _ParamMeta(
    label: 'Debris-flow Probability — I15 = 20 mm/hr',
    unit: '0–1',
    description:
        'Estimated probability of a post-fire debris flow at '
        'I15 = 20 mm/hr (~5-year storm). Staley et al. (2017) M1 model.',
  ),
  'P_2': _ParamMeta(
    label: 'Debris-flow Probability — I15 = 24 mm/hr',
    unit: '0–1',
    description:
        'Estimated probability of a post-fire debris flow at '
        'I15 = 24 mm/hr (~10-year storm). Staley et al. (2017) M1 model.',
  ),
  'P_3': _ParamMeta(
    label: 'Debris-flow Probability — I15 = 40 mm/hr',
    unit: '0–1',
    description:
        'Estimated probability of a post-fire debris flow at '
        'I15 = 40 mm/hr (~25-year storm). Staley et al. (2017) M1 model. '
        'This is the primary hazard-classification threshold.',
  ),
  'V_0': _ParamMeta(
    label: 'Estimated Debris-flow Volume — I15 = 16 mm/hr',
    unit: 'm³',
    description:
        'Estimated peak debris-flow volume at I15 = 16 mm/hr. '
        'Computed using the Gartner et al. (2014) OLS regression model '
        'as a function of rainfall intensity, basin area, and burn severity.',
  ),
  'V_1': _ParamMeta(
    label: 'Estimated Debris-flow Volume — I15 = 20 mm/hr',
    unit: 'm³',
    description:
        'Estimated peak debris-flow volume at I15 = 20 mm/hr. '
        'Gartner et al. (2014) OLS model.',
  ),
  'V_2': _ParamMeta(
    label: 'Estimated Debris-flow Volume — I15 = 24 mm/hr',
    unit: 'm³',
    description:
        'Estimated peak debris-flow volume at I15 = 24 mm/hr. '
        'Gartner et al. (2014) OLS model.',
  ),
  'V_3': _ParamMeta(
    label: 'Estimated Debris-flow Volume — I15 = 40 mm/hr',
    unit: 'm³',
    description:
        'Estimated peak debris-flow volume at I15 = 40 mm/hr (extreme event). '
        'Gartner et al. (2014) OLS model.',
  ),
  'H_0': _ParamMeta(
    label: 'Combined Hazard Class — I15 = 16 mm/hr',
    unit: '0–3',
    description:
        'Composite hazard classification at I15 = 16 mm/hr based on '
        'Cannon et al. (2010): '
        '3 = High (P ≥ 0.6 and V ≥ 1000 m³), '
        '2 = Moderate (P ≥ 0.4 or V ≥ 500 m³), '
        '1 = Low (P ≥ 0.2 or V ≥ 100 m³), '
        '0 = Very Low.',
  ),
  'H_1': _ParamMeta(
    label: 'Combined Hazard Class — I15 = 20 mm/hr',
    unit: '0–3',
    description:
        'Composite hazard classification at I15 = 20 mm/hr. '
        'Cannon et al. (2010) thresholds applied to P and V.',
  ),
  'H_2': _ParamMeta(
    label: 'Combined Hazard Class — I15 = 24 mm/hr',
    unit: '0–3',
    description:
        'Composite hazard classification at I15 = 24 mm/hr. '
        'Cannon et al. (2010) thresholds applied to P and V.',
  ),
  'H_3': _ParamMeta(
    label: 'Combined Hazard Class — I15 = 40 mm/hr',
    unit: '0–3',
    description:
        'Composite hazard classification at I15 = 40 mm/hr (extreme rainfall). '
        'Cannon et al. (2010). This is the primary reporting scenario.',
  ),
};

class _ParamMeta {
  final String label;
  final String unit;
  final String description;
  const _ParamMeta(
      {required this.label, required this.unit, required this.description});
}

/// Side panel that shows the attribute table for a selected sub-basin.
class AttributePanel extends StatelessWidget {
  final SubBasinFeature? feature;
  final VoidCallback onClose;

  const AttributePanel({
    super.key,
    required this.feature,
    required this.onClose,
  });

  @override
  Widget build(BuildContext context) {
    if (feature == null) return const SizedBox.shrink();

    final props = feature!.properties;

    return Container(
      width: 340,
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.15),
            blurRadius: 12,
            offset: const Offset(-2, 0),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: Colors.blueGrey.shade800,
            ),
            child: Row(
              children: [
                const Icon(Icons.terrain, color: Colors.white, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Sub-basin ${feature!.label}',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                InkWell(
                  onTap: onClose,
                  child: const Icon(Icons.close, color: Colors.white70, size: 20),
                ),
              ],
            ),
          ),

          // Attribute table
          Expanded(
            child: ListView.separated(
              padding: EdgeInsets.zero,
              itemCount: props.length,
              separatorBuilder: (_, __) =>
                  Divider(height: 1, color: Colors.grey.shade200),
              itemBuilder: (context, index) {
                final key = props.keys.elementAt(index);
                final value = props[key];
                final meta = _kParamMeta[key];

                return Padding(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 14, vertical: 10),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Parameter label + value row
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: Text(
                              meta?.label ?? key,
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w700,
                                color: Colors.blueGrey.shade800,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            _formatValue(value, meta?.unit),
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                              color: _valueColor(key, value),
                            ),
                          ),
                        ],
                      ),
                      // Description text
                      if (meta != null) ...[
                        const SizedBox(height: 3),
                        Text(
                          meta.description,
                          style: TextStyle(
                            fontSize: 10,
                            color: Colors.grey.shade600,
                            height: 1.3,
                          ),
                        ),
                      ],
                    ],
                  ),
                );
              },
            ),
          ),

          // Footer — model attribution
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            color: Colors.grey.shade100,
            child: Text(
              'Models: Staley (2017) M1 · Gartner (2014) · Cannon (2010)\n'
              'Hydrology: WhiteboxTools D8 · DEM: 10 m resolution',
              style: TextStyle(fontSize: 9, color: Colors.grey.shade500),
            ),
          ),
        ],
      ),
    );
  }

  String _formatValue(dynamic value, String? unit) {
    if (value == null) return '—';
    String formatted;
    if (value is double) {
      formatted = value.toStringAsFixed(4)
          .replaceAll(RegExp(r'0+$'), '')
          .replaceAll(RegExp(r'\.$'), '');
    } else {
      formatted = value.toString();
    }
    if (unit != null) return '$formatted $unit';
    return formatted;
  }

  /// Color-code values for quick visual scanning.
  Color _valueColor(String key, dynamic value) {
    if (key.startsWith('P_') && value is num) {
      final p = value.toDouble();
      if (p >= 0.6) return Colors.red.shade700;
      if (p >= 0.4) return Colors.orange.shade700;
      if (p >= 0.2) return Colors.amber.shade800;
      return Colors.green.shade700;
    }
    if (key.startsWith('H_') && value is num) {
      final h = value.toDouble();
      if (h >= 3) return Colors.red.shade700;
      if (h >= 2) return Colors.orange.shade700;
      if (h >= 1) return Colors.amber.shade800;
      return Colors.green.shade700;
    }
    return Colors.blueGrey.shade900;
  }
}
