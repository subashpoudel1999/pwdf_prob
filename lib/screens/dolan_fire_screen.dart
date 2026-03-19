import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:http/http.dart' as http;

import '../config/app_config.dart';
import '../utils/geojson_parser.dart';
import '../widgets/attribute_panel.dart';

const _kSteps = [
  'Loading fire perimeter, DEM, and burn severity rasters...',
  'Reprojecting to UTM Zone 10N (projected CRS for Big Sur area)...',
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
  Icons.transform,
  Icons.terrain,
  Icons.water,
  Icons.trending_up,
  Icons.account_tree_outlined,
  Icons.grain,
  Icons.show_chart,
  Icons.science_outlined,
  Icons.file_download_done,
];

const _kAccent = Color(0xFF00BFA5);

class DolanFireScreen extends StatefulWidget {
  const DolanFireScreen({super.key});

  @override
  State<DolanFireScreen> createState() => _DolanFireScreenState();
}

enum _ScreenState { configure, analyzing, results }

class _DolanFireScreenState extends State<DolanFireScreen>
    with TickerProviderStateMixin {
  static const String _backendUrl = AppConfig.backendUrl;
  static const LatLng _dolanCenter = LatLng(36.06, -121.40);

  final MapController _mapController = MapController();
  final MapController _previewMapController = MapController();

  _ScreenState _screenState = _ScreenState.configure;

  // --- Configure state ---
  String _selectedMetric = 'dnbr'; // used as MODEL INPUT
  String _previewLayer = 'dnbr';   // used for MAP PREVIEW (can include 'dem')
  List<Map<String, dynamic>> _datasets = [];
  bool _datasetsLoading = true;
  Uint8List? _previewBytes;
  Map<String, dynamic>? _previewBounds;
  bool _previewLoading = false;
  Map<String, dynamic>? _perimeterGeoJson; // loaded on init for preview map

  // --- Analyze state ---
  String? _jobId;
  int _currentStep = 0;
  String _stepMessage = '';
  int _progress = 0;
  String? _error;

  // --- Results state ---
  ParsedGeoJson? _results;
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
    _loadDatasetsAndPerimeter();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _zonePollTimer?.cancel();
    _pulseController.dispose();
    super.dispose();
  }

  // -------------------------------------------------------------------------
  // Data loading helpers
  // -------------------------------------------------------------------------

  Future<void> _loadDatasetsAndPerimeter() async {
    // Load available inputs metadata and fire perimeter in parallel
    await Future.wait([_loadAvailableInputs(), _loadPerimeter()]);
    if (mounted && _datasets.isNotEmpty) {
      _fetchPreview(_previewLayer);
    }
  }

  Future<void> _loadAvailableInputs() async {
    try {
      final resp =
          await http.get(Uri.parse('$_backendUrl/dolan/available-inputs'));
      if (resp.statusCode == 200) {
        final body = json.decode(resp.body);
        if (mounted) {
          setState(() {
            _datasets = List<Map<String, dynamic>>.from(body['datasets']);
            _datasetsLoading = false;
          });
        }
      }
    } catch (_) {
      if (mounted) setState(() => _datasetsLoading = false);
    }
  }

  Future<void> _loadPerimeter() async {
    try {
      final resp = await http.get(Uri.parse('$_backendUrl/dolan/perimeter'));
      if (resp.statusCode == 200 && mounted) {
        setState(() => _perimeterGeoJson = json.decode(resp.body));
      }
    } catch (_) {}
  }

  Future<void> _fetchPreview(String metric) async {
    if (!mounted) return;
    setState(() {
      _previewLoading = true;
      _previewBytes = null;
      _previewBounds = null;
    });
    try {
      final resp =
          await http.get(Uri.parse('$_backendUrl/dolan/preview/$metric'));
      if (resp.statusCode == 200 && mounted) {
        final body = json.decode(resp.body);
        final bytes = base64Decode(body['image_base64'] as String);
        setState(() {
          _previewBytes = bytes;
          _previewBounds = body['bounds'] as Map<String, dynamic>;
          _previewLoading = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _previewLoading = false);
    }
  }

  // -------------------------------------------------------------------------
  // Analysis flow
  // -------------------------------------------------------------------------

  Future<void> _startAnalysis() async {
    setState(() {
      _screenState = _ScreenState.analyzing;
      _currentStep = 0;
      _stepMessage = 'Initialising analysis pipeline...';
      _progress = 0;
      _error = null;
    });
    try {
      final uri = Uri.parse(
          '$_backendUrl/dolan/analyze?burn_metric=$_selectedMetric');
      final resp =
          await http.post(uri, headers: {'Content-Type': 'application/json'});
      if (resp.statusCode != 200) throw Exception('Backend error: ${resp.body}');
      final body = json.decode(resp.body);
      _jobId = body['job_id'] as String;
      _pollTimer?.cancel();
      _pollTimer =
          Timer.periodic(const Duration(milliseconds: 1200), (_) => _poll());
    } catch (e) {
      setState(() {
        _error = 'Failed to start: $e';
        _screenState = _ScreenState.configure;
      });
    }
  }

  Future<void> _poll() async {
    if (_jobId == null) return;
    try {
      final resp =
          await http.get(Uri.parse('$_backendUrl/dolan/status/$_jobId'));
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
          _currentStep = 10;
          _progress = 100;
          _stepMessage = msg;
        });
        await _loadResults();
      } else if (status == 'error') {
        _pollTimer?.cancel();
        setState(() {
          _error = data['error'] as String? ?? 'Unknown error';
          _screenState = _ScreenState.configure;
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
          await http.get(Uri.parse('$_backendUrl/dolan/results'));
      final perimResp =
          await http.get(Uri.parse('$_backendUrl/dolan/perimeter'));
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
        _screenState = _ScreenState.configure;
      });
    }
  }

  // -------------------------------------------------------------------------
  // Zone analysis
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

  void _cancelDrawing() => setState(() {
        _drawingZone = false;
        _drawPoints = [];
      });

  void _undoPoint() {
    if (_drawPoints.isNotEmpty) setState(() => _drawPoints.removeLast());
  }

  Future<void> _confirmZone() async {
    if (_drawPoints.length < 3) return;
    final pts = List<LatLng>.from(_drawPoints)..add(_drawPoints.first); // close ring
    setState(() {
      _drawingZone = false;
      _drawPoints = [];
      _zoneBoundary = pts;
      _zoneRunning = true;
      _zoneStep = 0;
      _zoneProgress = 0;
      _zoneMessage = 'Submitting zone...';
      _zoneError = null;
      _zoneResults = null;
    });

    final coords = pts.map((p) => [p.longitude, p.latitude]).toList();
    final polygon = {'type': 'Polygon', 'coordinates': [coords]};
    try {
      final resp = await http.post(
        Uri.parse('$_backendUrl/dolan/analyze-zone'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'polygon': polygon}),
      );
      if (resp.statusCode != 200) throw Exception(resp.body);
      final body = json.decode(resp.body);
      _zoneJobId = body['job_id'] as String;
      _zonePollTimer?.cancel();
      _zonePollTimer =
          Timer.periodic(const Duration(milliseconds: 1200), (_) => _pollZone());
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
      final resp =
          await http.get(Uri.parse('$_backendUrl/dolan/status/$_zoneJobId'));
      if (resp.statusCode != 200) return;
      final data = json.decode(resp.body);
      final status = data['status'] as String? ?? 'running';
      if (!mounted) return;
      if (status == 'completed') {
        _zonePollTimer?.cancel();
        setState(() {
          _zoneStep = 10;
          _zoneProgress = 100;
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
          .get(Uri.parse('$_backendUrl/dolan/zone-results/$_zoneJobId'));
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

  // -------------------------------------------------------------------------
  // Build
  // -------------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D1B2A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0D2137),
        foregroundColor: Colors.white,
        title: const Row(children: [
          Icon(Icons.local_fire_department, color: _kAccent),
          SizedBox(width: 10),
          Text('Dolan Fire',
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
            IconButton(
              tooltip:
                  _useSatellite ? 'Switch to Street Map' : 'Switch to Satellite',
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
                _screenState = _ScreenState.configure;
                _selectedFeatureIndex = null;
              }),
              icon: const Icon(Icons.tune, color: _kAccent),
              label: const Text('Re-configure',
                  style: TextStyle(color: _kAccent)),
            ),
          ],
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    switch (_screenState) {
      case _ScreenState.configure:
        return _buildConfigure();
      case _ScreenState.analyzing:
        return _buildAnalyzing();
      case _ScreenState.results:
        return _buildResults();
    }
  }

  // -------------------------------------------------------------------------
  // Configure screen (side-by-side)
  // -------------------------------------------------------------------------

  Widget _buildConfigure() {
    return Row(
      children: [
        // Left panel: dataset selector
        SizedBox(
          width: 320,
          child: Container(
            color: const Color(0xFF0D1B2A),
            child: Column(
              children: [
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Title
                        const Text('Configure Analysis',
                            style: TextStyle(
                                color: Colors.white,
                                fontSize: 18,
                                fontWeight: FontWeight.bold)),
                        const SizedBox(height: 4),
                        Text('Select the burn severity dataset to use as input.',
                            style: TextStyle(
                                color: Colors.white.withValues(alpha: 0.5),
                                fontSize: 12)),

                        const SizedBox(height: 20),

                        // Dataset selector cards
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
                            child: CircularProgressIndicator(color: _kAccent),
                          ))
                        else
                          ..._datasets.map((ds) => _buildDatasetCard(ds)),

                        const SizedBox(height: 20),

                        // Map preview layer selector (burn metrics + DEM)
                        const Text('Map Preview Layer',
                            style: TextStyle(
                                color: Colors.white70,
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                letterSpacing: 0.8)),
                        const SizedBox(height: 8),
                        _buildPreviewLayerChips(),

                        const SizedBox(height: 20),

                        // Dynamic legend for selected PREVIEW layer
                        _buildSelectedLegend(),

                        if (_error != null) ...[
                          const SizedBox(height: 16),
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                                color: Colors.red.withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(8)),
                            child: Text(_error!,
                                style: const TextStyle(
                                    color: Colors.red, fontSize: 12)),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),

                // Run button at bottom
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(children: [
                    SizedBox(
                      width: double.infinity,
                      height: 52,
                      child: ElevatedButton.icon(
                        onPressed: _datasetsLoading ? null : _startAnalysis,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: _kAccent,
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(10)),
                        ),
                        icon: const Icon(Icons.play_arrow, size: 24),
                        label: Text(
                          'Run Analysis with ${_selectedDatasetLabel()}',
                          style: const TextStyle(
                              fontSize: 15, fontWeight: FontWeight.bold),
                        ),
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text('Estimated time: 60–120 seconds',
                        style: TextStyle(
                            color: Colors.white.withValues(alpha: 0.35),
                            fontSize: 11)),
                  ]),
                ),
              ],
            ),
          ),
        ),

        // Divider
        Container(width: 1, color: Colors.white.withValues(alpha: 0.08)),

        // Right panel: preview map
        Expanded(child: _buildPreviewMap()),
      ],
    );
  }

  Widget _buildDatasetCard(Map<String, dynamic> ds) {
    final id = ds['id'] as String;
    final label = ds['label'] as String;
    final fullName = ds['full_name'] as String;
    final description = ds['description'] as String;
    final available = ds['available'] as bool? ?? false;
    final isSelected = _selectedMetric == id;

    return GestureDetector(
      onTap: available
          ? () {
              if (_selectedMetric != id) {
                setState(() {
                  _selectedMetric = id;
                  _previewLayer = id;
                });
                _fetchPreview(id);
              }
            }
          : null,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: isSelected
              ? _kAccent.withValues(alpha: 0.12)
              : Colors.white.withValues(alpha: 0.04),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: isSelected
                ? _kAccent.withValues(alpha: 0.6)
                : Colors.white.withValues(alpha: 0.1),
            width: isSelected ? 1.5 : 1.0,
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Radio indicator
            Container(
              width: 18,
              height: 18,
              margin: const EdgeInsets.only(top: 2),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(
                    color: isSelected ? _kAccent : Colors.white38, width: 2),
                color: isSelected ? _kAccent : Colors.transparent,
              ),
              child: isSelected
                  ? const Icon(Icons.circle, color: Colors.white, size: 8)
                  : null,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    Text(label,
                        style: TextStyle(
                            color: available ? Colors.white : Colors.white38,
                            fontWeight: FontWeight.bold,
                            fontSize: 14)),
                    const SizedBox(width: 8),
                    Flexible(
                      child: Text(fullName,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                              color: available
                                  ? Colors.white.withValues(alpha: 0.5)
                                  : Colors.white24,
                              fontSize: 11)),
                    ),
                  ]),
                  const SizedBox(height: 4),
                  Text(description,
                      style: TextStyle(
                          color: available
                              ? Colors.white.withValues(alpha: 0.6)
                              : Colors.white24,
                          fontSize: 11,
                          height: 1.4)),
                  if (!available) ...[
                    const SizedBox(height: 4),
                    const Text('File not available',
                        style: TextStyle(color: Colors.red, fontSize: 10)),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPreviewLayerChips() {
    final layers = [
      ..._datasets.map((d) => {'id': d['id'], 'label': d['label'], 'available': d['available']}),
      {'id': 'dem', 'label': 'DEM', 'available': true},
    ];
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: layers.map((layer) {
        final id = layer['id'] as String;
        final label = layer['label'] as String;
        final available = layer['available'] as bool? ?? true;
        final isSelected = _previewLayer == id;
        return GestureDetector(
          onTap: available
              ? () {
                  if (_previewLayer != id) {
                    setState(() => _previewLayer = id);
                    _fetchPreview(id);
                  }
                }
              : null,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 180),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
            decoration: BoxDecoration(
              color: isSelected
                  ? _kAccent.withValues(alpha: 0.2)
                  : Colors.white.withValues(alpha: 0.06),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: isSelected
                    ? _kAccent
                    : Colors.white.withValues(alpha: 0.15),
                width: isSelected ? 1.5 : 1.0,
              ),
            ),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(
                id == 'dem' ? Icons.terrain : Icons.local_fire_department,
                size: 12,
                color: isSelected ? _kAccent : Colors.white54,
              ),
              const SizedBox(width: 5),
              Text(label,
                  style: TextStyle(
                      color: isSelected ? _kAccent : Colors.white54,
                      fontSize: 12,
                      fontWeight:
                          isSelected ? FontWeight.bold : FontWeight.normal)),
            ]),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildSelectedLegend() {
    // Show DEM legend when DEM preview is active
    if (_previewLayer == 'dem') {
      return Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.05),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: Colors.white.withValues(alpha: 0.1)),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Row(children: [
            Icon(Icons.terrain, color: _kAccent, size: 14),
            SizedBox(width: 6),
            Text('DEM — Terrain Elevation',
                style: TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.bold)),
          ]),
          const SizedBox(height: 10),
          // Terrain gradient bar
          Container(
            height: 14,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(4),
              gradient: const LinearGradient(colors: [
                Color(0xFF22754C), // low — dark green
                Color(0xFF9ABF64), // mid — yellow-green
                Color(0xFFCDA25F), // upper — tan
                Color(0xFFAF875A), // high — brown
                Color(0xFFE6E6E6), // peak — light gray
              ]),
            ),
          ),
          const SizedBox(height: 6),
          const Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Low elev.', style: TextStyle(color: Colors.white54, fontSize: 10)),
              Text('High elev.', style: TextStyle(color: Colors.white54, fontSize: 10)),
            ],
          ),
          const SizedBox(height: 8),
          Text('3DEP 10 m resolution — visualization only, not used as model input',
              style: TextStyle(color: Colors.white.withValues(alpha: 0.35), fontSize: 10)),
        ]),
      );
    }

    final ds = _datasets.where((d) => d['id'] == _previewLayer).firstOrNull
        ?? _datasets.where((d) => d['id'] == _selectedMetric).firstOrNull;
    if (ds == null) return const SizedBox.shrink();

    final legend = (ds['legend'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    final colormap = ds['colormap'] as String? ?? 'continuous';

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.white.withValues(alpha: 0.1)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.palette_outlined, color: _kAccent, size: 14),
          const SizedBox(width: 6),
          Text('${ds['label']} Legend',
              style: const TextStyle(
                  color: Colors.white,
                  fontSize: 12,
                  fontWeight: FontWeight.bold)),
        ]),
        const SizedBox(height: 10),

        if (colormap == 'continuous') ...[
          // Gradient bar
          _buildGradientBar(),
          const SizedBox(height: 6),
        ],

        // Legend rows
        ...legend.map((item) => Padding(
              padding: const EdgeInsets.only(bottom: 5),
              child: Row(children: [
                Container(
                  width: 14,
                  height: 14,
                  decoration: BoxDecoration(
                    color: _hexColor(item['color'] as String),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(item['label'] as String,
                      style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.75),
                          fontSize: 11)),
                ),
              ]),
            )),
      ]),
    );
  }

  Widget _buildGradientBar() {
    // Green → Yellow → Red gradient for dNBR/rdNBR
    return Container(
      height: 14,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(4),
        gradient: const LinearGradient(colors: [
          Color(0xFF1a9641), // green (low/unburned)
          Color(0xFFa6d96a),
          Color(0xFFffffc0), // yellow
          Color(0xFFfdae61),
          Color(0xFFd7191c), // red (high severity)
        ]),
      ),
    );
  }

  Widget _buildPreviewMap() {
    final hasPreview = _previewBytes != null && _previewBounds != null;

    return Stack(children: [
      FlutterMap(
        mapController: _previewMapController,
        options: MapOptions(
          initialCenter: _dolanCenter,
          initialZoom: 10.5,
        ),
        children: [
          TileLayer(
            urlTemplate:
                'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            userAgentPackageName: 'com.example.fire_webapp',
          ),
          // Raster overlay
          if (hasPreview)
            OverlayImageLayer(overlayImages: [
              OverlayImage(
                bounds: LatLngBounds(
                  LatLng((_previewBounds!['south'] as num).toDouble(),
                      (_previewBounds!['west'] as num).toDouble()),
                  LatLng((_previewBounds!['north'] as num).toDouble(),
                      (_previewBounds!['east'] as num).toDouble()),
                ),
                imageProvider: MemoryImage(_previewBytes!),
                opacity: 0.80,
              ),
            ]),
          // Perimeter outline
          if (_perimeterGeoJson != null)
            PolygonLayer(polygons: _buildPerimeterPolygons()),
        ],
      ),

      // Loading spinner over map
      if (_previewLoading)
        const Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(color: _kAccent),
              SizedBox(height: 12),
              Text('Loading raster preview...',
                  style: TextStyle(color: Colors.white70)),
            ],
          ),
        ),

      // Map label
      Positioned(
        bottom: 12,
        left: 12,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: const Color(0xCC0D1B2A),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(
            hasPreview
                ? '${_selectedDatasetLabel()} preview — select a dataset to update'
                : 'Map preview — select a dataset to see it here',
            style: const TextStyle(color: Colors.white70, fontSize: 11),
          ),
        ),
      ),
    ]);
  }

  // -------------------------------------------------------------------------
  // Analyzing screen
  // -------------------------------------------------------------------------

  Widget _buildAnalyzing() {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF0D1B2A), Color(0xFF0D2137)],
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
                width: 120,
                height: 120,
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
            const Text('WhiteboxTools Analysis Running',
                style: TextStyle(
                    color: Colors.white,
                    fontSize: 20,
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            Text('Burn metric: ${_selectedDatasetLabel()}',
                style: TextStyle(
                    color: _kAccent.withValues(alpha: 0.8), fontSize: 13)),
            const SizedBox(height: 8),
            Text(_stepMessage,
                textAlign: TextAlign.center,
                style:
                    TextStyle(color: Colors.white.withValues(alpha: 0.7), fontSize: 14)),
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
                    margin: const EdgeInsets.only(bottom: 8),
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(
                      color: isCurrent
                          ? _kAccent.withValues(alpha: 0.15)
                          : isDone
                              ? Colors.green.withValues(alpha: 0.08)
                              : Colors.white.withValues(alpha: 0.03),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: isCurrent
                            ? _kAccent.withValues(alpha: 0.5)
                            : isDone
                                ? Colors.green.withValues(alpha: 0.3)
                                : Colors.white.withValues(alpha: 0.06),
                      ),
                    ),
                    child: Row(children: [
                      SizedBox(
                        width: 28,
                        height: 28,
                        child: isDone
                            ? const Icon(Icons.check_circle,
                                color: Colors.green, size: 22)
                            : isCurrent
                                ? AnimatedBuilder(
                                    animation: _pulseAnim,
                                    builder: (context, child) => Opacity(
                                        opacity: _pulseAnim.value,
                                        child: Icon(_kStepIcons[i],
                                            color: _kAccent, size: 22)))
                                : Icon(_kStepIcons[i],
                                    color: Colors.white.withValues(alpha: 0.25),
                                    size: 22),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text('$stepNum. ${_kSteps[i]}',
                            style: TextStyle(
                                color: isDone
                                    ? Colors.green.shade300
                                    : isCurrent
                                        ? Colors.white
                                        : Colors.white.withValues(alpha: 0.35),
                                fontSize: 13,
                                fontWeight: isCurrent
                                    ? FontWeight.bold
                                    : FontWeight.normal)),
                      ),
                      if (isCurrent)
                        const SizedBox(
                            width: 14,
                            height: 14,
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

  // -------------------------------------------------------------------------
  // Results screen
  // -------------------------------------------------------------------------

  Widget _buildResults() {
    final hasZone = _zoneResults != null;
    return Stack(children: [
      FlutterMap(
        mapController: _mapController,
        options: MapOptions(
          initialCenter: _dolanCenter,
          initialZoom: 11.0,
          onTap: (tapPosition, point) {
            // Drawing mode: add vertex
            if (_drawingZone) {
              setState(() => _drawPoints.add(point));
              return;
            }
            // Zone results mode: tap zone basins first, then full basins
            final hitList = hasZone ? _zoneResults!.features : (_results?.features ?? []);
            for (final feature in hitList) {
              if (_pointInPolygon(point, feature.rings[0])) {
                setState(() {
                  _selectedFeatureIndex =
                      _selectedFeatureIndex == feature.index ? null : feature.index;
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

          // Full basins: dimmed when zone results exist, normal otherwise
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

          // Zone results at full opacity
          if (hasZone)
            PolygonLayer(polygons: buildPolygons(
              features: _zoneResults!.features,
              selectedIndex: _selectedFeatureIndex,
              onTap: (i) => setState(() {
                _selectedFeatureIndex = _selectedFeatureIndex == i ? null : i;
              }),
            )),

          // Zone boundary outline (white)
          if (_zoneBoundary.isNotEmpty)
            PolygonLayer(polygons: [
              Polygon(
                points: _zoneBoundary,
                color: Colors.white.withValues(alpha: 0.08),
                borderColor: Colors.white,
                borderStrokeWidth: 2.5,
              ),
            ]),

          // Drawing polygon (in progress)
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
                        width: 10,
                        height: 10,
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
        top: 12,
        left: 12,
        right: _drawingZone ? 12 : 200,
        child: Material(
          color: const Color(0xCC0D1B2A),
          borderRadius: BorderRadius.circular(10),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            child: Row(children: [
              Icon(
                _drawingZone ? Icons.draw : Icons.check_circle,
                color: _drawingZone ? Colors.amberAccent : _kAccent,
                size: 18,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  _drawingZone
                      ? 'Tap map to add vertices (${_drawPoints.length} points)'
                      : hasZone
                          ? '${_zoneResults!.features.length} zone sub-basins  |  ${_results?.features.length ?? 0} full  |  Tap to inspect'
                          : '${_results?.features.length ?? 0} sub-basins  |  ${_selectedDatasetLabel()}  |  Tap to inspect',
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
          top: 12,
          right: 12,
          child: Material(
            color: const Color(0xCC0D1B2A),
            borderRadius: BorderRadius.circular(10),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
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
                  child: Text(
                    'Confirm',
                    style: TextStyle(
                        color: _drawPoints.length >= 3
                            ? Colors.amberAccent
                            : Colors.white24,
                        fontWeight: FontWeight.bold),
                  ),
                ),
                TextButton(
                  onPressed: _cancelDrawing,
                  child: const Text('Cancel',
                      style: TextStyle(color: Colors.white54)),
                ),
              ]),
            ),
          ),
        ),

      // Zone running progress bar
      if (_zoneRunning)
        Positioned(
          top: 60,
          left: 12,
          right: 12,
          child: Material(
            color: const Color(0xCC0D1B2A),
            borderRadius: BorderRadius.circular(10),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Row(children: [
                  const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.amberAccent),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Zone analysis running — Step $_zoneStep/10  ($_zoneProgress%)',
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
                    valueColor:
                        const AlwaysStoppedAnimation(Colors.amberAccent),
                    minHeight: 6,
                  ),
                ),
                const SizedBox(height: 6),
                Text(_zoneMessage,
                    style:
                        const TextStyle(color: Colors.white54, fontSize: 11)),
              ]),
            ),
          ),
        ),

      // Zone error
      if (_zoneError != null)
        Positioned(
          top: 60,
          left: 12,
          right: 12,
          child: Material(
            color: Colors.red.shade900.withValues(alpha: 0.92),
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              child: Row(children: [
                const Icon(Icons.error_outline, color: Colors.white70, size: 16),
                const SizedBox(width: 8),
                Expanded(
                    child: Text(_zoneError!,
                        style:
                            const TextStyle(color: Colors.white, fontSize: 11))),
                GestureDetector(
                  onTap: () => setState(() => _zoneError = null),
                  child: const Icon(Icons.close, color: Colors.white54, size: 16),
                ),
              ]),
            ),
          ),
        ),

      // Legend (hide during drawing to save space)
      if (!_drawingZone)
        Positioned(top: 60, right: 12, child: _buildHazardLegend()),

      // Attribute panel — shows zone or full basin
      if (!_drawingZone && !_zoneRunning) ...[
        if (hasZone &&
            _selectedFeatureIndex != null &&
            _selectedFeatureIndex! < _zoneResults!.features.length)
          Positioned(
            left: 12,
            top: 60,
            bottom: 16,
            child: AttributePanel(
              feature: _zoneResults!.features[_selectedFeatureIndex!],
              onClose: () => setState(() => _selectedFeatureIndex = null),
            ),
          )
        else if (!hasZone &&
            _results != null &&
            _selectedFeatureIndex != null &&
            _selectedFeatureIndex! < _results!.features.length)
          Positioned(
            left: 12,
            top: 60,
            bottom: 16,
            child: AttributePanel(
              feature: _results!.features[_selectedFeatureIndex!],
              onClose: () => setState(() => _selectedFeatureIndex = null),
            ),
          ),
      ],
    ]);
  }

  // -------------------------------------------------------------------------
  // Shared helpers
  // -------------------------------------------------------------------------

  String _selectedDatasetLabel() {
    final ds = _datasets.where((d) => d['id'] == _selectedMetric).firstOrNull;
    return ds != null ? ds['label'] as String : _selectedMetric.toUpperCase();
  }

  Color _hexColor(String hex) {
    final h = hex.replaceFirst('#', '');
    return Color(int.parse('FF$h', radix: 16));
  }

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
        final points = ring
            .map((c) =>
                LatLng((c[1] as num).toDouble(), (c[0] as num).toDouble()))
            .toList();
        polygons.add(Polygon(
          points: points,
          color: Colors.transparent,
          borderColor: _kAccent.withValues(alpha: 0.8),
          borderStrokeWidth: 2.5,
        ));
      }
    }
    return polygons;
  }

  Widget _buildHazardLegend() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xCC0D1B2A),
        borderRadius: BorderRadius.circular(10),
        border:
            Border.all(color: Colors.white.withValues(alpha: 0.15)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Debris-flow hazard',
            style: TextStyle(
                color: Colors.white,
                fontSize: 11,
                fontWeight: FontWeight.bold)),
        const SizedBox(height: 6),
        _legendRow(Colors.red, 'High (P ≥ 0.6, V ≥ 1000 m³)'),
        _legendRow(Colors.orange, 'Moderate (P ≥ 0.4 or V ≥ 500 m³)'),
        _legendRow(Colors.yellow, 'Low (P ≥ 0.2 or V ≥ 100 m³)'),
        _legendRow(Colors.green, 'Very Low'),
        const SizedBox(height: 4),
        Text('Model: Staley (2017) M1, I15=40 mm/hr\nInput: ${_selectedDatasetLabel()}',
            style: const TextStyle(color: Colors.white54, fontSize: 9)),
      ]),
    );
  }

  Widget _legendRow(Color color, String label) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Container(
            width: 14,
            height: 14,
            decoration: BoxDecoration(
                color: color, borderRadius: BorderRadius.circular(2))),
        const SizedBox(width: 6),
        Text(label,
            style: const TextStyle(color: Colors.white70, fontSize: 10)),
      ]),
    );
  }
}
