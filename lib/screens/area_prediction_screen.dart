import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;

import '../utils/geojson_parser.dart';
import '../widgets/attribute_panel.dart';

/// Area Prediction screen - draw a polygon to analyze debris-flow hazards
class AreaPredictionScreen extends StatefulWidget {
  const AreaPredictionScreen({super.key});

  @override
  State<AreaPredictionScreen> createState() => _AreaPredictionScreenState();
}

class _AreaPredictionScreenState extends State<AreaPredictionScreen> {
  final MapController _mapController = MapController();

  List<LatLng> _selectedPolygon = [];
  bool _isDrawing = false;
  bool _predictionRunning = false;
  String? _predictionError;
  ParsedGeoJson? _results;
  int? _selectedFeatureIndex;

  static const String _backendUrl = 'http://localhost:8000/api/v1';

  // Franklin Fire center
  static const LatLng _center = LatLng(34.1, -118.9);

  void _startDrawing() {
    setState(() {
      _isDrawing = true;
      _selectedPolygon.clear();
      _results = null;
      _predictionError = null;
      _selectedFeatureIndex = null;
    });
  }

  void _finishDrawing() {
    if (_selectedPolygon.length < 3) {
      setState(() {
        _predictionError = 'Need at least 3 points to create a polygon';
      });
      return;
    }
    setState(() => _isDrawing = false);
  }

  void _clearSelection() {
    setState(() {
      _selectedPolygon.clear();
      _isDrawing = false;
      _results = null;
      _predictionError = null;
      _selectedFeatureIndex = null;
    });
  }

  Future<void> _runAnalysis() async {
    if (_selectedPolygon.length < 3) {
      setState(() => _predictionError = 'Draw a polygon first');
      return;
    }

    setState(() {
      _predictionRunning = true;
      _predictionError = null;
    });

    try {
      final coordinates = _selectedPolygon
          .map((p) => [p.longitude, p.latitude])
          .toList();
      coordinates.add([_selectedPolygon.first.longitude, _selectedPolygon.first.latitude]);

      final body = json.encode({
        'polygon': {'type': 'Polygon', 'coordinates': [coordinates]}
      });

      final response = await http.post(
        Uri.parse('$_backendUrl/custom-analysis'),
        headers: {'Content-Type': 'application/json'},
        body: body,
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final parsed = parseGeoJson(data['results']);
        setState(() {
          _results = parsed;
          _predictionRunning = false;
        });
        if (parsed.bounds != null) {
          _mapController.fitCamera(
            CameraFit.bounds(bounds: parsed.bounds!, padding: const EdgeInsets.all(50)),
          );
        }
      } else {
        throw Exception('Server error: ${response.body}');
      }
    } catch (e) {
      setState(() {
        _predictionError = 'Analysis failed: $e';
        _predictionRunning = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            Icon(Icons.place, color: Colors.white),
            SizedBox(width: 10),
            Text('Area Prediction'),
          ],
        ),
        backgroundColor: Colors.green.shade800,
        actions: [
          if (_results != null)
            TextButton.icon(
              onPressed: _clearSelection,
              icon: const Icon(Icons.refresh, color: Colors.white),
              label: const Text('New', style: TextStyle(color: Colors.white)),
            ),
        ],
      ),
      body: Stack(
        children: [
          FlutterMap(
            mapController: _mapController,
            options: MapOptions(
              initialCenter: _center,
              initialZoom: 12.0,
              onTap: (tapPosition, point) {
                if (_isDrawing) setState(() => _selectedPolygon.add(point));
              },
            ),
            children: [
              TileLayer(
                urlTemplate: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                userAgentPackageName: 'com.example.fire_webapp',
              ),
              // Results basins
              if (_results != null)
                PolygonLayer(
                  polygons: buildPolygons(
                    features: _results!.features,
                    selectedIndex: _selectedFeatureIndex,
                    onTap: (i) => setState(() {
                      _selectedFeatureIndex = _selectedFeatureIndex == i ? null : i;
                    }),
                  ),
                ),
              // User polygon
              if (_selectedPolygon.isNotEmpty)
                PolygonLayer(
                  polygons: [
                    Polygon(
                      points: _selectedPolygon,
                      color: Colors.blue.withValues(alpha: 0.2),
                      borderColor: Colors.blue,
                      borderStrokeWidth: 2.5,
                    ),
                  ],
                ),
              // Points
              if (_selectedPolygon.isNotEmpty)
                MarkerLayer(
                  markers: _selectedPolygon.asMap().entries.map((e) => Marker(
                    point: e.value,
                    width: 26, height: 26,
                    child: Container(
                      decoration: BoxDecoration(
                        color: Colors.blue,
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: 2),
                      ),
                      child: Center(
                        child: Text('${e.key + 1}',
                          style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold)),
                      ),
                    ),
                  )).toList(),
                ),
            ],
          ),

          // Instructions / status panel
          Positioned(
            top: 16, left: 16, right: 16,
            child: Material(
              elevation: 4,
              borderRadius: BorderRadius.circular(10),
              child: Container(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      _results != null
                          ? 'Analysis Complete: ${_results!.features.length} basins'
                          : _isDrawing
                              ? 'Tap map to add points (${_selectedPolygon.length} added)'
                              : 'Draw a polygon within the Franklin Fire area',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 15,
                        color: _results != null ? Colors.green.shade700 : Colors.black87,
                      ),
                    ),
                    if (_predictionError != null) ...[
                      const SizedBox(height: 6),
                      Text(_predictionError!, style: const TextStyle(color: Colors.red, fontSize: 13)),
                    ],
                    if (_results != null) ...[
                      const SizedBox(height: 4),
                      const Text('Tap any basin to see debris-flow hazard details',
                        style: TextStyle(fontSize: 12, color: Colors.grey)),
                    ],
                  ],
                ),
              ),
            ),
          ),

          // Control buttons
          Positioned(
            bottom: 16, right: 16,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                if (!_isDrawing && _selectedPolygon.isEmpty && _results == null)
                  FloatingActionButton.extended(
                    heroTag: 'start',
                    onPressed: _startDrawing,
                    backgroundColor: Colors.blue,
                    icon: const Icon(Icons.draw),
                    label: const Text('Start Drawing'),
                  ),
                if (_isDrawing) ...[
                  FloatingActionButton.extended(
                    heroTag: 'finish',
                    onPressed: _finishDrawing,
                    backgroundColor: Colors.green,
                    icon: const Icon(Icons.check),
                    label: const Text('Finish Drawing'),
                  ),
                  const SizedBox(height: 10),
                  FloatingActionButton(
                    heroTag: 'clear',
                    onPressed: _clearSelection,
                    backgroundColor: Colors.red,
                    child: const Icon(Icons.clear),
                  ),
                ],
                if (!_isDrawing && _selectedPolygon.length >= 3 && _results == null) ...[
                  FloatingActionButton.extended(
                    heroTag: 'analyze',
                    onPressed: _predictionRunning ? null : _runAnalysis,
                    backgroundColor: Colors.green.shade800,
                    icon: _predictionRunning
                        ? const SizedBox(width: 20, height: 20,
                            child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                        : const Icon(Icons.analytics),
                    label: Text(_predictionRunning ? 'Analyzing...' : 'Run Analysis'),
                  ),
                  const SizedBox(height: 10),
                  FloatingActionButton(
                    heroTag: 'reset',
                    onPressed: _clearSelection,
                    backgroundColor: Colors.grey,
                    child: const Icon(Icons.replay),
                  ),
                ],
                if (_results != null)
                  FloatingActionButton.extended(
                    heroTag: 'new',
                    onPressed: _clearSelection,
                    backgroundColor: Colors.green.shade800,
                    icon: const Icon(Icons.add),
                    label: const Text('New Analysis'),
                  ),
              ],
            ),
          ),

          // Attribute panel
          if (_results != null && _selectedFeatureIndex != null &&
              _selectedFeatureIndex! < _results!.features.length)
            Positioned(
              left: 16, bottom: 16,
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
