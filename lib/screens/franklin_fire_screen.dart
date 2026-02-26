import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;

import '../services/wildcat_service.dart';
import '../utils/geojson_parser.dart';
import '../widgets/attribute_panel.dart';

/// Dedicated Franklin Fire screen that:
/// 1. Runs live Wildcat analysis on full Franklin Fire on load
/// 2. Shows results with hazard visualization
/// 3. Allows drawing custom polygons within Franklin Fire
/// 4. Re-runs analysis on custom areas
class FranklinFireScreen extends StatefulWidget {
  const FranklinFireScreen({Key? key}) : super(key: key);

  @override
  State<FranklinFireScreen> createState() => _FranklinFireScreenState();
}

enum MapType { standard, satellite, terrain, dark, topo }

class _FranklinFireScreenState extends State<FranklinFireScreen> with SingleTickerProviderStateMixin {
  final MapController _mapController = MapController();

  // Analysis states
  bool _isLoadingFullAnalysis = true;
  bool _isRunningCustomAnalysis = false;
  ParsedGeoJson? _fullResults;
  ParsedGeoJson? _customResults;
  String? _error;
  int? _selectedFeatureIndex;

  // Drawing states
  bool _isDrawingCustom = false;
  final List<LatLng> _drawnPoints = [];

  // View mode
  bool _showingCustomResults = false;

  // Map settings
  MapType _currentMapType = MapType.satellite;
  late AnimationController _animationController;

  // Franklin Fire location
  static const LatLng _franklinFireCenter = LatLng(34.1, -118.9);
  static const double _initialZoom = 12.0;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 300),
    );
    _animationController.forward();

    WidgetsBinding.instance.addPostFrameCallback((_) {
      _mapController.move(_franklinFireCenter, _initialZoom);
      _runFullFranklinFireAnalysis();
    });
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  TileLayer _buildTileLayer() {
    switch (_currentMapType) {
      case MapType.satellite:
        return TileLayer(
          urlTemplate: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
          userAgentPackageName: 'com.example.fire_webapp',
        );
      case MapType.terrain:
        return TileLayer(
          urlTemplate: 'https://stamen-tiles.a.ssl.fastly.net/terrain/{z}/{x}/{y}.jpg',
          userAgentPackageName: 'com.example.fire_webapp',
        );
      case MapType.dark:
        return TileLayer(
          urlTemplate: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
          subdomains: const ['a', 'b', 'c', 'd'],
          userAgentPackageName: 'com.example.fire_webapp',
        );
      case MapType.topo:
        return TileLayer(
          urlTemplate: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
          subdomains: const ['a', 'b', 'c'],
          userAgentPackageName: 'com.example.fire_webapp',
        );
      case MapType.standard:
      default:
        return TileLayer(
          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          userAgentPackageName: 'com.example.fire_webapp',
        );
    }
  }

  Future<void> _runFullFranklinFireAnalysis() async {
    setState(() {
      _isLoadingFullAnalysis = true;
      _error = null;
    });

    try {
      print('Loading Franklin Fire Wildcat analysis results...');

      // Fetch pre-computed results from backend
      final geojson = await WildcatService.fetchWildcatResults('franklin-fire');
      final parsed = parseGeoJson(geojson);

      setState(() {
        _fullResults = parsed;
        _isLoadingFullAnalysis = false;
        _showingCustomResults = false;
      });

      // Zoom to results
      if (parsed.bounds != null) {
        _mapController.fitCamera(
          CameraFit.bounds(
            bounds: parsed.bounds!,
            padding: const EdgeInsets.all(50),
          ),
        );
      }
    } catch (e) {
      setState(() {
        _error = 'Failed to run Franklin Fire analysis: $e';
        _isLoadingFullAnalysis = false;
      });
    }
  }

  void _startCustomDrawing() {
    setState(() {
      _isDrawingCustom = true;
      _drawnPoints.clear();
      _customResults = null;
      _showingCustomResults = false;
      _selectedFeatureIndex = null;
    });
  }

  void _addPoint(LatLng point) {
    if (_isDrawingCustom) {
      setState(() {
        _drawnPoints.add(point);
      });
    }
  }

  void _completePolygon() {
    if (_drawnPoints.length < 3) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Need at least 3 points')),
      );
      return;
    }

    setState(() {
      _isDrawingCustom = false;
    });
  }

  void _clearCustom() {
    setState(() {
      _drawnPoints.clear();
      _isDrawingCustom = false;
      _customResults = null;
      _showingCustomResults = false;
      _selectedFeatureIndex = null;
    });
  }

  Future<void> _runCustomAnalysis() async {
    if (_drawnPoints.length < 3) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Draw a polygon first')),
      );
      return;
    }

    setState(() {
      _isRunningCustomAnalysis = true;
      _error = null;
    });

    try {
      // Convert to GeoJSON
      final coordinates = _drawnPoints.map((p) => [p.longitude, p.latitude]).toList();
      coordinates.add([_drawnPoints.first.longitude, _drawnPoints.first.latitude]);

      final polygonGeometry = {
        "type": "Polygon",
        "coordinates": [coordinates]
      };

      // Call custom analysis endpoint
      final response = await http.post(
        Uri.parse('http://localhost:8000/api/v1/custom-analysis'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'polygon': polygonGeometry}),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final geojson = data['results'];
        final parsed = parseGeoJson(geojson);

        setState(() {
          _customResults = parsed;
          _showingCustomResults = true;
          _isRunningCustomAnalysis = false;
        });

        // Zoom to custom results
        if (parsed.bounds != null) {
          _mapController.fitCamera(
            CameraFit.bounds(
              bounds: parsed.bounds!,
              padding: const EdgeInsets.all(50),
            ),
          );
        }

        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Custom analysis complete!'),
            backgroundColor: Colors.green,
          ),
        );
      } else {
        throw Exception('Analysis failed: ${response.body}');
      }
    } catch (e) {
      setState(() {
        _error = 'Custom analysis failed: $e';
        _isRunningCustomAnalysis = false;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
      );
    }
  }

  void _showFullResults() {
    setState(() {
      _showingCustomResults = false;
      _selectedFeatureIndex = null;
    });

    if (_fullResults?.bounds != null) {
      _mapController.fitCamera(
        CameraFit.bounds(
          bounds: _fullResults!.bounds!,
          padding: const EdgeInsets.all(50),
        ),
      );
    }
  }

  void _onPolygonTap(int index) {
    setState(() {
      if (_selectedFeatureIndex == index) {
        _selectedFeatureIndex = null;
      } else {
        _selectedFeatureIndex = index;
      }
    });
  }

  ParsedGeoJson? get _currentResults =>
      _showingCustomResults ? _customResults : _fullResults;

  Widget _buildMapTypeButton(
    MapType type,
    IconData icon,
    String label,
    Color color,
  ) {
    final isSelected = _currentMapType == type;
    return InkWell(
      onTap: () => setState(() => _currentMapType = type),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: isSelected ? color.withOpacity(0.1) : Colors.transparent,
          borderRadius: isSelected ? BorderRadius.circular(8) : null,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              color: isSelected ? color : Colors.grey.shade600,
              size: 20,
            ),
            const SizedBox(width: 8),
            Text(
              label,
              style: TextStyle(
                color: isSelected ? color : Colors.grey.shade700,
                fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                fontSize: 13,
              ),
            ),
            if (isSelected) ...[
              const SizedBox(width: 4),
              Icon(Icons.check_circle, color: color, size: 16),
            ],
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            const Icon(Icons.local_fire_department, color: Colors.white, size: 28),
            const SizedBox(width: 12),
            const Text(
              'Franklin Fire Analysis',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                letterSpacing: 0.5,
              ),
            ),
            if (_showingCustomResults)
              Container(
                margin: const EdgeInsets.only(left: 12),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.2),
                      blurRadius: 4,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: const Text(
                  'CUSTOM AREA',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: Colors.deepOrange,
                    letterSpacing: 0.8,
                  ),
                ),
              ),
          ],
        ),
        flexibleSpace: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                Color(0xFFFF6B35),
                Color(0xFFFF8C42),
              ],
            ),
          ),
        ),
        elevation: 8,
        actions: [
          if (_customResults != null && !_showingCustomResults)
            TextButton.icon(
              onPressed: () => setState(() => _showingCustomResults = true),
              icon: const Icon(Icons.draw, color: Colors.white, size: 18),
              label: const Text(
                'Show Custom',
                style: TextStyle(color: Colors.white),
              ),
            ),
          if (_showingCustomResults)
            TextButton.icon(
              onPressed: _showFullResults,
              icon: const Icon(Icons.view_module, color: Colors.white, size: 18),
              label: const Text(
                'Show Full',
                style: TextStyle(color: Colors.white),
              ),
            ),
          const SizedBox(width: 8),
        ],
      ),
      body: Stack(
        children: [
          // Map
          FlutterMap(
            mapController: _mapController,
            options: MapOptions(
              initialCenter: _franklinFireCenter,
              initialZoom: _initialZoom,
              onTap: (tapPosition, point) {
                if (_isDrawingCustom) {
                  _addPoint(point);
                }
              },
            ),
            children: [
              _buildTileLayer(),
              // Results polygons
              if (_currentResults != null)
                PolygonLayer(
                  polygons: buildPolygons(
                    features: _currentResults!.features,
                    selectedIndex: _selectedFeatureIndex,
                    onTap: _onPolygonTap,
                  ),
                ),
              // Drawn custom polygon
              if (_drawnPoints.isNotEmpty)
                PolygonLayer(
                  polygons: [
                    Polygon(
                      points: _drawnPoints,
                      color: _isDrawingCustom
                          ? Colors.blue.withOpacity(0.3)
                          : Colors.green.withOpacity(0.3),
                      borderColor: _isDrawingCustom ? Colors.blue : Colors.green,
                      borderStrokeWidth: 3.0,
                    ),
                  ],
                ),
              // Drawing points
              if (_drawnPoints.isNotEmpty)
                MarkerLayer(
                  markers: _drawnPoints.asMap().entries.map((entry) {
                    return Marker(
                      point: entry.value,
                      width: 30,
                      height: 30,
                      child: Container(
                        decoration: BoxDecoration(
                          color: Colors.blue,
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white, width: 2),
                        ),
                        child: Center(
                          child: Text(
                            '${entry.key + 1}',
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                              fontSize: 12,
                            ),
                          ),
                        ),
                      ),
                    );
                  }).toList(),
                ),
            ],
          ),

          // Loading overlay
          if (_isLoadingFullAnalysis)
            Container(
              color: Colors.black54,
              child: const Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    CircularProgressIndicator(color: Colors.orange),
                    SizedBox(height: 16),
                    Text(
                      'Running Wildcat analysis on Franklin Fire...',
                      style: TextStyle(color: Colors.white, fontSize: 16),
                    ),
                    SizedBox(height: 8),
                    Text(
                      'This may take 30-60 seconds',
                      style: TextStyle(color: Colors.white70, fontSize: 14),
                    ),
                  ],
                ),
              ),
            ),

          // Info panel
          if (!_isLoadingFullAnalysis && _currentResults != null && !_isDrawingCustom)
            Positioned(
              top: 16,
              left: 16,
              child: Material(
                elevation: 4,
                borderRadius: BorderRadius.circular(8),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  constraints: const BoxConstraints(maxWidth: 300),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        _showingCustomResults ? 'Custom Area Results' : 'Full Franklin Fire',
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${_currentResults!.features.length} sub-basins analyzed',
                        style: const TextStyle(fontSize: 14),
                      ),
                      const Text(
                        'Tap polygons for details',
                        style: TextStyle(fontSize: 12, color: Colors.grey),
                      ),
                    ],
                  ),
                ),
              ),
            ),

          // Drawing instructions
          if (_isDrawingCustom)
            Positioned(
              top: 16,
              left: 16,
              right: 16,
              child: Material(
                elevation: 4,
                borderRadius: BorderRadius.circular(8),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text(
                        'Draw Custom Analysis Area',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Tap on map to add points. Points: ${_drawnPoints.length}',
                        style: const TextStyle(fontSize: 14),
                      ),
                      if (_error != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 8),
                          child: Text(
                            _error!,
                            style: const TextStyle(color: Colors.red, fontSize: 12),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),

          // Map layer switcher
          Positioned(
            top: 80,
            right: 16,
            child: Material(
              elevation: 8,
              borderRadius: BorderRadius.circular(12),
              child: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [Colors.white, Colors.grey.shade50],
                  ),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.grey.shade300),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _buildMapTypeButton(
                      MapType.satellite,
                      Icons.satellite_alt,
                      'Satellite',
                      Colors.blue,
                    ),
                    const Divider(height: 1),
                    _buildMapTypeButton(
                      MapType.terrain,
                      Icons.terrain,
                      'Terrain',
                      Colors.green,
                    ),
                    const Divider(height: 1),
                    _buildMapTypeButton(
                      MapType.dark,
                      Icons.dark_mode,
                      'Dark',
                      Colors.grey.shade800,
                    ),
                    const Divider(height: 1),
                    _buildMapTypeButton(
                      MapType.topo,
                      Icons.landscape,
                      'Topo',
                      Colors.orange,
                    ),
                    const Divider(height: 1),
                    _buildMapTypeButton(
                      MapType.standard,
                      Icons.map,
                      'Standard',
                      Colors.purple,
                    ),
                  ],
                ),
              ),
            ),
          ),

          // Control buttons
          Positioned(
            bottom: 16,
            right: 16,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                // Draw custom button
                if (!_isDrawingCustom && _drawnPoints.isEmpty && !_isLoadingFullAnalysis)
                  FloatingActionButton.extended(
                    onPressed: _startCustomDrawing,
                    backgroundColor: Colors.blue,
                    icon: const Icon(Icons.draw),
                    label: const Text('Draw Custom Area'),
                  ),

                // Drawing controls
                if (_isDrawingCustom) ...[
                  FloatingActionButton.extended(
                    onPressed: _completePolygon,
                    backgroundColor: Colors.green,
                    icon: const Icon(Icons.check),
                    label: const Text('Complete'),
                  ),
                  const SizedBox(height: 8),
                  FloatingActionButton(
                    onPressed: _clearCustom,
                    backgroundColor: Colors.red,
                    child: const Icon(Icons.clear),
                  ),
                ],

                // Run custom analysis
                if (!_isDrawingCustom && _drawnPoints.length >= 3 && !_showingCustomResults) ...[
                  FloatingActionButton.extended(
                    onPressed: _isRunningCustomAnalysis ? null : _runCustomAnalysis,
                    backgroundColor: Colors.deepOrange,
                    icon: _isRunningCustomAnalysis
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              color: Colors.white,
                              strokeWidth: 2,
                            ),
                          )
                        : const Icon(Icons.analytics),
                    label: Text(_isRunningCustomAnalysis ? 'Analyzing...' : 'Run Analysis'),
                  ),
                  const SizedBox(height: 8),
                  FloatingActionButton(
                    onPressed: _clearCustom,
                    backgroundColor: Colors.grey,
                    child: const Icon(Icons.refresh),
                  ),
                ],

                // New custom area (when showing custom results)
                if (_showingCustomResults && !_isDrawingCustom)
                  FloatingActionButton(
                    onPressed: _clearCustom,
                    backgroundColor: Colors.blue,
                    child: const Icon(Icons.add),
                    tooltip: 'Draw New Area',
                  ),
              ],
            ),
          ),

          // Attribute panel
          if (_currentResults != null &&
              _selectedFeatureIndex != null &&
              _selectedFeatureIndex! < _currentResults!.features.length)
            Positioned(
              left: 16,
              bottom: 16,
              child: AttributePanel(
                feature: _currentResults!.features[_selectedFeatureIndex!],
                onClose: () => setState(() => _selectedFeatureIndex = null),
              ),
            ),
        ],
      ),
    );
  }
}
