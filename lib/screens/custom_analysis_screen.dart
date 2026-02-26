import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;

import '../utils/geojson_parser.dart';
import '../widgets/attribute_panel.dart';

class CustomAnalysisScreen extends StatefulWidget {
  const CustomAnalysisScreen({Key? key}) : super(key: key);

  @override
  State<CustomAnalysisScreen> createState() => _CustomAnalysisScreenState();
}

class _CustomAnalysisScreenState extends State<CustomAnalysisScreen> {
  final MapController _mapController = MapController();
  final List<LatLng> _drawnPoints = [];
  bool _isDrawing = false;
  bool _isAnalyzing = false;
  bool _hasResults = false;
  String? _error;
  ParsedGeoJson? _results;
  int? _selectedFeatureIndex;

  // Franklin Fire approximate center and bounds
  static const LatLng _franklinFireCenter = LatLng(34.1, -118.9);
  static const double _initialZoom = 12.0;

  @override
  void initState() {
    super.initState();
    // Center map on Franklin Fire area
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _mapController.move(_franklinFireCenter, _initialZoom);
    });
  }

  void _startDrawing() {
    setState(() {
      _isDrawing = true;
      _drawnPoints.clear();
      _hasResults = false;
      _results = null;
      _error = null;
    });
  }

  void _addPoint(LatLng point) {
    if (_isDrawing) {
      setState(() {
        _drawnPoints.add(point);
      });
    }
  }

  void _completePolygon() {
    if (_drawnPoints.length < 3) {
      setState(() {
        _error = 'Need at least 3 points to create a polygon';
      });
      return;
    }

    setState(() {
      _isDrawing = false;
    });
  }

  void _clearPolygon() {
    setState(() {
      _drawnPoints.clear();
      _isDrawing = false;
      _hasResults = false;
      _results = null;
      _error = null;
      _selectedFeatureIndex = null;
    });
  }

  Future<void> _runAnalysis() async {
    if (_drawnPoints.length < 3) {
      setState(() {
        _error = 'Draw a polygon first';
      });
      return;
    }

    setState(() {
      _isAnalyzing = true;
      _error = null;
    });

    try {
      // Convert drawn polygon to GeoJSON
      final coordinates = _drawnPoints.map((p) => [p.longitude, p.latitude]).toList();
      coordinates.add([_drawnPoints.first.longitude, _drawnPoints.first.latitude]); // Close polygon

      final polygonGeometry = {
        "type": "Polygon",
        "coordinates": [coordinates]
      };

      // Call backend API
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
          _results = parsed;
          _hasResults = true;
          _isAnalyzing = false;
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
      } else {
        throw Exception('Analysis failed: ${response.body}');
      }
    } catch (e) {
      setState(() {
        _error = 'Analysis failed: $e';
        _isAnalyzing = false;
      });
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Custom Area Analysis'),
        backgroundColor: Colors.deepOrange,
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
                if (_isDrawing) {
                  _addPoint(point);
                }
              },
            ),
            children: [
              TileLayer(
                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.example.fire_webapp',
              ),
              // Results polygons
              if (_hasResults && _results != null)
                PolygonLayer(
                  polygons: buildPolygons(
                    features: _results!.features,
                    selectedIndex: _selectedFeatureIndex,
                    onTap: _onPolygonTap,
                  ),
                ),
              // Drawn polygon
              if (_drawnPoints.isNotEmpty)
                PolygonLayer(
                  polygons: [
                    Polygon(
                      points: _drawnPoints,
                      color: _isDrawing
                          ? Colors.blue.withOpacity(0.3)
                          : Colors.green.withOpacity(0.3),
                      borderColor: _isDrawing ? Colors.blue : Colors.green,
                      borderStrokeWidth: 3.0,
                    ),
                  ],
                ),
              // Drawn points markers
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

          // Instructions panel
          if (!_hasResults)
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
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        _isDrawing
                            ? 'Tap on the map to add points. Need at least 3 points.'
                            : 'Click "Start Drawing" to define your analysis area within the Franklin Fire.',
                        style: TextStyle(color: Colors.grey[700]),
                      ),
                      if (_drawnPoints.isNotEmpty)
                        Text(
                          'Points: ${_drawnPoints.length}',
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            color: Colors.blue,
                          ),
                        ),
                      if (_error != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 8),
                          child: Text(
                            _error!,
                            style: const TextStyle(color: Colors.red),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),

          // Results info
          if (_hasResults && _results != null)
            Positioned(
              top: 16,
              left: 16,
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
                        'Analysis Complete',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: Colors.green,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${_results!.features.length} sub-basins analyzed',
                        style: const TextStyle(fontSize: 14),
                      ),
                      const Text(
                        'Tap any polygon for details',
                        style: TextStyle(fontSize: 12, color: Colors.grey),
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
                if (!_isDrawing && _drawnPoints.isEmpty && !_hasResults)
                  FloatingActionButton.extended(
                    onPressed: _startDrawing,
                    backgroundColor: Colors.blue,
                    icon: const Icon(Icons.draw),
                    label: const Text('Start Drawing'),
                  ),
                if (_isDrawing) ...[
                  FloatingActionButton.extended(
                    onPressed: _completePolygon,
                    backgroundColor: Colors.green,
                    icon: const Icon(Icons.check),
                    label: const Text('Complete Polygon'),
                  ),
                  const SizedBox(height: 8),
                  FloatingActionButton(
                    onPressed: _clearPolygon,
                    backgroundColor: Colors.red,
                    child: const Icon(Icons.clear),
                  ),
                ],
                if (!_isDrawing && _drawnPoints.length >= 3 && !_hasResults) ...[
                  FloatingActionButton.extended(
                    onPressed: _isAnalyzing ? null : _runAnalysis,
                    backgroundColor: Colors.deepOrange,
                    icon: _isAnalyzing
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              color: Colors.white,
                              strokeWidth: 2,
                            ),
                          )
                        : const Icon(Icons.analytics),
                    label: Text(_isAnalyzing ? 'Analyzing...' : 'Run Analysis'),
                  ),
                  const SizedBox(height: 8),
                  FloatingActionButton(
                    onPressed: _clearPolygon,
                    backgroundColor: Colors.grey,
                    child: const Icon(Icons.refresh),
                  ),
                ],
                if (_hasResults)
                  FloatingActionButton(
                    onPressed: _clearPolygon,
                    backgroundColor: Colors.deepOrange,
                    child: const Icon(Icons.add),
                    tooltip: 'New Analysis',
                  ),
              ],
            ),
          ),

          // Attribute panel for selected feature
          if (_hasResults &&
              _results != null &&
              _selectedFeatureIndex != null &&
              _selectedFeatureIndex! < _results!.features.length)
            Positioned(
              left: 16,
              bottom: 16,
              child: AttributePanel(
                feature: _results!.features[_selectedFeatureIndex!],
                onClose: () => setState(() => _selectedFeatureIndex = null),
              ),
            ),
        ],
      ),
    );
  }
}
