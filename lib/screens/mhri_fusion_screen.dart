import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:http/http.dart' as http;
import 'package:file_picker/file_picker.dart';

import '../config/app_config.dart';
import '../utils/geojson_parser.dart';

// Bundled catalog of pre-made zipped Shapefiles for California cities, so
// users assessing one of these don't need to source/zip their own AOI file.
// Keys are asset filenames under assets/CA_city_shapefiles/ (must match
// pubspec.yaml's asset declaration); values are the human-readable labels
// shown in the dropdown.
const Map<String, String> _kCaCityShapefiles = {
  'CoronaCA.zip': 'Corona, CA',
  'FontanaCA.zip': 'Fontana, CA',
  'HesperiaCA.zip': 'Hesperia, CA',
  'IrvineCA.zip': 'Irvine, CA',
  'Los_AngelesCA.zip': 'Los Angeles, CA',
  'MalibuCA.zip': 'Malibu, CA',
  'OceansideCA.zip': 'Oceanside, CA',
  'PalmdaleCA.zip': 'Palmdale, CA',
  'PhelanCA.zip': 'Phelan, CA',
  'RiversideCA.zip': 'Riverside, CA',
  'SacramentoCA.zip': 'Sacramento, CA',
  'SageCA.zip': 'Sage, CA',
  'San_DiegoCA.zip': 'San Diego, CA',
  'San_FranciscoCA.zip': 'San Francisco, CA',
  'San_JoseCA.zip': 'San Jose, CA',
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const _kAccent     = Color(0xFF26C6DA); // cyan — distinct from Wildcat's orange
const _kPanelWidth = 360.0;
const _kMaxAreaKm2 = 700.0;

const _kFixedI15 = [16.0, 20.0, 24.0, 40.0];
const _kScenarioLabels = ['16 mm/hr', '20 mm/hr', '24 mm/hr', '40 mm/hr'];

// ---------------------------------------------------------------------------
// Screen state
// ---------------------------------------------------------------------------

enum _Step {
  upload,           // pick file + name/year/date
  uploading,        // POSTing the file
  downloading,      // GEE DEM+dNBR prep running
  downloadFailed,
  configure,        // pick rainfall scenario, run Wildcat
  running,          // Wildcat pipeline running
  fusing,           // MHRI fusion request running
  results,          // both layers ready
}

enum _Layer { debrisFlow, mhri }

class MhriFusionScreen extends StatefulWidget {
  const MhriFusionScreen({super.key});

  @override
  State<MhriFusionScreen> createState() => _MhriFusionScreenState();
}

class _MhriFusionScreenState extends State<MhriFusionScreen>
    with TickerProviderStateMixin {
  static final String _base = AppConfig.backendUrl;

  final MapController _mapCtrl = MapController();
  final TextEditingController _nameCtrl = TextEditingController(text: 'My AOI');
  final TextEditingController _yearCtrl = TextEditingController(
      text: DateTime.now().year.toString());
  final TextEditingController _dateCtrl = TextEditingController(
      text: '${DateTime.now().year}-07-01');

  _Step _step = _Step.upload;

  // ── Upload state ───────────────────────────────────────────────────────────
  PlatformFile? _pickedFile;
  String? _selectedCityShapefile; // key into _kCaCityShapefiles, if chosen from the catalog
  bool _loadingCityShapefile = false;
  String? _uploadError;
  String? _fireId;
  double? _aoiAreaKm2;
  bool _inMhriCoverage = false;
  double? _historicalBurnPct;
  List<dynamic> _historicalFireMatches = [];

  // ── GEE prep state ─────────────────────────────────────────────────────────
  String? _prepJobId;
  int _prepProgress = 0;
  String _prepMessage = '';
  String? _prepError;
  Timer? _prepTimer;

  // ── Wildcat run state ───────────────────────────────────────────────────────
  String? _jobId;
  int _progress = 0;
  String _stepMsg = '';
  String? _runError;
  Timer? _pollTimer;

  // ── Results ─────────────────────────────────────────────────────────────────
  ParsedGeoJson? _basins;        // debris-flow catchments (P_0..P_3)
  ParsedGeoJson? _mhriCells;     // MHRI 1km grid cells
  ParsedGeoJson? _perimeter;     // uploaded AOI boundary outline
  List<String> _mhriCounties = [];
  int? _mhriCellCount;
  String? _mhriError;
  Map<String, dynamic> _paramMetadata = {}; // param key -> {name, unit, category}
  int _scenario = 0;             // shared rainfall-scenario index for both layers
  _Layer _layer = _Layer.debrisFlow;
  int? _selectedBasinIdx;
  int? _selectedCellIdx;
  bool _useSatellite = true;

  final LayerHitNotifier<Object> _hitNotifier = ValueNotifier(null);

  late final AnimationController _pulse;
  late final Animation<double> _pulseAnim;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(
        duration: const Duration(milliseconds: 1500), vsync: this)
      ..repeat(reverse: true);
    _pulseAnim = Tween<double>(begin: 0.55, end: 1.0).animate(
        CurvedAnimation(parent: _pulse, curve: Curves.easeInOut));
  }

  @override
  void dispose() {
    _prepTimer?.cancel();
    _pollTimer?.cancel();
    _pulse.dispose();
    _nameCtrl.dispose();
    _yearCtrl.dispose();
    _dateCtrl.dispose();
    _hitNotifier.dispose();
    super.dispose();
  }

  // ---------------------------------------------------------------------------
  // Network: upload → prepare → analyze → mhri fusion
  // ---------------------------------------------------------------------------

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['geojson', 'json', 'zip'],
    );
    if (result != null && result.files.isNotEmpty) {
      setState(() {
        _pickedFile = result.files.first;
        _selectedCityShapefile = null; // manual pick overrides any catalog choice
        _uploadError = null;
      });
    }
  }

  /// Loads a bundled California-city Shapefile from assets and feeds it into
  /// the same `_pickedFile` slot a manual upload would use, so `_upload()`
  /// doesn't need to know or care where the bytes came from.
  Future<void> _selectCityShapefile(String? key) async {
    if (key == null) {
      setState(() { _selectedCityShapefile = null; _pickedFile = null; });
      return;
    }
    setState(() { _loadingCityShapefile = true; _selectedCityShapefile = key; _uploadError = null; });
    try {
      final data = await rootBundle.load('assets/CA_city_shapefiles/$key');
      final bytes = data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes);
      if (!mounted) return;
      setState(() {
        _pickedFile = PlatformFile(name: key, size: bytes.length, bytes: bytes);
        _nameCtrl.text = _kCaCityShapefiles[key] ?? key;
        _loadingCityShapefile = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _uploadError = 'Failed to load $key: $e';
        _selectedCityShapefile = null;
        _loadingCityShapefile = false;
      });
    }
  }

  Future<void> _upload() async {
    final file = _pickedFile;
    if (file == null || file.bytes == null) {
      setState(() => _uploadError = 'Pick a .geojson or zipped .shp file first.');
      return;
    }
    setState(() {
      _step = _Step.uploading; _uploadError = null;
      // Clear any previous AOI's results -- otherwise a re-upload without
      // explicitly hitting "Start a new AOI" leaves stale basins/MHRI cells
      // rendered on the map underneath this one.
      _basins = null; _mhriCells = null; _perimeter = null;
      _selectedBasinIdx = null; _selectedCellIdx = null; _paramMetadata = {};
      _historicalBurnPct = null; _historicalFireMatches = [];
    });
    try {
      final req = http.MultipartRequest(
          'POST', Uri.parse('$_base/wildcat/fires/upload'))
        ..fields['name'] = _nameCtrl.text.trim().isEmpty ? 'My AOI' : _nameCtrl.text.trim()
        ..fields['year'] = _yearCtrl.text.trim()
        ..fields['fire_date'] = _dateCtrl.text.trim()
        ..files.add(http.MultipartFile.fromBytes('file', file.bytes!, filename: file.name));
      final streamed = await req.send();
      final resp = await http.Response.fromStream(streamed);

      if (resp.statusCode == 200) {
        final data = json.decode(resp.body) as Map<String, dynamic>;
        setState(() {
          _fireId                = data['id'] as String;
          _aoiAreaKm2            = (data['area_km2'] as num?)?.toDouble();
          _inMhriCoverage        = data['in_mhri_coverage'] as bool? ?? false;
          _historicalBurnPct     = (data['historical_burn_pct'] as num?)?.toDouble();
          _historicalFireMatches = data['historical_fire_matches'] as List<dynamic>? ?? [];
          _step                  = _Step.downloading;
        });
      } else {
        final detail = _safeDetail(resp.body);
        setState(() { _uploadError = detail; _step = _Step.upload; });
      }
    } catch (e) {
      setState(() { _uploadError = e.toString(); _step = _Step.upload; });
    }
  }

  Future<void> _startPrep() async {
    _prepTimer?.cancel();
    setState(() { _prepProgress = 0; _prepMessage = 'Starting GEE data prep...'; _prepError = null; });
    try {
      final resp = await http.post(
        Uri.parse('$_base/wildcat/fires/$_fireId/prepare'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({}),
      );
      if (resp.statusCode == 200) {
        final data = json.decode(resp.body);
        if (data['already_ready'] == true) {
          setState(() => _step = _Step.configure);
          return;
        }
        _prepJobId = data['job_id'] as String;
        _prepTimer = Timer.periodic(const Duration(milliseconds: 2000), (_) => _pollPrep());
      } else {
        setState(() { _prepError = _safeDetail(resp.body); _step = _Step.downloadFailed; });
      }
    } catch (e) {
      setState(() { _prepError = e.toString(); _step = _Step.downloadFailed; });
    }
  }

  Future<void> _pollPrep() async {
    if (_prepJobId == null) return;
    try {
      final resp = await http.get(Uri.parse('$_base/wildcat/prepare/status/$_prepJobId'));
      if (resp.statusCode != 200 || !mounted) return;
      final data = json.decode(resp.body) as Map<String, dynamic>;
      final status = data['status'] as String? ?? 'running';
      if (status == 'completed') {
        _prepTimer?.cancel();
        setState(() => _step = _Step.configure);
      } else if (status == 'failed') {
        _prepTimer?.cancel();
        setState(() { _prepError = data['error'] ?? 'Data prep failed'; _step = _Step.downloadFailed; });
      } else {
        setState(() {
          _prepProgress = (data['progress'] as num?)?.toInt() ?? _prepProgress;
          _prepMessage  = data['message'] as String? ?? '';
        });
      }
    } catch (_) {}
  }

  Future<void> _runWildcat() async {
    _pollTimer?.cancel();
    setState(() {
      _step = _Step.running; _jobId = null; _progress = 0; _runError = null;
      _stepMsg = 'Starting Wildcat pipeline...';
    });
    try {
      final resp = await http.post(
        Uri.parse('$_base/wildcat/fires/$_fireId/analyze'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'force': false,
          'settings': {'I15_mm_hr': _kFixedI15, 'kf': 0.2, 'min_slope': 0.12,
            'min_burn_ratio': 0.25, 'min_area_km2': 0.025, 'locate_basins': true,
            'buffer_km': 3.0, 'severity_thresholds': [125.0, 250.0, 500.0]},
        }),
      );
      if (resp.statusCode != 200) {
        setState(() { _runError = _safeDetail(resp.body); _step = _Step.configure; });
        return;
      }
      final data = json.decode(resp.body);
      if (data['cached'] == true) {
        await _loadDebrisFlowResults();
        return;
      }
      _jobId = data['job_id'] as String;
      _pollTimer = Timer.periodic(const Duration(milliseconds: 2000), (_) => _pollAnalyze());
    } catch (e) {
      setState(() { _runError = e.toString(); _step = _Step.configure; });
    }
  }

  Future<void> _pollAnalyze() async {
    if (_jobId == null) return;
    try {
      final resp = await http.get(Uri.parse('$_base/wildcat/analyze/status/$_jobId'));
      if (resp.statusCode != 200 || !mounted) return;
      final data = json.decode(resp.body) as Map<String, dynamic>;
      final status = data['status'] as String? ?? 'running';
      if (status == 'completed') {
        _pollTimer?.cancel();
        await _loadDebrisFlowResults();
      } else if (status == 'failed') {
        _pollTimer?.cancel();
        setState(() { _runError = data['error'] ?? 'Unknown error'; _step = _Step.configure; });
      } else {
        setState(() {
          _progress = (data['progress'] as num?)?.toInt() ?? _progress;
          _stepMsg  = data['message'] as String? ?? '';
        });
      }
    } catch (_) {}
  }

  Future<void> _loadDebrisFlowResults() async {
    try {
      final resp = await http.get(Uri.parse('$_base/wildcat/fires/$_fireId/results'));
      if (resp.statusCode == 200 && mounted) {
        setState(() => _basins = parseGeoJson(json.decode(resp.body) as Map<String, dynamic>));
        unawaited(_loadPerimeter());
        if (_inMhriCoverage) {
          await _loadMhriFusion();
        } else {
          setState(() => _step = _Step.results);
        }
        _fitToResults();
      }
    } catch (e) {
      setState(() { _runError = e.toString(); _step = _Step.configure; });
    }
  }

  /// Fetches the AOI's own boundary so it can be outlined on the map under
  /// both the debris-flow and MHRI layers — independent of MHRI coverage.
  Future<void> _loadPerimeter() async {
    try {
      final resp = await http.get(Uri.parse('$_base/wildcat/fires/$_fireId/perimeter'));
      if (resp.statusCode == 200 && mounted) {
        setState(() => _perimeter = parseGeoJson(json.decode(resp.body) as Map<String, dynamic>));
      }
    } catch (_) {}
  }

  Future<void> _loadMhriFusion() async {
    setState(() { _step = _Step.fusing; _mhriError = null; });
    try {
      final resp = await http.get(
          Uri.parse('$_base/mhri/fires/$_fireId/results?i15_index=$_scenario'));
      if (resp.statusCode == 200 && mounted) {
        final data = json.decode(resp.body) as Map<String, dynamic>;
        setState(() {
          _mhriCells     = parseGeoJson(data['mhri_grid'] as Map<String, dynamic>);
          _mhriCounties  = (data['counties'] as List).cast<String>();
          _mhriCellCount = (data['cell_count'] as num?)?.toInt();
          _paramMetadata = (data['param_metadata'] as Map?)?.cast<String, dynamic>() ?? {};
          _step          = _Step.results;
        });
      } else if (mounted) {
        setState(() { _mhriError = _safeDetail(resp.body); _step = _Step.results; });
      }
    } catch (e) {
      setState(() { _mhriError = e.toString(); _step = _Step.results; });
    }
  }

  void _changeScenario(int i) {
    setState(() { _scenario = i; _selectedBasinIdx = null; _selectedCellIdx = null; });
    if (_inMhriCoverage) _loadMhriFusion();
  }

  String _safeDetail(String body) {
    try {
      final d = json.decode(body);
      return d['detail']?.toString() ?? body;
    } catch (_) {
      return body;
    }
  }

  void _fitToResults() {
    final feats = _basins?.features ?? [];
    double? minLat, maxLat, minLon, maxLon;
    for (final f in feats) {
      for (final ring in f.rings) {
        for (final pt in ring) {
          minLat = minLat == null ? pt.latitude  : math.min(minLat, pt.latitude);
          maxLat = maxLat == null ? pt.latitude  : math.max(maxLat, pt.latitude);
          minLon = minLon == null ? pt.longitude : math.min(minLon, pt.longitude);
          maxLon = maxLon == null ? pt.longitude : math.max(maxLon, pt.longitude);
        }
      }
    }
    if (minLat == null) return;
    final b = LatLngBounds(LatLng(minLat, minLon!), LatLng(maxLat!, maxLon!));
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _mapCtrl.fitCamera(CameraFit.bounds(bounds: b, padding: const EdgeInsets.all(52)));
    });
  }

  // ---------------------------------------------------------------------------
  // Colors
  // ---------------------------------------------------------------------------

  Color _probColor(double p) {
    if (p < 0.25) return Colors.green.shade700;
    if (p < 0.50) return Colors.yellow.shade700;
    if (p < 0.75) return Colors.orange.shade700;
    return Colors.red.shade700;
  }

  Color _mhriColor(double score) {
    // MHRI is a 0-100ish composite score (cube root of normalized H*E*S/AC).
    if (score < 25) return Colors.green.shade700;
    if (score < 40) return Colors.yellow.shade700;
    if (score < 55) return Colors.orange.shade700;
    return Colors.red.shade900;
  }

  // ---------------------------------------------------------------------------
  // Build
  // ---------------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF080A0E),
      appBar: _buildAppBar(),
      body: Row(children: [
        Container(
          width: _kPanelWidth,
          decoration: const BoxDecoration(
            color: Color(0xFF0C0E14),
            border: Border(right: BorderSide(color: Color(0xFF1A1F2A))),
          ),
          child: _buildPanel(),
        ),
        Expanded(child: _buildMap()),
      ]),
    );
  }

  PreferredSizeWidget _buildAppBar() => AppBar(
    backgroundColor: const Color(0xFF0A0C10),
    automaticallyImplyLeading: false,
    title: Row(children: [
      Container(
        padding: const EdgeInsets.all(6),
        decoration: BoxDecoration(
          color: _kAccent.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(6),
        ),
        child: const Icon(Icons.layers_outlined, color: _kAccent, size: 18),
      ),
      const SizedBox(width: 10),
      const Text('Wildcat × MHRI Fusion',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 16)),
      const SizedBox(width: 10),
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
        decoration: BoxDecoration(
          color: _kAccent.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(4),
          border: Border.all(color: _kAccent.withValues(alpha: 0.40)),
        ),
        child: const Text('ASBPA',
            style: TextStyle(fontFamily: 'monospace', fontSize: 9,
                color: _kAccent, letterSpacing: 1.0)),
      ),
    ]),
  );

  // ---------------------------------------------------------------------------
  // Panel routing
  // ---------------------------------------------------------------------------

  Widget _buildPanel() => switch (_step) {
    _Step.upload         => _panelUpload(),
    _Step.uploading       => _panelBusy('Uploading AOI...', Icons.cloud_upload_outlined),
    _Step.downloading    => _panelDownloading(),
    _Step.downloadFailed => _panelDownloadFailed(),
    _Step.configure      => _panelConfigure(),
    _Step.running        => _panelRunning(),
    _Step.fusing         => _panelBusy('Fusing into MHRI grid...', Icons.grid_on),
    _Step.results        => _panelResults(),
  };

  Widget _panelBusy(String label, IconData icon) => Center(
    child: Column(mainAxisSize: MainAxisSize.min, children: [
      AnimatedBuilder(
        animation: _pulseAnim,
        builder: (_, __) => Opacity(opacity: _pulseAnim.value, child: Icon(icon, color: _kAccent, size: 44)),
      ),
      const SizedBox(height: 18),
      Text(label, style: const TextStyle(color: Colors.white54)),
      const SizedBox(height: 12),
      const CircularProgressIndicator(color: _kAccent, strokeWidth: 2),
    ]),
  );

  // ── Upload ───────────────────────────────────────────────────────────────

  Widget _panelUpload() => SingleChildScrollView(
    padding: const EdgeInsets.all(20),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _sectionLabel('Step 1 of 4', Icons.upload_file),
      const SizedBox(height: 6),
      const Text('Upload Your Area of Interest',
          style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700)),
      const SizedBox(height: 6),
      Text('Draw your AOI in QGIS/ArcGIS/geojson.io and upload it here as a '
          '.geojson or a zipped Shapefile. Maximum area: ${_kMaxAreaKm2.toStringAsFixed(0)} km².',
          style: const TextStyle(color: Colors.white38, fontSize: 11, height: 1.5)),
      const SizedBox(height: 20),

      _subLabel('Select a California City (optional)'),
      const SizedBox(height: 8),
      _citySelector(),
      const SizedBox(height: 16),
      const Center(
        child: Text('OR',
            style: TextStyle(color: Colors.white70, fontSize: 13, fontWeight: FontWeight.bold,
                decoration: TextDecoration.underline, letterSpacing: 1.2)),
      ),
      const SizedBox(height: 16),

      GestureDetector(
        onTap: _pickFile,
        child: Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: const Color(0xFF141820),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: _pickedFile != null
                  ? _kAccent.withValues(alpha: 0.55)
                  : Colors.white.withValues(alpha: 0.10),
              style: BorderStyle.solid,
            ),
          ),
          child: Column(children: [
            Icon(_pickedFile != null ? Icons.check_circle_outline : Icons.add_circle_outline,
                color: _pickedFile != null ? _kAccent : Colors.white38, size: 28),
            const SizedBox(height: 8),
            Text(_pickedFile?.name ?? 'Tap to choose a .geojson/.json/.zip file',
                style: TextStyle(color: _pickedFile != null ? Colors.white : Colors.white38, fontSize: 12),
                textAlign: TextAlign.center),
          ]),
        ),
      ),
      const SizedBox(height: 20),

      _subLabel('AOI Name'),
      const SizedBox(height: 8),
      _textField(_nameCtrl, 'e.g. Refugio Canyon Study Area'),
      const SizedBox(height: 14),
      _subLabel('Year'),
      const SizedBox(height: 8),
      _textField(_yearCtrl, 'e.g. 2024'),
      const SizedBox(height: 14),
      _subLabel('Fire / Burn Date (YYYY-MM-DD)'),
      const SizedBox(height: 8),
      _textField(_dateCtrl, 'e.g. 2024-07-01'),

      if (_uploadError != null) ...[
        const SizedBox(height: 14),
        _buildErrorBanner(_uploadError!),
      ],

      const SizedBox(height: 24),
      SizedBox(width: double.infinity, child: ElevatedButton(
        style: ElevatedButton.styleFrom(
          backgroundColor: _kAccent,
          padding: const EdgeInsets.symmetric(vertical: 13),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
        onPressed: _upload,
        child: const Text('Upload AOI  →', style: TextStyle(color: Colors.black, fontWeight: FontWeight.w700)),
      )),
    ]),
  );

  Widget _citySelector() => DropdownButtonFormField<String>(
    initialValue: _selectedCityShapefile,
    isExpanded: true,
    dropdownColor: const Color(0xFF141820),
    icon: _loadingCityShapefile
        ? const SizedBox(width: 14, height: 14,
            child: CircularProgressIndicator(strokeWidth: 2, color: _kAccent))
        : const Icon(Icons.arrow_drop_down, color: Colors.white54),
    hint: const Text('Choose from 15 preloaded city shapefiles...',
        style: TextStyle(color: Colors.white30, fontSize: 12)),
    style: const TextStyle(color: Colors.white, fontSize: 12),
    decoration: InputDecoration(
      filled: true, fillColor: const Color(0xFF141820),
      border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: BorderSide(color: _kAccent.withValues(alpha: 0.25))),
      enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: Color(0xFF2A2F3A))),
      focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: BorderSide(color: _kAccent.withValues(alpha: 0.55))),
      contentPadding: const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
    ),
    items: _kCaCityShapefiles.entries
        .map((e) => DropdownMenuItem(value: e.key, child: Text(e.value, overflow: TextOverflow.ellipsis)))
        .toList(),
    onChanged: _loadingCityShapefile ? null : _selectCityShapefile,
  );

  Widget _textField(TextEditingController ctrl, String hint) => TextField(
    controller: ctrl,
    style: const TextStyle(color: Colors.white, fontSize: 12),
    decoration: InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(color: Colors.white30, fontSize: 12),
      filled: true, fillColor: const Color(0xFF141820),
      border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: BorderSide(color: _kAccent.withValues(alpha: 0.25))),
      enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: Color(0xFF2A2F3A))),
      focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: BorderSide(color: _kAccent.withValues(alpha: 0.55))),
      contentPadding: const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
    ),
  );

  // ── GEE download ─────────────────────────────────────────────────────────

  Widget _panelDownloading() {
    final started = _prepJobId != null;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _sectionLabel('Step 2 of 4', Icons.cloud_download_outlined),
        const SizedBox(height: 6),
        const Text('Data Download', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        _aoiSummaryChip(),
        if (_historicalBurnPct != null) ...[
          const SizedBox(height: 10),
          _burnHistoryBanner(),
        ],
        const SizedBox(height: 14),
        const Text('Fetches the USGS 3DEP 10m DEM and computes dNBR (Landsat) for your AOI.',
            style: TextStyle(color: Colors.white38, fontSize: 11, height: 1.5)),
        const SizedBox(height: 20),

        if (!started) ...[
          const Text('The backend will use the configured Earth Engine project for this deployment.',
              style: TextStyle(color: Colors.white38, fontSize: 11, height: 1.5)),
          const SizedBox(height: 24),
        ],
        if (started) ...[
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: _prepProgress / 100,
              backgroundColor: const Color(0xFF1A1F2A),
              valueColor: const AlwaysStoppedAnimation(_kAccent),
              minHeight: 6,
            ),
          ),
          const SizedBox(height: 8),
          Text(_prepMessage, style: const TextStyle(color: Colors.white54, fontSize: 11, height: 1.4)),
          const SizedBox(height: 24),
        ],

        Row(children: [
          Expanded(child: OutlinedButton(
            style: OutlinedButton.styleFrom(
              side: const BorderSide(color: Color(0xFF2A2F3A)),
              padding: const EdgeInsets.symmetric(vertical: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () => setState(() { _prepTimer?.cancel(); _prepJobId = null; _step = _Step.upload; }),
            child: const Text('← Back', style: TextStyle(color: Colors.white54)),
          )),
          const SizedBox(width: 10),
          Expanded(flex: 2, child: ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: _kAccent,
              padding: const EdgeInsets.symmetric(vertical: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: started ? null : _startPrep,
            child: Text(started ? 'Downloading...' : 'Start GEE Download  →',
                style: const TextStyle(color: Colors.black, fontWeight: FontWeight.w700)),
          )),
        ]),
      ]),
    );
  }

  Widget _panelDownloadFailed() => Padding(
    padding: const EdgeInsets.all(20),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _sectionLabel('Download Failed', Icons.error_outline),
      const SizedBox(height: 12),
      _buildErrorBanner(_prepError ?? 'Unknown error'),
      const SizedBox(height: 20),
      SizedBox(width: double.infinity, child: ElevatedButton(
        style: ElevatedButton.styleFrom(
          backgroundColor: _kAccent,
          padding: const EdgeInsets.symmetric(vertical: 12),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
        onPressed: () => setState(() { _prepJobId = null; _step = _Step.downloading; }),
        child: const Text('Retry download', style: TextStyle(color: Colors.black, fontWeight: FontWeight.w700)),
      )),
    ]),
  );

  // ── Configure ────────────────────────────────────────────────────────────

  Widget _panelConfigure() => SingleChildScrollView(
    padding: const EdgeInsets.all(20),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _sectionLabel('Step 3 of 4', Icons.tune),
      const SizedBox(height: 6),
      const Text('Run Wildcat', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700)),
      const SizedBox(height: 8),
      _aoiSummaryChip(),
      if (_runError != null) ...[const SizedBox(height: 12), _buildErrorBanner(_runError!)],
      const SizedBox(height: 16),
      const Text(
        'Wildcat models post-fire debris-flow probability per catchment for four '
        'fixed rainfall intensities. After it runs, the same I₁₅ scenario you pick '
        'on the results screen also drives the live MHRI fusion (a8 indicator).',
        style: TextStyle(color: Colors.white38, fontSize: 11, height: 1.5),
      ),
      const SizedBox(height: 24),
      SizedBox(width: double.infinity, child: ElevatedButton(
        style: ElevatedButton.styleFrom(
          backgroundColor: _kAccent,
          padding: const EdgeInsets.symmetric(vertical: 13),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
        onPressed: _runWildcat,
        child: const Text('Run Wildcat  →', style: TextStyle(color: Colors.black, fontWeight: FontWeight.w700)),
      )),
    ]),
  );

  // ── Running ──────────────────────────────────────────────────────────────

  Widget _panelRunning() => Padding(
    padding: const EdgeInsets.all(20),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _sectionLabel('Step 4 of 4', Icons.settings_outlined),
      const SizedBox(height: 6),
      const Text('Running Wildcat', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700)),
      const SizedBox(height: 20),
      ClipRRect(
        borderRadius: BorderRadius.circular(4),
        child: LinearProgressIndicator(
          value: _progress / 100,
          backgroundColor: const Color(0xFF1A1F2A),
          valueColor: const AlwaysStoppedAnimation(_kAccent),
          minHeight: 6,
        ),
      ),
      const SizedBox(height: 8),
      Text(_stepMsg, style: const TextStyle(color: Colors.white38, fontSize: 11)),
    ]),
  );

  // ── Results ──────────────────────────────────────────────────────────────

  Widget _panelResults() {
    final selectedBasin = (_selectedBasinIdx != null && _basins != null)
        ? _basins!.features[_selectedBasinIdx!] : null;
    final selectedCell = (_selectedCellIdx != null && _mhriCells != null)
        ? _mhriCells!.features[_selectedCellIdx!] : null;

    return Column(children: [
      Container(
        padding: const EdgeInsets.all(14),
        decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: Color(0xFF1A1F2A)))),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          _sectionLabel('Results', Icons.map_outlined),
          const SizedBox(height: 8),
          _aoiSummaryChip(),
          const SizedBox(height: 12),

          // Layer toggle
          Row(children: [
            Expanded(child: _layerTab('Debris-flow', Icons.water_drop_outlined, _Layer.debrisFlow)),
            const SizedBox(width: 8),
            Expanded(child: _layerTab('MHRI grid', Icons.grid_on, _Layer.mhri)),
          ]),
          const SizedBox(height: 12),

          // Rainfall scenario tabs (drives both layers)
          Text('RAINFALL SCENARIO (I₁₅)', style: TextStyle(
              color: _kAccent.withValues(alpha: 0.65), fontSize: 9, fontFamily: 'monospace', letterSpacing: 1.0)),
          const SizedBox(height: 6),
          Wrap(spacing: 6, runSpacing: 6, children: List.generate(_kFixedI15.length, (i) {
            final sel = i == _scenario;
            return GestureDetector(
              onTap: () => _changeScenario(i),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 140),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: sel ? _kAccent.withValues(alpha: 0.18) : const Color(0xFF141820),
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: sel ? _kAccent : Colors.white.withValues(alpha: 0.12)),
                ),
                child: Text(_kScenarioLabels[i],
                    style: TextStyle(color: sel ? _kAccent : Colors.white54, fontSize: 10, fontFamily: 'monospace')),
              ),
            );
          })),

          if (!_inMhriCoverage) ...[
            const SizedBox(height: 10),
            _infoBanner('AOI is outside the ASBPA 60-county coverage area — '
                'debris-flow results only, no MHRI fusion for this location.'),
          ],
          if (_mhriError != null) ...[
            const SizedBox(height: 10),
            _buildErrorBanner('MHRI fusion: $_mhriError'),
          ],
          if (_layer == _Layer.mhri && _mhriCellCount != null) ...[
            const SizedBox(height: 10),
            Text('$_mhriCellCount cells  ·  ${_mhriCounties.join(', ')}',
                style: const TextStyle(color: Colors.white38, fontSize: 10)),
          ],
        ]),
      ),

      Expanded(
        child: selectedBasin != null && _layer == _Layer.debrisFlow
            ? _basinDetail(selectedBasin)
            : selectedCell != null && _layer == _Layer.mhri
                ? _cellDetail(selectedCell)
                : Center(
                    child: Column(mainAxisSize: MainAxisSize.min, children: [
                      Icon(Icons.touch_app, color: _kAccent.withValues(alpha: 0.4), size: 36),
                      const SizedBox(height: 12),
                      Text('Tap a ${_layer == _Layer.debrisFlow ? "catchment" : "1km cell"} on the map',
                          style: const TextStyle(color: Colors.white54, fontSize: 13, fontWeight: FontWeight.w600)),
                    ]),
                  ),
      ),

      Padding(
        padding: const EdgeInsets.all(14),
        child: SizedBox(width: double.infinity, child: OutlinedButton(
          style: OutlinedButton.styleFrom(
            side: BorderSide(color: _kAccent.withValues(alpha: 0.35)),
            padding: const EdgeInsets.symmetric(vertical: 11),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          ),
          onPressed: () => setState(() {
            _step = _Step.upload; _basins = null; _mhriCells = null; _perimeter = null;
            _selectedBasinIdx = null; _selectedCellIdx = null; _fireId = null;
            _pickedFile = null; _selectedCityShapefile = null; _paramMetadata = {};
            _historicalBurnPct = null; _historicalFireMatches = [];
          }),
          child: const Text('← Start a new AOI', style: TextStyle(color: _kAccent, fontSize: 13)),
        )),
      ),
    ]);
  }

  Widget _layerTab(String label, IconData icon, _Layer layer) {
    final sel = _layer == layer;
    final disabled = layer == _Layer.mhri && !_inMhriCoverage;
    return GestureDetector(
      onTap: disabled ? null : () => setState(() => _layer = layer),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(vertical: 9),
        decoration: BoxDecoration(
          color: sel ? _kAccent.withValues(alpha: 0.18) : const Color(0xFF141820),
          borderRadius: BorderRadius.circular(7),
          border: Border.all(color: sel ? _kAccent : Colors.white.withValues(alpha: 0.10)),
        ),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 16, color: disabled ? Colors.white24 : (sel ? _kAccent : Colors.white54)),
          const SizedBox(height: 3),
          Text(label, style: TextStyle(
              fontSize: 10, color: disabled ? Colors.white24 : (sel ? _kAccent : Colors.white54))),
        ]),
      ),
    );
  }

  String _riskLabel(double p) {
    if (p >= 0.60) return 'HIGH';
    if (p >= 0.40) return 'MODERATE';
    if (p >= 0.20) return 'LOW';
    return 'VERY LOW';
  }

  Color _hazardClassColor(int h) {
    const c = [Color(0xFF4CAF50), Color(0xFFFFC107), Color(0xFFFF5722), Color(0xFFB71C1C)];
    return c[h.clamp(0, 3)];
  }

  String _fmtVolume(double v) {
    if (v >= 1e6) return '${(v / 1e6).toStringAsFixed(2)}M m³';
    if (v >= 1000) return '${(v / 1000).toStringAsFixed(1)}k m³';
    return '${v.toStringAsFixed(0)} m³';
  }

  Widget _basinDetail(SubBasinFeature feat) {
    final props = feat.properties;
    final area     = (props['Area_km2']  as num?)?.toDouble();
    final burn     = (props['BurnRatio'] as num?)?.toDouble();
    final slope    = (props['Slope']     as num?)?.toDouble();
    final extRatio = (props['ExtRatio']  as num?)?.toDouble();
    final relief   = (props['Relief_m']  as num?)?.toDouble();
    final p = (props['P_$_scenario'] as num?)?.toDouble() ?? 0.0;
    final v = (props['V_$_scenario'] as num?)?.toDouble();
    final h = (props['H_$_scenario'] as num?)?.toInt();
    final col = _probColor(p);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text('Catchment ${props['Segment_ID'] ?? feat.label}',
              style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold))),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
            decoration: BoxDecoration(
              color: col.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(7),
              border: Border.all(color: col.withValues(alpha: 0.5)),
            ),
            child: Text(_riskLabel(p), style: TextStyle(color: col, fontSize: 10, fontWeight: FontWeight.bold)),
          ),
        ]),
        if (area != null) Text('${area.toStringAsFixed(3)} km²  ·  ${_kScenarioLabels[_scenario]}',
            style: const TextStyle(color: Colors.white38, fontSize: 11)),
        const SizedBox(height: 14),

        IntrinsicHeight(
          child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Expanded(child: _statCard('Probability', '${(p * 100).toStringAsFixed(1)}%', col)),
            if (v != null) ...[
              const SizedBox(width: 8),
              Expanded(child: _statCard('Volume', _fmtVolume(v), Colors.blueAccent)),
            ],
            if (h != null) ...[
              const SizedBox(width: 8),
              Expanded(child: _statCard('Hazard', 'Class $h', _hazardClassColor(h))),
            ],
          ]),
        ),
        const SizedBox(height: 14),

        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          const Text('P(debris flow)', style: TextStyle(color: Colors.white54, fontSize: 11)),
          Text('${(p * 100).toStringAsFixed(1)}%',
              style: TextStyle(color: col, fontFamily: 'monospace', fontSize: 11, fontWeight: FontWeight.bold)),
        ]),
        const SizedBox(height: 5),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: p.clamp(0.0, 1.0), backgroundColor: Colors.white.withValues(alpha: 0.07),
            valueColor: AlwaysStoppedAnimation(col), minHeight: 8,
          ),
        ),

        const SizedBox(height: 16),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.03),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: Colors.white.withValues(alpha: 0.07)),
          ),
          child: Wrap(spacing: 16, runSpacing: 10, children: [
            if (area != null)     _propChip('Area', '${area.toStringAsFixed(3)} km²'),
            if (burn != null)     _propChip('Burn ratio', burn.toStringAsFixed(3)),
            if (slope != null)    _propChip('Slope', '${slope.toStringAsFixed(3)} rad'),
            if (extRatio != null) _propChip('Ext. ratio', extRatio.toStringAsFixed(4)),
            if (relief != null)   _propChip('Relief', '${relief.toStringAsFixed(1)} m'),
          ]),
        ),
        const SizedBox(height: 10),
        const Text('Staley (2017) M1  ·  Gartner (2014)  ·  WhiteboxTools D8',
            style: TextStyle(color: Colors.white24, fontSize: 9, height: 1.4)),
      ]),
    );
  }

  Widget _propChip(String label, String value) => SizedBox(
    width: 130,
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label.toUpperCase(),
          style: TextStyle(color: _kAccent.withValues(alpha: 0.55), fontSize: 8, fontFamily: 'monospace', letterSpacing: 0.8)),
      const SizedBox(height: 3),
      Text(value, style: const TextStyle(color: Colors.white70, fontSize: 11, fontWeight: FontWeight.w600, fontFamily: 'monospace')),
    ]),
  );

  Widget _cellDetail(SubBasinFeature feat) {
    final props = feat.properties;
    final mhri = (props['MHRI'] as num?)?.toDouble() ?? 0.0;
    final h  = (props['H']  as num?)?.toDouble();
    final e  = (props['E']  as num?)?.toDouble();
    final s  = (props['S']  as num?)?.toDouble();
    final ac = (props['AC'] as num?)?.toDouble();
    final a8Src = props['a8_source']?.toString() ?? 'unknown';
    final col = _mhriColor(mhri);
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(props['county']?.toString() ?? '1km cell',
            style: const TextStyle(color: Colors.white38, fontSize: 11)),
        const SizedBox(height: 4),
        const Text('MHRI Cell', style: TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold)),
        const SizedBox(height: 14),
        _statCard('MHRI score', mhri.toStringAsFixed(1), col),
        const SizedBox(height: 10),
        if (h != null)  _categoryBar('Hazard (H)', h, Colors.redAccent),
        if (e != null)  _categoryBar('Exposure (E)', e, Colors.amber),
        if (s != null)  _categoryBar('Susceptibility (S)', s, Colors.blueAccent),
        if (ac != null) _categoryBar('Adaptive capacity (AC)', ac, Colors.greenAccent),
        const SizedBox(height: 6),
        Text('a8 debris-flow source: ${a8Src == "wildcat_live" ? "live Wildcat catchment" : "static ASBPA county raster"}',
            style: TextStyle(color: _kAccent.withValues(alpha: 0.7), fontSize: 10, height: 1.4)),

        const SizedBox(height: 18),
        const Divider(color: Color(0xFF1A1F2A)),
        const SizedBox(height: 6),
        Text('PARAMETER BREAKDOWN', style: TextStyle(
            color: _kAccent.withValues(alpha: 0.65), fontSize: 9, fontFamily: 'monospace', letterSpacing: 1.0)),
        const SizedBox(height: 6),
        _categoryExpander('Hazard', 'H', h, Colors.redAccent, props),
        _categoryExpander('Exposure', 'E', e, Colors.amber, props),
        _categoryExpander('Susceptibility', 'S', s, Colors.blueAccent, props),
        _categoryExpander('Adaptive Capacity', 'AC', ac, Colors.greenAccent, props),
      ]),
    );
  }

  Widget _categoryExpander(
    String label, String catKey, double? catValue, Color color, Map<String, dynamic> props,
  ) {
    final entries = _paramMetadata.entries.where((e) => e.value['category'] == catKey).toList()
      ..sort((a, b) => (a.value['name'] ?? a.key).toString().compareTo((b.value['name'] ?? b.key).toString()));
    if (entries.isEmpty) return const SizedBox.shrink();

    return Theme(
      data: ThemeData.dark().copyWith(dividerColor: Colors.transparent),
      child: Container(
        margin: const EdgeInsets.only(bottom: 6),
        decoration: BoxDecoration(
          color: const Color(0xFF10141A),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withValues(alpha: 0.18)),
        ),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 12),
          childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 10),
          iconColor: color, collapsedIconColor: color.withValues(alpha: 0.6),
          title: Row(children: [
            Expanded(child: Text(label, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600))),
            if (catValue != null)
              Text(catValue.toStringAsFixed(2),
                  style: TextStyle(color: color, fontSize: 11, fontFamily: 'monospace')),
          ]),
          children: entries.map((entry) {
            final param = entry.key;
            final meta  = entry.value as Map;
            final raw   = (props['raw_$param']  as num?)?.toDouble();
            final norm  = (props['norm_$param'] as num?)?.toDouble();
            final name  = meta['name']?.toString() ?? param;
            final unit  = meta['unit']?.toString() ?? '';
            final isLiveA8 = param == 'a8_post_wildfire_debris_flow' &&
                props['a8_source'] == 'wildcat_live';
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                  Expanded(child: Text(
                    name + (isLiveA8 ? '  (live Wildcat)' : ''),
                    style: TextStyle(
                        color: isLiveA8 ? _kAccent : Colors.white60, fontSize: 10.5,
                        fontWeight: isLiveA8 ? FontWeight.w600 : FontWeight.normal),
                  )),
                  Text(
                    raw != null ? '${raw.toStringAsFixed(3)}${unit.isNotEmpty ? " $unit" : ""}' : '—',
                    style: const TextStyle(color: Colors.white70, fontSize: 10.5, fontFamily: 'monospace'),
                  ),
                ]),
                if (norm != null) ...[
                  const SizedBox(height: 3),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(3),
                    child: LinearProgressIndicator(
                      value: norm.clamp(0.0, 1.0), backgroundColor: Colors.white.withValues(alpha: 0.06),
                      valueColor: AlwaysStoppedAnimation(isLiveA8 ? _kAccent : color.withValues(alpha: 0.7)),
                      minHeight: 4,
                    ),
                  ),
                ],
              ]),
            );
          }).toList(),
        ),
      ),
    );
  }

  Widget _categoryBar(String label, double value, Color color) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text(label, style: const TextStyle(color: Colors.white60, fontSize: 11)),
        Text(value.toStringAsFixed(2), style: TextStyle(color: color, fontSize: 11, fontFamily: 'monospace')),
      ]),
      const SizedBox(height: 4),
      ClipRRect(
        borderRadius: BorderRadius.circular(3),
        child: LinearProgressIndicator(
          value: value.clamp(0.0, 1.0), backgroundColor: Colors.white.withValues(alpha: 0.07),
          valueColor: AlwaysStoppedAnimation(color), minHeight: 5,
        ),
      ),
    ]),
  );

  Widget _statCard(String label, String value, Color color) => Container(
    width: double.infinity,
    padding: const EdgeInsets.symmetric(vertical: 14),
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.10),
      borderRadius: BorderRadius.circular(10),
      border: Border.all(color: color.withValues(alpha: 0.30)),
    ),
    child: Column(children: [
      Text(label, style: TextStyle(color: color.withValues(alpha: 0.75), fontSize: 11, fontWeight: FontWeight.w600)),
      const SizedBox(height: 5),
      Text(value, style: TextStyle(color: color, fontSize: 22, fontWeight: FontWeight.bold)),
    ]),
  );

  // ---------------------------------------------------------------------------
  // Map
  // ---------------------------------------------------------------------------

  Widget _buildMap() => Stack(children: [
    FlutterMap(
      mapController: _mapCtrl,
      options: MapOptions(
        initialCenter: const LatLng(37.5, -119.5),
        initialZoom: 6.0,
        onTap: (_, __) {
          final hit = _hitNotifier.value;
          if (hit != null && hit.hitValues.isNotEmpty) {
            final idx = hit.hitValues.first as int;
            setState(() {
              if (_layer == _Layer.debrisFlow) {
                _selectedBasinIdx = idx;
              } else {
                _selectedCellIdx = idx;
              }
            });
          }
        },
      ),
      children: [
        TileLayer(
          urlTemplate: _useSatellite
              ? 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
              : 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          userAgentPackageName: 'com.example.fire_webapp2',
        ),
        if (_layer == _Layer.debrisFlow && _basins != null)
          PolygonLayer(polygons: _buildBasinPolygons(), hitNotifier: _hitNotifier),
        if (_layer == _Layer.mhri && _mhriCells != null)
          PolygonLayer(polygons: _buildCellPolygons(), hitNotifier: _hitNotifier),
        // AOI boundary outline — drawn on top of both layers, fill-less so
        // it never intercepts taps meant for basins/cells underneath.
        if (_perimeter != null)
          PolygonLayer(polygons: _buildPerimeterPolygons()),
      ],
    ),
    Positioned(
      top: 12, right: 12,
      child: GestureDetector(
        onTap: () => setState(() => _useSatellite = !_useSatellite),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
          decoration: BoxDecoration(
            color: const Color(0xCC0C0E14), borderRadius: BorderRadius.circular(6),
            border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(_useSatellite ? Icons.map : Icons.satellite, color: Colors.white70, size: 15),
            const SizedBox(width: 6),
            Text(_useSatellite ? 'Topo' : 'Satellite', style: const TextStyle(color: Colors.white70, fontSize: 11)),
          ]),
        ),
      ),
    ),
  ]);

  List<Polygon> _buildBasinPolygons() {
    final feats = _basins?.features ?? [];
    return feats.asMap().entries.map((entry) {
      final i = entry.key;
      final feat = entry.value;
      final p = (feat.properties['P_$_scenario'] as num?)?.toDouble() ?? 0.0;
      final sel = i == _selectedBasinIdx;
      final col = _probColor(p);
      if (feat.rings.isEmpty) return null;
      return Polygon(
        points: feat.rings[0],
        holePointsList: feat.rings.length > 1 ? feat.rings.sublist(1) : null,
        // Fill alpha never drops below 0.55 — a uniformly low-probability
        // AOI (e.g. one with no fire history) would otherwise render as a
        // near-invisible tint indistinguishable from green vegetation
        // basemap tiles, looking like nothing rendered at all.
        color: col.withValues(alpha: sel ? 0.75 : 0.55),
        borderColor: sel ? Colors.white : Colors.black.withValues(alpha: 0.55),
        borderStrokeWidth: sel ? 2.0 : 1.0,
        hitValue: i,
      );
    }).whereType<Polygon>().toList();
  }

  List<Polygon> _buildCellPolygons() {
    final feats = _mhriCells?.features ?? [];
    return feats.asMap().entries.map((entry) {
      final i = entry.key;
      final feat = entry.value;
      final mhri = (feat.properties['MHRI'] as num?)?.toDouble() ?? 0.0;
      final sel = i == _selectedCellIdx;
      final col = _mhriColor(mhri);
      if (feat.rings.isEmpty) return null;
      return Polygon(
        points: feat.rings[0],
        holePointsList: feat.rings.length > 1 ? feat.rings.sublist(1) : null,
        color: col.withValues(alpha: sel ? 0.75 : 0.50),
        borderColor: sel ? Colors.white : Colors.white.withValues(alpha: 0.25),
        borderStrokeWidth: sel ? 2.0 : 0.4,
        hitValue: i,
      );
    }).whereType<Polygon>().toList();
  }

  List<Polygon> _buildPerimeterPolygons() {
    final feats = _perimeter?.features ?? [];
    return feats.map((feat) {
      if (feat.rings.isEmpty) return null;
      return Polygon(
        points: feat.rings[0],
        holePointsList: feat.rings.length > 1 ? feat.rings.sublist(1) : null,
        color: Colors.transparent,
        borderColor: Colors.white,
        borderStrokeWidth: 2.5,
        pattern: const StrokePattern.dotted(),
      );
    }).whereType<Polygon>().toList();
  }

  // ---------------------------------------------------------------------------
  // Shared helpers
  // ---------------------------------------------------------------------------

  Widget _aoiSummaryChip() => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
    decoration: BoxDecoration(
      color: const Color(0xFF141820),
      borderRadius: BorderRadius.circular(8),
      border: Border.all(color: _kAccent.withValues(alpha: 0.20)),
    ),
    child: Row(children: [
      Icon(_inMhriCoverage ? Icons.check_circle_outline : Icons.info_outline,
          size: 14, color: _inMhriCoverage ? Colors.greenAccent : Colors.amber),
      const SizedBox(width: 8),
      Expanded(child: Text(
        '${_nameCtrl.text}'
        '${_aoiAreaKm2 != null ? '  ·  ${_aoiAreaKm2!.toStringAsFixed(1)} km²' : ''}'
        '${_fireId != null ? '\n$_fireId' : ''}',
        style: const TextStyle(color: Colors.white60, fontSize: 10, height: 1.4),
      )),
    ]),
  );

  /// Non-fatal warning about whether this AOI has any record of actually
  /// having burned, per the 2017-2024 California fire-perimeter catalog
  /// (wildcat/fires_perimeters.geojson). Surfaced because Wildcat will model
  /// debris-flow probability for ANY polygon you give it, fire or not.
  Widget _burnHistoryBanner() {
    final pct = _historicalBurnPct ?? 0.0;
    if (pct < 1.0) {
      return _infoBanner(
        'No record of wildfire here in our 2017-2024 California fire history. '
        'Debris-flow modeling will still run, but results won\'t reflect a real burn.',
      );
    }
    final top = _historicalFireMatches.isNotEmpty ? _historicalFireMatches.first : null;
    final label = top != null ? '${top['name']} (${top['year']})' : 'a known fire';
    if (pct >= 50.0) {
      return Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: Colors.greenAccent.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.greenAccent.withValues(alpha: 0.30)),
        ),
        child: Row(children: [
          const Icon(Icons.check_circle_outline, color: Colors.greenAccent, size: 15),
          const SizedBox(width: 8),
          Expanded(child: Text(
            '${pct.toStringAsFixed(0)}% of this area overlaps $label.',
            style: const TextStyle(color: Colors.greenAccent, fontSize: 11, height: 1.4),
          )),
        ]),
      );
    }
    return _infoBanner(
      'Only ${pct.toStringAsFixed(0)}% of this area overlaps $label — the rest has '
      'no recorded burn in our 2017-2024 history.',
    );
  }

  Widget _sectionLabel(String text, IconData icon) => Row(children: [
    Icon(icon, color: _kAccent, size: 14),
    const SizedBox(width: 6),
    Text(text, style: TextStyle(color: _kAccent.withValues(alpha: 0.70),
        fontSize: 10, fontFamily: 'monospace', letterSpacing: 1.0)),
  ]);

  Widget _subLabel(String text) => Text(text,
      style: const TextStyle(color: Colors.white54, fontSize: 11, fontWeight: FontWeight.w600, letterSpacing: 0.3));

  Widget _buildErrorBanner(String msg) => Container(
    padding: const EdgeInsets.all(10),
    decoration: BoxDecoration(
      color: Colors.red.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(8),
      border: Border.all(color: Colors.red.withValues(alpha: 0.30)),
    ),
    child: Row(children: [
      const Icon(Icons.error_outline, color: Colors.redAccent, size: 15),
      const SizedBox(width: 8),
      Expanded(child: Text(msg, style: const TextStyle(color: Colors.redAccent, fontSize: 11, height: 1.4))),
    ]),
  );

  Widget _infoBanner(String msg) => Container(
    padding: const EdgeInsets.all(10),
    decoration: BoxDecoration(
      color: Colors.amber.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(8),
      border: Border.all(color: Colors.amber.withValues(alpha: 0.30)),
    ),
    child: Row(children: [
      const Icon(Icons.info_outline, color: Colors.amber, size: 15),
      const SizedBox(width: 8),
      Expanded(child: Text(msg, style: const TextStyle(color: Colors.amber, fontSize: 11, height: 1.4))),
    ]),
  );
}
