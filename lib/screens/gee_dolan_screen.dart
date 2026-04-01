import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:http/http.dart' as http;

import '../config/app_config.dart';
import '../utils/geojson_parser.dart';
import '../widgets/attribute_panel.dart';

// Step labels (identical to Dolan — same pipeline)
const _kSteps = [
  'Loading fire perimeter, DEM request, and burn severity rasters...',
  'Downloading 3DEP 10m DEM from Google Earth Engine...',
  'Filling topographic depressions in DEM...',
  'Computing D8 flow direction across terrain...',
  'Computing flow accumulation (upslope contributing area)...',
  'Extracting stream network (threshold: 0.15 km²)...',
  'Delineating sub-basins from stream network...',
  'Computing slope and burn severity for each sub-basin...',
  'Running Staley (2017) debris-flow probability model...',
  'Exporting GeoJSON results and fire perimeter...',
];

const _kStepIcons = [
  Icons.map_outlined,
  Icons.cloud_download_outlined,
  Icons.terrain,
  Icons.water,
  Icons.trending_up,
  Icons.account_tree_outlined,
  Icons.grain,
  Icons.show_chart,
  Icons.science_outlined,
  Icons.file_download_done,
];

const _kAccent = Color(0xFF42A5F5); // blue accent for GEE screen
const _kDolanCenter = LatLng(36.06, -121.40);

enum _GeeScreenState { connect, configure, drawArea, analyzing, results }

class GeeDolanScreen extends StatefulWidget {
  const GeeDolanScreen({super.key});

  @override
  State<GeeDolanScreen> createState() => _GeeDolanScreenState();
}

class _GeeDolanScreenState extends State<GeeDolanScreen>
    with TickerProviderStateMixin {
  static final String _backendUrl = AppConfig.backendUrl;

  final MapController _mapController = MapController();
  final TextEditingController _projectIdController = TextEditingController();

  _GeeScreenState _screenState = _GeeScreenState.connect;

  // --- Connection state ---
  bool _connecting = false;
  bool _connected = false;
  String? _connectError;
  String _connectedProjectId = '';

  // --- Configure state ---
  String _selectedMetric = 'dnbr';
  List<Map<String, dynamic>> _datasets = [];
  bool _datasetsLoading = true;
  bool _useCache = true;
  bool _perimeterLoading = true;

  // --- Draw area (primary analysis polygon) ---
  List<LatLng> _primaryPoints = [];
  String? _primaryDrawError;
  bool _jobIsZoneBased = false; // true when primary analysis used a drawn polygon

  // --- Analyze state ---
  String? _jobId;
  int _currentStep = 0;
  String _stepMessage = '';
  int _progress = 0;
  String? _error;
  Timer? _pollTimer;

  // --- Results state ---
  ParsedGeoJson? _results;
  Map<String, dynamic>? _perimeterGeoJson;
  int? _selectedFeatureIndex;
  bool _useSatellite = true;

  // --- Zone analysis state ---
  bool _drawingZone = false;
  List<LatLng> _drawPoints = [];
  String? _zoneJobId;
  int _zoneStep = 0;
  int _zoneProgress = 0;
  String _zoneMessage = '';
  bool _zoneRunning = false;
  ParsedGeoJson? _zoneResults;
  List<LatLng> _zoneBoundary = [];
  String? _zoneError;
  Timer? _zonePollTimer;

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
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _zonePollTimer?.cancel();
    _pulseController.dispose();
    _projectIdController.dispose();
    super.dispose();
  }

  // -----------------------------------------------------------------------
  // GEE Connection
  // -----------------------------------------------------------------------

  Future<void> _testConnection() async {
    final projectId = _projectIdController.text.trim();
    if (projectId.isEmpty) {
      setState(() => _connectError = 'Please enter your GEE project ID.');
      return;
    }
    setState(() {
      _connecting = true;
      _connectError = null;
      _connected = false;
    });
    try {
      final resp = await http.post(
        Uri.parse('$_backendUrl/gee/test-connection'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'project_id': projectId}),
      );
      final body = json.decode(resp.body);
      if (resp.statusCode == 200 && (body['success'] as bool? ?? false)) {
        setState(() {
          _connected = true;
          _connectedProjectId = projectId;
          _connecting = false;
        });
        await _loadAvailableInputs();
        if (mounted) setState(() => _screenState = _GeeScreenState.configure);
      } else {
        setState(() {
          _connecting = false;
          _connectError = body['detail'] ?? body['message'] ?? 'Connection failed.';
        });
      }
    } catch (e) {
      setState(() {
        _connecting = false;
        _connectError = 'Could not reach backend: $e';
      });
    }
  }

  Future<void> _loadAvailableInputs() async {
    // Load perimeter for configure screen map preview (best-effort)
    http.get(Uri.parse('$_backendUrl/gee/dolan/perimeter')).then((resp) {
      if (resp.statusCode == 200 && mounted) {
        setState(() {
          _perimeterGeoJson = json.decode(resp.body);
          _perimeterLoading = false;
        });
      } else if (mounted) {
        setState(() => _perimeterLoading = false);
      }
    }).catchError((_) {
      if (mounted) setState(() => _perimeterLoading = false);
    });

    try {
      final resp = await http.get(
          Uri.parse('$_backendUrl/gee/dolan/available-inputs'));
      if (resp.statusCode == 200 && mounted) {
        final body = json.decode(resp.body);
        setState(() {
          _datasets = List<Map<String, dynamic>>.from(body['datasets']);
          _datasetsLoading = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _datasetsLoading = false);
    }
  }

  // -----------------------------------------------------------------------
  // Analysis
  // -----------------------------------------------------------------------

  // Enter draw-area mode — load perimeter for background, then let user draw.
  void _enterDrawArea() {
    setState(() {
      _screenState = _GeeScreenState.drawArea;
      _primaryPoints = [];
      _primaryDrawError = null;
      _error = null; // clear any stale error from a previous run
    });
    // Load perimeter as background reference (best-effort; not fatal if missing)
    if (_perimeterGeoJson == null) {
      http.get(Uri.parse('$_backendUrl/gee/dolan/perimeter')).then((resp) {
        if (resp.statusCode == 200 && mounted) {
          setState(() => _perimeterGeoJson = json.decode(resp.body));
        }
      });
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _mapController.move(_kDolanCenter, 10);
    });
  }

  Future<void> _confirmPrimaryArea() async {
    if (_primaryPoints.length < 3) return;
    final pts = List<LatLng>.from(_primaryPoints)..add(_primaryPoints.first);
    final coords = pts.map((p) => [p.longitude, p.latitude]).toList();
    final polygon = {'type': 'Polygon', 'coordinates': [coords]};

    setState(() => _primaryDrawError = null);
    try {
      final valResp = await http.post(
        Uri.parse('$_backendUrl/gee/validate-area'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'polygon': polygon, 'buffer_m': 1000}),
      );
      final valBody = json.decode(valResp.body);
      final ok = valBody['ok'] as bool? ?? false;
      if (!ok) {
        setState(() => _primaryDrawError = valBody['message'] as String? ??
            'Area too large. Draw a smaller polygon.');
        return;
      }
    } catch (e) {
      setState(() => _primaryDrawError = 'Could not validate area: $e');
      return;
    }

    setState(() {
      _jobIsZoneBased = true;
      _zoneBoundary = pts; // store outline for display in results
      _screenState = _GeeScreenState.analyzing;
      _currentStep = 0;
      _stepMessage = 'Initialising GEE analysis pipeline...';
      _progress = 0;
      _error = null;
    });
    try {
      final resp = await http.post(
        Uri.parse(
            '$_backendUrl/gee/dolan/analyze-zone?burn_metric=$_selectedMetric'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'project_id': _connectedProjectId,
          'polygon': polygon,
        }),
      );
      if (resp.statusCode != 200) throw Exception(resp.body);
      final body = json.decode(resp.body);
      _jobId = body['job_id'] as String;
      _pollTimer?.cancel();
      _pollTimer =
          Timer.periodic(const Duration(milliseconds: 1200), (_) => _poll());
    } catch (e) {
      setState(() {
        _error = 'Failed to start: $e';
        _screenState = _GeeScreenState.drawArea;
      });
    }
  }

  Future<void> _poll() async {
    if (_jobId == null) return;
    try {
      final resp = await http
          .get(Uri.parse('$_backendUrl/gee/dolan/status/$_jobId'));
      if (resp.statusCode != 200) return;
      final data = json.decode(resp.body);
      final status = data['status'] as String? ?? 'running';
      if (!mounted) return;
      if (status == 'completed') {
        _pollTimer?.cancel();
        setState(() {
          _currentStep = 10;
          _progress = 100;
          _stepMessage = data['message'] as String? ?? 'Done';
        });
        await _loadResults();
      } else if (status == 'error') {
        _pollTimer?.cancel();
        setState(() {
          _error = data['error'] as String? ?? 'Unknown error';
          _screenState = _GeeScreenState.configure;
        });
      } else {
        setState(() {
          _currentStep = (data['step'] as num?)?.toInt() ?? _currentStep;
          _stepMessage = data['message'] as String? ?? _stepMessage;
          _progress = (data['progress'] as num?)?.toInt() ?? _progress;
        });
      }
    } catch (_) {}
  }

  Future<void> _loadResults() async {
    try {
      final http.Response resultsResp;
      if (_jobIsZoneBased && _jobId != null) {
        resultsResp = await http
            .get(Uri.parse('$_backendUrl/gee/dolan/zone-results/$_jobId'));
      } else {
        resultsResp =
            await http.get(Uri.parse('$_backendUrl/gee/dolan/results'));
      }
      if (resultsResp.statusCode != 200) throw Exception(resultsResp.body);
      final parsed = parseGeoJson(json.decode(resultsResp.body));
      if (!mounted) return;

      if (!_jobIsZoneBased) {
        final perimResp =
            await http.get(Uri.parse('$_backendUrl/gee/dolan/perimeter'));
        if (perimResp.statusCode == 200 && mounted) {
          setState(() => _perimeterGeoJson = json.decode(perimResp.body));
        }
      }
      // When zone-based, _perimeterGeoJson keeps whatever was loaded as
      // background; _zoneBoundary already holds the drawn outline.

      if (!mounted) return;
      setState(() {
        _results = parsed;
        _screenState = _GeeScreenState.results;
      });
      if (parsed.bounds != null) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            _mapController.fitCamera(CameraFit.bounds(
                bounds: parsed.bounds!, padding: const EdgeInsets.all(60)));
          }
        });
      }
    } catch (e) {
      setState(() {
        _error = 'Failed to load results: $e';
        _screenState =
            _jobIsZoneBased ? _GeeScreenState.drawArea : _GeeScreenState.configure;
      });
    }
  }

  // -----------------------------------------------------------------------
  // Zone analysis
  // -----------------------------------------------------------------------

  void _startDrawing() => setState(() {
        _drawingZone = true;
        _drawPoints = [];
        _zoneResults = null;
        _zoneBoundary = [];
        _zoneError = null;
        _selectedFeatureIndex = null;
      });

  void _cancelDrawing() =>
      setState(() { _drawingZone = false; _drawPoints = []; });

  void _undoPoint() {
    if (_drawPoints.isNotEmpty) setState(() => _drawPoints.removeLast());
  }

  Future<void> _confirmZone() async {
    if (_drawPoints.length < 3) return;
    final pts = List<LatLng>.from(_drawPoints)..add(_drawPoints.first);
    final coords = pts.map((p) => [p.longitude, p.latitude]).toList();
    final polygon = {'type': 'Polygon', 'coordinates': [coords]};

    // --- Area validation before touching GEE ---
    // Stay in drawing mode but show the error so user can adjust the polygon.
    setState(() => _zoneError = null);
    try {
      final valResp = await http.post(
        Uri.parse('$_backendUrl/gee/validate-area'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'polygon': polygon, 'buffer_m': 200}),
      );
      final valBody = json.decode(valResp.body);
      final ok = valBody['ok'] as bool? ?? false;
      if (!ok) {
        // Keep user in drawing mode — let them undo points and redraw
        setState(() => _zoneError = valBody['message'] as String? ??
            'Zone area too large. Please draw a smaller area.');
        return;
      }
    } catch (e) {
      // Validation endpoint unreachable — block and report
      setState(() =>
          _zoneError = 'Could not validate zone area: $e. Is the backend running?');
      return;
    }

    // --- Area is OK — proceed with full pipeline ---
    setState(() {
      _drawingZone = false;
      _drawPoints = [];
      _zoneBoundary = pts;
      _zoneRunning = true;
      _zoneStep = 0;
      _zoneProgress = 0;
      _zoneMessage = 'Submitting zone to GEE pipeline...';
      _zoneError = null;
      _zoneResults = null;
    });
    try {
      final resp = await http.post(
        Uri.parse('$_backendUrl/gee/dolan/analyze-zone'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'project_id': _connectedProjectId,
          'polygon': polygon,
        }),
      );
      if (resp.statusCode != 200) throw Exception(resp.body);
      final body = json.decode(resp.body);
      _zoneJobId = body['job_id'] as String;
      _zonePollTimer?.cancel();
      _zonePollTimer = Timer.periodic(
          const Duration(milliseconds: 1200), (_) => _pollZone());
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
          .get(Uri.parse('$_backendUrl/gee/dolan/status/$_zoneJobId'));
      if (resp.statusCode != 200) return;
      final data = json.decode(resp.body);
      final status = data['status'] as String? ?? 'running';
      if (!mounted) return;
      if (status == 'completed') {
        _zonePollTimer?.cancel();
        setState(() {
          _zoneStep = 10; _zoneProgress = 100;
          _zoneMessage = data['message'] as String? ?? 'Zone complete';
        });
        await _loadZoneResults();
      } else if (status == 'error') {
        _zonePollTimer?.cancel();
        setState(() {
          _zoneRunning = false;
          _zoneError = data['error'] as String? ?? 'Unknown error';
        });
      } else {
        setState(() {
          _zoneStep = (data['step'] as num?)?.toInt() ?? _zoneStep;
          _zoneProgress = (data['progress'] as num?)?.toInt() ?? _zoneProgress;
          _zoneMessage = data['message'] as String? ?? _zoneMessage;
        });
      }
    } catch (_) {}
  }

  Future<void> _loadZoneResults() async {
    try {
      final resp = await http
          .get(Uri.parse('$_backendUrl/gee/dolan/zone-results/$_zoneJobId'));
      if (resp.statusCode == 200 && mounted) {
        setState(() {
          _zoneResults = parseGeoJson(json.decode(resp.body));
          _zoneRunning = false;
        });
      }
    } catch (e) {
      setState(() {
        _zoneRunning = false;
        _zoneError = 'Failed to load zone results: $e';
      });
    }
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

  // -----------------------------------------------------------------------
  // Build
  // -----------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A1628),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0D2137),
        foregroundColor: Colors.white,
        title: const Row(children: [
          Icon(Icons.cloud_outlined, color: _kAccent),
          SizedBox(width: 10),
          Text('Dolan Fire  ×  GEE',
              style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
          SizedBox(width: 10),
          Text('DEM via Google Earth Engine',
              style: TextStyle(
                  color: Colors.white54,
                  fontSize: 13,
                  fontWeight: FontWeight.normal)),
        ]),
        actions: [
          if (_screenState == _GeeScreenState.results) ...[
            IconButton(
              tooltip: _useSatellite ? 'Street Map' : 'Satellite',
              onPressed: () => setState(() => _useSatellite = !_useSatellite),
              icon: Icon(
                _useSatellite ? Icons.map_outlined : Icons.satellite_alt,
                color: Colors.white70,
              ),
            ),
            if (!_drawingZone && !_zoneRunning)
              TextButton.icon(
                onPressed: _startDrawing,
                icon: const Icon(Icons.draw, color: Colors.amberAccent),
                label: const Text('Analyze Zone',
                    style: TextStyle(color: Colors.amberAccent)),
              ),
            TextButton.icon(
              onPressed: () => setState(() {
                _jobIsZoneBased = false;
                _zoneBoundary = [];
                _zoneResults = null;
                _screenState = _GeeScreenState.configure;
                _selectedFeatureIndex = null;
              }),
              icon: const Icon(Icons.tune, color: _kAccent),
              label: const Text('Re-configure',
                  style: TextStyle(color: _kAccent)),
            ),
          ],
          if (_screenState == _GeeScreenState.configure ||
              _screenState == _GeeScreenState.connect ||
              _screenState == _GeeScreenState.drawArea)
            Padding(
              padding: const EdgeInsets.only(right: 12),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.circle,
                    size: 8,
                    color: _connected ? Colors.greenAccent : Colors.white30),
                const SizedBox(width: 6),
                Text(
                  _connected
                      ? 'Connected: $_connectedProjectId'
                      : 'Not connected',
                  style: TextStyle(
                      color: _connected ? Colors.greenAccent : Colors.white38,
                      fontSize: 12),
                ),
              ]),
            ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    switch (_screenState) {
      case _GeeScreenState.connect:
        return _buildConnect();
      case _GeeScreenState.configure:
        return _buildConfigure();
      case _GeeScreenState.drawArea:
        return _buildDrawArea();
      case _GeeScreenState.analyzing:
        return _buildAnalyzing();
      case _GeeScreenState.results:
        return _buildResults();
    }
  }

  // -----------------------------------------------------------------------
  // Connect screen
  // -----------------------------------------------------------------------

  Widget _buildConnect() {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 540),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // GEE icon + title
              Row(children: [
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: _kAccent.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: _kAccent.withValues(alpha: 0.3)),
                  ),
                  child: const Icon(Icons.cloud_outlined,
                      color: _kAccent, size: 36),
                ),
                const SizedBox(width: 18),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Google Earth Engine',
                          style: TextStyle(
                              color: Colors.white,
                              fontSize: 22,
                              fontWeight: FontWeight.bold)),
                      SizedBox(height: 4),
                      Text('DEM-on-demand for Dolan Fire Analysis',
                          style:
                              TextStyle(color: Colors.white54, fontSize: 13)),
                    ],
                  ),
                ),
              ]),

              const SizedBox(height: 28),

              // Prerequisite info box
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.blueGrey.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                      color: Colors.blueGrey.withValues(alpha: 0.3)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(children: [
                      Icon(Icons.info_outline,
                          color: Colors.white60, size: 16),
                      SizedBox(width: 8),
                      Text('Prerequisite',
                          style: TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                              fontSize: 13)),
                    ]),
                    const SizedBox(height: 10),
                    _prereqRow('earthengine authenticate',
                        'Run this once in your terminal to store local credentials'),
                    _prereqRow('GEE project ID',
                        'A Google Cloud project with Earth Engine API enabled'),
                    _prereqRow('Local DEM file not needed',
                        'The 1.1 GB DEM is downloaded on-demand from USGS 3DEP'),
                  ],
                ),
              ),

              const SizedBox(height: 28),

              // Project ID input
              const Text('GEE Project ID',
                  style: TextStyle(
                      color: Colors.white70,
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.5)),
              const SizedBox(height: 8),
              TextField(
                controller: _projectIdController,
                style: const TextStyle(color: Colors.white, fontSize: 14),
                decoration: InputDecoration(
                  hintText: 'e.g.  my-gee-project-123',
                  hintStyle: const TextStyle(color: Colors.white30),
                  prefixIcon: const Icon(Icons.account_tree_outlined,
                      color: Colors.white38, size: 18),
                  filled: true,
                  fillColor: Colors.white.withValues(alpha: 0.06),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: BorderSide(
                        color: Colors.white.withValues(alpha: 0.15)),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: BorderSide(
                        color: Colors.white.withValues(alpha: 0.15)),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide:
                        const BorderSide(color: _kAccent, width: 1.5),
                  ),
                  errorText: _connectError,
                  errorStyle:
                      const TextStyle(color: Colors.redAccent, fontSize: 12),
                ),
                onSubmitted: (_) => _testConnection(),
              ),

              const SizedBox(height: 20),

              // Connect button
              SizedBox(
                width: double.infinity,
                height: 52,
                child: ElevatedButton.icon(
                  onPressed: _connecting ? null : _testConnection,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _kAccent,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10)),
                  ),
                  icon: _connecting
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: Colors.white))
                      : const Icon(Icons.link, size: 20),
                  label: Text(
                    _connecting
                        ? 'Testing connection...'
                        : 'Test Connection & Continue',
                    style: const TextStyle(
                        fontSize: 15, fontWeight: FontWeight.bold),
                  ),
                ),
              ),

              const SizedBox(height: 24),

              // What GEE provides
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: _kAccent.withValues(alpha: 0.06),
                  borderRadius: BorderRadius.circular(10),
                  border:
                      Border.all(color: _kAccent.withValues(alpha: 0.2)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('What changes vs. the standard Dolan screen',
                        style: TextStyle(
                            color: Colors.white70,
                            fontSize: 12,
                            fontWeight: FontWeight.w600)),
                    const SizedBox(height: 10),
                    _changeRow(Icons.cloud_download_outlined, _kAccent,
                        'DEM source',
                        'Downloaded live from USGS 3DEP via GEE (~20 MB clip). No local 1.1 GB file needed.'),
                    _changeRow(Icons.folder_outlined, Colors.white38,
                        'Burn severity',
                        'Still read from local files (dNBR/rdNBR/dNBR6) — only 3 MB each.'),
                    _changeRow(Icons.timer_outlined, Colors.white38,
                        'Extra time',
                        'GEE download adds ~20–40 s before the WhiteboxTools pipeline starts.'),
                    _changeRow(Icons.check_circle_outline, Colors.greenAccent,
                        'Steps 3–10',
                        'WhiteboxTools pipeline is completely unchanged.'),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _prereqRow(String code, String description) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(4),
          ),
          child: Text(code,
              style: const TextStyle(
                  color: _kAccent, fontSize: 11, fontFamily: 'monospace')),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Text(description,
              style: const TextStyle(color: Colors.white54, fontSize: 11)),
        ),
      ]),
    );
  }

  Widget _changeRow(
      IconData icon, Color iconColor, String label, String detail) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, size: 14, color: iconColor),
        const SizedBox(width: 8),
        SizedBox(
          width: 90,
          child: Text(label,
              style: const TextStyle(
                  color: Colors.white70,
                  fontSize: 11,
                  fontWeight: FontWeight.w600)),
        ),
        Expanded(
          child: Text(detail,
              style:
                  const TextStyle(color: Colors.white54, fontSize: 11)),
        ),
      ]),
    );
  }

  // -----------------------------------------------------------------------
  // Configure screen
  // -----------------------------------------------------------------------

  Widget _buildConfigure() {
    return Row(children: [
      // Left panel
      SizedBox(
        width: 300,
        child: Container(
          color: const Color(0xFF0A1628),
          child: Column(children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(20),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  const Text('Configure Analysis',
                      style: TextStyle(
                          color: Colors.white,
                          fontSize: 17,
                          fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Text('GEE will download a fresh 10m DEM for this area.',
                      style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.45),
                          fontSize: 12)),
                  const SizedBox(height: 20),

                  // Burn metric selector
                  const Text('Burn Severity Input',
                      style: TextStyle(
                          color: Colors.white70,
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 0.8)),
                  const SizedBox(height: 10),

                  if (_datasetsLoading)
                    const Center(
                        child: Padding(
                      padding: EdgeInsets.all(20),
                      child:
                          CircularProgressIndicator(color: _kAccent),
                    ))
                  else
                    ..._datasets.map((ds) => _buildMetricCard(ds)),

                  const SizedBox(height: 20),

                  // GEE note
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: _kAccent.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                          color: _kAccent.withValues(alpha: 0.25)),
                    ),
                    child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                      const Icon(Icons.cloud_outlined,
                          color: _kAccent, size: 14),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'DEM will be fetched from USGS 3DEP via GEE during Step 2 (~20–40 s download).',
                          style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.55),
                              fontSize: 11,
                              height: 1.4),
                        ),
                      ),
                    ]),
                  ),

                  const SizedBox(height: 12),

                  // Cache toggle
                  InkWell(
                    onTap: () => setState(() => _useCache = !_useCache),
                    borderRadius: BorderRadius.circular(6),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Row(children: [
                        SizedBox(
                          width: 20,
                          height: 20,
                          child: Checkbox(
                            value: _useCache,
                            onChanged: (v) =>
                                setState(() => _useCache = v ?? true),
                            activeColor: _kAccent,
                            side: BorderSide(
                                color: Colors.white.withValues(alpha: 0.35)),
                            materialTapTargetSize:
                                MaterialTapTargetSize.shrinkWrap,
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            'Use cached DEM if available',
                            style: TextStyle(
                                color: Colors.white.withValues(alpha: 0.75),
                                fontSize: 12),
                          ),
                        ),
                      ]),
                    ),
                  ),
                  if (!_useCache)
                    Padding(
                      padding: const EdgeInsets.only(left: 30, top: 2),
                      child: Text(
                        'A fresh DEM will be downloaded from GEE each run.',
                        style: TextStyle(
                            color: Colors.amber.withValues(alpha: 0.7),
                            fontSize: 10,
                            height: 1.3),
                      ),
                    ),

                  if (_error != null) ...[
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.fromLTRB(12, 8, 8, 8),
                      decoration: BoxDecoration(
                          color: Colors.red.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(8)),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: Text(_error!,
                                style: const TextStyle(
                                    color: Colors.red, fontSize: 12)),
                          ),
                          GestureDetector(
                            onTap: () => setState(() => _error = null),
                            child: const Icon(Icons.close,
                                size: 14, color: Colors.red),
                          ),
                        ],
                      ),
                    ),
                  ],
                ]),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(16),
              child: SizedBox(
                width: double.infinity,
                height: 52,
                child: ElevatedButton.icon(
                  onPressed:
                      _datasetsLoading ? null : _enterDrawArea,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _kAccent,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10)),
                  ),
                  icon: const Icon(Icons.play_arrow, size: 22),
                  label: const Text('Run via GEE',
                      style: TextStyle(
                          fontSize: 15, fontWeight: FontWeight.bold)),
                ),
              ),
            ),
          ]),
        ),
      ),

      Container(width: 1, color: Colors.white.withValues(alpha: 0.08)),

      // Right: map preview showing Dolan fire perimeter
      Expanded(
        child: Stack(children: [
          FlutterMap(
            options: const MapOptions(
              initialCenter: _kDolanCenter,
              initialZoom: 10.5,
            ),
            children: [
              TileLayer(
                urlTemplate:
                    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                userAgentPackageName: 'com.example.fire_webapp',
              ),
              PolygonLayer(polygons: _buildPerimeterFill()),
              PolylineLayer(polylines: _buildPerimeterPolylines()),
            ],
          ),
          // Loading / legend overlay
          Positioned(
            bottom: 12,
            left: 12,
            child: Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
              decoration: BoxDecoration(
                color: const Color(0xCC0A1628),
                borderRadius: BorderRadius.circular(6),
              ),
              child: _perimeterLoading
                  ? const Row(mainAxisSize: MainAxisSize.min, children: [
                      SizedBox(
                          width: 10,
                          height: 10,
                          child: CircularProgressIndicator(
                              strokeWidth: 1.5,
                              color: Colors.white54)),
                      SizedBox(width: 8),
                      Text('Loading fire perimeter...',
                          style: TextStyle(
                              color: Colors.white54, fontSize: 10)),
                    ])
                  : _perimeterGeoJson != null
                      ? Row(mainAxisSize: MainAxisSize.min, children: [
                          Container(
                              width: 14,
                              height: 3,
                              color: Colors.orangeAccent),
                          const SizedBox(width: 6),
                          const Text('Dolan Fire perimeter',
                              style: TextStyle(
                                  color: Colors.white70, fontSize: 10)),
                        ])
                      : const Text('Perimeter unavailable',
                          style: TextStyle(
                              color: Colors.white38, fontSize: 10)),
            ),
          ),
        ]),
      ),
    ]);
  }

  Widget _buildMetricCard(Map<String, dynamic> ds) {
    final id = ds['id'] as String;
    final label = ds['label'] as String;
    final fullName = ds['full_name'] as String;
    final description = ds['description'] as String;
    final available = ds['available'] as bool? ?? false;
    final isSelected = _selectedMetric == id;
    return GestureDetector(
      onTap: available
          ? () => setState(() => _selectedMetric = id)
          : null,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isSelected
              ? _kAccent.withValues(alpha: 0.10)
              : Colors.white.withValues(alpha: 0.04),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: isSelected
                ? _kAccent.withValues(alpha: 0.55)
                : Colors.white.withValues(alpha: 0.09),
            width: isSelected ? 1.5 : 1.0,
          ),
        ),
        child: Row(children: [
          Container(
            width: 16, height: 16,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(
                  color: isSelected ? _kAccent : Colors.white38, width: 2),
              color: isSelected ? _kAccent : Colors.transparent,
            ),
            child: isSelected
                ? const Icon(Icons.circle, color: Colors.white, size: 7)
                : null,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
              Row(children: [
                Text(label,
                    style: TextStyle(
                        color: available ? Colors.white : Colors.white38,
                        fontWeight: FontWeight.bold,
                        fontSize: 13)),
                const SizedBox(width: 6),
                Flexible(
                  child: Text(fullName,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                          color: available
                              ? Colors.white.withValues(alpha: 0.45)
                              : Colors.white24,
                          fontSize: 10)),
                ),
              ]),
              const SizedBox(height: 3),
              Text(description,
                  style: TextStyle(
                      color: available
                          ? Colors.white.withValues(alpha: 0.55)
                          : Colors.white24,
                      fontSize: 10,
                      height: 1.4)),
            ]),
          ),
        ]),
      ),
    );
  }

  // -----------------------------------------------------------------------
  // Draw area screen (primary analysis polygon selection)
  // -----------------------------------------------------------------------

  List<LatLng> _perimeterRingPoints(List<dynamic> ring) => ring
      .map((c) => LatLng((c[1] as num).toDouble(), (c[0] as num).toDouble()))
      .toList();

  List<List<dynamic>> _perimeterRings(Map<String, dynamic> feature) {
    final geomType = feature['geometry']?['type'] as String?;
    final coords = feature['geometry']?['coordinates'] as List?;
    if (coords == null) return [];
    if (geomType == 'Polygon') return [coords[0] as List<dynamic>];
    if (geomType == 'MultiPolygon') {
      return [
        for (final poly in coords) (poly as List)[0] as List<dynamic>
      ];
    }
    return [];
  }

  List<Polyline> _buildPerimeterPolylines() {
    if (_perimeterGeoJson == null) return [];
    final features = _perimeterGeoJson!['features'] as List? ?? [];
    return [
      for (final f in features)
        for (final ring in _perimeterRings(f as Map<String, dynamic>))
          Polyline(
            points: _perimeterRingPoints(ring),
            color: Colors.orangeAccent,
            strokeWidth: 3.5,
          ),
    ];
  }

  List<Polygon> _buildPerimeterFill() {
    if (_perimeterGeoJson == null) return [];
    final features = _perimeterGeoJson!['features'] as List? ?? [];
    return [
      for (final f in features)
        for (final ring in _perimeterRings(f as Map<String, dynamic>))
          Polygon(
            points: _perimeterRingPoints(ring),
            color: Colors.orangeAccent.withValues(alpha: 0.12),
            borderColor: Colors.transparent,
            borderStrokeWidth: 0,
          ),
    ];
  }

  Widget _buildDrawArea() {
    final hasEnough = _primaryPoints.length >= 3;
    return Stack(children: [
      // Map
      FlutterMap(
        mapController: _mapController,
        options: MapOptions(
          initialCenter: _kDolanCenter,
          initialZoom: 10,
          onTap: (_, latlng) =>
              setState(() => _primaryPoints.add(latlng)),
        ),
        children: [
          TileLayer(
            urlTemplate: _useSatellite
                ? 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
                : 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          ),
          // Dolan fire perimeter — fill + outline
          PolygonLayer(polygons: _buildPerimeterFill()),
          PolylineLayer(polylines: _buildPerimeterPolylines()),
          // Drawn polygon preview
          if (_primaryPoints.length >= 2)
            PolylineLayer(polylines: [
              Polyline(
                points: [..._primaryPoints, _primaryPoints.first],
                color: Colors.amberAccent,
                strokeWidth: 2,
              ),
            ]),
          // Vertex dots
          if (_primaryPoints.isNotEmpty)
            MarkerLayer(
              markers: _primaryPoints
                  .map((p) => Marker(
                        point: p,
                        width: 8,
                        height: 8,
                        child: Container(
                          decoration: const BoxDecoration(
                            color: Colors.amberAccent,
                            shape: BoxShape.circle,
                          ),
                        ),
                      ))
                  .toList(),
            ),
        ],
      ),

      // Instructions panel (top-left)
      Positioned(
        top: 12,
        left: 12,
        child: Material(
          color: const Color(0xCC0A1628),
          borderRadius: BorderRadius.circular(10),
          child: Padding(
            padding:
                const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('Select Analysis Area',
                      style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                          fontSize: 13)),
                  const SizedBox(height: 4),
                  Text(
                    'Tap the map to draw a polygon within the\n'
                    'Dolan Fire area (orange outline).\n'
                    'Minimum 3 points required.',
                    style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.6),
                        fontSize: 11,
                        height: 1.4),
                  ),
                  const SizedBox(height: 4),
                  Text('Points placed: ${_primaryPoints.length}',
                      style: const TextStyle(
                          color: Colors.amberAccent, fontSize: 11)),
                ]),
          ),
        ),
      ),

      // Toolbar (top-right)
      Positioned(
        top: 12,
        right: 12,
        child: Material(
          color: const Color(0xCC0A1628),
          borderRadius: BorderRadius.circular(10),
          child: Padding(
            padding:
                const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Row(mainAxisSize: MainAxisSize.min, children: [
                IconButton(
                  tooltip: 'Undo last point',
                  onPressed: _primaryPoints.isNotEmpty
                      ? () => setState(() => _primaryPoints.removeLast())
                      : null,
                  icon: Icon(Icons.undo,
                      color: _primaryPoints.isNotEmpty
                          ? Colors.white70
                          : Colors.white24,
                      size: 20),
                ),
                TextButton(
                  onPressed: hasEnough ? _confirmPrimaryArea : null,
                  child: Text('Run Analysis',
                      style: TextStyle(
                          color: hasEnough
                              ? Colors.amberAccent
                              : Colors.white24,
                          fontWeight: FontWeight.bold)),
                ),
                TextButton(
                  onPressed: () =>
                      setState(() => _screenState = _GeeScreenState.configure),
                  child: const Text('Back',
                      style: TextStyle(color: Colors.white54)),
                ),
              ]),
              // Area-too-large error
              if (_primaryDrawError != null)
                Container(
                  constraints: const BoxConstraints(maxWidth: 340),
                  margin:
                      const EdgeInsets.only(bottom: 6, left: 4, right: 4),
                  padding: const EdgeInsets.symmetric(
                      horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.red.shade900.withValues(alpha: 0.9),
                    borderRadius: BorderRadius.circular(7),
                  ),
                  child: Row(mainAxisSize: MainAxisSize.min, children: [
                    const Icon(Icons.warning_amber_rounded,
                        color: Colors.orangeAccent, size: 14),
                    const SizedBox(width: 6),
                    Flexible(
                      child: Text(_primaryDrawError!,
                          style: const TextStyle(
                              color: Colors.white, fontSize: 11)),
                    ),
                    const SizedBox(width: 6),
                    GestureDetector(
                      onTap: () =>
                          setState(() => _primaryDrawError = null),
                      child: const Icon(Icons.close,
                          color: Colors.white54, size: 13),
                    ),
                  ]),
                ),
            ]),
          ),
        ),
      ),

      // Satellite toggle
      Positioned(
        bottom: 16,
        right: 16,
        child: FloatingActionButton.small(
          onPressed: () => setState(() => _useSatellite = !_useSatellite),
          backgroundColor: const Color(0xCC0A1628),
          child: Icon(
              _useSatellite ? Icons.map_outlined : Icons.satellite_alt,
              color: Colors.white70,
              size: 18),
        ),
      ),
    ]);
  }

  // -----------------------------------------------------------------------
  // Analyzing screen
  // -----------------------------------------------------------------------

  Widget _buildAnalyzing() {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF0A1628), Color(0xFF0D2137)],
        ),
      ),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(children: [
            const SizedBox(height: 24),
            AnimatedBuilder(
              animation: _pulseAnim,
              builder: (context, child) =>
                  Opacity(opacity: _pulseAnim.value, child: child),
              child: SizedBox(
                width: 120, height: 120,
                child: Stack(alignment: Alignment.center, children: [
                  CircularProgressIndicator(
                    value: _progress / 100,
                    strokeWidth: 8,
                    backgroundColor: Colors.white.withValues(alpha: 0.1),
                    valueColor: const AlwaysStoppedAnimation<Color>(_kAccent),
                  ),
                  Text('$_progress%',
                      style: const TextStyle(
                          color: Colors.white,
                          fontSize: 24,
                          fontWeight: FontWeight.bold)),
                ]),
              ),
            ),
            const SizedBox(height: 16),
            const Text('GEE + WhiteboxTools Pipeline Running',
                style: TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            Text('Project: $_connectedProjectId',
                style: TextStyle(
                    color: _kAccent.withValues(alpha: 0.8), fontSize: 12)),
            const SizedBox(height: 8),
            Text(_stepMessage,
                textAlign: TextAlign.center,
                style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.7),
                    fontSize: 13)),
            const SizedBox(height: 24),
            Expanded(
              child: ListView.builder(
                itemCount: _kSteps.length,
                itemBuilder: (context, i) {
                  final stepNum = i + 1;
                  final isDone = stepNum < _currentStep;
                  final isCurrent = stepNum == _currentStep;
                  return AnimatedContainer(
                    duration: const Duration(milliseconds: 400),
                    margin: const EdgeInsets.only(bottom: 7),
                    padding: const EdgeInsets.symmetric(
                        horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(
                      color: isCurrent
                          ? _kAccent.withValues(alpha: 0.13)
                          : isDone
                              ? Colors.green.withValues(alpha: 0.07)
                              : Colors.white.withValues(alpha: 0.03),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: isCurrent
                            ? _kAccent.withValues(alpha: 0.45)
                            : isDone
                                ? Colors.green.withValues(alpha: 0.25)
                                : Colors.white.withValues(alpha: 0.06),
                      ),
                    ),
                    child: Row(children: [
                      SizedBox(
                        width: 26, height: 26,
                        child: isDone
                            ? const Icon(Icons.check_circle,
                                color: Colors.green, size: 20)
                            : isCurrent
                                ? AnimatedBuilder(
                                    animation: _pulseAnim,
                                    builder: (_, child) => Opacity(
                                        opacity: _pulseAnim.value,
                                        child: Icon(_kStepIcons[i],
                                            color: _kAccent, size: 20)))
                                : Icon(_kStepIcons[i],
                                    color: Colors.white.withValues(alpha: 0.22),
                                    size: 20),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text('$stepNum. ${_kSteps[i]}',
                            style: TextStyle(
                                color: isDone
                                    ? Colors.green.shade300
                                    : isCurrent
                                        ? Colors.white
                                        : Colors.white.withValues(alpha: 0.32),
                                fontSize: 12,
                                fontWeight: isCurrent
                                    ? FontWeight.bold
                                    : FontWeight.normal)),
                      ),
                      if (isCurrent)
                        const SizedBox(
                            width: 14, height: 14,
                            child: CircularProgressIndicator(
                                strokeWidth: 2, color: _kAccent)),
                    ]),
                  );
                },
              ),
            ),
          ]),
        ),
      ),
    );
  }

  // -----------------------------------------------------------------------
  // Results screen
  // -----------------------------------------------------------------------

  Widget _buildResults() {
    final hasZone = _zoneResults != null;
    return Stack(children: [
      FlutterMap(
        mapController: _mapController,
        options: MapOptions(
          initialCenter: _kDolanCenter,
          initialZoom: 11.0,
          onTap: (_, point) {
            if (_drawingZone) {
              setState(() => _drawPoints.add(point));
              return;
            }
            final hitList = hasZone
                ? _zoneResults!.features
                : (_results?.features ?? []);
            for (final feature in hitList) {
              if (_pointInPolygon(point, feature.rings[0])) {
                setState(() {
                  _selectedFeatureIndex =
                      _selectedFeatureIndex == feature.index
                          ? null
                          : feature.index;
                });
                return;
              }
            }
            setState(() => _selectedFeatureIndex = null);
          },
        ),
        children: [
          TileLayer(
            urlTemplate: _useSatellite
                ? 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
                : 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
            userAgentPackageName: 'com.example.fire_webapp',
          ),
          if (_perimeterGeoJson != null)
            PolygonLayer(polygons: _buildPerimeterPolygons()),
          if (_results != null)
            PolygonLayer(polygons: buildPolygons(
              features: _results!.features,
              selectedIndex: hasZone ? null : _selectedFeatureIndex,
              dimmed: hasZone,
              onTap: (i) {
                if (!hasZone) {
                  setState(() => _selectedFeatureIndex =
                      _selectedFeatureIndex == i ? null : i);
                }
              },
            )),
          if (hasZone)
            PolygonLayer(polygons: buildPolygons(
              features: _zoneResults!.features,
              selectedIndex: _selectedFeatureIndex,
              onTap: (i) => setState(() {
                _selectedFeatureIndex =
                    _selectedFeatureIndex == i ? null : i;
              }),
            )),
          if (_zoneBoundary.isNotEmpty)
            PolygonLayer(polygons: [
              Polygon(
                points: _zoneBoundary,
                color: Colors.white.withValues(alpha: 0.07),
                borderColor: Colors.white,
                borderStrokeWidth: 2.5,
              ),
            ]),
          if (_drawPoints.isNotEmpty)
            PolygonLayer(polygons: [
              Polygon(
                points: _drawPoints,
                color: Colors.amberAccent.withValues(alpha: 0.10),
                borderColor: Colors.amberAccent,
                borderStrokeWidth: 2.0,
              ),
            ]),
          if (_drawPoints.isNotEmpty)
            MarkerLayer(
              markers: _drawPoints
                  .map((p) => Marker(
                        point: p,
                        width: 10, height: 10,
                        child: Container(
                          decoration: const BoxDecoration(
                            color: Colors.amberAccent,
                            shape: BoxShape.circle,
                          ),
                        ),
                      ))
                  .toList(),
            ),
        ],
      ),

      // Status banner
      Positioned(
        top: 12, left: 12,
        right: _drawingZone ? 12 : 200,
        child: Material(
          color: const Color(0xCC0A1628),
          borderRadius: BorderRadius.circular(10),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
            child: Row(children: [
              Icon(
                _drawingZone ? Icons.draw : Icons.check_circle,
                color: _drawingZone ? Colors.amberAccent : _kAccent,
                size: 16,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  _drawingZone
                      ? 'Tap map to add vertices (${_drawPoints.length} points)'
                      : hasZone
                          ? '${_zoneResults!.features.length} zone basins  |  ${_results?.features.length ?? 0} full  |  Tap to inspect'
                          : '${_results?.features.length ?? 0} sub-basins  |  GEE DEM  |  Tap to inspect',
                  style: const TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.w600),
                ),
              ),
            ]),
          ),
        ),
      ),

      // Drawing toolbar
      if (_drawingZone)
        Positioned(
          top: 12, right: 12,
          child: Material(
            color: const Color(0xCC0A1628),
            borderRadius: BorderRadius.circular(10),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Row(mainAxisSize: MainAxisSize.min, children: [
                  IconButton(
                    tooltip: 'Undo last point',
                    onPressed: _drawPoints.isNotEmpty ? _undoPoint : null,
                    icon: Icon(Icons.undo,
                        color: _drawPoints.isNotEmpty
                            ? Colors.white70
                            : Colors.white24,
                        size: 20),
                  ),
                  TextButton(
                    onPressed: _drawPoints.length >= 3 ? _confirmZone : null,
                    child: Text('Confirm',
                        style: TextStyle(
                            color: _drawPoints.length >= 3
                                ? Colors.amberAccent
                                : Colors.white24,
                            fontWeight: FontWeight.bold)),
                  ),
                  TextButton(
                    onPressed: _cancelDrawing,
                    child: const Text('Cancel',
                        style: TextStyle(color: Colors.white54)),
                  ),
                ]),
                // Area-too-large error — shown inline, user stays in drawing mode
                if (_zoneError != null && _drawingZone)
                  Container(
                    constraints: const BoxConstraints(maxWidth: 340),
                    margin: const EdgeInsets.only(bottom: 6, left: 4, right: 4),
                    padding: const EdgeInsets.symmetric(
                        horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: Colors.red.shade900.withValues(alpha: 0.9),
                      borderRadius: BorderRadius.circular(7),
                    ),
                    child: Row(mainAxisSize: MainAxisSize.min, children: [
                      const Icon(Icons.warning_amber_rounded,
                          color: Colors.orangeAccent, size: 14),
                      const SizedBox(width: 6),
                      Flexible(
                        child: Text(_zoneError!,
                            style: const TextStyle(
                                color: Colors.white, fontSize: 11)),
                      ),
                      const SizedBox(width: 6),
                      GestureDetector(
                        onTap: () => setState(() => _zoneError = null),
                        child: const Icon(Icons.close,
                            color: Colors.white54, size: 13),
                      ),
                    ]),
                  ),
              ]),
            ),
          ),
        ),

      // Zone running progress
      if (_zoneRunning)
        Positioned(
          top: 56, left: 12, right: 12,
          child: Material(
            color: const Color(0xCC0A1628),
            borderRadius: BorderRadius.circular(10),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Row(children: [
                  const SizedBox(
                    width: 15, height: 15,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.amberAccent),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Zone (GEE) — Step $_zoneStep/10  ($_zoneProgress%)',
                      style: const TextStyle(
                          color: Colors.amberAccent,
                          fontSize: 12,
                          fontWeight: FontWeight.bold),
                    ),
                  ),
                ]),
                const SizedBox(height: 8),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: _zoneProgress / 100,
                    backgroundColor: Colors.white12,
                    valueColor: const AlwaysStoppedAnimation(Colors.amberAccent),
                    minHeight: 5,
                  ),
                ),
                const SizedBox(height: 5),
                Text(_zoneMessage,
                    style: const TextStyle(
                        color: Colors.white54, fontSize: 11)),
              ]),
            ),
          ),
        ),

      // Zone error
      if (_zoneError != null)
        Positioned(
          top: 56, left: 12, right: 12,
          child: Material(
            color: Colors.red.shade900.withValues(alpha: 0.92),
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.symmetric(
                  horizontal: 14, vertical: 8),
              child: Row(children: [
                const Icon(Icons.error_outline,
                    color: Colors.white70, size: 15),
                const SizedBox(width: 8),
                Expanded(
                    child: Text(_zoneError!,
                        style: const TextStyle(
                            color: Colors.white, fontSize: 11))),
                GestureDetector(
                  onTap: () => setState(() => _zoneError = null),
                  child: const Icon(Icons.close,
                      color: Colors.white54, size: 15),
                ),
              ]),
            ),
          ),
        ),

      // Hazard legend
      if (!_drawingZone)
        Positioned(top: 56, right: 12, child: _buildHazardLegend()),

      // Attribute panel
      if (!_drawingZone && !_zoneRunning) ...[
        if (hasZone &&
            _selectedFeatureIndex != null &&
            _selectedFeatureIndex! < _zoneResults!.features.length)
          Positioned(
            left: 12, top: 56, bottom: 16,
            child: AttributePanel(
              feature: _zoneResults!.features[_selectedFeatureIndex!],
              onClose: () =>
                  setState(() => _selectedFeatureIndex = null),
            ),
          )
        else if (!hasZone &&
            _results != null &&
            _selectedFeatureIndex != null &&
            _selectedFeatureIndex! < _results!.features.length)
          Positioned(
            left: 12, top: 56, bottom: 16,
            child: AttributePanel(
              feature: _results!.features[_selectedFeatureIndex!],
              onClose: () =>
                  setState(() => _selectedFeatureIndex = null),
            ),
          ),
      ],
    ]);
  }

  // -----------------------------------------------------------------------
  // Shared helpers
  // -----------------------------------------------------------------------

  List<Polygon> _buildPerimeterPolygons() {
    if (_perimeterGeoJson == null) return [];
    final polygons = <Polygon>[];
    final features = _perimeterGeoJson!['features'] as List? ?? [];
    for (final f in features) {
      final geomType = f['geometry']?['type'] as String?;
      final coords = f['geometry']?['coordinates'] as List?;
      if (coords == null) continue;
      List<List<dynamic>> rings = [];
      if (geomType == 'Polygon') {
        rings = [coords[0] as List<dynamic>];
      } else if (geomType == 'MultiPolygon') {
        for (final poly in coords) {
          rings.add((poly as List)[0] as List<dynamic>);
        }
      }
      for (final ring in rings) {
        polygons.add(Polygon(
          points: ring
              .map((c) =>
                  LatLng((c[1] as num).toDouble(), (c[0] as num).toDouble()))
              .toList(),
          color: Colors.transparent,
          borderColor: _kAccent.withValues(alpha: 0.7),
          borderStrokeWidth: 2.5,
        ));
      }
    }
    return polygons;
  }

  Widget _buildHazardLegend() {
    const items = [
      (Colors.red, 'H3 — High'),
      (Colors.orange, 'H2 — Moderate'),
      (Colors.yellow, 'H1 — Low'),
      (Colors.green, 'H0 — Negligible'),
    ];
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xCC0A1628),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
      ),
      child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: items.map((item) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 5),
              child: Row(children: [
                Container(
                  width: 12, height: 12,
                  decoration: BoxDecoration(
                    color: item.$1.withValues(alpha: 0.8),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const SizedBox(width: 7),
                Text(item.$2,
                    style: const TextStyle(
                        color: Colors.white70, fontSize: 11)),
              ]),
            );
          }).toList()),
    );
  }
}
