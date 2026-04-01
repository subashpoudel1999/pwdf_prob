import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:http/http.dart' as http;

import '../config/app_config.dart';

// ---------------------------------------------------------------------------
// Accent colour — warm amber/red distinct from every other screen
// ---------------------------------------------------------------------------
const _kAccent = Color(0xFFEF5350);   // Material red 400

// Pipeline step labels
const _kSteps = [
  'Step 1 — Loading WildCat sub-basin polygons and derived stream segments...',
  'Step 2 — Downloading NHDPlus HR stream network from USGS REST API...',
  'Step 3 — Building 30m stream corridors (NHDPlus ∪ WildCat segments)...',
  'Step 4 — Computing pre/post spectral change via Google Earth Engine (S2 / L8–9)...',
  'Step 5 — Normalising dNDWI / dBSI / dNBR and computing debris_flow_score...',
];

const _kStepIcons = [
  Icons.grain,
  Icons.water,
  Icons.route,
  Icons.cloud_outlined,
  Icons.bar_chart,
];

// ---------------------------------------------------------------------------
// Screen widget
// ---------------------------------------------------------------------------

class RetroDetectionScreen extends StatefulWidget {
  const RetroDetectionScreen({super.key});

  @override
  State<RetroDetectionScreen> createState() => _RetroDetectionScreenState();
}

enum _ScreenState { ready, analyzing, results }

// ---------------------------------------------------------------------------
// Storm event data class
// ---------------------------------------------------------------------------
class _StormEvent {
  final String date;
  final double peakPrecipMm;
  final double eventPrecipMm;
  final String preStart;
  final String preEnd;
  final String postStart;
  final String postEnd;

  const _StormEvent({
    required this.date,
    required this.peakPrecipMm,
    required this.eventPrecipMm,
    required this.preStart,
    required this.preEnd,
    required this.postStart,
    required this.postEnd,
  });

  factory _StormEvent.fromJson(Map<String, dynamic> j) => _StormEvent(
        date: j['date'] as String,
        peakPrecipMm: (j['peak_precip_mm'] as num).toDouble(),
        eventPrecipMm: (j['event_precip_mm'] as num).toDouble(),
        preStart: j['pre_start'] as String,
        preEnd: j['pre_end'] as String,
        postStart: j['post_start'] as String,
        postEnd: j['post_end'] as String,
      );

  String get formattedDate {
    try {
      final parts = date.split('-');
      final months = ['Jan','Feb','Mar','Apr','May','Jun',
                      'Jul','Aug','Sep','Oct','Nov','Dec'];
      return '${months[int.parse(parts[1]) - 1]} ${int.parse(parts[2])}, ${parts[0]}';
    } catch (_) {
      return date;
    }
  }

  static String _fmtDate(String d) {
    try {
      final parts = d.split('-');
      final months = ['Jan','Feb','Mar','Apr','May','Jun',
                      'Jul','Aug','Sep','Oct','Nov','Dec'];
      return '${months[int.parse(parts[1]) - 1]} ${int.parse(parts[2])}, ${parts[0]}';
    } catch (_) {
      return d;
    }
  }

  String get windowSummary =>
      'Pre:  ${_fmtDate(preStart)} – ${_fmtDate(preEnd)}\n'
      'Post: ${_fmtDate(postStart)} – ${_fmtDate(postEnd)}';
}

class _RetroDetectionScreenState extends State<RetroDetectionScreen>
    with TickerProviderStateMixin {
  static final String _base = AppConfig.backendUrl;
  static const LatLng _dolanCenter = LatLng(36.06, -121.40);

  final MapController _mapController = MapController();

  _ScreenState _screenState = _ScreenState.ready;

  // ── ready state ───────────────────────────────────────────────────────────
  final String _selectedFireId = 'dolan';

  // ── GEE project ID ────────────────────────────────────────────────────────
  final TextEditingController _projectIdController = TextEditingController();
  String _projectId = '';            // validated project id

  // ── storm event selection ─────────────────────────────────────────────────
  List<_StormEvent>? _stormEvents;   // null = not yet loaded
  bool _loadingStorms = false;
  String? _stormLoadError;
  int _selectedStormIdx = 0;         // index into _stormEvents; -1 = use fire defaults

  // ── analysis state ────────────────────────────────────────────────────────
  String? _jobId;
  int _currentStep = 0;
  String _stepMessage = '';
  int _progress = 0;
  String? _error;
  String? _activeStormDate;  // storm_date used for the current/last run (for results fetch)

  // ── results state ─────────────────────────────────────────────────────────
  List<_BasinFeature> _basins = [];
  List<_SamplePoint> _samplePoints = [];
  List<List<LatLng>> _streamLines = [];
  int? _selectedIdx;        // selected basin index
  int? _selectedPointIdx;   // selected sample-point index (takes priority in panel)
  bool _useSatellite = false;
  bool _showPoints = true;
  bool _showStreams = true;

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

  // -------------------------------------------------------------------------
  // Storm event loading
  // -------------------------------------------------------------------------

  void _onConnectGee() {
    final id = _projectIdController.text.trim();
    if (id.isEmpty) return;
    setState(() {
      _projectId = id;
      _stormEvents = null;
      _stormLoadError = null;
    });
    _fetchStormEvents();
  }

  Future<void> _fetchStormEvents({bool force = false}) async {
    if (_projectId.isEmpty) return;
    setState(() {
      _loadingStorms = true;
      _stormLoadError = null;
    });
    try {
      final params = 'project_id=${Uri.encodeComponent(_projectId)}${force ? "&force=true" : ""}';
      final uri = Uri.parse('$_base/retro/$_selectedFireId/storm-events?$params');
      final resp = await http.get(uri);
      if (resp.statusCode == 200) {
        final List<dynamic> raw = json.decode(resp.body) as List<dynamic>;
        final events = raw
            .cast<Map<String, dynamic>>()
            .map(_StormEvent.fromJson)
            .toList();
        setState(() {
          _stormEvents = events;
          _selectedStormIdx = events.isNotEmpty ? 0 : -1;
        });
      } else {
        setState(() => _stormLoadError = 'Server error ${resp.statusCode}');
      }
    } catch (e) {
      setState(() => _stormLoadError = 'Could not load storm events: $e');
    } finally {
      setState(() => _loadingStorms = false);
    }
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _pulseController.dispose();
    _projectIdController.dispose();
    super.dispose();
  }

  // -------------------------------------------------------------------------
  // Analysis flow
  // -------------------------------------------------------------------------

  Future<void> _startAnalysis({bool force = false}) async {
    // Determine which storm event's windows to use
    _StormEvent? selectedStorm;
    if (_stormEvents != null &&
        _selectedStormIdx >= 0 &&
        _selectedStormIdx < _stormEvents!.length) {
      selectedStorm = _stormEvents![_selectedStormIdx];
    }

    setState(() {
      _screenState = _ScreenState.analyzing;
      _currentStep = 0;
      _stepMessage = 'Starting pipeline...';
      _progress = 0;
      _error = null;
      _activeStormDate = selectedStorm?.date;
    });

    try {
      final payload = <String, dynamic>{
        'project_id': _projectId,
        'force': force,
      };
      if (selectedStorm != null) {
        payload['pre_start']  = selectedStorm.preStart;
        payload['pre_end']    = selectedStorm.preEnd;
        payload['post_start'] = selectedStorm.postStart;
        payload['post_end']   = selectedStorm.postEnd;
        payload['storm_date'] = selectedStorm.date;
      }

      final resp = await http.post(
        Uri.parse('$_base/retro/$_selectedFireId/analyze'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode(payload),
      );
      if (resp.statusCode != 200) {
        throw Exception('Backend error: ${resp.body}');
      }
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
      final resp = await http.get(
          Uri.parse('$_base/retro/$_selectedFireId/status/$_jobId'));
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
          _currentStep = 6;
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
      final uri = _activeStormDate != null
          ? Uri.parse(
              '$_base/retro/$_selectedFireId/results?storm_date=$_activeStormDate')
          : Uri.parse('$_base/retro/$_selectedFireId/results');
      final resp = await http.get(uri);
      if (resp.statusCode != 200) {
        throw Exception('HTTP ${resp.statusCode}: ${resp.body}');
      }
      final fc = json.decode(resp.body) as Map<String, dynamic>;
      final features =
          (fc['features'] as List<dynamic>).cast<Map<String, dynamic>>();

      final basins = features
          .map((f) => _BasinFeature.fromGeoJson(f))
          .where((b) => b.rings.isNotEmpty)
          .toList();

      // Parse per-point sample data
      final pointsRaw = fc['sample_points'] as Map<String, dynamic>?;
      final samplePoints = pointsRaw == null
          ? <_SamplePoint>[]
          : (pointsRaw['features'] as List<dynamic>)
              .cast<Map<String, dynamic>>()
              .map(_SamplePoint.fromGeoJson)
              .toList();

      // Parse stream line geometries (LineString + MultiLineString)
      final streamsRaw = fc['streams'] as Map<String, dynamic>?;
      final streamLines = <List<LatLng>>[];
      if (streamsRaw != null) {
        for (final feat
            in (streamsRaw['features'] as List<dynamic>)
                .cast<Map<String, dynamic>>()) {
          final geom = feat['geometry'] as Map<String, dynamic>?;
          if (geom == null) continue;
          final type = geom['type'] as String;
          final coords = geom['coordinates'] as List<dynamic>;
          if (type == 'LineString') {
            streamLines.add(coords
                .cast<List<dynamic>>()
                .map((c) => LatLng(
                    (c[1] as num).toDouble(), (c[0] as num).toDouble()))
                .toList());
          } else if (type == 'MultiLineString') {
            for (final seg in coords.cast<List<dynamic>>()) {
              streamLines.add(seg
                  .cast<List<dynamic>>()
                  .map((c) => LatLng(
                      (c[1] as num).toDouble(), (c[0] as num).toDouble()))
                  .toList());
            }
          }
        }
      }

      if (!mounted) return;
      setState(() {
        _basins = basins;
        _samplePoints = samplePoints;
        _streamLines = streamLines;
        _screenState = _ScreenState.results;
        _selectedIdx = null;
      });

      if (basins.isNotEmpty) {
        final allLats = basins.expand((b) => b.rings).map((p) => p.latitude);
        final allLngs = basins.expand((b) => b.rings).map((p) => p.longitude);
        final bounds = LatLngBounds(
          LatLng(allLats.reduce((a, b) => a < b ? a : b),
              allLngs.reduce((a, b) => a < b ? a : b)),
          LatLng(allLats.reduce((a, b) => a > b ? a : b),
              allLngs.reduce((a, b) => a > b ? a : b)),
        );
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            _mapController.fitCamera(
                CameraFit.bounds(bounds: bounds, padding: const EdgeInsets.all(60)));
          }
        });
      }
    } catch (e) {
      setState(() {
        _error = 'Failed to load results: $e';
        _screenState = _ScreenState.ready;
      });
    }
  }

  void _showError(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: Colors.red.shade700,
      ),
    );
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
          Icon(Icons.satellite_alt, color: _kAccent),
          SizedBox(width: 10),
          Text('Retrospective Debris Flow Detection',
              style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
          SizedBox(width: 10),
          Text('GEE Spectral Change',
              style: TextStyle(
                  color: Colors.white54, fontSize: 13, fontWeight: FontWeight.normal)),
        ]),
        actions: [
          if (_screenState == _ScreenState.results) ...[
            IconButton(
              tooltip: _showStreams ? 'Hide streams' : 'Show streams',
              onPressed: () => setState(() => _showStreams = !_showStreams),
              icon: Icon(
                Icons.water,
                color: _showStreams ? const Color(0xFF29B6F6) : Colors.white38,
              ),
            ),
            IconButton(
              tooltip: _showPoints ? 'Hide sample points' : 'Show sample points',
              onPressed: () => setState(() => _showPoints = !_showPoints),
              icon: Icon(
                Icons.scatter_plot,
                color: _showPoints ? _kAccent : Colors.white38,
              ),
            ),
            IconButton(
              tooltip: _useSatellite ? 'Dark map' : 'Satellite',
              onPressed: () => setState(() => _useSatellite = !_useSatellite),
              icon: Icon(
                _useSatellite ? Icons.nightlight_round : Icons.satellite_alt,
                color: Colors.white70,
              ),
            ),
            TextButton.icon(
              onPressed: () => setState(() {
                _screenState = _ScreenState.ready;
                _selectedIdx = null;
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
  // Storm event selector widget
  // -------------------------------------------------------------------------

  Widget _buildStormSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // ── GEE Project ID ──────────────────────────────────────────────────
        Text('GEE PROJECT ID',
            style: TextStyle(
                color: Colors.white38,
                fontSize: 10,
                fontWeight: FontWeight.w600,
                letterSpacing: 1.1)),
        const SizedBox(height: 6),
        Row(children: [
          Expanded(
            child: TextField(
              controller: _projectIdController,
              style: const TextStyle(color: Colors.white, fontSize: 13),
              decoration: InputDecoration(
                hintText: 'e.g. my-gee-project-123',
                hintStyle: TextStyle(
                    color: Colors.white.withValues(alpha: 0.25), fontSize: 12),
                filled: true,
                fillColor: Colors.white.withValues(alpha: 0.05),
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide:
                      BorderSide(color: Colors.white.withValues(alpha: 0.12)),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide:
                      BorderSide(color: Colors.white.withValues(alpha: 0.12)),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide:
                      BorderSide(color: _kAccent.withValues(alpha: 0.6)),
                ),
              ),
              onSubmitted: (_) => _onConnectGee(),
            ),
          ),
          const SizedBox(width: 8),
          ElevatedButton(
            onPressed: _loadingStorms ? null : _onConnectGee,
            style: ElevatedButton.styleFrom(
              backgroundColor: _kAccent.withValues(alpha: 0.85),
              foregroundColor: Colors.white,
              disabledBackgroundColor: Colors.white12,
              padding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8)),
            ),
            child: _loadingStorms
                ? const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                        strokeWidth: 1.5, color: Colors.white54))
                : const Text('Connect',
                    style:
                        TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
          ),
        ]),
        const SizedBox(height: 18),

        // ── Section header ──────────────────────────────────────────────────
        Row(children: [
          const Icon(Icons.thunderstorm_outlined, size: 14, color: _kAccent),
          const SizedBox(width: 6),
          const Text('SELECT STORM EVENT',
              style: TextStyle(
                  color: Colors.white,
                  fontSize: 13,
                  fontWeight: FontWeight.bold)),
          const Spacer(),
          if (_loadingStorms)
            const SizedBox(
                width: 12,
                height: 12,
                child: CircularProgressIndicator(
                    strokeWidth: 1.5, color: Colors.white38))
          else
            Tooltip(
              message: 'Re-query ERA5 / GEE (bypasses cache)',
              child: InkWell(
                onTap: () => _fetchStormEvents(force: true),
                borderRadius: BorderRadius.circular(4),
                child: const Padding(
                  padding: EdgeInsets.all(4),
                  child: Icon(Icons.refresh, size: 14, color: Colors.white38),
                ),
              ),
            ),
        ]),
        const SizedBox(height: 4),
        Text(
          'Top 5 extreme rainfall events detected via ERA5-Land (GEE) '
          'within 2 years of the Dolan Fire. '
          'One pre-storm and one post-storm satellite image will be pulled '
          'around the selected date.',
          style: TextStyle(
              color: Colors.white.withValues(alpha: 0.45),
              fontSize: 11,
              height: 1.4),
        ),
        const SizedBox(height: 12),

        // ── Content ─────────────────────────────────────────────────────────
        if (_loadingStorms && _stormEvents == null)
          _infoBox(
            child: Row(children: [
              const SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(
                      strokeWidth: 1.5, color: Colors.white54)),
              const SizedBox(width: 10),
              Text('Querying ERA5-Land precipitation via GEE…',
                  style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.5),
                      fontSize: 12)),
            ]),
          )
        else if (_stormLoadError != null)
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.orange.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(8),
              border:
                  Border.all(color: Colors.orange.withValues(alpha: 0.3)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  const Icon(Icons.warning_amber_rounded,
                      size: 14, color: Colors.orange),
                  const SizedBox(width: 6),
                  const Text('Could not load storm events',
                      style: TextStyle(
                          color: Colors.orange,
                          fontSize: 12,
                          fontWeight: FontWeight.w600)),
                ]),
                const SizedBox(height: 4),
                Text(
                  'Analysis will run with the default Jan 27 2021 window.\n'
                  'Error: $_stormLoadError',
                  style: TextStyle(
                      color: Colors.orange.withValues(alpha: 0.7),
                      fontSize: 11),
                ),
              ],
            ),
          )
        else if (_stormEvents != null && _stormEvents!.isEmpty)
          _infoBox(
            child: Text(
              'No storm events found in the 2-year post-fire window.',
              style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.45),
                  fontSize: 12),
            ),
          )
        else if (_stormEvents != null) ...[
          // ── Storm event cards ────────────────────────────────────────────
          ..._stormEvents!.asMap().entries.map((entry) {
            final i = entry.key;
            final storm = entry.value;
            final selected = i == _selectedStormIdx;

            // rank bar width proportional to event precipitation
            final maxPrecip = _stormEvents!
                .map((s) => s.eventPrecipMm)
                .reduce((a, b) => a > b ? a : b);
            final barFraction =
                maxPrecip > 0 ? storm.eventPrecipMm / maxPrecip : 0.0;

            return GestureDetector(
              onTap: () => setState(() => _selectedStormIdx = i),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 150),
                margin: const EdgeInsets.only(bottom: 6),
                decoration: BoxDecoration(
                  color: selected
                      ? _kAccent.withValues(alpha: 0.10)
                      : Colors.white.withValues(alpha: 0.04),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: selected
                        ? _kAccent.withValues(alpha: 0.55)
                        : Colors.white.withValues(alpha: 0.08),
                    width: selected ? 1.5 : 1.0,
                  ),
                ),
                child: Column(children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(10, 10, 10, 6),
                    child: Row(children: [
                      // Rank badge
                      Container(
                        width: 22,
                        height: 22,
                        decoration: BoxDecoration(
                          color: selected
                              ? _kAccent
                              : Colors.white.withValues(alpha: 0.08),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        alignment: Alignment.center,
                        child: Text('${i + 1}',
                            style: TextStyle(
                                color: selected
                                    ? Colors.white
                                    : Colors.white38,
                                fontSize: 11,
                                fontWeight: FontWeight.bold)),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(storm.formattedDate,
                                style: TextStyle(
                                    color: selected
                                        ? Colors.white
                                        : Colors.white70,
                                    fontSize: 13,
                                    fontWeight: selected
                                        ? FontWeight.w700
                                        : FontWeight.w500)),
                            const SizedBox(height: 1),
                            Text(
                              '${storm.eventPrecipMm.toStringAsFixed(1)} mm cumulative  '
                              '·  ${storm.peakPrecipMm.toStringAsFixed(1)} mm/day peak',
                              style: TextStyle(
                                  color: Colors.white.withValues(
                                      alpha: selected ? 0.6 : 0.4),
                                  fontSize: 10.5),
                            ),
                          ],
                        ),
                      ),
                      Icon(
                        selected
                            ? Icons.check_circle
                            : Icons.circle_outlined,
                        size: 16,
                        color: selected ? _kAccent : Colors.white24,
                      ),
                    ]),
                  ),
                  // Precipitation bar
                  ClipRRect(
                    borderRadius: const BorderRadius.vertical(
                        bottom: Radius.circular(7)),
                    child: LinearProgressIndicator(
                      value: barFraction,
                      minHeight: 3,
                      backgroundColor: Colors.white.withValues(alpha: 0.06),
                      valueColor: AlwaysStoppedAnimation<Color>(
                          selected
                              ? _kAccent.withValues(alpha: 0.7)
                              : Colors.white24),
                    ),
                  ),
                ]),
              ),
            );
          }),

          // ── Selected event imagery window summary ────────────────────────
          if (_selectedStormIdx >= 0 &&
              _selectedStormIdx < _stormEvents!.length) ...[
            const SizedBox(height: 4),
            Container(
              padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
              decoration: BoxDecoration(
                color: _kAccent.withValues(alpha: 0.06),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                    color: _kAccent.withValues(alpha: 0.2)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.date_range,
                      size: 14, color: _kAccent),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('SATELLITE IMAGERY WINDOWS',
                            style: TextStyle(
                                color: _kAccent,
                                fontSize: 9,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 1.0)),
                        const SizedBox(height: 6),
                        Text(
                          _stormEvents![_selectedStormIdx].windowSummary,
                          style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.7),
                              fontSize: 11.5,
                              fontFamily: 'monospace',
                              height: 1.7),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ],
    );
  }

  // Helper for neutral info boxes
  Widget _infoBox({required Widget child}) => Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.04),
          borderRadius: BorderRadius.circular(8),
          border:
              Border.all(color: Colors.white.withValues(alpha: 0.08)),
        ),
        child: child,
      );

  // -------------------------------------------------------------------------
  // Ready screen
  // -------------------------------------------------------------------------

  Widget _buildReady() {
    // Determine selected storm label for the Run button
    String runLabel = 'Run Detection';
    if (_stormEvents != null &&
        _selectedStormIdx >= 0 &&
        _selectedStormIdx < _stormEvents!.length) {
      runLabel = 'Analyse  •  ${_stormEvents![_selectedStormIdx].formattedDate}';
    }

    return Row(children: [
      // Left panel
      SizedBox(
        width: 380,
        child: Container(
          color: const Color(0xFF0D1B2A),
          child: Column(children: [
            // ── compact header ──────────────────────────────────────────────
            Container(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 14),
              decoration: BoxDecoration(
                color: const Color(0xFF0A2030),
                border: Border(
                    bottom: BorderSide(
                        color: Colors.white.withValues(alpha: 0.07))),
              ),
              child: Row(children: [
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: _kAccent.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(20),
                    border:
                        Border.all(color: _kAccent.withValues(alpha: 0.4)),
                  ),
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.satellite_alt, color: _kAccent, size: 12),
                      SizedBox(width: 5),
                      Text('GEE · S2 / L8–9 · dNDWI / dBSI / dNBR',
                          style: TextStyle(
                              color: _kAccent,
                              fontSize: 10,
                              fontWeight: FontWeight.w600)),
                    ],
                  ),
                ),
                const Spacer(),
                Text('Dolan Fire  •  2020',
                    style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.35),
                        fontSize: 11)),
              ]),
            ),

            // ── scrollable body ─────────────────────────────────────────────
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // ── Storm event selector (PRIMARY — shown first) ─────────
                    _buildStormSelector(),

                    const SizedBox(height: 20),
                    Divider(color: Colors.white.withValues(alpha: 0.08)),
                    const SizedBox(height: 16),

                    // ── Scoring formula (secondary) ──────────────────────────
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.04),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                            color: Colors.white.withValues(alpha: 0.08)),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('SCORING FORMULA',
                              style: TextStyle(
                                  color: Colors.white38,
                                  fontSize: 10,
                                  fontWeight: FontWeight.w600,
                                  letterSpacing: 1.2)),
                          const SizedBox(height: 8),
                          Text(
                            'score = 0.4×norm(dNDWI) + 0.4×norm(dBSI) + 0.2×norm(dNBR)',
                            style: TextStyle(
                                color: Colors.white.withValues(alpha: 0.5),
                                fontSize: 11,
                                fontFamily: 'monospace',
                                height: 1.5),
                          ),
                        ],
                      ),
                    ),

                    const SizedBox(height: 14),

                    // ── GEE timing note ──────────────────────────────────────
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: Colors.amber.withValues(alpha: 0.06),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                            color: Colors.amber.withValues(alpha: 0.2)),
                      ),
                      child: Row(children: [
                        const Icon(Icons.timer_outlined,
                            color: Colors.amber, size: 14),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'GEE satellite analysis takes 2–5 min. '
                            'NHDPlus stream data is cached after the first run.',
                            style: TextStyle(
                                color: Colors.amber.withValues(alpha: 0.75),
                                fontSize: 11,
                                height: 1.4),
                          ),
                        ),
                      ]),
                    ),

                    if (_error != null) ...[
                      const SizedBox(height: 14),
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: Colors.red.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                              color: Colors.red.withValues(alpha: 0.3)),
                        ),
                        child: Text(_error!,
                            style: const TextStyle(
                                color: Colors.redAccent, fontSize: 12)),
                      ),
                    ],
                  ],
                ),
              ),
            ),

            // ── Run button ───────────────────────────────────────────────────
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
              child: SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _loadingStorms ? null : _startAnalysis,
                  icon: const Icon(Icons.play_arrow),
                  label: Text(runLabel,
                      style: const TextStyle(
                          fontSize: 14, fontWeight: FontWeight.bold)),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _kAccent,
                    foregroundColor: Colors.white,
                    disabledBackgroundColor: Colors.white12,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10)),
                  ),
                ),
              ),
            ),
          ]),
        ),
      ),

      // Right: map preview with fire center
      Expanded(
        child: _buildMapPreview(),
      ),
    ]);
  }

  Widget _buildMapPreview() {
    return FlutterMap(
      mapController: _mapController,
      options: MapOptions(
        initialCenter: _dolanCenter,
        initialZoom: 11.0,
      ),
      children: [
        TileLayer(
          urlTemplate:
              'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
          userAgentPackageName: 'com.example.fire_webapp',
        ),
        MarkerLayer(
          markers: [
            Marker(
              point: _dolanCenter,
              width: 40,
              height: 40,
              child: Container(
                decoration: BoxDecoration(
                  color: _kAccent.withValues(alpha: 0.85),
                  shape: BoxShape.circle,
                  border: Border.all(color: Colors.white, width: 2),
                ),
                child: const Icon(Icons.local_fire_department,
                    color: Colors.white, size: 20),
              ),
            ),
          ],
        ),
      ],
    );
  }

  // -------------------------------------------------------------------------
  // Analyzing screen
  // -------------------------------------------------------------------------

  Widget _buildAnalyzing() {
    return SingleChildScrollView(
      child: Center(
        child: Container(
        constraints: const BoxConstraints(maxWidth: 560),
        padding: const EdgeInsets.all(40),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Pulsing icon
            AnimatedBuilder(
              animation: _pulseAnim,
              builder: (_, __) => Opacity(
                opacity: _pulseAnim.value,
                child: Container(
                  width: 72,
                  height: 72,
                  decoration: BoxDecoration(
                    color: _kAccent.withValues(alpha: 0.15),
                    shape: BoxShape.circle,
                    border: Border.all(
                        color: _kAccent.withValues(alpha: 0.4), width: 2),
                  ),
                  child: const Icon(Icons.satellite_alt,
                      color: _kAccent, size: 36),
                ),
              ),
            ),
            const SizedBox(height: 28),
            const Text('Detecting Debris Flows...',
                style: TextStyle(
                    color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text(_stepMessage,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.white60, fontSize: 13, height: 1.4)),
            const SizedBox(height: 28),

            // Progress bar
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: _progress / 100.0,
                backgroundColor: Colors.white12,
                valueColor: const AlwaysStoppedAnimation<Color>(_kAccent),
                minHeight: 6,
              ),
            ),
            const SizedBox(height: 8),
            Text('$_progress%',
                style: const TextStyle(color: Colors.white38, fontSize: 12)),
            const SizedBox(height: 32),

            // Steps list
            ..._kSteps.asMap().entries.map((e) {
              final stepNum = e.key + 1;
              final isDone = _currentStep > stepNum;
              final isActive = _currentStep == stepNum;
              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Row(
                  children: [
                    Container(
                      width: 32,
                      height: 32,
                      decoration: BoxDecoration(
                        color: isDone
                            ? Colors.green.withValues(alpha: 0.15)
                            : isActive
                                ? _kAccent.withValues(alpha: 0.15)
                                : Colors.white.withValues(alpha: 0.05),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: isDone
                              ? Colors.green.withValues(alpha: 0.4)
                              : isActive
                                  ? _kAccent.withValues(alpha: 0.5)
                                  : Colors.white.withValues(alpha: 0.1),
                        ),
                      ),
                      child: Icon(
                        isDone ? Icons.check : _kStepIcons[e.key],
                        size: 16,
                        color: isDone
                            ? Colors.greenAccent
                            : isActive
                                ? _kAccent
                                : Colors.white24,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        e.value,
                        style: TextStyle(
                          color: isDone
                              ? Colors.white60
                              : isActive
                                  ? Colors.white
                                  : Colors.white30,
                          fontSize: 12,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
        ),
      ),
    );
  }

  // -------------------------------------------------------------------------
  // Results screen
  // -------------------------------------------------------------------------

  Widget _buildResults() {
    return Row(children: [
      // Map
      Expanded(child: _buildResultsMap()),

      // Right panel
      SizedBox(
        width: 320,
        child: Container(
          color: const Color(0xFF0D1B2A),
          child: Column(children: [
            // Header
            Container(
              padding: const EdgeInsets.all(16),
              color: const Color(0xFF0A2030),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    const Icon(Icons.bar_chart, color: _kAccent, size: 18),
                    const SizedBox(width: 8),
                    const Text('Detection Results',
                        style: TextStyle(
                            color: Colors.white,
                            fontSize: 15,
                            fontWeight: FontWeight.bold)),
                  ]),
                  const SizedBox(height: 4),
                  Text(
                    '${_basins.where((b) => b.score != null).length} / ${_basins.length} sub-basins scored',
                    style: const TextStyle(color: Colors.white54, fontSize: 12),
                  ),
                ],
              ),
            ),

            // Score legend
            _buildLegend(),

            // Point detail takes priority; basin detail as fallback
            if (_selectedPointIdx != null)
              _buildPointDetail(_samplePoints[_selectedPointIdx!])
            else if (_selectedIdx != null)
              _buildBasinDetail(_basins[_selectedIdx!]),

            // Imagery source note at bottom
            const Spacer(),
            if (_basins.isNotEmpty) ...[
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                child: Row(children: [
                  const Icon(Icons.info_outline, color: Colors.white30, size: 14),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _imagerySourceNote(),
                      style: const TextStyle(color: Colors.white30, fontSize: 11, height: 1.4),
                    ),
                  ),
                ]),
              ),
            ],
          ]),
        ),
      ),
    ]);
  }

  String _imagerySourceNote() {
    final sources = _basins
        .where((b) => b.imagerySource != null)
        .map((b) => b.imagerySource!)
        .toSet();
    if (sources.isEmpty) return 'No imagery source information available.';
    final srcLabel = sources.contains('sentinel2')
        ? 'Sentinel-2 (10m, COPERNICUS/S2_SR_HARMONIZED)'
        : 'Landsat-8/9 (30m)';
    return 'Imagery: $srcLabel\n'
        'Pre-storm: Oct–Dec 2020  •  Post-storm: Jan–Mar 2021\n'
        'Corridor: 30m buffer around NHDPlus + WildCat segments';
  }

  Widget _buildResultsMap() {
    // Determine tap-to-select.
    // Priority: sample point (if visible and within hit radius) → basin polygon.
    void onTap(TapPosition tp, LatLng tapped) {
      if (_showPoints && _samplePoints.isNotEmpty) {
        // Compute a hit-radius in degrees that matches ~14 screen pixels at
        // the current zoom level so the target scales naturally when zoomed.
        final zoom = _mapController.camera.zoom;
        final hitDeg = 14.0 * 360.0 / (256.0 * math.pow(2, zoom));
        int? nearest;
        double nearestDist = double.infinity;
        for (int i = 0; i < _samplePoints.length; i++) {
          final p = _samplePoints[i].position;
          final dlat = p.latitude  - tapped.latitude;
          final dlng = p.longitude - tapped.longitude;
          final d = math.sqrt(dlat * dlat + dlng * dlng);
          if (d < hitDeg && d < nearestDist) {
            nearestDist = d;
            nearest = i;
          }
        }
        if (nearest != null) {
          setState(() {
            _selectedPointIdx = nearest;
            _selectedIdx = null;
          });
          return;
        }
      }

      // No point hit — fall back to basin polygon selection.
      for (int i = 0; i < _basins.length; i++) {
        if (_pointInBasin(tapped, _basins[i])) {
          setState(() {
            _selectedIdx = i;
            _selectedPointIdx = null;
          });
          return;
        }
      }
      setState(() {
        _selectedIdx = null;
        _selectedPointIdx = null;
      });
    }

    return FlutterMap(
      mapController: _mapController,
      options: MapOptions(
        initialCenter: _dolanCenter,
        initialZoom: 11.0,
        onTap: onTap,
      ),
      children: [
        TileLayer(
          urlTemplate: _useSatellite
              ? 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
              : 'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
          userAgentPackageName: 'com.example.fire_webapp',
        ),
        // Basin polygons — higher opacity on dark background for crisp colour contrast
        PolygonLayer(
          polygons: [
            for (int i = 0; i < _basins.length; i++)
              if (_basins[i].rings.isNotEmpty)
                Polygon(
                  points: _basins[i].rings,
                  color: _scoreColor(_basins[i].score)
                      .withValues(alpha: _selectedIdx == i ? 0.80 : 0.62),
                  borderColor: _selectedIdx == i
                      ? Colors.white
                      : Colors.white.withValues(alpha: 0.18),
                  borderStrokeWidth: _selectedIdx == i ? 2.0 : 0.4,
                ),
          ],
        ),
        // Stream network — thin cyan lines so they read clearly over dark bg
        if (_showStreams && _streamLines.isNotEmpty)
          PolylineLayer(
            polylines: [
              for (final pts in _streamLines)
                if (pts.length >= 2)
                  Polyline(
                    points: pts,
                    color: const Color(0xFF29B6F6),   // light-blue 400
                    strokeWidth: 1.2,
                  ),
            ],
          ),
        // Sample points — sized up and fully opaque; sit above stream lines
        if (_showPoints && _samplePoints.isNotEmpty)
          CircleLayer(
            circles: [
              for (int i = 0; i < _samplePoints.length; i++)
                CircleMarker(
                  point: _samplePoints[i].position,
                  radius: _selectedPointIdx == i ? 8.0 : 5.0,
                  color: _scoreColor(_samplePoints[i].score)
                      .withValues(alpha: 0.92),
                  borderColor: _selectedPointIdx == i
                      ? Colors.white
                      : Colors.black.withValues(alpha: 0.55),
                  borderStrokeWidth: _selectedPointIdx == i ? 2.0 : 1.0,
                ),
            ],
          ),
      ],
    );
  }

  Widget _buildLegend() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('DEBRIS FLOW SCORE',
              style: TextStyle(
                  color: Colors.white38,
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 1.2)),
          const SizedBox(height: 8),
          // Gradient bar
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: SizedBox(
              height: 12,
              child: LinearProgressIndicator(
                value: 1,
                backgroundColor: Colors.transparent,
                valueColor: const AlwaysStoppedAnimation<Color>(Colors.transparent),
              ),
            ),
          ),
          SizedBox(
            height: 12,
            child: DecoratedBox(
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  colors: [Color(0xFF4CAF50), Color(0xFFFF9800), Color(0xFFF44336)],
                ),
                borderRadius: BorderRadius.all(Radius.circular(4)),
              ),
            ),
          ),
          const SizedBox(height: 4),
          const Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Low', style: TextStyle(color: Colors.white38, fontSize: 11)),
              Text('Medium', style: TextStyle(color: Colors.white38, fontSize: 11)),
              Text('High', style: TextStyle(color: Colors.white38, fontSize: 11)),
            ],
          ),
          const SizedBox(height: 10),
          Row(children: [
            Container(
              width: 12,
              height: 12,
              decoration: BoxDecoration(
                color: Colors.white24,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(width: 6),
            const Text('No stream data',
                style: TextStyle(color: Colors.white38, fontSize: 11)),
          ]),
          const SizedBox(height: 8),
          Row(children: [
            Container(
              width: 22,
              height: 3,
              decoration: BoxDecoration(
                color: Color(0xFF29B6F6),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(width: 6),
            const Expanded(
              child: Text('Stream network (NHDPlus + WildCat)',
                  style: TextStyle(color: Colors.white38, fontSize: 11)),
            ),
          ]),
          const SizedBox(height: 6),
          Row(children: [
            Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(
                color: Color(0xFFFF9800),
                shape: BoxShape.circle,
                border: Border.all(color: Colors.black45, width: 1.0),
              ),
            ),
            const SizedBox(width: 6),
            const Expanded(
              child: Text('GEE sample point (individual score)',
                  style: TextStyle(color: Colors.white38, fontSize: 11)),
            ),
          ]),
        ],
      ),
    );
  }

  Widget _buildBasinDetail(_BasinFeature b) {
    return Container(
      margin: const EdgeInsets.all(12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: _kAccent.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(
                color: _scoreColor(b.score),
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 8),
            Text(
              b.subBasinId ?? 'Basin',
              style: const TextStyle(
                  color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold),
            ),
          ]),
          const SizedBox(height: 10),
          _detailRow('Debris Flow Score',
              b.score != null ? b.score!.toStringAsFixed(3) : 'N/A',
              highlight: true),
          const Divider(color: Colors.white12, height: 16),
          _detailRow('dNDWI (norm)',
              b.dNdwi != null ? b.dNdwi!.toStringAsFixed(3) : 'N/A'),
          _detailRow('dBSI (norm)',
              b.dBsi != null ? b.dBsi!.toStringAsFixed(3) : 'N/A'),
          _detailRow('dNBR (norm)',
              b.dNbr != null ? b.dNbr!.toStringAsFixed(3) : 'N/A'),
          const Divider(color: Colors.white12, height: 16),
          _detailRow('dNDWI (raw)',
              b.dNdwiRaw != null ? b.dNdwiRaw!.toStringAsFixed(4) : 'N/A'),
          _detailRow('dBSI (raw)',
              b.dBsiRaw != null ? b.dBsiRaw!.toStringAsFixed(4) : 'N/A'),
          _detailRow('dNBR (raw)',
              b.dNbrRaw != null ? b.dNbrRaw!.toStringAsFixed(4) : 'N/A'),
          const Divider(color: Colors.white12, height: 16),
          _detailRow('Stream Length',
              b.streamLengthM != null ? '${b.streamLengthM!.toStringAsFixed(0)} m' : 'N/A'),
          _detailRow('Imagery',
              b.imagerySource == 'sentinel2' ? 'Sentinel-2 (10m)' :
              b.imagerySource == 'landsat89' ? 'Landsat-8/9 (30m)' : 'N/A'),
        ],
      ),
    );
  }

  Widget _buildPointDetail(_SamplePoint pt) {
    return Container(
      margin: const EdgeInsets.all(12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF29B6F6).withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(
                color: _scoreColor(pt.score),
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white54, width: 1),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                pt.subBasinId ?? 'Sample Point',
                style: const TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    fontWeight: FontWeight.bold),
              ),
            ),
          ]),
          const SizedBox(height: 4),
          const Text(
            'GEE sample point',
            style: TextStyle(color: Color(0xFF29B6F6), fontSize: 10),
          ),
          const SizedBox(height: 10),
          _detailRow('Debris Flow Score',
              pt.score != null ? pt.score!.toStringAsFixed(3) : 'N/A',
              highlight: true),
          const Divider(color: Colors.white12, height: 16),
          _detailRow('dNDWI (norm)',
              pt.dNdwi != null ? pt.dNdwi!.toStringAsFixed(3) : 'N/A'),
          _detailRow('dBSI (norm)',
              pt.dBsi != null ? pt.dBsi!.toStringAsFixed(3) : 'N/A'),
          _detailRow('dNBR (norm)',
              pt.dNbr != null ? pt.dNbr!.toStringAsFixed(3) : 'N/A'),
          const Divider(color: Colors.white12, height: 16),
          _detailRow('Lat', pt.position.latitude.toStringAsFixed(5)),
          _detailRow('Lon', pt.position.longitude.toStringAsFixed(5)),
        ],
      ),
    );
  }

  Widget _detailRow(String label, String value, {bool highlight = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label,
              style: const TextStyle(color: Colors.white54, fontSize: 11)),
          Text(value,
              style: TextStyle(
                  color: highlight ? _kAccent : Colors.white,
                  fontSize: highlight ? 14 : 11,
                  fontWeight: highlight ? FontWeight.bold : FontWeight.normal)),
        ],
      ),
    );
  }

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  /// Colour interpolation: 0=green, 0.5=orange, 1=red. Grey when null.
  static Color _scoreColor(double? score) {
    if (score == null) return const Color(0x44FFFFFF);
    if (score <= 0.5) {
      final t = score / 0.5;
      return Color.lerp(const Color(0xFF4CAF50), const Color(0xFFFF9800), t)!;
    } else {
      final t = (score - 0.5) / 0.5;
      return Color.lerp(const Color(0xFFFF9800), const Color(0xFFF44336), t)!;
    }
  }

  static bool _pointInBasin(LatLng point, _BasinFeature basin) {
    // Ray-casting point-in-polygon for the first ring (exterior)
    if (basin.rings.isEmpty) return false;
    final ring = basin.rings;
    final px = point.longitude;
    final py = point.latitude;
    bool inside = false;
    int j = ring.length - 1;
    for (int i = 0; i < ring.length; i++) {
      final xi = ring[i].longitude, yi = ring[i].latitude;
      final xj = ring[j].longitude, yj = ring[j].latitude;
      if (((yi > py) != (yj > py)) &&
          (px < (xj - xi) * (py - yi) / (yj - yi) + xi)) {
        inside = !inside;
      }
      j = i;
    }
    return inside;
  }
}

// ---------------------------------------------------------------------------
// Data model for a parsed basin feature
// ---------------------------------------------------------------------------

class _BasinFeature {
  final List<LatLng> rings;
  final String? subBasinId;
  final double? score;
  final double? dNdwi;
  final double? dBsi;
  final double? dNbr;
  final double? dNdwiRaw;
  final double? dBsiRaw;
  final double? dNbrRaw;
  final String? imagerySource;
  final double? streamLengthM;

  const _BasinFeature({
    required this.rings,
    this.subBasinId,
    this.score,
    this.dNdwi,
    this.dBsi,
    this.dNbr,
    this.dNdwiRaw,
    this.dBsiRaw,
    this.dNbrRaw,
    this.imagerySource,
    this.streamLengthM,
  });

  factory _BasinFeature.fromGeoJson(Map<String, dynamic> feature) {
    final geom = feature['geometry'] as Map<String, dynamic>?;
    final props = feature['properties'] as Map<String, dynamic>? ?? {};

    List<LatLng> rings = [];
    if (geom != null) {
      final type = geom['type'] as String? ?? '';
      final coords = geom['coordinates'];
      if (type == 'Polygon' && coords is List && coords.isNotEmpty) {
        final outer = coords[0] as List;
        rings = outer
            .whereType<List>()
            .map((c) => LatLng(
                  (c[1] as num).toDouble(),
                  (c[0] as num).toDouble(),
                ))
            .toList();
      } else if (type == 'MultiPolygon' && coords is List && coords.isNotEmpty) {
        // Use the first polygon ring of the largest polygon
        List largest = [];
        for (final poly in coords) {
          if (poly is List && poly.isNotEmpty) {
            final outer = poly[0] as List;
            if (outer.length > largest.length) largest = outer;
          }
        }
        rings = largest
            .whereType<List>()
            .map((c) => LatLng(
                  (c[1] as num).toDouble(),
                  (c[0] as num).toDouble(),
                ))
            .toList();
      }
    }

    double? numProp(String key) {
      final v = props[key];
      if (v == null) return null;
      return (v as num).toDouble();
    }

    return _BasinFeature(
      rings: rings,
      subBasinId: props['sub_basin_id'] as String?,
      score: numProp('debris_flow_score'),
      dNdwi: numProp('dNDWI_norm'),
      dBsi: numProp('dBSI_norm'),
      dNbr: numProp('dNBR_norm'),
      dNdwiRaw: numProp('dNDWI_raw'),
      dBsiRaw: numProp('dBSI_raw'),
      dNbrRaw: numProp('dNBR_raw'),
      imagerySource: props['imagery_source'] as String?,
      streamLengthM: numProp('stream_length_m'),
    );
  }
}

// ---------------------------------------------------------------------------
// Data model for an individual GEE sample point
// ---------------------------------------------------------------------------

class _SamplePoint {
  final LatLng position;
  final String? subBasinId;
  final double? score;
  final double? dNdwi;
  final double? dBsi;
  final double? dNbr;

  const _SamplePoint({
    required this.position,
    this.subBasinId,
    this.score,
    this.dNdwi,
    this.dBsi,
    this.dNbr,
  });

  factory _SamplePoint.fromGeoJson(Map<String, dynamic> feature) {
    final geom   = feature['geometry'] as Map<String, dynamic>?;
    final props  = feature['properties'] as Map<String, dynamic>? ?? {};
    final coords = geom?['coordinates'] as List?;
    final pos = coords != null && coords.length >= 2
        ? LatLng((coords[1] as num).toDouble(), (coords[0] as num).toDouble())
        : const LatLng(0, 0);

    double? numProp(String key) {
      final v = props[key];
      return v != null ? (v as num).toDouble() : null;
    }

    return _SamplePoint(
      position:   pos,
      subBasinId: props['sub_basin_id'] as String?,
      score:      numProp('debris_flow_score'),
      dNdwi:      numProp('dNDWI_norm'),
      dBsi:       numProp('dBSI_norm'),
      dNbr:       numProp('dNBR_norm'),
    );
  }
}
