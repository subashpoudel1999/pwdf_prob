import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'dart:math' as math;

import '../models/fire_data.dart';
import '../services/api_service.dart';
import '../services/wildcat_service.dart';
import '../utils/geojson_parser.dart';
import '../widgets/attribute_panel.dart';
import 'palisades_fire_screen.dart';

class MapScreen extends StatefulWidget {
  const MapScreen({super.key});

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  // Data
  List<FireData> _fires = [];
  List<FireData> _filteredFires = [];
  FireData? _selectedFire;
  ParsedGeoJson? _parsedGeoJson;
  int? _selectedFeatureIndex;

  // Search
  final TextEditingController _searchController = TextEditingController();
  bool _isSearching = false;

  // Area selection
  List<LatLng> _selectedArea = [];
  bool _isAreaSelectionMode = false;
  bool _isDrawing = false;
  LatLng? _areaCentroid;

  // State
  bool _loadingFires = true;
  bool _loadingGeoJson = false;
  String? _error;

  // Map controller
  final MapController _mapController = MapController();

  @override
  void initState() {
    super.initState();
    _loadFireList();
  }

  Future<void> _loadFireList() async {
    try {
      final fires = await ApiService.fetchFireList();
      setState(() {
        _fires = fires;
        _filteredFires = fires;
        _loadingFires = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Cannot load fire data.\n\nError: $e';
        _loadingFires = false;
      });
    }
  }

  void _filterFires(String query) {
    setState(() {
      if (query.isEmpty) {
        _filteredFires = _fires;
      } else {
        _filteredFires = _fires.where((fire) {
          return fire.displayName.toLowerCase().contains(query.toLowerCase()) ||
                 fire.year.toString().contains(query);
        }).toList();
      }
    });
  }

  Future<void> _onFireSelected(FireData fire) async {
    setState(() {
      _selectedFire = fire;
      _loadingGeoJson = true;
      _parsedGeoJson = null;
      _selectedFeatureIndex = null;
      _error = null;
    });

    try {
      // Check if this fire has Wildcat analysis
      final hasWildcatResults = await WildcatService.hasResults(fire.id);

      Map<String, dynamic> geojson;

      if (hasWildcatResults) {
        // Load from Wildcat backend (pre-computed results)
        print('Loading Wildcat analysis for ${fire.id}');

        // Fetch pre-computed results
        geojson = await WildcatService.fetchWildcatResults(fire.id);
      } else {
        // Fall back to existing local JSON
        geojson = await ApiService.fetchFireGeoJson(fire.id);
      }

      final parsed = parseGeoJson(geojson);

      setState(() {
        _parsedGeoJson = parsed;
        _loadingGeoJson = false;
      });

      // Fly to the fire extent
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
        _error = 'Failed to load GeoJSON: $e';
        _loadingGeoJson = false;
      });
    }
  }

  void _onPolygonTap(int featureIndex) {
    setState(() {
      if (_selectedFeatureIndex == featureIndex) {
        _selectedFeatureIndex = null;
      } else {
        _selectedFeatureIndex = featureIndex;
      }
    });
  }

  void _onMapTap(TapPosition tapPosition, LatLng point) {
    if (_isAreaSelectionMode && _isDrawing) {
      // Add point to area selection
      setState(() {
        _selectedArea.add(point);
      });
    } else if (!_isAreaSelectionMode && _parsedGeoJson != null) {
      // Original polygon selection logic
      for (final feature in _parsedGeoJson!.features) {
        if (_pointInPolygon(point, feature.rings[0])) {
          _onPolygonTap(feature.index);
          return;
        }
      }
      setState(() {
        _selectedFeatureIndex = null;
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

  void _toggleAreaSelection() {
    setState(() {
      _isAreaSelectionMode = !_isAreaSelectionMode;
      _isDrawing = false;
      _selectedArea.clear();
      _areaCentroid = null;
      
      if (!_isAreaSelectionMode) {
        // Exiting area selection mode
        _selectedFire = null;
        _parsedGeoJson = null;
        _selectedFeatureIndex = null;
      }
    });
  }

  void _startDrawing() {
    setState(() {
      _isDrawing = true;
      _selectedArea.clear();
      _areaCentroid = null;
    });
  }

  void _finishAreaSelection() {
    if (_selectedArea.length < 3) {
      _showSnackBar('Please select at least 3 points');
      return;
    }

    // Calculate centroid
    double sumLat = 0, sumLng = 0;
    for (var point in _selectedArea) {
      sumLat += point.latitude;
      sumLng += point.longitude;
    }
    
    final centroid = LatLng(
      sumLat / _selectedArea.length,
      sumLng / _selectedArea.length,
    );

    setState(() {
      _isDrawing = false;
      _areaCentroid = centroid;
    });

    // Find closest fire
    _findClosestFire(centroid);
  }

  Future<void> _findClosestFire(LatLng centroid) async {
    if (_fires.isEmpty) return;

    setState(() {
      _loadingGeoJson = true;
    });

    FireData? closestFire;
    double minDistance = double.infinity;

    // Calculate actual centroid for each fire from its GeoJSON data
    for (final fire in _fires) {
      try {
        // Load the fire's GeoJSON to calculate its actual centroid
        final geojson = await ApiService.fetchFireGeoJson(fire.id);
        final parsed = parseGeoJson(geojson);
        
        if (parsed.bounds != null) {
          // Calculate centroid from bounds
          final bounds = parsed.bounds!;
          final fireLatitude = (bounds.north + bounds.south) / 2;
          final fireLongitude = (bounds.east + bounds.west) / 2;
          final fireCentroid = LatLng(fireLatitude, fireLongitude);
          
          final distance = _calculateDistance(centroid, fireCentroid);
          if (distance < minDistance) {
            minDistance = distance;
            closestFire = fire;
          }
        }
      } catch (e) {
        // Skip this fire if we can't load its data
        print('Error loading fire ${fire.fireName}: $e');
        continue;
      }
    }

    setState(() {
      _loadingGeoJson = false;
    });

    if (closestFire != null) {
      _showSnackBar('Found closest fire: ${closestFire.fireName} (${closestFire.year}) - ${minDistance.toStringAsFixed(1)} km away');
      // Switch back to fire list mode and load the fire
      setState(() {
        _isAreaSelectionMode = false;
      });
      await _onFireSelected(closestFire);
    } else {
      _showSnackBar('No nearby fires found');
    }
  }

  double _calculateDistance(LatLng point1, LatLng point2) {
    var p = 0.017453292519943295;
    var c = math.cos;
    var a = 0.5 - c((point2.latitude - point1.latitude) * p)/2 + 
            c(point1.latitude * p) * c(point2.latitude * p) * 
            (1 - c((point2.longitude - point1.longitude) * p))/2;
    return 12742 * math.asin(math.sqrt(a));
  }

  void _clearAreaSelection() {
    setState(() {
      _selectedArea.clear();
      _areaCentroid = null;
      _isDrawing = false;
    });
  }

  void _showSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  SubBasinFeature? get _selectedFeature {
    if (_parsedGeoJson == null || _selectedFeatureIndex == null) return null;
    try {
      return _parsedGeoJson!.features
          .firstWhere((f) => f.index == _selectedFeatureIndex);
    } catch (_) {
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          _buildTopBar(),
          Expanded(
            child: _error != null && _parsedGeoJson == null
                ? _buildError()
                : _buildMapArea(),
          ),
        ],
      ),
    );
  }

  Widget _buildTopBar() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.blueGrey.shade900,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.3),
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          // App title
          const Icon(Icons.local_fire_department,
              color: Colors.orangeAccent, size: 26),
          const SizedBox(width: 10),
          const Text(
            'Post-Wildfire Debris Flow Dashboard',
            style: TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.3,
            ),
          ),

          const SizedBox(width: 40),

          // Mode toggle
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [
                _buildModeButton(
                  'Fire List',
                  !_isAreaSelectionMode,
                  () => _toggleAreaSelection(),
                ),
                const SizedBox(width: 4),
                _buildModeButton(
                  'Area Selection',
                  _isAreaSelectionMode,
                  () => _toggleAreaSelection(),
                ),
              ],
            ),
          ),

          const SizedBox(width: 20),

          // Controls based on mode
          if (!_isAreaSelectionMode) ...[
            if (_loadingFires)
              const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                    strokeWidth: 2, color: Colors.white70),
              )
            else ...[
              // Search field
              Container(
                width: 200,
                height: 36,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.white24),
                ),
                child: TextField(
                  controller: _searchController,
                  onChanged: _filterFires,
                  style: const TextStyle(color: Colors.white, fontSize: 14),
                  decoration: const InputDecoration(
                    hintText: 'Search fires...',
                    hintStyle: TextStyle(color: Colors.white60, fontSize: 13),
                    prefixIcon: Icon(Icons.search, color: Colors.white60, size: 18),
                    border: InputBorder.none,
                    contentPadding: EdgeInsets.symmetric(vertical: 8),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              _buildFireDropdown(),
            ],
          ] else ...[
            _buildAreaControls(),
          ],

          const Spacer(),

          // Palisades Fire button
          TextButton.icon(
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const PalisadesFireScreen()),
            ),
            icon: const Icon(Icons.local_fire_department,
                color: Color(0xFFFF6B35), size: 18),
            label: const Text(
              'Palisades Fire',
              style: TextStyle(
                color: Color(0xFFFF6B35),
                fontWeight: FontWeight.bold,
                fontSize: 13,
              ),
            ),
          ),

          const SizedBox(width: 8),

          // Status chip
          if (_selectedFire != null && _parsedGeoJson != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Text(
                '${_parsedGeoJson!.features.length} sub-basins',
                style: const TextStyle(color: Colors.white70, fontSize: 13),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildModeButton(String title, bool isActive, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(6),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isActive ? Colors.white.withValues(alpha: 0.2) : Colors.transparent,
          borderRadius: BorderRadius.circular(6),
        ),
        child: Text(
          title,
          style: TextStyle(
            color: isActive ? Colors.white : Colors.white60,
            fontSize: 13,
            fontWeight: isActive ? FontWeight.w600 : FontWeight.normal,
          ),
        ),
      ),
    );
  }

  Widget _buildFireDropdown() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white24),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: _selectedFire?.id,
          hint: const Text(
            'Select a fire...',
            style: TextStyle(color: Colors.white60, fontSize: 14),
          ),
          dropdownColor: Colors.blueGrey.shade800,
          icon: const Icon(Icons.arrow_drop_down, color: Colors.white60),
          menuMaxHeight: 500,
          items: _filteredFires.map((fire) {
            return DropdownMenuItem<String>(
              value: fire.id,
              child: Text(
                fire.displayName,
                style: const TextStyle(color: Colors.white, fontSize: 14),
              ),
            );
          }).toList(),
          onChanged: (id) {
            if (id != null) {
              final fire = _fires.firstWhere((f) => f.id == id);
              _onFireSelected(fire);
            }
          },
        ),
      ),
    );
  }

  Widget _buildAreaControls() {
    return Row(
      children: [
        if (!_isDrawing && _selectedArea.isEmpty) ...[
          ElevatedButton.icon(
            onPressed: _startDrawing,
            icon: const Icon(Icons.edit, size: 16),
            label: const Text('Draw Area'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.green,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            ),
          ),
        ] else if (_isDrawing) ...[
          ElevatedButton.icon(
            onPressed: _finishAreaSelection,
            icon: const Icon(Icons.check, size: 16),
            label: const Text('Finish'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.blue,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            ),
          ),
          const SizedBox(width: 8),
          ElevatedButton.icon(
            onPressed: _clearAreaSelection,
            icon: const Icon(Icons.clear, size: 16),
            label: const Text('Clear'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            ),
          ),
        ] else if (_selectedArea.isNotEmpty) ...[
          ElevatedButton.icon(
            onPressed: _startDrawing,
            icon: const Icon(Icons.edit, size: 16),
            label: const Text('Redraw'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.orange,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            ),
          ),
          const SizedBox(width: 8),
          ElevatedButton.icon(
            onPressed: _clearAreaSelection,
            icon: const Icon(Icons.clear, size: 16),
            label: const Text('Clear'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildMapArea() {
    return Stack(
      children: [
        Row(
          children: [
            // Map
            Expanded(child: _buildMap()),

            // Attribute panel
            if (_selectedFeature != null)
              AttributePanel(
                feature: _selectedFeature,
                onClose: () => setState(() => _selectedFeatureIndex = null),
              ),
          ],
        ),

        // Loading overlay
        if (_loadingGeoJson)
          Container(
            color: Colors.black26,
            child: const Center(
              child: Card(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      CircularProgressIndicator(),
                      SizedBox(height: 16),
                      Text('Calculating debris flow probabilities...'),
                    ],
                  ),
                ),
              ),
            ),
          ),

        // Instruction overlays
        if (_isAreaSelectionMode && _isDrawing)
          Positioned(
            top: 16,
            left: 16,
            right: 16,
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.green.shade800,
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Text(
                'Click on the map to add points to your area. Click "Finish" when done.',
                style: TextStyle(color: Colors.white, fontSize: 14),
                textAlign: TextAlign.center,
              ),
            ),
          ),

        if (_parsedGeoJson != null && _selectedFeatureIndex == null && !_isAreaSelectionMode)
          Positioned(
            bottom: 16,
            left: 0,
            right: 0,
            child: Center(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                decoration: BoxDecoration(
                  color: Colors.black87,
                  borderRadius: BorderRadius.circular(20),
                ),
                child: const Text(
                  'Click a sub-basin to view its attributes',
                  style: TextStyle(color: Colors.white70, fontSize: 13),
                ),
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildMap() {
    return FlutterMap(
      mapController: _mapController,
      options: MapOptions(
        initialCenter: const LatLng(37.5, -119.5), // California center
        initialZoom: 6,
        onTap: _onMapTap,
      ),
      children: [
        // Base map tiles
        TileLayer(
          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          userAgentPackageName: 'com.example.fire_webapp',
          maxZoom: 19,
        ),

        // Sub-basin polygons (only in fire list mode)
        if (_parsedGeoJson != null && !_isAreaSelectionMode)
          PolygonLayer(
            polygons: buildPolygons(
              features: _parsedGeoJson!.features,
              selectedIndex: _selectedFeatureIndex,
              onTap: _onPolygonTap,
            ),
          ),

        // Selected area polygon
        if (_selectedArea.length > 2 && _isAreaSelectionMode)
          PolygonLayer(
            polygons: [
              Polygon(
                points: _selectedArea,
                color: Colors.red.withOpacity(0.3),
                borderColor: Colors.red,
                borderStrokeWidth: 2.0,
              ),
            ],
          ),

        // Area selection points
        if (_selectedArea.isNotEmpty && _isAreaSelectionMode)
          MarkerLayer(
            markers: _selectedArea.asMap().entries.map((entry) {
              final index = entry.key;
              final point = entry.value;
              return Marker(
                point: point,
                width: 20,
                height: 20,
                child: Container(
                  decoration: BoxDecoration(
                    color: Colors.red,
                    shape: BoxShape.circle,
                    border: Border.all(color: Colors.white, width: 2),
                  ),
                  child: Center(
                    child: Text(
                      '${index + 1}',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
              );
            }).toList(),
          ),

        // Centroid marker
        if (_areaCentroid != null && _isAreaSelectionMode)
          MarkerLayer(
            markers: [
              Marker(
                point: _areaCentroid!,
                width: 30,
                height: 30,
                child: Container(
                  decoration: BoxDecoration(
                    color: Colors.blue,
                    shape: BoxShape.circle,
                    border: Border.all(color: Colors.white, width: 3),
                  ),
                  child: const Icon(
                    Icons.center_focus_strong,
                    color: Colors.white,
                    size: 16,
                  ),
                ),
              ),
            ],
          ),
      ],
    );
  }

  Widget _buildError() {
    return Center(
      child: Container(
        padding: const EdgeInsets.all(32),
        constraints: const BoxConstraints(maxWidth: 500),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.cloud_off, size: 64, color: Colors.red.shade300),
            const SizedBox(height: 16),
            Text(
              _error ?? 'Unknown error',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 15),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: () {
                setState(() {
                  _error = null;
                  _loadingFires = true;
                });
                _loadFireList();
              },
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}