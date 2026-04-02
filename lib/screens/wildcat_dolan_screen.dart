import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:http/http.dart' as http;

import '../config/app_config.dart';
import '../utils/geojson_parser.dart';
import '../widgets/attribute_panel.dart';

// Three wildcat pipeline steps
const _kSteps = [
  'Step 1 — wildcat.preprocess: conditioning DEM, estimating burn severity from dNBR, building Kf raster...',
  'Step 2 — wildcat.assess: D8 flow routing, network delineation, Staley M1 / Gartner G14 / Cannon C10 models...',
  'Step 3 — Saving results to cache...',
];

const _kStepIcons = [
  Icons.terrain,
  Icons.account_tree_outlined,
  Icons.save_outlined,
];

// I15 rainfall intensity presets
const _kI15Presets = {
  'Standard (16/20/24/40 mm/hr)': [16.0, 20.0, 24.0, 40.0],
  'Moderate storm (20/24/40/60 mm/hr)': [20.0, 24.0, 40.0, 60.0],
  'Intense storm (24/40/60/80 mm/hr)': [24.0, 40.0, 60.0, 80.0],
};

const _kAccent = Color(0xFF26C6DA);

class WildcatDolanScreen extends StatefulWidget {
  const WildcatDolanScreen({super.key});

  @override
  State<WildcatDolanScreen> createState() => _WildcatDolanScreenState();
}

enum _ScreenState { ready, analyzing, results }

class _WildcatDolanScreenState extends State<WildcatDolanScreen>
    with TickerProviderStateMixin {
  static final String _base = AppConfig.backendUrl;
  static const LatLng _dolanCenter = LatLng(36.06, -121.40);

  final MapController _mapController = MapController();

  _ScreenState _screenState = _ScreenState.ready;

  // --- Settings ---
  String _i15Preset = 'Standard (16/20/24/40 mm/hr)';
  double _kf = 0.2;
  double _minSlope = 0.12;
  double _minBurnRatio = 0.25;
  double _minAreaKm2 = 0.025;
  bool _locateBasins = true;

  // --- Full analysis state ---
  String? _jobId;
  int _currentStep = 0;
  String _stepMessage = '';
  int _progress = 0;
  String? _error;

  // --- Results state ---
  ParsedGeoJson? _results;
  Map<String, dynamic>? _perimeterGeoJson;
  int? _selectedFeatureIndex;
  bool _useSatellite = true;

  // --- Zone drawing state ---
  bool _drawingZone = false;
  List<LatLng> _drawPoints = [];

  // --- Zone analysis state ---
  String? _zoneJobId;
  int _zoneStep = 0;
  int _zoneProgress = 0;
  String _zoneMessage = '';
  bool _zoneRunning = false;
  ParsedGeoJson? _zoneResults;
  List<LatLng> _zoneBoundary = [];
  String? _zoneError;
  Timer? _zonePollTimer;

  Timer? _pollTimer;
  late AnimationController _pulseController;
  late Animation<double> _pulseAnim;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    )..repeat(reverse: true);
    _pulseAnim = Tween<double>(begin: 0.6, end: 1.0).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
    _loadPerimeter();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _zonePollTimer?.cancel();
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _loadPerimeter() async {
    try {
      final resp = await http.get(Uri.parse('$_base/wildcat/dolan/perimeter'));
      if (resp.statusCode == 200 && mounted) {
        setState(() => _perimeterGeoJson = json.decode(resp.body));
      }
    } catch (_) {}
  }

  // -------------------------------------------------------------------------
  // Full analysis flow
  // -------------------------------------------------------------------------

  Future<void> _startAnalysis({bool force = false}) async {
    setState(() {
      _screenState = _ScreenState.analyzing;
      _currentStep = 0;
      _stepMessage = 'Starting Wildcat pipeline...';
      _progress = 0;
      _error = null;
    });
    final i15 = _kI15Presets[_i15Preset]!;
    try {
      final resp = await http.post(
        Uri.parse('$_base/wildcat/dolan/analyze'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'force': force,
          'settings': {
            'I15_mm_hr': i15,
            'kf': _kf,
            'min_area_km2': _minAreaKm2,
            'min_slope': _minSlope,
            'min_burn_ratio': _minBurnRatio,
            'locate_basins': _locateBasins,
            'buffer_km': 3.0,
            'severity_thresholds': [125.0, 250.0, 500.0],
          },
        }),
      );
      if (resp.statusCode != 200) throw Exception('Backend error: ${resp.body}');
      final body = json.decode(resp.body);
      _jobId = body['job_id'] as String;
      _pollTimer?.cancel();
      _pollTimer =
          Timer.periodic(const Duration(milliseconds: 2000), (_) => _poll());
    } catch (e) {
      setState(() {
        _error = 'Failed to start: $e';
        _screenState = _ScreenState.ready;
      });
    }
  }

  Future<void> _poll() async {
    if (_jobId == null) return;
    try {
      final resp =
          await http.get(Uri.parse('$_base/wildcat/dolan/status/$_jobId'));
      if (resp.statusCode != 200) return;
      final data = json.decode(resp.body);
      final status = data['status'] as String? ?? 'running';
      final step = (data['step'] as num?)?.toInt() ?? _currentStep;
      final msg = data['message'] as String? ?? _stepMessage;
      final prog = (data['progress'] as num?)?.toInt() ?? _progress;
      if (!mounted) return;
      if (status == 'completed') {
        _pollTimer?.cancel();
        setState(() {
          _currentStep = 4;
          _progress = 100;
          _stepMessage = msg;
        });
        await _loadResults();
      } else if (status == 'failed') {
        _pollTimer?.cancel();
        setState(() {
          _error = data['error'] as String? ?? 'Pipeline failed';
          _screenState = _ScreenState.ready;
        });
      } else {
        setState(() {
          _currentStep = step;
          _stepMessage = msg;
          _progress = prog;
        });
      }
    } catch (_) {}
  }

  Future<void> _loadResults() async {
    try {
      final resultsResp =
          await http.get(Uri.parse('$_base/wildcat/dolan/results'));
      final perimResp =
          await http.get(Uri.parse('$_base/wildcat/dolan/perimeter'));
      if (resultsResp.statusCode == 200 && perimResp.statusCode == 200) {
        final parsed = parseGeoJson(json.decode(resultsResp.body));
        if (!mounted) return;
        setState(() {
          _results = parsed;
          _perimeterGeoJson = json.decode(perimResp.body);
          _screenState = _ScreenState.results;
        });
        if (parsed.bounds != null) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              _mapController.fitCamera(CameraFit.bounds(
                  bounds: parsed.bounds!,
                  padding: const EdgeInsets.all(60)));
            }
          });
        }
      }
    } catch (e) {
      setState(() {
        _error = 'Failed to load results: $e';
        _screenState = _ScreenState.ready;
      });
    }
  }

  // -------------------------------------------------------------------------
  // Zone drawing helpers
  // -------------------------------------------------------------------------

  void _startDrawing() {
    setState(() {
      _drawingZone = true;
      _drawPoints = [];
      _zoneResults = null;
      _zoneBoundary = [];
      _zoneError = null;
      _selectedFeatureIndex = null;
    });
  }

  void _cancelDrawing() =>
      setState(() {
        _drawingZone = false;
        _drawPoints = [];
        _zoneError = null;
      });

  void _undoPoint() {
    if (_drawPoints.isNotEmpty) setState(() => _drawPoints.removeLast());
  }

  void _clearZone() {
    setState(() {
      _zoneResults = null;
      _zoneBoundary = [];
      _zoneError = null;
      _zoneJobId = null;
      _zoneRunning = false;
      _selectedFeatureIndex = null;
    });
    _zonePollTimer?.cancel();
  }

  Future<void> _confirmZone() async {
    if (_drawPoints.length < 3) return;
    final pts = List<LatLng>.from(_drawPoints)..add(_drawPoints.first);
    final coords = pts.map((p) => [p.longitude, p.latitude]).toList();
    final polygon = {'type': 'Polygon', 'coordinates': [coords]};

    setState(() {
      _zoneError = null;
      _drawingZone = false;
      _drawPoints = [];
      _zoneBoundary = pts;
      _zoneRunning = true;
      _zoneStep = 0;
      _zoneProgress = 0;
      _zoneMessage = 'Clipping DEM and dNBR to drawn zone...';
      _zoneResults = null;
    });

    final i15 = _kI15Presets[_i15Preset]!;
    try {
      final resp = await http.post(
        Uri.parse('$_base/wildcat/dolan/analyze-zone'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'polygon': polygon,
          'settings': {
            'I15_mm_hr': i15,
            'kf': _kf,
            'min_area_km2': _minAreaKm2,
            'min_slope': _minSlope,
            'min_burn_ratio': _minBurnRatio,
            'locate_basins': _locateBasins,
            'severity_thresholds': [125.0, 250.0, 500.0],
          },
        }),
      );
      if (resp.statusCode != 200) {
        setState(() {
          _zoneRunning = false;
          _zoneError = 'Backend error: ${resp.body}';
        });
        return;
      }
      _zoneJobId = json.decode(resp.body)['job_id'] as String;
      _zonePollTimer?.cancel();
      _zonePollTimer = Timer.periodic(
          const Duration(milliseconds: 2000), (_) => _pollZone());
    } catch (e) {
      setState(() {
        _zoneRunning = false;
        _zoneError = 'Failed to start zone analysis: $e';
      });
    }
  }

  Future<void> _pollZone() async {
    if (_zoneJobId == null) return;
    try {
      final resp = await http
          .get(Uri.parse('$_base/wildcat/dolan/status/$_zoneJobId'));
      if (resp.statusCode != 200) return;
      final data = json.decode(resp.body);
      final status = data['status'] as String? ?? 'running';
      if (!mounted) return;
      if (status == 'completed') {
        _zonePollTimer?.cancel();
        setState(() {
          _zoneStep = 3;
          _zoneProgress = 100;
          _zoneMessage = 'Zone analysis complete!';
        });
        await _loadZoneResults();
      } else if (status == 'failed') {
        _zonePollTimer?.cancel();
        setState(() {
          _zoneRunning = false;
          _zoneError = data['error'] as String? ?? 'Zone analysis failed';
        });
      } else {
        setState(() {
          _zoneStep = (data['step'] as num?)?.toInt() ?? _zoneStep;
          _zoneProgress =
              (data['progress'] as num?)?.toInt() ?? _zoneProgress;
          _zoneMessage = data['message'] as String? ?? _zoneMessage;
        });
      }
    } catch (_) {}
  }

  Future<void> _loadZoneResults() async {
    try {
      final resp = await http
          .get(Uri.parse('$_base/wildcat/dolan/zone-results/$_zoneJobId'));
      if (resp.statusCode == 200 && mounted) {
        setState(() {
          _zoneResults = parseGeoJson(json.decode(resp.body));
          _zoneRunning = false;
          _selectedFeatureIndex = null;
        });
      } else {
        setState(() {
          _zoneRunning = false;
          _zoneError = 'Could not load zone results (${resp.statusCode})';
        });
      }
    } catch (e) {
      setState(() {
        _zoneRunning = false;
        _zoneError = 'Failed to load zone results: $e';
      });
    }
  }

  // -------------------------------------------------------------------------
  // Build
  // -------------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D1B2A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0A2030),
        foregroundColor: Colors.white,
        title: const Row(children: [
          Icon(Icons.science, color: _kAccent),
          SizedBox(width: 10),
          Text('Dolan Fire — Real Wildcat',
              style:
                  TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
          SizedBox(width: 10),
          Text('2020  •  Big Sur, CA',
              style: TextStyle(
                  color: Colors.white54,
                  fontSize: 13,
                  fontWeight: FontWeight.normal)),
        ]),
        actions: [
          if (_screenState == _ScreenState.results) ...[
            // Zone controls
            if (_zoneResults != null)
              TextButton.icon(
                onPressed: _clearZone,
                icon: const Icon(Icons.clear, color: Colors.redAccent),
                label: const Text('Clear Zone',
                    style: TextStyle(color: Colors.redAccent)),
              )
            else if (!_drawingZone && !_zoneRunning)
              TextButton.icon(
                onPressed: _startDrawing,
                icon: const Icon(Icons.draw, color: Colors.amberAccent),
                label: const Text('Draw Zone',
                    style: TextStyle(color: Colors.amberAccent)),
              ),
            const SizedBox(width: 4),
            // Map toggle
            IconButton(
              tooltip:
                  _useSatellite ? 'Switch to Street Map' : 'Switch to Satellite',
              onPressed: () => setState(() => _useSatellite = !_useSatellite),
              icon: Icon(
                _useSatellite ? Icons.map_outlined : Icons.satellite_alt,
                color: Colors.white70,
              ),
            ),
            TextButton.icon(
              onPressed: () => setState(() {
                _screenState = _ScreenState.ready;
                _selectedFeatureIndex = null;
                _clearZone();
              }),
              icon: const Icon(Icons.refresh, color: _kAccent),
              label: const Text('Re-run', style: TextStyle(color: _kAccent)),
            ),
          ],
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    switch (_screenState) {
      case _ScreenState.ready:
        return _buildReady();
      case _ScreenState.analyzing:
        return _buildAnalyzing();
      case _ScreenState.results:
        return _buildResults();
    }
  }

  // -------------------------------------------------------------------------
  // Ready screen
  // -------------------------------------------------------------------------

  Widget _buildReady() {
    return Row(
      children: [
        // Left panel
        SizedBox(
          width: 340,
          child: Container(
            color: const Color(0xFF0D1B2A),
            child: Column(
              children: [
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Badge
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: _kAccent.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(
                                color: _kAccent.withValues(alpha: 0.4)),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.verified,
                                  color: _kAccent, size: 14),
                              const SizedBox(width: 6),
                              const Text('USGS Wildcat v1.1.0 + pfdf',
                                  style: TextStyle(
                                      color: _kAccent,
                                      fontSize: 11,
                                      fontWeight: FontWeight.w600)),
                            ],
                          ),
                        ),
                        const SizedBox(height: 20),
                        const Text('Real Wildcat Analysis',
                            style: TextStyle(
                                color: Colors.white,
                                fontSize: 20,
                                fontWeight: FontWeight.bold)),
                        const SizedBox(height: 8),
                        Text(
                          'Runs the genuine USGS pfdf pipeline — not an approximation. '
                          'Uses flow-path slope, accumulated Bmh, pfdf Segments delineation, '
                          'and the actual Staley (2017) M1, Gartner (2014), and Cannon (2010) models.',
                          style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.6),
                              fontSize: 13,
                              height: 1.5),
                        ),
                        const SizedBox(height: 24),

                        // Pipeline steps preview
                        const Text('PIPELINE',
                            style: TextStyle(
                                color: Colors.white38,
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                letterSpacing: 1.2)),
                        const SizedBox(height: 12),
                        ..._kSteps.asMap().entries.map((e) => Padding(
                              padding: const EdgeInsets.only(bottom: 12),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Container(
                                    width: 28,
                                    height: 28,
                                    decoration: BoxDecoration(
                                      color: _kAccent.withValues(alpha: 0.12),
                                      borderRadius: BorderRadius.circular(6),
                                    ),
                                    child: Icon(_kStepIcons[e.key],
                                        color: _kAccent, size: 16),
                                  ),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: Text(
                                      e.value,
                                      style: TextStyle(
                                          color: Colors.white
                                              .withValues(alpha: 0.55),
                                          fontSize: 12,
                                          height: 1.4),
                                    ),
                                  ),
                                ],
                              ),
                            )),

                        const SizedBox(height: 16),
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Colors.amber.withValues(alpha: 0.08),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                                color: Colors.amber.withValues(alpha: 0.25)),
                          ),
                          child: Row(
                            children: [
                              const Icon(Icons.timer_outlined,
                                  color: Colors.amber, size: 16),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  'The assessment step (basin delineation) may take 3–8 minutes '
                                  'for the full Dolan fire area.',
                                  style: TextStyle(
                                      color: Colors.amber.withValues(alpha: 0.85),
                                      fontSize: 12,
                                      height: 1.4),
                                ),
                              ),
                            ],
                          ),
                        ),

                        const SizedBox(height: 20),
                        const Text('FIXED INPUTS',
                            style: TextStyle(
                                color: Colors.white38,
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                letterSpacing: 1.2)),
                        const SizedBox(height: 10),
                        _inputRow(Icons.terrain, 'DEM',
                            'dolan_dem_3dep10m.tif (USGS 3DEP 10m)'),
                        _inputRow(Icons.local_fire_department, 'dNBR',
                            'MTBS dNBR raster (severity estimated by wildcat)'),
                        _inputRow(Icons.crop_square, 'Perimeter',
                            'MTBS burn boundary shapefile'),

                        const SizedBox(height: 24),
                        const Text('ANALYSIS PARAMETERS',
                            style: TextStyle(
                                color: Colors.white38,
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                letterSpacing: 1.2)),
                        const SizedBox(height: 14),

                        _settingsLabel(Icons.water, 'Rainfall Intensity (I15)'),
                        const SizedBox(height: 8),
                        ..._kI15Presets.keys.map((label) => Padding(
                              padding: const EdgeInsets.only(bottom: 6),
                              child: InkWell(
                                onTap: () =>
                                    setState(() => _i15Preset = label),
                                borderRadius: BorderRadius.circular(8),
                                child: Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 12, vertical: 8),
                                  decoration: BoxDecoration(
                                    color: _i15Preset == label
                                        ? _kAccent.withValues(alpha: 0.15)
                                        : Colors.white.withValues(alpha: 0.04),
                                    borderRadius: BorderRadius.circular(8),
                                    border: Border.all(
                                      color: _i15Preset == label
                                          ? _kAccent.withValues(alpha: 0.5)
                                          : Colors.white
                                              .withValues(alpha: 0.08),
                                    ),
                                  ),
                                  child: Row(children: [
                                    Icon(
                                      _i15Preset == label
                                          ? Icons.radio_button_checked
                                          : Icons.radio_button_unchecked,
                                      color: _i15Preset == label
                                          ? _kAccent
                                          : Colors.white38,
                                      size: 16,
                                    ),
                                    const SizedBox(width: 8),
                                    Expanded(
                                      child: Text(label,
                                          style: TextStyle(
                                              color: _i15Preset == label
                                                  ? Colors.white
                                                  : Colors.white54,
                                              fontSize: 12)),
                                    ),
                                  ]),
                                ),
                              ),
                            )),

                        const SizedBox(height: 14),

                        _settingsLabel(Icons.water_drop,
                            'Soil Erodibility (Kf)  —  ${_kf.toStringAsFixed(2)}'),
                        SliderTheme(
                          data: _sliderTheme(context),
                          child: Slider(
                            value: _kf,
                            min: 0.05,
                            max: 0.50,
                            divisions: 9,
                            onChanged: (v) => setState(
                                () => _kf = double.parse(v.toStringAsFixed(2))),
                          ),
                        ),
                        _sliderLabels('0.05', '0.50', 'erodible'),

                        const SizedBox(height: 10),

                        _settingsLabel(Icons.show_chart,
                            'Min Slope Filter  —  ${_minSlope.toStringAsFixed(2)}'),
                        SliderTheme(
                          data: _sliderTheme(context),
                          child: Slider(
                            value: _minSlope,
                            min: 0.05,
                            max: 0.30,
                            divisions: 10,
                            onChanged: (v) => setState(() =>
                                _minSlope = double.parse(v.toStringAsFixed(2))),
                          ),
                        ),
                        _sliderLabels('0.05', '0.30', 'steeper only'),

                        const SizedBox(height: 10),

                        _settingsLabel(Icons.local_fire_department,
                            'Min Burn Ratio  —  ${(_minBurnRatio * 100).round()}%'),
                        SliderTheme(
                          data: _sliderTheme(context),
                          child: Slider(
                            value: _minBurnRatio,
                            min: 0.05,
                            max: 0.60,
                            divisions: 11,
                            onChanged: (v) => setState(() => _minBurnRatio =
                                double.parse(v.toStringAsFixed(2))),
                          ),
                        ),
                        _sliderLabels('5%', '60%', 'more burned'),

                        const SizedBox(height: 10),

                        _settingsLabel(Icons.crop_free,
                            'Min Basin Area  —  ${_minAreaKm2.toStringAsFixed(3)} km²'),
                        SliderTheme(
                          data: _sliderTheme(context),
                          child: Slider(
                            value: _minAreaKm2,
                            min: 0.010,
                            max: 0.100,
                            divisions: 9,
                            onChanged: (v) => setState(() => _minAreaKm2 =
                                double.parse(v.toStringAsFixed(3))),
                          ),
                        ),
                        _sliderLabels(
                            '0.010', '0.100 km²', 'fewer/larger basins →'),

                        const SizedBox(height: 14),

                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 12, vertical: 10),
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.04),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                                color: Colors.white.withValues(alpha: 0.08)),
                          ),
                          child: Row(children: [
                            const Icon(Icons.pentagon_outlined,
                                color: Colors.white38, size: 16),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Text('Locate Basin Polygons',
                                      style: TextStyle(
                                          color: Colors.white70,
                                          fontSize: 12,
                                          fontWeight: FontWeight.w600)),
                                  Text(
                                    _locateBasins
                                        ? 'On — full polygon map (slower)'
                                        : 'Off — segment lines only (faster)',
                                    style: TextStyle(
                                        color:
                                            Colors.white.withValues(alpha: 0.4),
                                        fontSize: 11),
                                  ),
                                ],
                              ),
                            ),
                            Switch(
                              value: _locateBasins,
                              activeThumbColor: _kAccent,
                              activeTrackColor:
                                  _kAccent.withValues(alpha: 0.4),
                              onChanged: (v) =>
                                  setState(() => _locateBasins = v),
                            ),
                          ]),
                        ),

                        if (_error != null) ...[
                          const SizedBox(height: 16),
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                                color: Colors.red.withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(8)),
                            child: Text(_error!,
                                style: const TextStyle(
                                    color: Colors.redAccent, fontSize: 12)),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),

                Padding(
                  padding: const EdgeInsets.all(16),
                  child: SizedBox(
                    width: double.infinity,
                    height: 52,
                    child: ElevatedButton.icon(
                      onPressed: () => _startAnalysis(force: false),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _kAccent,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(10)),
                      ),
                      icon: const Icon(Icons.play_arrow),
                      label: const Text('Run Wildcat Analysis',
                          style: TextStyle(
                              fontSize: 15, fontWeight: FontWeight.bold)),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),

        Expanded(child: _buildPerimeterMap()),
      ],
    );
  }

  Widget _settingsLabel(IconData icon, String text) => Padding(
        padding: const EdgeInsets.only(bottom: 4),
        child: Row(children: [
          Icon(icon, color: Colors.white38, size: 13),
          const SizedBox(width: 6),
          Text(text,
              style: const TextStyle(
                  color: Colors.white54,
                  fontSize: 12,
                  fontWeight: FontWeight.w600)),
        ]),
      );

  Widget _sliderLabels(String lo, String hi, String note) => Padding(
        padding: const EdgeInsets.only(top: 0, bottom: 4),
        child: Row(children: [
          Text(lo,
              style: const TextStyle(color: Colors.white24, fontSize: 10)),
          Expanded(
              child: Text(note,
                  textAlign: TextAlign.center,
                  style:
                      const TextStyle(color: Colors.white24, fontSize: 10))),
          Text(hi,
              style: const TextStyle(color: Colors.white24, fontSize: 10)),
        ]),
      );

  SliderThemeData _sliderTheme(BuildContext context) =>
      SliderTheme.of(context).copyWith(
        activeTrackColor: _kAccent,
        inactiveTrackColor: Colors.white12,
        thumbColor: _kAccent,
        overlayColor: _kAccent.withValues(alpha: 0.15),
        trackHeight: 3,
        thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 6),
      );

  Widget _inputRow(IconData icon, String label, String value) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: Colors.white38, size: 14),
            const SizedBox(width: 8),
            Text('$label: ',
                style: const TextStyle(
                    color: Colors.white54,
                    fontSize: 12,
                    fontWeight: FontWeight.w600)),
            Expanded(
                child: Text(value,
                    style: const TextStyle(
                        color: Colors.white38, fontSize: 12))),
          ],
        ),
      );

  Widget _buildPerimeterMap() {
    final perimLayers = <Polygon>[];
    if (_perimeterGeoJson != null) {
      final features = (_perimeterGeoJson!['features'] as List?) ?? [];
      for (final f in features) {
        final geom = f['geometry'] as Map<String, dynamic>?;
        if (geom == null) continue;
        final type = geom['type'] as String? ?? '';
        final coordsList = type == 'Polygon'
            ? [geom['coordinates'] as List]
            : geom['type'] == 'MultiPolygon'
                ? (geom['coordinates'] as List)
                : <dynamic>[];
        for (final ring in coordsList) {
          final outer = (ring is List && ring.isNotEmpty)
              ? ring[0] as List
              : <dynamic>[];
          final pts = outer
              .map((c) =>
                  LatLng((c[1] as num).toDouble(), (c[0] as num).toDouble()))
              .toList();
          if (pts.isNotEmpty) {
            perimLayers.add(Polygon(
              points: pts,
              color: Colors.orange.withValues(alpha: 0.08),
              borderColor: Colors.orangeAccent,
              borderStrokeWidth: 1.5,
            ));
          }
        }
      }
    }
    return FlutterMap(
      mapController: _mapController,
      options: const MapOptions(
        initialCenter: _dolanCenter,
        initialZoom: 10,
      ),
      children: [
        TileLayer(
          urlTemplate:
              'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
          userAgentPackageName: 'com.example.fire_webapp',
        ),
        if (perimLayers.isNotEmpty) PolygonLayer(polygons: perimLayers),
      ],
    );
  }

  // -------------------------------------------------------------------------
  // Analyzing screen
  // -------------------------------------------------------------------------

  Widget _buildAnalyzing() {
    final stepIdx = (_currentStep - 1).clamp(0, _kSteps.length - 1);
    return Center(
      child: Container(
        constraints: const BoxConstraints(maxWidth: 600),
        padding: const EdgeInsets.all(40),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AnimatedBuilder(
              animation: _pulseAnim,
              builder: (_, __) => Opacity(
                opacity: _pulseAnim.value,
                child: Container(
                  width: 72,
                  height: 72,
                  decoration: BoxDecoration(
                    color: _kAccent.withValues(alpha: 0.12),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.science, color: _kAccent, size: 36),
                ),
              ),
            ),
            const SizedBox(height: 24),
            const Text('Running Real Wildcat Pipeline',
                style: TextStyle(
                    color: Colors.white,
                    fontSize: 20,
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 6),
            const Text('USGS pfdf v3.0.3 — not an approximation',
                style: TextStyle(color: _kAccent, fontSize: 13)),
            const SizedBox(height: 32),

            ...List.generate(_kSteps.length, (i) {
              final done = i < _currentStep - 1;
              final active = i == stepIdx && _currentStep > 0;
              return AnimatedContainer(
                duration: const Duration(milliseconds: 300),
                margin: const EdgeInsets.only(bottom: 10),
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  color: active
                      ? _kAccent.withValues(alpha: 0.1)
                      : done
                          ? Colors.white.withValues(alpha: 0.04)
                          : Colors.transparent,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                      color: active
                          ? _kAccent.withValues(alpha: 0.4)
                          : Colors.white.withValues(alpha: 0.06)),
                ),
                child: Row(
                  children: [
                    Icon(
                      done
                          ? Icons.check_circle
                          : active
                              ? _kStepIcons[i]
                              : Icons.radio_button_unchecked,
                      color: done
                          ? Colors.greenAccent
                          : active
                              ? _kAccent
                              : Colors.white24,
                      size: 20,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        _kSteps[i],
                        style: TextStyle(
                            color: active
                                ? Colors.white
                                : done
                                    ? Colors.white54
                                    : Colors.white24,
                            fontSize: 12,
                            height: 1.4),
                      ),
                    ),
                    if (active)
                      const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: _kAccent)),
                  ],
                ),
              );
            }),

            const SizedBox(height: 24),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: _progress / 100.0,
                backgroundColor: Colors.white12,
                valueColor: const AlwaysStoppedAnimation<Color>(_kAccent),
                minHeight: 6,
              ),
            ),
            const SizedBox(height: 12),
            Text('$_progress%  —  $_stepMessage',
                style: const TextStyle(color: Colors.white54, fontSize: 12),
                textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }

  // -------------------------------------------------------------------------
  // Results screen
  // -------------------------------------------------------------------------

  Widget _buildResults() {
    if (_results == null) return const Center(child: CircularProgressIndicator());

    final hasZone = _zoneResults != null;

    // Full basins — dimmed when zone is active (tap handled via MapOptions.onTap)
    final fullPolygons = buildPolygons(
      features: _results!.features,
      selectedIndex: hasZone ? null : _selectedFeatureIndex,
      onTap: (i) => setState(() => _selectedFeatureIndex = i),
      dimmed: hasZone,
    );

    // Zone basins — full opacity, on top
    final zonePolygons = hasZone
        ? buildPolygons(
            features: _zoneResults!.features,
            selectedIndex: _selectedFeatureIndex,
            onTap: (i) => setState(() => _selectedFeatureIndex = i),
          )
        : <Polygon>[];

    // Fire perimeter outline
    final perimPolygons = _buildPerimeterPolygons();

    // Zone drawing in-progress polygon
    final drawPolygons = _drawPoints.length >= 2
        ? [
            Polygon(
              points: [..._drawPoints, _drawPoints.first],
              color: Colors.amberAccent.withValues(alpha: 0.15),
              borderColor: Colors.amberAccent,
              borderStrokeWidth: 2,
            )
          ]
        : <Polygon>[];

    // Completed zone boundary outline
    final zoneBoundaryPolygons = _zoneBoundary.length >= 3
        ? [
            Polygon(
              points: _zoneBoundary,
              color: Colors.transparent,
              borderColor: Colors.white,
              borderStrokeWidth: 2.5,
            )
          ]
        : <Polygon>[];

    // Draw-mode markers
    final drawMarkers = _drawPoints
        .map((p) => Marker(
              point: p,
              width: 10,
              height: 10,
              child: Container(
                decoration: BoxDecoration(
                  color: Colors.amberAccent,
                  shape: BoxShape.circle,
                  border: Border.all(color: Colors.white, width: 1.5),
                ),
              ),
            ))
        .toList();

    return Stack(
      children: [
        // ── Map ──────────────────────────────────────────────────────────────
        FlutterMap(
          mapController: _mapController,
          options: MapOptions(
            initialCenter: _dolanCenter,
            initialZoom: 10,
            onTap: (tapPos, latLng) {
              if (_drawingZone) {
                setState(() => _drawPoints.add(latLng));
                return;
              }
              // Basin tap via ray-casting
              final feats = hasZone
                  ? _zoneResults!.features
                  : _results!.features;
              int? hit;
              for (int i = 0; i < feats.length; i++) {
                if (feats[i].rings.isEmpty) continue;
                if (_pointInPolygon(latLng, feats[i].rings[0])) {
                  hit = i;
                  break;
                }
              }
              setState(() => _selectedFeatureIndex = hit);
            },
          ),
          children: [
            TileLayer(
              urlTemplate: _useSatellite
                  ? 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
                  : 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
              userAgentPackageName: 'com.example.fire_webapp',
            ),
            PolygonLayer(polygons: fullPolygons),
            if (zonePolygons.isNotEmpty) PolygonLayer(polygons: zonePolygons),
            if (perimPolygons.isNotEmpty) PolygonLayer(polygons: perimPolygons),
            if (zoneBoundaryPolygons.isNotEmpty)
              PolygonLayer(polygons: zoneBoundaryPolygons),
            if (drawPolygons.isNotEmpty) PolygonLayer(polygons: drawPolygons),
            if (drawMarkers.isNotEmpty) MarkerLayer(markers: drawMarkers),
          ],
        ),

        // ── Top-left badge ────────────────────────────────────────────────────
        Positioned(
          top: 12,
          left: 12,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: const Color(0xCC0A2030),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: _kAccent.withValues(alpha: 0.5)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.verified, color: _kAccent, size: 13),
                const SizedBox(width: 5),
                Text(
                  _drawingZone
                      ? 'Drawing Zone — ${_drawPoints.length} pts'
                      : hasZone
                          ? 'Zone: ${_zoneResults!.features.length} basins  |  Full: ${_results!.features.length}'
                          : 'Real Wildcat (pfdf)  |  ${_results!.features.length} basins',
                  style: const TextStyle(
                      color: _kAccent, fontSize: 11, fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
        ),

        // ── Hazard legend ─────────────────────────────────────────────────────
        Positioned(
          bottom: 24,
          left: 12,
          child: _buildLegend(),
        ),

        // ── Drawing toolbar ───────────────────────────────────────────────────
        if (_drawingZone)
          Positioned(
            bottom: 24,
            right: 12,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                if (_drawPoints.length >= 3)
                  ElevatedButton.icon(
                    onPressed: _confirmZone,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _kAccent,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(8)),
                    ),
                    icon: const Icon(Icons.check, size: 16),
                    label: const Text('Run Zone Wildcat',
                        style: TextStyle(fontSize: 12)),
                  ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    OutlinedButton.icon(
                      onPressed:
                          _drawPoints.isNotEmpty ? _undoPoint : null,
                      style: OutlinedButton.styleFrom(
                        foregroundColor: Colors.white54,
                        side: const BorderSide(color: Colors.white24),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8)),
                      ),
                      icon: const Icon(Icons.undo, size: 14),
                      label: const Text('Undo',
                          style: TextStyle(fontSize: 12)),
                    ),
                    const SizedBox(width: 8),
                    OutlinedButton.icon(
                      onPressed: _cancelDrawing,
                      style: OutlinedButton.styleFrom(
                        foregroundColor: Colors.redAccent,
                        side: const BorderSide(color: Colors.redAccent),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8)),
                      ),
                      icon: const Icon(Icons.close, size: 14),
                      label: const Text('Cancel',
                          style: TextStyle(fontSize: 12)),
                    ),
                  ],
                ),
              ],
            ),
          ),

        // ── Zone running overlay ──────────────────────────────────────────────
        if (_zoneRunning)
          Positioned(
            bottom: 24,
            right: 12,
            child: Container(
              constraints: const BoxConstraints(maxWidth: 300),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: const Color(0xDD0A2030),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: _kAccent.withValues(alpha: 0.4)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: _kAccent)),
                      const SizedBox(width: 8),
                      const Text('Zone Analysis Running',
                          style: TextStyle(
                              color: _kAccent,
                              fontSize: 12,
                              fontWeight: FontWeight.w600)),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Step $_zoneStep/3  ·  $_zoneProgress%',
                    style: const TextStyle(
                        color: Colors.white54, fontSize: 11),
                  ),
                  const SizedBox(height: 6),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(3),
                    child: LinearProgressIndicator(
                      value: _zoneProgress / 100.0,
                      backgroundColor: Colors.white12,
                      valueColor:
                          const AlwaysStoppedAnimation<Color>(_kAccent),
                      minHeight: 4,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    _zoneMessage,
                    style:
                        const TextStyle(color: Colors.white38, fontSize: 10),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ),

        // ── Zone error ────────────────────────────────────────────────────────
        if (_zoneError != null)
          Positioned(
            bottom: 24,
            right: 12,
            child: GestureDetector(
              onTap: () => setState(() => _zoneError = null),
              child: Container(
                constraints: const BoxConstraints(maxWidth: 280),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.red.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                      color: Colors.redAccent.withValues(alpha: 0.5)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.error_outline,
                        color: Colors.redAccent, size: 14),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(_zoneError!,
                          style: const TextStyle(
                              color: Colors.redAccent, fontSize: 11)),
                    ),
                    const Icon(Icons.close,
                        color: Colors.redAccent, size: 12),
                  ],
                ),
              ),
            ),
          ),

        // ── Attribute panel ───────────────────────────────────────────────────
        if (_selectedFeatureIndex != null) ...[
          () {
            final feats =
                hasZone ? _zoneResults!.features : _results!.features;
            if (_selectedFeatureIndex! >= feats.length) return const SizedBox();
            return Positioned(
              top: 0,
              right: 0,
              bottom: 0,
              width: 320,
              child: AttributePanel(
                feature: feats[_selectedFeatureIndex!],
                onClose: () =>
                    setState(() => _selectedFeatureIndex = null),
              ),
            );
          }(),
        ],
      ],
    );
  }

  List<Polygon> _buildPerimeterPolygons() {
    if (_perimeterGeoJson == null) return [];
    final result = <Polygon>[];
    final pf = (_perimeterGeoJson!['features'] as List?) ?? [];
    for (final f in pf) {
      final geom = f['geometry'] as Map<String, dynamic>?;
      if (geom == null) continue;
      final type = geom['type'] as String? ?? '';
      final coordsList = type == 'Polygon'
          ? [geom['coordinates'] as List]
          : type == 'MultiPolygon'
              ? (geom['coordinates'] as List)
              : <dynamic>[];
      for (final ring in coordsList) {
        final outer =
            (ring is List && ring.isNotEmpty) ? ring[0] as List : <dynamic>[];
        final pts = outer
            .map((c) =>
                LatLng((c[1] as num).toDouble(), (c[0] as num).toDouble()))
            .toList();
        if (pts.isNotEmpty) {
          result.add(Polygon(
            points: pts,
            color: Colors.transparent,
            borderColor: Colors.orangeAccent,
            borderStrokeWidth: 1.5,
          ));
        }
      }
    }
    return result;
  }

  Widget _buildLegend() {
    const items = [
      (Color(0xFFE53935), 'H3 — High'),
      (Color(0xFFFB8C00), 'H2 — Moderate'),
      (Color(0xFFFFEE58), 'H1 — Low'),
      (Color(0xFF43A047), 'H0 — Very Low'),
    ];
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xCC0D1B2A),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Hazard @ I15=24mm/hr',
              style: TextStyle(
                  color: Colors.white54,
                  fontSize: 10,
                  fontWeight: FontWeight.w600)),
          const SizedBox(height: 6),
          ...items.map((item) => Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(children: [
                  Container(
                      width: 14,
                      height: 14,
                      decoration: BoxDecoration(
                          color: item.$1,
                          borderRadius: BorderRadius.circular(3))),
                  const SizedBox(width: 6),
                  Text(item.$2,
                      style: const TextStyle(
                          color: Colors.white70, fontSize: 11)),
                ]),
              )),
        ],
      ),
    );
  }

  bool _pointInPolygon(LatLng point, List<LatLng> polygon) {
    bool inside = false;
    int j = polygon.length - 1;
    for (int i = 0; i < polygon.length; i++) {
      if (((polygon[i].latitude > point.latitude) !=
              (polygon[j].latitude > point.latitude)) &&
          (point.longitude <
              (polygon[j].longitude - polygon[i].longitude) *
                      (point.latitude - polygon[i].latitude) /
                      (polygon[j].latitude - polygon[i].latitude) +
                  polygon[i].longitude)) {
        inside = !inside;
      }
      j = i;
    }
    return inside;
  }
}
