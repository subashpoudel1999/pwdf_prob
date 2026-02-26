import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:http/http.dart' as http;

import '../utils/geojson_parser.dart';
import '../widgets/attribute_panel.dart';

const _kSteps = [
  'Loading fire perimeter, DEM, and dNBR rasters...',
  'Reprojecting to UTM Zone 11N (projected CRS for LA area)...',
  'Filling topographic depressions in DEM...',
  'Computing D8 flow direction across terrain...',
  'Computing flow accumulation (upslope contributing area)...',
  'Extracting stream network (threshold: 0.025 km^2)...',
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

class PalisadesFireScreen extends StatefulWidget {
  const PalisadesFireScreen({super.key});

  @override
  State<PalisadesFireScreen> createState() => _PalisadesFireScreenState();
}

enum _ScreenState { landing, analyzing, results }

class _PalisadesFireScreenState extends State<PalisadesFireScreen>
    with TickerProviderStateMixin {
  static const String _backendUrl = 'http://localhost:8000/api/v1';
  static const LatLng _palisadesCenter = LatLng(34.099, -118.570);

  final MapController _mapController = MapController();

  _ScreenState _screenState = _ScreenState.landing;
  String? _jobId;
  int _currentStep = 0;
  String _stepMessage = '';
  int _progress = 0;
  String? _error;

  ParsedGeoJson? _results;
  Map<String, dynamic>? _perimeterGeoJson;
  int? _selectedFeatureIndex;

  bool _isDrawing = false;
  List<LatLng> _drawnPolygon = [];
  List<LatLng> _zoneBoundary = [];     // saved polygon outline shown after zone analysis
  ParsedGeoJson? _customResults;
  int? _selectedZoneFeatureIndex;       // index into _customResults.features
  bool _useSatellite = true;
  bool _isZoneJob = false;

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
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _startAnalysis({bool force = false}) async {
    setState(() {
      _screenState = _ScreenState.analyzing;
      _currentStep = 0;
      _stepMessage = 'Initialising analysis pipeline...';
      _progress = 0;
      _error = null;
    });
    try {
      final uri = Uri.parse(
          force ? '$_backendUrl/palisades/analyze?force=true' : '$_backendUrl/palisades/analyze');
      final resp = await http.post(uri, headers: {'Content-Type': 'application/json'});
      if (resp.statusCode != 200) throw Exception('Backend error: ${resp.body}');
      final body = json.decode(resp.body);
      _jobId = body['job_id'] as String;
      _pollTimer?.cancel();
      _pollTimer = Timer.periodic(const Duration(milliseconds: 1200), (_) => _poll());
    } catch (e) {
      setState(() { _error = 'Failed to start: $e'; _screenState = _ScreenState.landing; });
    }
  }

  Future<void> _poll() async {
    if (_jobId == null) return;
    try {
      final resp = await http.get(Uri.parse('$_backendUrl/palisades/status/$_jobId'));
      if (resp.statusCode != 200) return;
      final data = json.decode(resp.body);
      final status = data['status'] as String? ?? 'running';
      final step = (data['step'] as num?)?.toInt() ?? _currentStep;
      final msg = data['message'] as String? ?? _stepMessage;
      final prog = (data['progress'] as num?)?.toInt() ?? _progress;
      if (!mounted) return;
      if (status == 'completed') {
        _pollTimer?.cancel();
        setState(() { _currentStep = 10; _progress = 100; _stepMessage = msg; });
        if (_isZoneJob) {
          await _loadZoneResults(_jobId!);
        } else {
          await _loadResults();
        }
      } else if (status == 'error') {
        _pollTimer?.cancel();
        setState(() {
          _error = data['error'] as String? ?? 'Unknown error';
          _screenState = _isZoneJob ? _ScreenState.results : _ScreenState.landing;
          _isZoneJob = false;
        });
      } else {
        setState(() { _currentStep = step; _stepMessage = msg; _progress = prog; });
      }
    } catch (_) {}
  }

  Future<void> _loadResults() async {
    try {
      final resultsResp = await http.get(Uri.parse('$_backendUrl/palisades/results'));
      final perimResp = await http.get(Uri.parse('$_backendUrl/palisades/perimeter'));
      if (resultsResp.statusCode == 200 && perimResp.statusCode == 200) {
        final parsed = parseGeoJson(json.decode(resultsResp.body));
        if (!mounted) return;
        setState(() {
          _results = parsed;
          _perimeterGeoJson = json.decode(perimResp.body);
          _screenState = _ScreenState.results;
        });
        // Defer fitCamera until FlutterMap has rendered at least one frame
        if (parsed.bounds != null) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              _mapController.fitCamera(
                  CameraFit.bounds(bounds: parsed.bounds!, padding: const EdgeInsets.all(60)));
            }
          });
        }
      }
    } catch (e) {
      setState(() { _error = 'Failed to load results: $e'; _screenState = _ScreenState.landing; });
    }
  }

  /// Starts a full WhiteboxTools re-run clipped to the drawn polygon.
  Future<void> _runCustomAnalysis() async {
    if (_drawnPolygon.length < 3) return;
    final coords = _drawnPolygon.map((p) => [p.longitude, p.latitude]).toList();
    coords.add([_drawnPolygon.first.longitude, _drawnPolygon.first.latitude]);

    // Save zone boundary so we can draw it after analysis completes
    final savedBoundary = List<LatLng>.from(_drawnPolygon);

    setState(() {
      _isZoneJob = true;
      _zoneBoundary = savedBoundary;
      _customResults = null;
      _selectedZoneFeatureIndex = null;
      _screenState = _ScreenState.analyzing;
      _currentStep = 0;
      _stepMessage = 'Starting zone analysis pipeline...';
      _progress = 0;
      _error = null;
    });

    try {
      final resp = await http.post(
        Uri.parse('$_backendUrl/palisades/analyze-zone'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'polygon': {'type': 'Polygon', 'coordinates': [coords]}}),
      );
      if (resp.statusCode != 200) {
        throw Exception('Backend error: ${resp.body}');
      }
      final body = json.decode(resp.body) as Map<String, dynamic>;
      _jobId = body['job_id'] as String;
      _pollTimer?.cancel();
      _pollTimer = Timer.periodic(const Duration(milliseconds: 1200), (_) => _poll());
    } catch (e) {
      setState(() {
        _error = 'Failed to start zone analysis: $e';
        _screenState = _ScreenState.results;
        _isZoneJob = false;
      });
    }
  }

  /// Load zone results from the backend and overlay on the map.
  Future<void> _loadZoneResults(String jobId) async {
    try {
      final resp = await http.get(Uri.parse('$_backendUrl/palisades/zone-results/$jobId'));
      if (!mounted) return;
      if (resp.statusCode == 200) {
        final parsed = parseGeoJson(json.decode(resp.body));
        setState(() {
          _customResults = parsed;
          _isDrawing = false;
          _drawnPolygon = [];           // clear numbered dots
          _selectedFeatureIndex = null; // deselect any main basin
          _selectedZoneFeatureIndex = null;
          _screenState = _ScreenState.results;
          _isZoneJob = false;
        });
        // Zoom to the zone extent
        if (parsed.bounds != null) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              _mapController.fitCamera(
                  CameraFit.bounds(bounds: parsed.bounds!, padding: const EdgeInsets.all(40)));
            }
          });
        }
      } else {
        setState(() {
          _error = 'Zone results unavailable (${resp.statusCode})';
          _screenState = _ScreenState.results;
          _isZoneJob = false;
        });
      }
    } catch (e) {
      setState(() {
        _error = 'Failed to load zone results: $e';
        _screenState = _ScreenState.results;
        _isZoneJob = false;
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D1B2A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1A1A2E),
        foregroundColor: Colors.white,
        title: const Row(children: [
          Icon(Icons.local_fire_department, color: Color(0xFFFF6B35)),
          SizedBox(width: 10),
          Text('Palisades Fire', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        ]),
        actions: [
          if (_screenState == _ScreenState.results) ...[
            IconButton(
              tooltip: _useSatellite ? 'Switch to Street Map' : 'Switch to Satellite',
              onPressed: () => setState(() => _useSatellite = !_useSatellite),
              icon: Icon(
                _useSatellite ? Icons.map_outlined : Icons.satellite_alt,
                color: Colors.white70,
              ),
            ),
            TextButton.icon(
              onPressed: () => setState(() {
                _isDrawing = !_isDrawing;
                _drawnPolygon.clear();
                if (_isDrawing) {
                  // Starting draw mode: reset any previous zone
                  _customResults = null;
                  _zoneBoundary = [];
                  _selectedZoneFeatureIndex = null;
                }
              }),
              icon: Icon(_isDrawing ? Icons.close : Icons.draw, color: Colors.white),
              label: Text(_isDrawing ? 'Cancel' : 'Draw Zone', style: const TextStyle(color: Colors.white)),
            ),
            if (_customResults != null)
              TextButton.icon(
                onPressed: () => setState(() {
                  _customResults = null;
                  _zoneBoundary = [];
                  _selectedZoneFeatureIndex = null;
                }),
                icon: const Icon(Icons.layers_clear, color: Colors.white60),
                label: const Text('Clear Zone', style: TextStyle(color: Colors.white60)),
              ),
            TextButton.icon(
              onPressed: () => _startAnalysis(force: true),
              icon: const Icon(Icons.refresh, color: Colors.orange),
              label: const Text('Re-run', style: TextStyle(color: Colors.orange)),
            ),
          ],
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    switch (_screenState) {
      case _ScreenState.landing: return _buildLanding();
      case _ScreenState.analyzing: return _buildAnalyzing();
      case _ScreenState.results: return _buildResults();
    }
  }

  Widget _buildLanding() {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft, end: Alignment.bottomRight,
          colors: [Color(0xFF0D1B2A), Color(0xFF1A1A2E), Color(0xFF16213E)],
        ),
      ),
      child: SafeArea(child: SingleChildScrollView(child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFFFF6B35).withOpacity(0.2),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFFF6B35).withOpacity(0.4)),
              ),
              child: const Icon(Icons.local_fire_department, color: Color(0xFFFF6B35), size: 48),
            ),
            const SizedBox(width: 24),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Palisades Fire', style: TextStyle(color: Colors.white, fontSize: 32, fontWeight: FontWeight.bold)),
              Text('May 2021  •  Pacific Palisades, CA', style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 14)),
            ])),
          ]),
          const SizedBox(height: 32),
          Wrap(spacing: 12, runSpacing: 12, children: [
            _infoChip(Icons.terrain, 'DEM', '10m resolution'),
            _infoChip(Icons.satellite_alt, 'dNBR', 'Sentinel-2'),
            _infoChip(Icons.water, 'Hydrology', 'WhiteboxTools D8'),
            _infoChip(Icons.science, 'Model', 'Staley (2017) M1'),
            _infoChip(Icons.bar_chart, 'Volume', 'Gartner (2014)'),
            _infoChip(Icons.area_chart, 'Area', '~5.5 km^2'),
          ]),
          const SizedBox(height: 32),
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.05),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.white.withOpacity(0.1)),
            ),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Live analysis pipeline:', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 15)),
              const SizedBox(height: 12),
              ..._kSteps.asMap().entries.map((e) => Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(children: [
                  Icon(_kStepIcons[e.key], size: 15, color: const Color(0xFFFF6B35).withOpacity(0.8)),
                  const SizedBox(width: 10),
                  Expanded(child: Text('${e.key + 1}. ${e.value}',
                    style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 12))),
                ]),
              )),
            ]),
          ),
          if (_error != null) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: Colors.red.withOpacity(0.15), borderRadius: BorderRadius.circular(8)),
              child: Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 13)),
            ),
          ],
          const SizedBox(height: 32),
          SizedBox(
            width: double.infinity, height: 58,
            child: ElevatedButton.icon(
              onPressed: _startAnalysis,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFFF6B35),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              icon: const Icon(Icons.play_arrow, size: 28),
              label: const Text('Run Live Analysis', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            ),
          ),
          const SizedBox(height: 8),
          Center(child: Text('Estimated time: 30–90 seconds',
            style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 12))),
        ]),
      ))),
    );
  }

  Widget _infoChip(IconData icon, String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.07),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white.withOpacity(0.12)),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 14, color: const Color(0xFFFF6B35)),
        const SizedBox(width: 8),
        Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 10, letterSpacing: 0.5)),
          Text(value, style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600)),
        ]),
      ]),
    );
  }

  Widget _buildAnalyzing() {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter,
          colors: [Color(0xFF0D1B2A), Color(0xFF16213E)]),
      ),
      child: SafeArea(child: Padding(padding: const EdgeInsets.all(24), child: Column(children: [
        const SizedBox(height: 24),
        AnimatedBuilder(
          animation: _pulseAnim,
          builder: (context, child) => Opacity(opacity: _pulseAnim.value, child: child),
          child: SizedBox(width: 120, height: 120, child: Stack(alignment: Alignment.center, children: [
            CircularProgressIndicator(
              value: _progress / 100, strokeWidth: 8,
              backgroundColor: Colors.white.withOpacity(0.1),
              valueColor: const AlwaysStoppedAnimation<Color>(Color(0xFFFF6B35)),
            ),
            Text('$_progress%', style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold)),
          ])),
        ),
        const SizedBox(height: 24),
        const Text('WhiteboxTools Analysis Running', style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        Text(_stepMessage, textAlign: TextAlign.center,
          style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 14)),
        const SizedBox(height: 32),
        Expanded(child: ListView.builder(
          itemCount: _kSteps.length,
          itemBuilder: (context, i) {
            final stepNum = i + 1;
            final isDone = stepNum < _currentStep;
            final isCurrent = stepNum == _currentStep;
            return AnimatedContainer(
              duration: const Duration(milliseconds: 400),
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: isCurrent ? const Color(0xFFFF6B35).withOpacity(0.15)
                    : isDone ? Colors.green.withOpacity(0.08)
                    : Colors.white.withOpacity(0.03),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: isCurrent ? const Color(0xFFFF6B35).withOpacity(0.5)
                      : isDone ? Colors.green.withOpacity(0.3)
                      : Colors.white.withOpacity(0.06),
                ),
              ),
              child: Row(children: [
                SizedBox(width: 28, height: 28, child: isDone
                    ? const Icon(Icons.check_circle, color: Colors.green, size: 22)
                    : isCurrent
                        ? AnimatedBuilder(animation: _pulseAnim,
                            builder: (context, child) => Opacity(opacity: _pulseAnim.value,
                              child: Icon(_kStepIcons[i], color: const Color(0xFFFF6B35), size: 22)))
                        : Icon(_kStepIcons[i], color: Colors.white.withOpacity(0.25), size: 22)),
                const SizedBox(width: 12),
                Expanded(child: Text('${stepNum}. ${_kSteps[i]}',
                  style: TextStyle(
                    color: isDone ? Colors.green.shade300 : isCurrent ? Colors.white : Colors.white.withOpacity(0.35),
                    fontSize: 13, fontWeight: isCurrent ? FontWeight.bold : FontWeight.normal))),
                if (isCurrent) const SizedBox(width: 14, height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFFFF6B35))),
              ]),
            );
          },
        )),
      ]))),
    );
  }

  Widget _buildResults() {
    return Stack(children: [
      FlutterMap(
        mapController: _mapController,
        options: MapOptions(
          initialCenter: _palisadesCenter,
          initialZoom: 14.0,
          onTap: (tapPosition, point) {
            if (_isDrawing) {
              setState(() => _drawnPolygon.add(point));
            } else if (_customResults != null) {
              // Zone mode: tap checks zone sub-basins first
              for (final feature in _customResults!.features) {
                if (_pointInPolygon(point, feature.rings[0])) {
                  setState(() {
                    _selectedZoneFeatureIndex =
                        _selectedZoneFeatureIndex == feature.index ? null : feature.index;
                  });
                  return;
                }
              }
              setState(() => _selectedZoneFeatureIndex = null);
            } else if (_results != null) {
              // Main results: tap checks full basins
              for (final feature in _results!.features) {
                if (_pointInPolygon(point, feature.rings[0])) {
                  setState(() {
                    _selectedFeatureIndex =
                        _selectedFeatureIndex == feature.index ? null : feature.index;
                  });
                  return;
                }
              }
              setState(() => _selectedFeatureIndex = null);
            }
          },
        ),
        children: [
          TileLayer(
            urlTemplate: _useSatellite
                ? 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
                : 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
            userAgentPackageName: 'com.example.fire_webapp',
          ),
          if (_perimeterGeoJson != null) PolygonLayer(polygons: _buildPerimeterPolygons()),
          // Full basins — dimmed when zone results are active
          if (_results != null) PolygonLayer(polygons: buildPolygons(
            features: _results!.features,
            selectedIndex: _customResults == null ? _selectedFeatureIndex : null,
            onTap: (i) => setState(() { _selectedFeatureIndex = _selectedFeatureIndex == i ? null : i; }),
            dimmed: _customResults != null,
          )),
          // Zone sub-basins on top
          if (_customResults != null) PolygonLayer(polygons: buildPolygons(
            features: _customResults!.features,
            selectedIndex: _selectedZoneFeatureIndex,
            onTap: (i) => setState(() {
              _selectedZoneFeatureIndex = _selectedZoneFeatureIndex == i ? null : i;
            }),
          )),
          // Zone boundary outline
          if (_zoneBoundary.length >= 3) PolygonLayer(polygons: [Polygon(
            points: _zoneBoundary,
            color: Colors.transparent,
            borderColor: Colors.white,
            borderStrokeWidth: 2.5,
          )]),
          if (_drawnPolygon.isNotEmpty) ...[
            PolygonLayer(polygons: [Polygon(
              points: _drawnPolygon, color: Colors.white.withOpacity(0.15),
              borderColor: Colors.white, borderStrokeWidth: 2.0,
            )]),
            MarkerLayer(markers: _drawnPolygon.asMap().entries.map((e) => Marker(
              point: e.value, width: 22, height: 22,
              child: Container(
                decoration: BoxDecoration(color: Colors.white, shape: BoxShape.circle,
                  border: Border.all(color: const Color(0xFFFF6B35), width: 2)),
                child: Center(child: Text('${e.key + 1}',
                  style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Color(0xFF0D1B2A)))),
              ),
            )).toList()),
          ],
        ],
      ),
      Positioned(top: 12, left: 12, right: 12, child: Material(
        color: const Color(0xCC0D1B2A), borderRadius: BorderRadius.circular(10),
        child: Padding(padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: Row(children: [
            Icon(
              _customResults != null ? Icons.crop_free : Icons.check_circle,
              color: _customResults != null ? Colors.orange : Colors.green,
              size: 18,
            ),
            const SizedBox(width: 10),
            Expanded(child: Text(
              _customResults != null
                  ? 'Zone analysis: ${_customResults!.features.length} sub-basins   |   Tap to explore   |   "Clear Zone" to return'
                  : 'Full analysis: ${_results?.features.length ?? 0} sub-basins   |   Tap a basin or draw a zone',
              style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600))),
          ])),
      )),
      // Error banner (zone analysis failed)
      if (_error != null) Positioned(top: 56, left: 12, right: 12, child: Material(
        color: Colors.red.shade900.withValues(alpha: 0.92),
        borderRadius: BorderRadius.circular(8),
        child: Padding(padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          child: Row(children: [
            const Icon(Icons.error_outline, color: Colors.white70, size: 16),
            const SizedBox(width: 8),
            Expanded(child: Text(_error!, style: const TextStyle(color: Colors.white, fontSize: 11))),
            GestureDetector(
              onTap: () => setState(() => _error = null),
              child: const Icon(Icons.close, color: Colors.white54, size: 16),
            ),
          ])),
      )),
      Positioned(top: 60, right: 12, child: _buildLegend()),
      if (_isDrawing) Positioned(bottom: 16, right: 16, child: Column(
        mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          FloatingActionButton.extended(
            heroTag: 'analyze_zone',
            onPressed: _drawnPolygon.length >= 3 ? _runCustomAnalysis : null,
            backgroundColor: Colors.green.shade700,
            icon: const Icon(Icons.analytics),
            label: Text(_drawnPolygon.length >= 3 ? 'Analyze Zone' : 'Add ${3 - _drawnPolygon.length} more points'),
          ),
          const SizedBox(height: 10),
          FloatingActionButton(
            heroTag: 'clear_draw', mini: true,
            onPressed: () => setState(() => _drawnPolygon.clear()),
            backgroundColor: Colors.grey.shade700,
            child: const Icon(Icons.clear),
          ),
          const SizedBox(height: 8),
          Container(padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(color: const Color(0xCC0D1B2A), borderRadius: BorderRadius.circular(8)),
            child: Text('Tap to draw  |  ${_drawnPolygon.length} points',
              textAlign: TextAlign.center, style: const TextStyle(color: Colors.white70, fontSize: 11))),
        ],
      )),
      // Zone feature attribute panel (takes priority)
      if (_customResults != null && _selectedZoneFeatureIndex != null &&
          _selectedZoneFeatureIndex! < _customResults!.features.length)
        Positioned(left: 12, top: 60, bottom: 16, child: AttributePanel(
          feature: _customResults!.features[_selectedZoneFeatureIndex!],
          onClose: () => setState(() => _selectedZoneFeatureIndex = null),
        ))
      // Main feature attribute panel
      else if (_results != null && _selectedFeatureIndex != null &&
          _selectedFeatureIndex! < _results!.features.length)
        Positioned(left: 12, top: 60, bottom: 16, child: AttributePanel(
          feature: _results!.features[_selectedFeatureIndex!],
          onClose: () => setState(() => _selectedFeatureIndex = null),
        )),
    ]);
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
        for (final poly in coords) { rings.add((poly as List)[0] as List<dynamic>); }
      }
      for (final ring in rings) {
        final points = ring.map((c) => LatLng((c[1] as num).toDouble(), (c[0] as num).toDouble())).toList();
        polygons.add(Polygon(points: points, color: Colors.transparent, borderColor: Colors.black, borderStrokeWidth: 3.0));
      }
    }
    return polygons;
  }

  Widget _buildLegend() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xCC0D1B2A), borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.white.withOpacity(0.15)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Debris-flow hazard', style: TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold)),
        const SizedBox(height: 6),
        _legendRow(Colors.red, 'High (P >= 0.6, V >= 1000 m3)'),
        _legendRow(Colors.orange, 'Moderate (P >= 0.4 or V >= 500 m3)'),
        _legendRow(Colors.yellow, 'Low (P >= 0.2 or V >= 100 m3)'),
        _legendRow(Colors.green, 'Very Low'),
        const SizedBox(height: 4),
        const Text('Model: Staley (2017) M1, I15=40 mm/hr', style: TextStyle(color: Colors.white54, fontSize: 9)),
      ]),
    );
  }

  Widget _legendRow(Color color, String label) {
    return Padding(padding: const EdgeInsets.only(bottom: 4), child: Row(mainAxisSize: MainAxisSize.min, children: [
      Container(width: 14, height: 14, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2))),
      const SizedBox(width: 6),
      Text(label, style: const TextStyle(color: Colors.white70, fontSize: 10)),
    ]));
  }
}
