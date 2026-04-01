// ignore_for_file: avoid_print
import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:http/http.dart' as http;

import '../config/app_config.dart';
import '../utils/geojson_parser.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Colour palette
// ─────────────────────────────────────────────────────────────────────────────
const _kAccent  = Color(0xFF7C4DFF);   // deep-purple — ML brand
const _kWildcat = Color(0xFF26C6DA);   // teal         — Wildcat brand
const _kBg      = Color(0xFF0D0B1F);

const _kRiskColors = {
  'Low':       Color(0xFF4CAF50),
  'Moderate':  Color(0xFFFFC107),
  'High':      Color(0xFFFF5722),
  'Very High': Color(0xFFB71C1C),
};

const _kCatColors = {
  'Terrain':           Color(0xFF42A5F5),
  'Burn Severity':     Color(0xFFFF7043),
  'Soil/Geology':      Color(0xFFA5D6A7),
  'NOAA Design Storm': Color(0xFFFFEE58),
  'ERA5 Rainfall':     Color(0xFF80DEEA),
  'Other':             Color(0xFFCE93D8),
};

// ─────────────────────────────────────────────────────────────────────────────
// Screen state enum
// ─────────────────────────────────────────────────────────────────────────────
enum _ScreenState { ready, loading, extracting, results }

enum _RunMode { precomputed, continueGee, fullGee }

// GEE extraction step labels (10 steps matching the backend service)
const _kExtractSteps = [
  'GEE auth + connection test',
  'Load fire perimeter + sub-basins',
  'Download USGS 3DEP DEM via geedim',
  'WhiteboxTools terrain analysis',
  'Terrain zonal statistics per basin',
  'Landsat-8 dNBR burn severity (GEE)',
  'ERA5-Land rainfall + soil moisture (GEE)',
  'NOAA Atlas 14 design storms',
  'SoilGrids v2.0 soil properties',
  'Assemble features + RF v3 inference',
];

// Pipeline steps shown during loading
const _kPipelineSteps = [
  (Icons.terrain,            'Loading Wildcat basins.geojson (886 pfdf-delineated basins)…'),
  (Icons.science,            'Reconstructing Staley M1 step-by-step for each basin × 4 scenarios…'),
  (Icons.psychology_outlined,'Loading ML model v3 predictions (dolan_predictions_v3.csv)…'),
  (Icons.bar_chart,          'Computing feature importances and probability histograms…'),
  (Icons.compare_arrows,     'Building side-by-side comparison dataset…'),
];

// ─────────────────────────────────────────────────────────────────────────────
// Data models
// ─────────────────────────────────────────────────────────────────────────────

class _ScenarioDetail {
  final int idx;
  final double i15, r15, T, F, S, tTerm, fTerm, sTerm;
  final double logit, pCalc, pStored;
  final double? vCalc, vStored, bmhKm2, reliefM;
  final int? hazard;
  final String riskTier;

  const _ScenarioDetail({
    required this.idx,
    required this.i15, required this.r15,
    required this.T, required this.F, required this.S,
    required this.tTerm, required this.fTerm, required this.sTerm,
    required this.logit, required this.pCalc, required this.pStored,
    this.vCalc, this.vStored, this.bmhKm2, this.reliefM,
    this.hazard, required this.riskTier,
  });

  factory _ScenarioDetail.fromJson(Map<String, dynamic> j) => _ScenarioDetail(
    idx:     j['scenario_idx'] as int,
    i15:     (j['i15']    as num).toDouble(),
    r15:     (j['r15']    as num).toDouble(),
    T:       (j['T']      as num).toDouble(),
    F:       (j['F']      as num).toDouble(),
    S:       (j['S']      as num).toDouble(),
    tTerm:   (j['T_term'] as num).toDouble(),
    fTerm:   (j['F_term'] as num).toDouble(),
    sTerm:   (j['S_term'] as num).toDouble(),
    logit:   (j['logit']    as num).toDouble(),
    pCalc:   (j['P_calc']   as num).toDouble(),
    pStored: (j['P_stored'] as num).toDouble(),
    vCalc:   j['V_calc']   != null ? (j['V_calc']   as num).toDouble() : null,
    vStored: j['V_stored'] != null ? (j['V_stored'] as num).toDouble() : null,
    bmhKm2:  j['bmh_km2']  != null ? (j['bmh_km2']  as num).toDouble() : null,
    reliefM: j['relief_m'] != null ? (j['relief_m'] as num).toDouble() : null,
    hazard:  j['H'] as int?,
    riskTier: j['risk_tier'] as String,
  );
}

class _BasinDetail {
  final int segmentId;
  final double areaKm2;
  final bool isBurned, isSteep, inPerim;
  final List<_ScenarioDetail> scenarios;

  const _BasinDetail({
    required this.segmentId, required this.areaKm2,
    required this.isBurned, required this.isSteep, required this.inPerim,
    required this.scenarios,
  });

  factory _BasinDetail.fromJson(Map<String, dynamic> j) => _BasinDetail(
    segmentId: (j['segment_id'] as num).toInt(),
    areaKm2:   (j['area_km2']  as num).toDouble(),
    isBurned:  j['is_burned'] == 1,
    isSteep:   j['is_steep']  == 1,
    inPerim:   j['in_perim']  == 1,
    scenarios: (j['scenarios'] as List)
        .map((s) => _ScenarioDetail.fromJson(s as Map<String, dynamic>))
        .toList(),
  );
}


class _MlMetrics {
  final double aucRoc, aucPr, accuracy, precision, recall, far, f1, threshold;
  final int tp, tn, fp, fn, trainN, testN, nFeatures;

  const _MlMetrics({
    required this.aucRoc, required this.aucPr, required this.accuracy,
    required this.precision, required this.recall, required this.far,
    required this.f1, required this.threshold,
    required this.tp, required this.tn, required this.fp, required this.fn,
    required this.trainN, required this.testN, required this.nFeatures,
  });

  factory _MlMetrics.fromJson(Map<String, dynamic> j) => _MlMetrics(
    aucRoc:    (j['auc_roc']   as num).toDouble(),
    aucPr:     (j['auc_pr']    as num).toDouble(),
    accuracy:  (j['accuracy']  as num).toDouble(),
    precision: (j['precision'] as num).toDouble(),
    recall:    (j['recall']    as num).toDouble(),
    far:       (j['far']       as num).toDouble(),
    f1:        (j['f1']        as num).toDouble(),
    threshold: (j['threshold'] as num).toDouble(),
    tp: j['tp_test'] as int,  tn: j['tn_test'] as int,
    fp: j['fp_test'] as int,  fn: j['fn_test'] as int,
    trainN: j['train_n'] as int, testN: j['test_n'] as int,
    nFeatures: j['n_features'] as int,
  );
}

class _FeatureImp {
  final String feature, category;
  final double importance;
  const _FeatureImp({required this.feature, required this.category, required this.importance});
}

class _HistBin {
  final double lo, hi;
  final int count;
  const _HistBin({required this.lo, required this.hi, required this.count});
}

// ─────────────────────────────────────────────────────────────────────────────
// Screen
// ─────────────────────────────────────────────────────────────────────────────

class MlComparisonScreen extends StatefulWidget {
  const MlComparisonScreen({super.key});

  @override
  State<MlComparisonScreen> createState() => _MlComparisonScreenState();
}

class _MlComparisonScreenState extends State<MlComparisonScreen>
    with SingleTickerProviderStateMixin {
  static final String _base = AppConfig.backendUrl;

  late TabController _tab;

  _ScreenState _screenState = _ScreenState.ready;
  bool _useCachedData = true;
  String? _error;

  // Pipeline loading state
  int _loadStep    = 0;
  bool _stepDone   = false;
  String? _loadError;   // error shown on loading screen
  Timer? _stepTimer;

  // Parsed data
  ParsedGeoJson? _wildcatGeoJson;
  ParsedGeoJson? _mlGeoJson;        // 47-basin ML geojson with ML_Prob
  final Map<int, _BasinDetail> _basinDetails = {};
  _MlMetrics?       _mlMetrics;
  List<_FeatureImp> _featureImps = [];
  List<_HistBin>    _mlHistogram = [];
  Map<String, Map<String, int>>      _wcRiskDist = {};
  Map<String, int>                   _mlRiskDist = {};
  Map<String, Map<String, dynamic>>  _wcStats    = {};

  // UI state (results view)
  int  _scenarioIdx    = 2;   // default: I15=24 mm/hr
  bool _useSatellite   = true;
  int? _selectedWcBasin;     // index into wildcatGeoJson.features
  int? _selectedMlBasin;     // index into mlGeoJson.features
  final MapController _mapCtrl   = MapController();
  final MapController _mlMapCtrl = MapController();
  static const _scenarioLabels = ['16 mm/hr', '20 mm/hr', '24 mm/hr', '40 mm/hr'];

  // Selected run mode
  _RunMode _runMode = _RunMode.precomputed;

  // GEE extraction state
  final TextEditingController _geeProjectCtrl =
      TextEditingController(text: 'ee-poudelsubash89');
  bool   _redownloadDem       = false;
  String _extractJobId        = '';
  int    _extractStep         = 0;
  int    _extractTotal        = 10;
  String _extractStepName     = '';
  String _extractMessage      = '';
  int    _extractProgress     = 0;
  int    _extractElapsed      = 0;
  int    _extractPollFailures = 0;   // consecutive poll failures
  // base64-encoded PNG visualizations keyed by name
  final Map<String, String> _extractViz = {};
  Timer? _extractPollTimer;

  @override
  void initState() {
    super.initState();
    // 2 tabs: Side-by-Side | ML Performance
    _tab = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tab.dispose();
    _stepTimer?.cancel();
    _extractPollTimer?.cancel();
    _geeProjectCtrl.dispose();
    super.dispose();
  }

  // ── Load flow ─────────────────────────────────────────────────────────────

  void _startLoad() {
    setState(() {
      _screenState = _ScreenState.loading;
      _loadStep    = 0;
      _stepDone    = false;
      _loadError   = null;
      _error       = null;
    });
    _animateSteps();
  }

  void _animateSteps() {
    _stepTimer?.cancel();
    _stepTimer = Timer.periodic(const Duration(milliseconds: 700), (t) async {
      if (!mounted) { t.cancel(); return; }
      final next = _loadStep + 1;
      if (next >= _kPipelineSteps.length) {
        t.cancel();
        setState(() => _stepDone = true);
        await Future.delayed(const Duration(milliseconds: 400));
        if (mounted) _fetchData();
      } else {
        setState(() => _loadStep = next);
      }
    });
  }

  Future<void> _fetchData() async {
    try {
      final resp = await http.get(
        Uri.parse('$_base/ml/dolan/comparison?use_cache=$_useCachedData'),
        headers: {'Accept': 'application/json'},
      ).timeout(const Duration(minutes: 5));

      if (resp.statusCode != 200) {
        throw Exception('Backend error ${resp.statusCode}: ${resp.body}');
      }
      final json = jsonDecode(resp.body) as Map<String, dynamic>;
      _parseData(json);
      if (mounted) setState(() => _screenState = _ScreenState.results);
    } catch (e) {
      if (mounted) setState(() {
        _loadError   = e.toString();
        _screenState = _ScreenState.loading; // stay on loading screen, show error
      });
    }
  }

  // ── GEE feature extraction flow ───────────────────────────────────────────

  Future<void> _startExtraction({String mode = 'full'}) async {
    final project = _geeProjectCtrl.text.trim();
    if (project.isEmpty) return;
    setState(() {
      _screenState      = _ScreenState.extracting;
      _extractStep      = 0;
      _extractTotal     = 10;
      _extractStepName  = 'Starting…';
      _extractMessage   = '';
      _extractProgress  = 0;
      _extractElapsed   = 0;
      _extractViz.clear();
      _error            = null;
    });
    try {
      final resp = await http.post(
        Uri.parse('$_base/ml/dolan/extract-features'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'gee_project':    project,
          'redownload_dem': _redownloadDem,
          'mode':           mode,
        }),
      ).timeout(const Duration(minutes: 3));
      if (resp.statusCode != 200) {
        throw Exception('Backend error ${resp.statusCode}: ${resp.body}');
      }
      final body = jsonDecode(resp.body) as Map<String, dynamic>;
      setState(() {
        _extractJobId    = body['job_id'] as String;
        _extractStepName = 'Job queued — waiting for first update…';
      });
      _extractPollTimer = Timer.periodic(
        const Duration(seconds: 2), (_) => _pollExtraction());
    } catch (e) {
      if (mounted) setState(() {
        _error       = e.toString();
        _screenState = _ScreenState.ready;
      });
    }
  }

  Future<void> _pollExtraction() async {
    if (_extractJobId.isEmpty) return;
    try {
      final resp = await http.get(
        Uri.parse('$_base/ml/dolan/extract-features/status/$_extractJobId'),
      ).timeout(const Duration(seconds: 15));
      if (!mounted) return;
      if (resp.statusCode != 200) return;
      final data = jsonDecode(resp.body) as Map<String, dynamic>;

      final status    = data['status'] as String;
      final viz       = data['visualizations'] as Map<String, dynamic>? ?? {};

      setState(() {
        _extractStep     = (data['step']      as num?)?.toInt()    ?? _extractStep;
        _extractTotal    = (data['total_steps'] as num?)?.toInt()  ?? _extractTotal;
        _extractStepName = data['step_name']  as String?           ?? _extractStepName;
        _extractMessage  = data['message']    as String?           ?? _extractMessage;
        _extractProgress = (data['progress']  as num?)?.toInt()    ?? _extractProgress;
        _extractElapsed  = (data['elapsed_sec'] as num?)?.toInt()  ?? _extractElapsed;
        for (final k in viz.keys) {
          _extractViz[k] = viz[k] as String;
        }
      });

      if (status == 'complete') {
        _extractPollTimer?.cancel();
        // merge live_geojson into ML map, then load full comparison
        final liveGeo = data['live_geojson'] as Map<String, dynamic>?;
        if (liveGeo != null) {
          setState(() => _mlGeoJson = parseGeoJson(liveGeo));
        }
        // now fetch the comparison data to populate Wildcat + metrics
        await _fetchDataAfterExtraction();
      } else if (status == 'error') {
        _extractPollTimer?.cancel();
        setState(() {
          _error       = data['error'] as String? ?? 'Unknown extraction error';
          _screenState = _ScreenState.ready;
        });
      }
    } catch (_) {
      // transient poll error — keep polling
    }
  }

  Future<void> _fetchDataAfterExtraction() async {
    try {
      // use_cache=false so the freshly-written CSV is used for RF inference
      final resp = await http.get(
        Uri.parse('$_base/ml/dolan/comparison?use_cache=false'),
        headers: {'Accept': 'application/json'},
      ).timeout(const Duration(minutes: 5));
      if (resp.statusCode != 200) {
        throw Exception('Backend error ${resp.statusCode}: ${resp.body}');
      }
      final json = jsonDecode(resp.body) as Map<String, dynamic>;
      _parseData(json);
      // Override the ML geojson with our extraction result (it has the same data)
      if (mounted) setState(() => _screenState = _ScreenState.results);
    } catch (e) {
      if (mounted) setState(() {
        _error       = e.toString();
        _screenState = _ScreenState.ready;
      });
    }
  }

  void _parseData(Map<String, dynamic> json) {
    // Wildcat
    final wc = json['wildcat'] as Map<String, dynamic>;
    _wildcatGeoJson = parseGeoJson(wc['geojson'] as Map<String, dynamic>);

    for (final d in (wc['basin_details'] as List)) {
      final bd = _BasinDetail.fromJson(d as Map<String, dynamic>);
      _basinDetails[bd.segmentId] = bd;
    }

    _wcRiskDist = {};
    for (final k in (wc['risk_dist_by_scenario'] as Map<String, dynamic>).keys) {
      final m = (wc['risk_dist_by_scenario'] as Map<String, dynamic>)[k] as Map<String, dynamic>;
      _wcRiskDist[k] = m.map((mk, mv) => MapEntry(mk, (mv as num).toInt()));
    }

    _wcStats = {};
    for (final k in (wc['stats_by_scenario'] as Map<String, dynamic>).keys) {
      _wcStats[k] = (wc['stats_by_scenario'] as Map<String, dynamic>)[k] as Map<String, dynamic>;
    }

    // ML
    final ml = json['ml'] as Map<String, dynamic>;
    _mlMetrics = _MlMetrics.fromJson(ml['metrics'] as Map<String, dynamic>);

    _featureImps = (ml['feature_importances'] as List).map((f) {
      final m = f as Map<String, dynamic>;
      return _FeatureImp(
        feature:    m['feature']    as String,
        category:   m['category']   as String,
        importance: (m['importance'] as num).toDouble(),
      );
    }).toList();

    _mlHistogram = (ml['probability_histogram'] as List).map((b) {
      final m = b as Map<String, dynamic>;
      return _HistBin(
        lo: (m['lo'] as num).toDouble(),
        hi: (m['hi'] as num).toDouble(),
        count: (m['count'] as num).toInt(),
      );
    }).toList();

    final rd = ml['risk_distribution'] as Map<String, dynamic>;
    _mlRiskDist = rd.map((k, v) => MapEntry(k, (v as num).toInt()));

    // ML live GeoJSON (47 basins with geometries for map rendering)
    if (ml['live_geojson'] != null) {
      _mlGeoJson = parseGeoJson(ml['live_geojson'] as Map<String, dynamic>);
    }
  }

  // ── Colour helpers ───────────────────────────────────────────────────────

  Color _probColor(double p) {
    if (p < 0.25) return const Color(0xFF4CAF50);
    if (p < 0.50) return const Color(0xFFFFC107);
    if (p < 0.75) return const Color(0xFFFF5722);
    return const Color(0xFFB71C1C);
  }

  Color _hazardColor(int h) {
    const c = [Color(0xFF757575), Color(0xFF4CAF50), Color(0xFFFFC107), Color(0xFFB71C1C)];
    return c[h.clamp(0, 3)];
  }

  // ── Map interaction ──────────────────────────────────────────────────────

  void _onMapTap(TapPosition _, LatLng latlng) {
    if (_wildcatGeoJson == null) return;
    final features = _wildcatGeoJson!.features;
    for (int i = 0; i < features.length; i++) {
      final f = features[i];
      if (f.rings.isNotEmpty && _pointInPoly(latlng, f.rings[0])) {
        setState(() => _selectedWcBasin = i);
        _showBasinSheet(i);
        return;
      }
    }
    setState(() => _selectedWcBasin = null);
  }

  bool _pointInPoly(LatLng p, List<LatLng> poly) {
    bool inside = false;
    int j = poly.length - 1;
    for (int i = 0; i < poly.length; i++) {
      if (((poly[i].latitude > p.latitude) != (poly[j].latitude > p.latitude)) &&
          (p.longitude < (poly[j].longitude - poly[i].longitude) *
              (p.latitude - poly[i].latitude) /
              (poly[j].latitude - poly[i].latitude) +
              poly[i].longitude)) {
        inside = !inside;
      }
      j = i;
    }
    return inside;
  }

  void _onMlMapTap(TapPosition _, LatLng latlng) {
    if (_mlGeoJson == null) return;
    final features = _mlGeoJson!.features;
    for (int i = 0; i < features.length; i++) {
      final f = features[i];
      if (f.rings.isNotEmpty && _pointInPoly(latlng, f.rings[0])) {
        setState(() => _selectedMlBasin = i);
        _showMlBasinSheet(i);
        return;
      }
    }
    setState(() => _selectedMlBasin = null);
  }

  void _showMlBasinSheet(int featureIdx) {
    final feat = _mlGeoJson!.features[featureIdx];
    final props = feat.properties;
    final subId   = props['Sub_ID']    ?? props['Segment_ID'] ?? '—';
    final prob    = (props['ML_Prob']  as num?)?.toDouble() ?? 0.0;
    final pred    = (props['ML_Pred']  as num?)?.toInt()    ?? 0;
    final risk    = props['Risk_Category'] as String? ?? '—';
    final probPct = (props['Probability_Pct'] as num?)?.toDouble()
                    ?? (prob * 100);
    final areaKm2 = (props['Area_km2'] as num?)?.toDouble();

    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF0D1B2A),
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (_) => Padding(
        padding: const EdgeInsets.fromLTRB(24, 12, 24, 32),
        child: Column(mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(child: Container(
              width: 40, height: 4,
              margin: const EdgeInsets.only(bottom: 16),
              decoration: BoxDecoration(color: Colors.white24,
                  borderRadius: BorderRadius.circular(2)),
            )),
            Row(children: [
              const Icon(Icons.psychology_outlined, color: _kAccent, size: 18),
              const SizedBox(width: 8),
              Text('ML Basin — $subId',
                  style: const TextStyle(color: Colors.white,
                      fontSize: 16, fontWeight: FontWeight.bold)),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: (_kRiskColors[risk] ?? Colors.white54)
                      .withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(
                    color: (_kRiskColors[risk] ?? Colors.white54)
                        .withValues(alpha: 0.5)),
                ),
                child: Text(risk,
                    style: TextStyle(
                        color: _kRiskColors[risk] ?? Colors.white54,
                        fontSize: 11, fontWeight: FontWeight.bold)),
              ),
            ]),
            if (areaKm2 != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text('Area: ${areaKm2.toStringAsFixed(3)} km²',
                    style: const TextStyle(color: Colors.white54, fontSize: 12)),
              ),
            const SizedBox(height: 20),
            Row(children: [
              _mlResultCard('Probability', '${probPct.toStringAsFixed(1)}%',
                  _probColor(prob)),
              const SizedBox(width: 12),
              _mlResultCard('Predicted', pred == 1 ? 'Flow' : 'No Flow',
                  pred == 1 ? Colors.redAccent : Colors.blueGrey),
              const SizedBox(width: 12),
              _mlResultCard('Raw prob', prob.toStringAsFixed(4), _kAccent),
            ]),
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Colors.black.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: _kAccent.withValues(alpha: 0.2)),
              ),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Random Forest v3 — How this prediction was made',
                      style: TextStyle(color: _kAccent, fontSize: 12,
                          fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  const Text(
                    'The model uses 37 features: terrain (TWI, slope, relief, '
                    'curvature), burn severity (Burn_High, RdNBR), soil '
                    '(clay, Ksat, depth), NOAA design storms (P15/P30/P60 '
                    '10-yr), and ERA5 rainfall (prcp_int60, prcp_acc, SM_Pre).\n\n'
                    'predict_proba returns the fraction of 500 trees that voted '
                    '"debris flow". The displayed probability is that fraction.',
                    style: TextStyle(color: Colors.white54, fontSize: 11,
                        height: 1.5),
                  ),
                  const SizedBox(height: 8),
                  Text('Threshold: ${_mlMetrics?.threshold.toStringAsFixed(4) ?? "—"}  '
                      '→  ${prob >= (_mlMetrics?.threshold ?? 0.5) ? "FLOW predicted ✓" : "No flow predicted"}',
                      style: TextStyle(
                          color: pred == 1 ? Colors.green : Colors.white54,
                          fontSize: 11, fontWeight: FontWeight.w600)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _mlResultCard(String label, String value, Color color) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.10),
      borderRadius: BorderRadius.circular(10),
      border: Border.all(color: color.withValues(alpha: 0.3)),
    ),
    child: Column(children: [
      Text(label, style: TextStyle(color: color.withValues(alpha: 0.7),
          fontSize: 10, fontWeight: FontWeight.w600)),
      const SizedBox(height: 4),
      Text(value, style: TextStyle(color: color, fontSize: 16,
          fontWeight: FontWeight.bold)),
    ]),
  );

  void _showBasinSheet(int featureIdx) {
    final feat  = _wildcatGeoJson!.features[featureIdx];
    final segId = feat.properties['Segment_ID'];
    final detail = segId != null ? _basinDetails[segId] : null;

    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF0D1B2A),
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (_) => _BasinDetailSheet(
        feat: feat, detail: detail,
        scenarioIdx: _scenarioIdx,
        probColor: _probColor, hazardColor: _hazardColor,
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Build
  // ─────────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _kBg,
      appBar: AppBar(
        backgroundColor: const Color(0xFF130D2E),
        foregroundColor: Colors.white,
        title: const Row(children: [
          Icon(Icons.compare_arrows, color: _kAccent),
          SizedBox(width: 10),
          Text('Wildcat  vs  ML Model v3',
              style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
          SizedBox(width: 10),
          Text('Dolan Fire 2020',
              style: TextStyle(color: Colors.white38, fontSize: 13,
                  fontWeight: FontWeight.normal)),
        ]),
        actions: [
          if (_screenState == _ScreenState.results)
            TextButton.icon(
              onPressed: () => setState(() {
                _screenState = _ScreenState.ready;
                _selectedWcBasin = null;
              }),
              icon: const Icon(Icons.refresh, color: _kAccent),
              label: const Text('Reset', style: TextStyle(color: _kAccent)),
            ),
        ],
        bottom: _screenState == _ScreenState.results ? TabBar(
          controller: _tab,
          indicatorColor: _kAccent,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white38,
          tabs: const [
            Tab(icon: Icon(Icons.compare_arrows), text: 'Side-by-Side'),
            Tab(icon: Icon(Icons.analytics_outlined), text: 'ML Performance'),
          ],
        ) : null,
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    switch (_screenState) {
      case _ScreenState.ready:      return _buildReady();
      case _ScreenState.loading:    return _buildLoading();
      case _ScreenState.extracting: return _buildExtracting();
      case _ScreenState.results:    return _buildResults();
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // READY screen
  // ══════════════════════════════════════════════════════════════════════════

  void _onRunPressed() {
    switch (_runMode) {
      case _RunMode.precomputed:
        _useCachedData = true;
        _startLoad();
      case _RunMode.continueGee:
        _startExtraction(mode: 'continue');
      case _RunMode.fullGee:
        _startExtraction(mode: 'full');
    }
  }

  Widget _buildReady() {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 660),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [

            // Title block
            Row(children: [
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: _kAccent.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: _kAccent.withValues(alpha: 0.3)),
                ),
                child: const Icon(Icons.compare_arrows, color: _kAccent, size: 36),
              ),
              const SizedBox(width: 20),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Wildcat  vs  ML Model v3',
                      style: TextStyle(color: Colors.white,
                          fontSize: 22, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Text('Dolan Fire 2020  •  Side-by-side comparison',
                      style: TextStyle(color: Colors.white.withValues(alpha: 0.5),
                          fontSize: 13)),
                ])),
            ]),

            const SizedBox(height: 32),

            // What this does
            const Text('What this screen does',
                style: TextStyle(color: Colors.white70,
                    fontSize: 13, fontWeight: FontWeight.w600)),
            const SizedBox(height: 12),
            const Text(
              'Shows the USGS Wildcat (Staley M1 logistic regression) and our '
              'Random Forest v3 results side by side on the same screen:\n\n'
              '  • Left panel — Wildcat map: 886 pfdf-delineated basins coloured by '
              'debris-flow probability P for the selected rainfall scenario. '
              'Tap any basin to see the full Staley M1 step-by-step and Gartner volume '
              'calculation with real numbers.\n\n'
              '  • Right panel — ML Model v3: 492 GIS-delineated basins with predicted '
              'outcome (0/1) and continuous probability (0–1), sorted by risk. '
              'Note: different basin delineations — no 1-to-1 match is possible.',
              style: TextStyle(color: Colors.white54, fontSize: 12, height: 1.65),
            ),

            const SizedBox(height: 32),

            // ── Mode selector ──────────────────────────────────────────────
            const Text('Choose how to run',
                style: TextStyle(color: Colors.white70,
                    fontSize: 13, fontWeight: FontWeight.w600)),
            const SizedBox(height: 12),

            _modeCard(
              mode:    _RunMode.precomputed,
              icon:    Icons.bolt,
              color:   _kAccent,
              title:   'Pre-computed results',
              subtitle:'Instant — reads notebook CSV outputs. No GEE needed.',
              detail:  '492 basins from dolan_predictions_v3.csv. '
                       'Best if you just want to explore the comparison.',
            ),
            const SizedBox(height: 10),
            _modeCard(
              mode:    _RunMode.continueGee,
              icon:    Icons.fast_forward_rounded,
              color:   const Color(0xFF26C6DA),
              title:   'Continue from downloads',
              subtitle:'Skips DEM + dNBR download — re-runs all processing steps.',
              detail:  'Uses existing gee_dem_live.tif and gee_dnbr_live.tif. '
                       'Re-runs terrain analysis, ERA5, NOAA, SoilGrids and ML '
                       'inference from scratch with live visualizations. '
                       '~5–8 min.',
            ),
            const SizedBox(height: 10),
            _modeCard(
              mode:    _RunMode.fullGee,
              icon:    Icons.cloud_download_outlined,
              color:   const Color(0xFF66BB6A),
              title:   'Full GEE extraction',
              subtitle:'Everything from scratch — DEM, burn severity, terrain, soil, ML.',
              detail:  'Downloads USGS 3DEP DEM via geedim (2–5 min), fetches '
                       'Landsat-8 dNBR, ERA5-Land rainfall, NOAA Atlas 14, SoilGrids. '
                       'Each step shows a live visualization. ~10–15 min total.',
            ),

            // GEE project field — shown only for GEE modes
            if (_runMode != _RunMode.precomputed) ...[
              const SizedBox(height: 20),
              Row(children: [
                const Text('GEE Project ID',
                    style: TextStyle(color: Colors.white60, fontSize: 12)),
                const SizedBox(width: 10),
                Expanded(
                  child: TextField(
                    controller: _geeProjectCtrl,
                    style: const TextStyle(color: Colors.white, fontSize: 12),
                    decoration: InputDecoration(
                      isDense: true,
                      contentPadding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 8),
                      filled: true,
                      fillColor: Colors.white.withValues(alpha: 0.06),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: BorderSide(
                            color: Colors.white.withValues(alpha: 0.2)),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: BorderSide(
                            color: Colors.white.withValues(alpha: 0.15)),
                      ),
                      hintText: 'e.g. ee-poudelsubash89',
                      hintStyle: const TextStyle(
                          color: Colors.white24, fontSize: 12),
                    ),
                  ),
                ),
              ]),
              // Re-download DEM toggle — only for full mode
              if (_runMode == _RunMode.fullGee) ...[
                const SizedBox(height: 12),
                Row(children: [
                  Expanded(child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Text('Re-download DEM',
                          style: TextStyle(color: Colors.white70,
                              fontSize: 12, fontWeight: FontWeight.w500)),
                      Text(
                        _redownloadDem
                            ? 'Will fetch fresh 10m DEM via geedim (~44 MB, 2–5 min).'
                            : 'Skips DEM if gee_dem_live.tif already exists (saves 2–5 min).',
                        style: const TextStyle(color: Colors.white30,
                            fontSize: 10, height: 1.4),
                      ),
                    ],
                  )),
                  Switch(
                    value: _redownloadDem,
                    onChanged: (v) => setState(() => _redownloadDem = v),
                    activeThumbColor: const Color(0xFF66BB6A),
                  ),
                ]),
              ],
            ],

            const SizedBox(height: 28),

            // ── Run button ─────────────────────────────────────────────────
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _onRunPressed,
                icon: Icon(_runMode == _RunMode.precomputed
                    ? Icons.play_arrow_rounded
                    : Icons.rocket_launch_outlined,
                    size: 20),
                label: Text(
                  switch (_runMode) {
                    _RunMode.precomputed  => 'Load Comparison',
                    _RunMode.continueGee  => 'Continue from Downloads',
                    _RunMode.fullGee      => 'Start Full GEE Extraction',
                  },
                  style: const TextStyle(
                      fontSize: 15, fontWeight: FontWeight.bold),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: switch (_runMode) {
                    _RunMode.precomputed  => _kAccent,
                    _RunMode.continueGee  => const Color(0xFF26C6DA),
                    _RunMode.fullGee      => const Color(0xFF66BB6A),
                  },
                  foregroundColor: _runMode == _RunMode.precomputed
                      ? Colors.white : Colors.black,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                ),
              ),
            ),

            if (_error != null) ...[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.red.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                      color: Colors.redAccent.withValues(alpha: 0.4)),
                ),
                child: Row(children: [
                  const Icon(Icons.error_outline,
                      color: Colors.redAccent, size: 18),
                  const SizedBox(width: 10),
                  Expanded(child: Text(_error!,
                      style: const TextStyle(
                          color: Colors.redAccent, fontSize: 11))),
                ]),
              ),
            ],
          ]),
        ),
      ),
    );
  }

  Widget _modeCard({
    required _RunMode mode,
    required IconData icon,
    required Color color,
    required String title,
    required String subtitle,
    required String detail,
  }) {
    final selected = _runMode == mode;
    return GestureDetector(
      onTap: () => setState(() => _runMode = mode),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: selected
              ? color.withValues(alpha: 0.10)
              : Colors.white.withValues(alpha: 0.03),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: selected
                ? color.withValues(alpha: 0.55)
                : Colors.white.withValues(alpha: 0.08),
            width: selected ? 1.5 : 1.0,
          ),
        ),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          // Radio circle
          Container(
            width: 20, height: 20,
            margin: const EdgeInsets.only(top: 2),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(
                  color: selected ? color : Colors.white24, width: 2),
              color: selected ? color : Colors.transparent,
            ),
            child: selected
                ? const Icon(Icons.check, size: 12, color: Colors.black)
                : null,
          ),
          const SizedBox(width: 14),
          // Icon
          Container(
            padding: const EdgeInsets.all(7),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: color, size: 18),
          ),
          const SizedBox(width: 14),
          // Text
          Expanded(child: Column(
            crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title,
                  style: TextStyle(
                      color: selected ? color : Colors.white,
                      fontSize: 13,
                      fontWeight: FontWeight.w700)),
              const SizedBox(height: 3),
              Text(subtitle,
                  style: const TextStyle(
                      color: Colors.white60, fontSize: 11,
                      fontWeight: FontWeight.w500)),
              if (selected) ...[
                const SizedBox(height: 6),
                Text(detail,
                    style: TextStyle(
                        color: color.withValues(alpha: 0.75),
                        fontSize: 10.5, height: 1.5)),
              ],
            ],
          )),
        ]),
      ),
    );
  }

  // ══════════════════════════════════════════════════════════════════════════
  // LOADING screen — animated pipeline steps
  // ══════════════════════════════════════════════════════════════════════════

  Widget _buildLoading() {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 520),
        child: Padding(
          padding: const EdgeInsets.all(40),
          child: Column(mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Loading comparison data…',
                  style: TextStyle(color: Colors.white,
                      fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 28),
              ...List.generate(_kPipelineSteps.length, (i) {
                final done    = i < _loadStep || _stepDone;
                final current = i == _loadStep && !_stepDone;
                final step    = _kPipelineSteps[i];
                return Padding(
                  padding: const EdgeInsets.only(bottom: 14),
                  child: Row(children: [
                    Container(
                      width: 32, height: 32,
                      decoration: BoxDecoration(
                        color: done
                            ? Colors.green.withValues(alpha: 0.15)
                            : current
                                ? _kAccent.withValues(alpha: 0.15)
                                : Colors.white.withValues(alpha: 0.04),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: done
                              ? Colors.green.withValues(alpha: 0.5)
                              : current
                                  ? _kAccent.withValues(alpha: 0.6)
                                  : Colors.white12,
                        ),
                      ),
                      child: done
                          ? const Icon(Icons.check, color: Colors.green, size: 16)
                          : current
                              ? const SizedBox(width: 16, height: 16,
                                  child: Padding(
                                    padding: EdgeInsets.all(6),
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2, color: _kAccent),
                                  ))
                              : Icon(step.$1,
                                  color: Colors.white24, size: 15),
                    ),
                    const SizedBox(width: 12),
                    Expanded(child: Text(step.$2,
                        style: TextStyle(
                          color: done
                              ? Colors.green.withValues(alpha: 0.85)
                              : current
                                  ? Colors.white
                                  : Colors.white24,
                          fontSize: 12,
                          height: 1.4,
                        ))),
                  ]),
                );
              }),

              // After all steps are ticked: spinner or error
              if (_stepDone) ...[
                const SizedBox(height: 20),
                if (_loadError != null)
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.red.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                          color: Colors.redAccent.withValues(alpha: 0.4)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Row(children: [
                          Icon(Icons.error_outline,
                              color: Colors.redAccent, size: 16),
                          SizedBox(width: 8),
                          Text('Backend error',
                              style: TextStyle(
                                  color: Colors.redAccent,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 12)),
                        ]),
                        const SizedBox(height: 6),
                        Text(_loadError!,
                            style: const TextStyle(
                                color: Colors.redAccent, fontSize: 11)),
                        const SizedBox(height: 10),
                        SizedBox(
                          width: double.infinity,
                          child: OutlinedButton(
                            onPressed: () => setState(() {
                              _screenState = _ScreenState.ready;
                              _loadError   = null;
                            }),
                            style: OutlinedButton.styleFrom(
                              foregroundColor: Colors.white54,
                              side: const BorderSide(color: Colors.white24),
                            ),
                            child: const Text('Back'),
                          ),
                        ),
                      ],
                    ),
                  )
                else
                  Row(children: [
                    const SizedBox(
                      width: 18, height: 18,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white38),
                    ),
                    const SizedBox(width: 12),
                    Text('Fetching data from backend…',
                        style: TextStyle(
                            color: Colors.white.withValues(alpha: 0.45),
                            fontSize: 12)),
                  ]),
              ],
            ],
          ),
        ),
      ),
    );
  }

  // ══════════════════════════════════════════════════════════════════════════
  // EXTRACTING screen — live GEE pipeline progress + visualizations
  // ══════════════════════════════════════════════════════════════════════════

  static const _kVizLabels = {
    'perimeter': 'Fire Perimeter & Sub-Basins',
    'dem':       'USGS 3DEP DEM — Downloaded via geedim',
    'terrain':   'WhiteboxTools: Slope & TWI',
    'dnbr':      'Landsat-8 dNBR Burn Severity',
    'era5':      'ERA5-Land Rainfall Features',
    'features':  'Feature Distributions (37 features)',
    'ml_prob':   'RF v3 Debris-flow Probability Map',
  };

  Widget _buildExtracting() {
    final pct = _extractTotal > 0
        ? _extractProgress / 100.0
        : 0.0;
    final mins = _extractElapsed ~/ 60;
    final secs = _extractElapsed % 60;
    final elapsed = mins > 0
        ? '${mins}m ${secs}s'
        : '${secs}s';

    return Row(children: [
      // ── Left: step progress ──────────────────────────────────────────────
      SizedBox(
        width: 340,
        child: Container(
          color: const Color(0xFF0A0818),
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                const Icon(Icons.cloud_download_outlined,
                    color: _kAccent, size: 22),
                const SizedBox(width: 10),
                const Expanded(
                  child: Text('GEE Feature Extraction',
                      style: TextStyle(color: Colors.white,
                          fontSize: 16, fontWeight: FontWeight.bold)),
                ),
              ]),
              const SizedBox(height: 4),
              Text('Elapsed: $elapsed',
                  style: const TextStyle(color: Colors.white38, fontSize: 11)),
              const SizedBox(height: 16),

              // Progress bar
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: pct,
                  minHeight: 6,
                  backgroundColor: Colors.white12,
                  valueColor: const AlwaysStoppedAnimation(_kAccent),
                ),
              ),
              const SizedBox(height: 8),
              Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                Text('Step $_extractStep / $_extractTotal',
                    style: const TextStyle(color: Colors.white54, fontSize: 11)),
                Text('$_extractProgress%',
                    style: const TextStyle(color: _kAccent, fontSize: 11,
                        fontWeight: FontWeight.bold)),
              ]),
              const SizedBox(height: 20),

              // Current step name
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: _kAccent.withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: _kAccent.withValues(alpha: 0.3)),
                ),
                child: Row(children: [
                  const SizedBox(
                    width: 14, height: 14,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: _kAccent),
                  ),
                  const SizedBox(width: 10),
                  Expanded(child: Text(_extractStepName,
                      style: const TextStyle(color: Colors.white,
                          fontSize: 12, fontWeight: FontWeight.w600))),
                ]),
              ),
              const SizedBox(height: 12),

              // Message
              if (_extractMessage.isNotEmpty)
                Text(_extractMessage,
                    style: const TextStyle(color: Colors.white60,
                        fontSize: 11, height: 1.5)),

              const SizedBox(height: 24),

              // Step list
              ..._kExtractSteps.asMap().entries.map((e) {
                final idx  = e.key + 1;
                final done = idx < _extractStep;
                final cur  = idx == _extractStep;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Row(children: [
                    Container(
                      width: 28, height: 28,
                      decoration: BoxDecoration(
                        color: done
                            ? Colors.green.withValues(alpha: 0.15)
                            : cur
                                ? _kAccent.withValues(alpha: 0.15)
                                : Colors.white.withValues(alpha: 0.04),
                        borderRadius: BorderRadius.circular(7),
                        border: Border.all(
                          color: done
                              ? Colors.green.withValues(alpha: 0.5)
                              : cur
                                  ? _kAccent.withValues(alpha: 0.6)
                                  : Colors.white12,
                        ),
                      ),
                      child: Center(
                        child: done
                            ? const Icon(Icons.check, color: Colors.green, size: 14)
                            : cur
                                ? const SizedBox(width: 12, height: 12,
                                    child: CircularProgressIndicator(
                                        strokeWidth: 2, color: _kAccent))
                                : Text('$idx',
                                    style: const TextStyle(
                                        color: Colors.white24, fontSize: 10)),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(child: Text(e.value,
                        style: TextStyle(
                          color: done
                              ? Colors.green.withValues(alpha: 0.8)
                              : cur ? Colors.white : Colors.white24,
                          fontSize: 11,
                          height: 1.35,
                        ))),
                  ]),
                );
              }),

              const SizedBox(height: 16),
              // Cancel button
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: () {
                    _extractPollTimer?.cancel();
                    setState(() {
                      _screenState = _ScreenState.ready;
                      _extractJobId = '';
                    });
                  },
                  icon: const Icon(Icons.stop_circle_outlined, size: 16),
                  label: const Text('Cancel'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.white54,
                    side: const BorderSide(color: Colors.white24),
                    padding: const EdgeInsets.symmetric(vertical: 10),
                  ),
                ),
              ),
            ]),
          ),
        ),
      ),

      // ── Right: visualizations as they arrive ─────────────────────────────
      Expanded(
        child: Container(
          color: const Color(0xFF0D0B1F),
          child: _extractViz.isEmpty
              ? Center(
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    const Icon(Icons.image_outlined,
                        color: Colors.white12, size: 48),
                    const SizedBox(height: 12),
                    const Text('Visualizations will appear here\nas each pipeline step completes',
                        textAlign: TextAlign.center,
                        style: TextStyle(color: Colors.white24, fontSize: 13)),
                  ]),
                )
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(20),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start,
                    children: _extractViz.entries.toList().reversed.map((entry) {
                      final label = _kVizLabels[entry.key] ?? entry.key;
                      final bytes = base64Decode(entry.value);
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 24),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(children: [
                              const Icon(Icons.bar_chart,
                                  color: _kAccent, size: 14),
                              const SizedBox(width: 6),
                              Text(label,
                                  style: const TextStyle(
                                      color: Colors.white70,
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600)),
                            ]),
                            const SizedBox(height: 8),
                            ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: Image.memory(bytes,
                                  fit: BoxFit.fitWidth,
                                  width: double.infinity),
                            ),
                          ],
                        ),
                      );
                    }).toList(),
                  ),
                ),
        ),
      ),
    ]);
  }

  // ══════════════════════════════════════════════════════════════════════════
  // RESULTS — TabBarView
  // ══════════════════════════════════════════════════════════════════════════

  Widget _buildResults() {
    return TabBarView(
      controller: _tab,
      physics: const NeverScrollableScrollPhysics(),
      children: [
        _buildSideBySide(),
        _buildMlPerformance(),
      ],
    );
  }

  // ══════════════════════════════════════════════════════════════════════════
  // TAB 1: Side-by-Side
  // ══════════════════════════════════════════════════════════════════════════

  Widget _buildSideBySide() {
    if (_wildcatGeoJson == null) return const SizedBox();

    // ── Wildcat polygons ────────────────────────────────────────────────────
    final wcFeatures = _wildcatGeoJson!.features;
    final pKey       = 'P_$_scenarioIdx';
    final wcPolygons = <Polygon>[];
    for (int i = 0; i < wcFeatures.length; i++) {
      final f = wcFeatures[i];
      if (f.rings.isEmpty) continue;
      final p   = (f.properties[pKey] as num?)?.toDouble() ?? 0.0;
      final sel = _selectedWcBasin == i;
      wcPolygons.add(Polygon(
        points: f.rings[0],
        color: _probColor(p).withValues(alpha: sel ? 0.9 : 0.62),
        borderColor: sel ? Colors.white : Colors.white.withValues(alpha: 0.2),
        borderStrokeWidth: sel ? 2.0 : 0.4,
      ));
    }

    // ── ML polygons (47 basins) ─────────────────────────────────────────────
    final mlPolygons = <Polygon>[];
    if (_mlGeoJson != null) {
      final mlFeatures = _mlGeoJson!.features;
      for (int i = 0; i < mlFeatures.length; i++) {
        final f = mlFeatures[i];
        if (f.rings.isEmpty) continue;
        final p   = (f.properties['ML_Prob'] as num?)?.toDouble() ?? 0.0;
        final sel = _selectedMlBasin == i;
        mlPolygons.add(Polygon(
          points: f.rings[0],
          color: _probColor(p).withValues(alpha: sel ? 0.92 : 0.70),
          borderColor: sel
              ? _kAccent
              : _kAccent.withValues(alpha: 0.45),
          borderStrokeWidth: sel ? 2.5 : 1.2,
        ));
      }
    }

    // Shared bottom bar (colour legend + scenario selector for Wildcat)
    Widget scenarioBar = Container(
      color: Colors.black.withValues(alpha: 0.70),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      child: Row(children: [
        const Text('I₁₅:', style: TextStyle(color: Colors.white54, fontSize: 10)),
        const SizedBox(width: 6),
        ...List.generate(4, (i) {
          final sel = _scenarioIdx == i;
          return Padding(
            padding: const EdgeInsets.only(right: 5),
            child: GestureDetector(
              onTap: () => setState(() {
                _scenarioIdx = i;
                _selectedWcBasin = null;
              }),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: sel
                      ? _kWildcat.withValues(alpha: 0.25)
                      : Colors.white.withValues(alpha: 0.07),
                  borderRadius: BorderRadius.circular(5),
                  border: Border.all(color: sel ? _kWildcat : Colors.white24),
                ),
                child: Text(_scenarioLabels[i],
                    style: TextStyle(
                        color: sel ? _kWildcat : Colors.white38,
                        fontSize: 9,
                        fontWeight: sel ? FontWeight.bold : FontWeight.normal)),
              ),
            ),
          );
        }),
        const Spacer(),
        ...(_kRiskColors.entries.map((e) => Padding(
          padding: const EdgeInsets.only(left: 5),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Container(width: 8, height: 8,
                decoration: BoxDecoration(color: e.value,
                    borderRadius: BorderRadius.circular(2))),
            const SizedBox(width: 2),
            Text(e.key, style: const TextStyle(color: Colors.white38, fontSize: 8)),
          ]),
        ))),
      ]),
    );

    return Row(children: [

      // ─────────────────────────────────────────────────────────────────────
      // LEFT: Wildcat map
      // ─────────────────────────────────────────────────────────────────────
      Expanded(
        child: Stack(children: [
          FlutterMap(
            mapController: _mapCtrl,
            options: MapOptions(
              initialCenter: const LatLng(36.06, -121.40),
              initialZoom: 10,
              onTap: _onMapTap,
            ),
            children: [
              TileLayer(
                urlTemplate: _useSatellite
                    ? 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
                    : 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
              ),
              PolygonLayer(polygons: wcPolygons),
            ],
          ),

          // Header chip
          Positioned(top: 10, left: 10,
            child: _modelChip('WILDCAT / pfdf', _kWildcat, '886 basins')),

          // Satellite toggle
          Positioned(top: 10, right: 10,
            child: IconButton.filled(
              onPressed: () => setState(() => _useSatellite = !_useSatellite),
              icon: Icon(_useSatellite ? Icons.map_outlined : Icons.satellite_alt,
                  size: 16),
              style: IconButton.styleFrom(
                backgroundColor: Colors.black54,
                foregroundColor: Colors.white,
                minimumSize: const Size(32, 32),
              ),
            ),
          ),

          // Hint
          Positioned(top: 48, left: 10,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
              decoration: BoxDecoration(
                  color: Colors.black54, borderRadius: BorderRadius.circular(5)),
              child: const Text('Tap basin → Staley M1 step-by-step',
                  style: TextStyle(color: Colors.white54, fontSize: 9)),
            ),
          ),

          // Bottom: scenario selector + legend
          Positioned(bottom: 0, left: 0, right: 0, child: scenarioBar),
        ]),
      ),

      // Thin divider
      Container(width: 1, color: Colors.white12),

      // ─────────────────────────────────────────────────────────────────────
      // RIGHT: ML map + stats strip below
      // ─────────────────────────────────────────────────────────────────────
      Expanded(
        child: Column(children: [

          // ML map (takes most of the space)
          Expanded(
            child: Stack(children: [
              FlutterMap(
                mapController: _mlMapCtrl,
                options: MapOptions(
                  initialCenter: const LatLng(36.06, -121.40),
                  initialZoom: 10,
                  onTap: _onMlMapTap,
                ),
                children: [
                  TileLayer(
                    urlTemplate: _useSatellite
                        ? 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
                        : 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  ),
                  PolygonLayer(polygons: mlPolygons),
                ],
              ),

              // Header chip
              Positioned(top: 10, left: 10,
                child: _modelChip('ML MODEL v3', _kAccent,
                    '${mlPolygons.length} basins')),

              // Legend
              Positioned(bottom: 0, left: 0, right: 0,
                child: Container(
                  color: Colors.black.withValues(alpha: 0.70),
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  child: Row(children: [
                    const Text('Probability (0–1)', style: TextStyle(
                        color: Colors.white38, fontSize: 9)),
                    const Spacer(),
                    ...(_kRiskColors.entries.map((e) => Padding(
                      padding: const EdgeInsets.only(left: 5),
                      child: Row(mainAxisSize: MainAxisSize.min, children: [
                        Container(width: 8, height: 8,
                            decoration: BoxDecoration(color: e.value,
                                borderRadius: BorderRadius.circular(2))),
                        const SizedBox(width: 2),
                        Text(e.key,
                            style: const TextStyle(color: Colors.white38, fontSize: 8)),
                      ]),
                    ))),
                  ]),
                ),
              ),

              // Hint
              Positioned(top: 48, left: 10,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                  decoration: BoxDecoration(
                      color: Colors.black54,
                      borderRadius: BorderRadius.circular(5)),
                  child: const Text('Tap basin → ML probability detail',
                      style: TextStyle(color: Colors.white54, fontSize: 9)),
                ),
              ),
            ]),
          ),

          // Stats strip below the ML map
          Container(
            color: const Color(0xFF0B0B20),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Row(children: [
                Expanded(child: _miniStat('AUC-ROC',
                    '${(_mlMetrics!.aucRoc * 100).toStringAsFixed(0)}%',
                    Colors.green)),
                Expanded(child: _miniStat('Recall',
                    '${(_mlMetrics!.recall * 100).toStringAsFixed(0)}%',
                    Colors.orange)),
                Expanded(child: _miniStat('FAR',
                    '${(_mlMetrics!.far * 100).toStringAsFixed(1)}%',
                    Colors.redAccent)),
                Expanded(child: _miniStat('Threshold',
                    _mlMetrics!.threshold.toStringAsFixed(3),
                    _kAccent)),
              ]),
              const SizedBox(height: 6),
              _MiniRiskBar(dist: _mlRiskDist),
              const SizedBox(height: 4),
              Row(children: [
                const Icon(Icons.info_outline, size: 11, color: Colors.white24),
                const SizedBox(width: 4),
                const Expanded(child: Text(
                  '47 GIS-delineated basins shown on map. '
                  'Different delineation than Wildcat — no 1-to-1 basin match.',
                  style: TextStyle(color: Colors.white24, fontSize: 9, height: 1.4),
                )),
              ]),
            ]),
          ),
        ]),
      ),
    ]);
  }

  Widget _modelChip(String label, Color color, String sub) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: color.withValues(alpha: 0.4)),
        ),
        child: Text(label,
            style: TextStyle(color: color, fontSize: 10,
                fontWeight: FontWeight.bold, letterSpacing: 0.5)),
      ),
      const SizedBox(width: 6),
      Text(sub, style: const TextStyle(color: Colors.white38, fontSize: 10)),
    ],
  );

  Widget _miniStat(String label, String value, Color color) => Container(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: Column(children: [
      Text(value, style: TextStyle(color: color,
          fontSize: 15, fontWeight: FontWeight.bold)),
      Text(label, style: const TextStyle(color: Colors.white38, fontSize: 9)),
    ]),
  );

  // ══════════════════════════════════════════════════════════════════════════
  // TAB 2: ML Performance
  // ══════════════════════════════════════════════════════════════════════════

  Widget _buildMlPerformance() {
    final m = _mlMetrics!;
    return Row(children: [
      // Left: metrics
      SizedBox(
        width: 340,
        child: Container(
          color: const Color(0xFF0B0B20),
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  const Icon(Icons.psychology_outlined, color: _kAccent, size: 18),
                  const SizedBox(width: 8),
                  const Text('Random Forest v3',
                      style: TextStyle(color: Colors.white,
                          fontWeight: FontWeight.bold, fontSize: 14)),
                ]),
                const SizedBox(height: 4),
                Text('${m.nFeatures} features  •  500 trees  •  '
                    'threshold ${m.threshold.toStringAsFixed(4)}',
                    style: const TextStyle(color: Colors.white54, fontSize: 11)),
                Text('Train: ${m.trainN}  •  Test: ${m.testN}  •  Stratified 70/30',
                    style: const TextStyle(color: Colors.white54, fontSize: 11)),

                const SizedBox(height: 20),
                const Text('Test-set performance',
                    style: TextStyle(color: Colors.white70,
                        fontSize: 12, fontWeight: FontWeight.w600)),
                const SizedBox(height: 10),
                Row(children: [
                  Expanded(child: _metricTile('AUC-ROC',
                      '${(m.aucRoc*100).toStringAsFixed(1)}%',
                      Colors.green, Icons.show_chart)),
                  const SizedBox(width: 8),
                  Expanded(child: _metricTile('AUC-PR',
                      '${(m.aucPr*100).toStringAsFixed(1)}%',
                      Colors.teal, Icons.area_chart)),
                ]),
                const SizedBox(height: 8),
                Row(children: [
                  Expanded(child: _metricTile('Recall',
                      '${(m.recall*100).toStringAsFixed(1)}%',
                      Colors.orange, Icons.track_changes)),
                  const SizedBox(width: 8),
                  Expanded(child: _metricTile('FAR',
                      '${(m.far*100).toStringAsFixed(1)}%',
                      Colors.redAccent, Icons.warning_amber_outlined)),
                ]),

                const SizedBox(height: 20),
                const Text('Confusion matrix (test set)',
                    style: TextStyle(color: Colors.white70,
                        fontSize: 12, fontWeight: FontWeight.w600)),
                const SizedBox(height: 10),
                _ConfusionMatrix(tp: m.tp, tn: m.tn, fp: m.fp, fn: m.fn),
                const SizedBox(height: 6),
                const Text('Test set = 30% of data (148 basins)',
                    style: TextStyle(color: Colors.white38, fontSize: 10)),

                const SizedBox(height: 20),
                const Text('Risk distribution (all 492 basins)',
                    style: TextStyle(color: Colors.white70,
                        fontSize: 12, fontWeight: FontWeight.w600)),
                const SizedBox(height: 10),
                _RiskDistBar(dist: _mlRiskDist),
              ],
            ),
          ),
        ),
      ),

      // Right: feature importances + histogram
      Expanded(
        child: Container(
          color: _kBg,
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  const Icon(Icons.bar_chart, color: _kAccent, size: 18),
                  const SizedBox(width: 8),
                  const Text('Feature Importances (MDI)',
                      style: TextStyle(color: Colors.white,
                          fontWeight: FontWeight.bold, fontSize: 14)),
                  const Spacer(),
                  const Text('top 20  —  colour = category',
                      style: TextStyle(color: Colors.white38, fontSize: 11)),
                ]),
                const SizedBox(height: 4),
                const Text(
                  'Mean Decrease in Impurity across 500 trees. '
                  'Higher = more useful for splitting decisions.',
                  style: TextStyle(color: Colors.white54, fontSize: 11, height: 1.4),
                ),
                const SizedBox(height: 16),
                _FeatureImportanceChart(importances: _featureImps),

                const SizedBox(height: 28),

                Row(children: [
                  const Icon(Icons.waterfall_chart, color: _kAccent, size: 18),
                  const SizedBox(width: 8),
                  const Text('Predicted Probability Distribution',
                      style: TextStyle(color: Colors.white,
                          fontWeight: FontWeight.bold, fontSize: 14)),
                ]),
                const SizedBox(height: 4),
                const Text('All 492 basins. Dashed line = decision threshold.',
                    style: TextStyle(color: Colors.white54, fontSize: 11)),
                const SizedBox(height: 16),
                _ProbHistogram(bins: _mlHistogram,
                    threshold: _mlMetrics!.threshold, barColor: _kAccent),
                const SizedBox(height: 4),
                const Row(mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('0', style: TextStyle(color: Colors.white38, fontSize: 9)),
                    Text('0.5', style: TextStyle(color: Colors.white38, fontSize: 9)),
                    Text('1.0', style: TextStyle(color: Colors.white38, fontSize: 9)),
                  ],
                ),

                const SizedBox(height: 28),
                // Category legend
                Wrap(spacing: 10, runSpacing: 6,
                  children: _kCatColors.entries.map((e) => Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(width: 10, height: 10,
                          decoration: BoxDecoration(color: e.value,
                              borderRadius: BorderRadius.circular(2))),
                      const SizedBox(width: 4),
                      Text(e.key,
                          style: const TextStyle(color: Colors.white54, fontSize: 10)),
                    ],
                  )).toList(),
                ),
              ],
            ),
          ),
        ),
      ),
    ]);
  }

  Widget _metricTile(String label, String value, Color color, IconData icon) =>
    Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 6),
          Text(label, style: TextStyle(color: color.withValues(alpha: 0.8),
              fontSize: 11, fontWeight: FontWeight.w600)),
        ]),
        const SizedBox(height: 6),
        Text(value, style: TextStyle(color: color, fontSize: 22,
            fontWeight: FontWeight.bold)),
      ]),
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Mini risk distribution bar (compact, horizontal)
// ─────────────────────────────────────────────────────────────────────────────

class _MiniRiskBar extends StatelessWidget {
  final Map<String, int> dist;
  const _MiniRiskBar({required this.dist});

  @override
  Widget build(BuildContext context) {
    const tiers = ['Low', 'Moderate', 'High', 'Very High'];
    final total = tiers.fold(0, (s, t) => s + (dist[t] ?? 0));
    if (total == 0) return const SizedBox();
    return Row(children: tiers.map((t) {
      final frac = (dist[t] ?? 0) / total;
      final color = _kRiskColors[t]!;
      return Expanded(
        flex: (frac * 100).round().clamp(1, 100),
        child: Tooltip(
          message: '$t: ${dist[t]}',
          child: Container(
            height: 8,
            color: color.withValues(alpha: 0.75),
          ),
        ),
      );
    }).toList());
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Basin detail bottom sheet (Wildcat tap)
// ─────────────────────────────────────────────────────────────────────────────

class _BasinDetailSheet extends StatefulWidget {
  final SubBasinFeature feat;
  final _BasinDetail? detail;
  final int scenarioIdx;
  final Color Function(double) probColor;
  final Color Function(int) hazardColor;

  const _BasinDetailSheet({
    required this.feat, required this.detail,
    required this.scenarioIdx,
    required this.probColor, required this.hazardColor,
  });

  @override
  State<_BasinDetailSheet> createState() => _BasinDetailSheetState();
}

class _BasinDetailSheetState extends State<_BasinDetailSheet> {
  late int _sc;

  @override
  void initState() {
    super.initState();
    _sc = widget.scenarioIdx;
  }

  @override
  Widget build(BuildContext context) {
    final detail = widget.detail;
    final props  = widget.feat.properties;
    final segId  = props['Segment_ID'];
    final sc = detail?.scenarios.firstWhere(
        (s) => s.idx == _sc,
        orElse: () => detail.scenarios[_sc.clamp(0, detail.scenarios.length - 1)]);

    return DraggableScrollableSheet(
      initialChildSize: 0.65,
      minChildSize: 0.3,
      maxChildSize: 0.95,
      expand: false,
      builder: (_, ctrl) => SingleChildScrollView(
        controller: ctrl,
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          // Drag handle
          Center(child: Container(
            width: 40, height: 4,
            margin: const EdgeInsets.only(bottom: 16),
            decoration: BoxDecoration(color: Colors.white24,
                borderRadius: BorderRadius.circular(2)),
          )),

          // Header
          Row(children: [
            const Icon(Icons.grain, color: _kWildcat, size: 18),
            const SizedBox(width: 8),
            Text('Basin #$segId',
                style: const TextStyle(color: Colors.white,
                    fontSize: 16, fontWeight: FontWeight.bold)),
            const Spacer(),
            if (detail != null) ...[
              if (detail.isBurned) _tag('Burned', Colors.orange),
              const SizedBox(width: 4),
              if (detail.isSteep) _tag('Steep', Colors.blue),
            ],
          ]),
          if (detail != null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text('Area: ${detail.areaKm2.toStringAsFixed(3)} km²',
                  style: const TextStyle(color: Colors.white54, fontSize: 12)),
            ),

          const SizedBox(height: 16),

          // Scenario selector
          Row(children: List.generate(4, (i) {
            final sel = _sc == i;
            const labels = ['16', '20', '24', '40'];
            return Padding(
              padding: const EdgeInsets.only(right: 6),
              child: GestureDetector(
                onTap: () => setState(() => _sc = i),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: sel
                        ? _kWildcat.withValues(alpha: 0.2)
                        : Colors.white.withValues(alpha: 0.05),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: sel ? _kWildcat : Colors.white24),
                  ),
                  child: Text('${labels[i]} mm/hr',
                      style: TextStyle(
                          color: sel ? _kWildcat : Colors.white38,
                          fontSize: 11,
                          fontWeight: sel ? FontWeight.bold : FontWeight.normal)),
                ),
              ),
            );
          })),

          const SizedBox(height: 16),

          if (sc != null) ...[
            // P / V / H results
            Row(children: [
              _resultCard('P', '${(sc.pStored * 100).toStringAsFixed(1)}%',
                  widget.probColor(sc.pStored), sc.riskTier),
              const SizedBox(width: 10),
              if (sc.vStored != null)
                _resultCard('V', '${_fmtVol(sc.vStored!)} m³', Colors.blueAccent, ''),
              const SizedBox(width: 10),
              if (sc.hazard != null)
                _resultCard('H', 'Class ${sc.hazard}',
                    widget.hazardColor(sc.hazard!), ''),
            ]),

            const SizedBox(height: 20),

            // Staley M1
            const Text('Staley (2017) M1 — Step-by-Step',
                style: TextStyle(color: Colors.white,
                    fontWeight: FontWeight.bold, fontSize: 13)),
            const SizedBox(height: 10),
            _eqBox([
              ('Inputs',  'I₁₅ = ${sc.i15} mm/hr  →  R₁₅ = I₁₅×15/60 = ${sc.r15.toStringAsFixed(4)}'),
              ('T',       'steep fraction = ${sc.T.toStringAsFixed(4)}'),
              ('F',       'burned fraction = ${sc.F.toStringAsFixed(4)}'),
              ('S',       'soil KF index = ${sc.S.toStringAsFixed(4)}'),
              ('—',       ''),
              ('T-term',  '(0.41 + 0.26·${sc.r15.toStringAsFixed(3)})·${sc.T.toStringAsFixed(4)} = ${sc.tTerm.toStringAsFixed(4)}'),
              ('F-term',  '(0.67 + 0.60·${sc.r15.toStringAsFixed(3)})·${sc.F.toStringAsFixed(4)} = ${sc.fTerm.toStringAsFixed(4)}'),
              ('S-term',  '(0.07 + 0.69·${sc.r15.toStringAsFixed(3)})·${sc.S.toStringAsFixed(4)} = ${sc.sTerm.toStringAsFixed(4)}'),
              ('—',       ''),
              ('logit',   '−3.63 + ${sc.tTerm.toStringAsFixed(4)} + ${sc.fTerm.toStringAsFixed(4)} + ${sc.sTerm.toStringAsFixed(4)} = ${sc.logit.toStringAsFixed(4)}'),
              ('P',       '1/(1+exp(−${sc.logit.toStringAsFixed(4)})) = ${sc.pCalc.toStringAsFixed(4)}'),
            ], _kWildcat),

            if (sc.vCalc != null && sc.bmhKm2 != null && sc.reliefM != null) ...[
              const SizedBox(height: 16),
              const Text('Gartner (2014) — Volume',
                  style: TextStyle(color: Colors.white,
                      fontWeight: FontWeight.bold, fontSize: 13)),
              const SizedBox(height: 8),
              _eqBox([
                ('Bmh',     '${sc.bmhKm2!.toStringAsFixed(4)} km²'),
                ('Relief',  '${sc.reliefM!.toStringAsFixed(1)} m'),
                ('—',       ''),
                ('log₁₀V',  '−0.699 + 0.989·log₁₀(${sc.i15}) + 0.369·log₁₀(${sc.bmhKm2!.toStringAsFixed(3)}) + 1.223·log₁₀(${sc.reliefM!.toStringAsFixed(1)})'),
                ('V',       '${_fmtVol(sc.vCalc!)} m³'),
              ], Colors.blueAccent),
            ],
          ],
        ]),
      ),
    );
  }

  Widget _tag(String label, Color color) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.15),
      borderRadius: BorderRadius.circular(4),
      border: Border.all(color: color.withValues(alpha: 0.5)),
    ),
    child: Text(label, style: TextStyle(color: color, fontSize: 10,
        fontWeight: FontWeight.bold)),
  );

  Widget _resultCard(String sym, String value, Color color, String sub) =>
    Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Column(children: [
        Text(sym, style: TextStyle(color: color.withValues(alpha: 0.7),
            fontSize: 11, fontWeight: FontWeight.w600)),
        Text(value, style: TextStyle(color: color, fontSize: 18,
            fontWeight: FontWeight.bold)),
        if (sub.isNotEmpty)
          Text(sub, style: TextStyle(color: color.withValues(alpha: 0.6),
              fontSize: 10)),
      ]),
    );

  Widget _eqBox(List<(String, String)> rows, Color accent) => Container(
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: Colors.black.withValues(alpha: 0.3),
      borderRadius: BorderRadius.circular(10),
      border: Border.all(color: accent.withValues(alpha: 0.2)),
    ),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start,
      children: rows.map((r) {
        if (r.$1 == '—') return const Divider(color: Colors.white12, height: 12);
        return Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            SizedBox(width: 56,
              child: Text(r.$1, style: TextStyle(
                  color: accent, fontSize: 11, fontWeight: FontWeight.w600))),
            Expanded(child: Text(r.$2, style: const TextStyle(
                color: Colors.white70, fontSize: 11, fontFamily: 'monospace'))),
          ]),
        );
      }).toList(),
    ),
  );

  String _fmtVol(double v) {
    if (v >= 1e6) return '${(v / 1e6).toStringAsFixed(2)}M';
    if (v >= 1000) return '${(v / 1000).toStringAsFixed(1)}k';
    return v.toStringAsFixed(0);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Shared chart widgets
// ─────────────────────────────────────────────────────────────────────────────

class _RiskDistBar extends StatelessWidget {
  final Map<String, int> dist;
  const _RiskDistBar({required this.dist});

  @override
  Widget build(BuildContext context) {
    const tiers = ['Low', 'Moderate', 'High', 'Very High'];
    final total = tiers.fold(0, (s, t) => s + (dist[t] ?? 0));
    if (total == 0) return const SizedBox();
    return Column(children: tiers.map((tier) {
      final count = dist[tier] ?? 0;
      final frac  = total > 0 ? count / total : 0.0;
      final color = _kRiskColors[tier]!;
      return Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Row(children: [
          SizedBox(width: 68,
            child: Text(tier, style: TextStyle(color: color, fontSize: 11,
                fontWeight: FontWeight.w600))),
          Expanded(child: Stack(children: [
            Container(height: 14, decoration: BoxDecoration(
                color: color.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(4))),
            FractionallySizedBox(
              widthFactor: frac.clamp(0, 1),
              child: Container(height: 14, decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.75),
                  borderRadius: BorderRadius.circular(4))),
            ),
          ])),
          const SizedBox(width: 8),
          SizedBox(width: 36,
            child: Text(count.toString(),
                style: const TextStyle(color: Colors.white54, fontSize: 11),
                textAlign: TextAlign.right)),
        ]),
      );
    }).toList());
  }
}

class _FeatureImportanceChart extends StatelessWidget {
  final List<_FeatureImp> importances;
  const _FeatureImportanceChart({required this.importances});

  @override
  Widget build(BuildContext context) {
    final maxImp = importances.isEmpty ? 1.0
        : importances.map((f) => f.importance).reduce(math.max);
    return Column(children: importances.map((f) {
      final color = _kCatColors[f.category] ?? const Color(0xFFCE93D8);
      final frac  = maxImp > 0 ? f.importance / maxImp : 0.0;
      return Padding(
        padding: const EdgeInsets.only(bottom: 5),
        child: Row(children: [
          SizedBox(width: 120,
            child: Text(f.feature, style: const TextStyle(
                color: Colors.white60, fontSize: 11),
                overflow: TextOverflow.ellipsis)),
          Expanded(child: Stack(children: [
            Container(height: 12, decoration: BoxDecoration(
                color: color.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(3))),
            FractionallySizedBox(
              widthFactor: frac.clamp(0, 1),
              child: Container(height: 12, decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.75),
                  borderRadius: BorderRadius.circular(3))),
            ),
          ])),
          const SizedBox(width: 8),
          SizedBox(width: 46,
            child: Text(f.importance.toStringAsFixed(4),
                style: const TextStyle(color: Colors.white38,
                    fontSize: 10, fontFamily: 'monospace'),
                textAlign: TextAlign.right)),
        ]),
      );
    }).toList());
  }
}

class _ProbHistogram extends StatelessWidget {
  final List<_HistBin> bins;
  final double? threshold;
  final Color barColor;
  const _ProbHistogram(
      {required this.bins, this.threshold, required this.barColor});

  @override
  Widget build(BuildContext context) {
    final maxCount =
        bins.isEmpty ? 1 : bins.map((b) => b.count).reduce(math.max);
    return SizedBox(
      height: 100,
      child: CustomPaint(
        size: Size.infinite,
        painter: _HistPainter(
            bins: bins, maxCount: maxCount,
            threshold: threshold, barColor: barColor),
      ),
    );
  }
}

class _HistPainter extends CustomPainter {
  final List<_HistBin> bins;
  final int maxCount;
  final double? threshold;
  final Color barColor;
  const _HistPainter(
      {required this.bins, required this.maxCount,
       this.threshold, required this.barColor});

  @override
  void paint(Canvas canvas, Size size) {
    if (bins.isEmpty) return;
    final barPaint = Paint()..color = barColor.withValues(alpha: 0.65);
    const gap = 1.0;
    final barW = size.width / bins.length - gap;
    for (int i = 0; i < bins.length; i++) {
      final frac = maxCount > 0 ? bins[i].count / maxCount : 0.0;
      final h = frac * size.height;
      final x = i * (barW + gap);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(x, size.height - h, barW, h),
          const Radius.circular(2),
        ),
        barPaint,
      );
    }
    if (threshold != null) {
      canvas.drawLine(
        Offset(threshold! * size.width, 0),
        Offset(threshold! * size.width, size.height),
        Paint()
          ..color = Colors.white60
          ..strokeWidth = 1.5
          ..style = PaintingStyle.stroke,
      );
    }
  }

  @override
  bool shouldRepaint(_HistPainter old) =>
      old.bins != bins || old.threshold != threshold;
}

class _ConfusionMatrix extends StatelessWidget {
  final int tp, tn, fp, fn;
  const _ConfusionMatrix(
      {required this.tp, required this.tn, required this.fp, required this.fn});

  @override
  Widget build(BuildContext context) {
    return Table(
      columnWidths: const {
        0: FlexColumnWidth(1.4),
        1: FlexColumnWidth(1),
        2: FlexColumnWidth(1),
      },
      children: [
        _hdr(),
        _row('Pred: Flow',    tp, fp, Colors.green,   Colors.red),
        _row('Pred: No Flow', fn, tn, Colors.orange, Colors.teal),
      ],
    );
  }

  TableRow _hdr() => TableRow(children: [
    const SizedBox(),
    _cell('Act: Flow',    Colors.white54, isHdr: true),
    _cell('Act: No Flow', Colors.white54, isHdr: true),
  ]);

  TableRow _row(String label, int a, int b, Color ca, Color cb) =>
      TableRow(children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Text(label, style: const TextStyle(
              color: Colors.white54, fontSize: 10)),
        ),
        _cell(a.toString(), ca),
        _cell(b.toString(), cb),
      ]);

  Widget _cell(String text, Color color, {bool isHdr = false}) => Container(
    margin: const EdgeInsets.all(2),
    padding: const EdgeInsets.symmetric(vertical: 8),
    decoration: BoxDecoration(
      color: isHdr ? Colors.transparent : color.withValues(alpha: 0.12),
      borderRadius: BorderRadius.circular(6),
      border: isHdr ? null : Border.all(color: color.withValues(alpha: 0.3)),
    ),
    child: Text(text,
        textAlign: TextAlign.center,
        style: TextStyle(
          color: isHdr ? Colors.white38 : color,
          fontSize: isHdr ? 10 : 18,
          fontWeight: isHdr ? FontWeight.normal : FontWeight.bold,
        )),
  );
}
