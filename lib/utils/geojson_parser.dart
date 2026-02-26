import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

/// Parsed result from a GeoJSON FeatureCollection.
class ParsedGeoJson {
  final List<SubBasinFeature> features;
  final LatLngBounds? bounds;

  ParsedGeoJson({required this.features, this.bounds});
}

/// One sub-basin polygon with its attribute properties.
class SubBasinFeature {
  final int index;
  final List<List<LatLng>> rings; // outer ring + any holes
  final Map<String, dynamic> properties;

  SubBasinFeature({
    required this.index,
    required this.rings,
    required this.properties,
  });

  /// The sub-basin ID if available, otherwise a fallback label.
  String get label {
    return properties['Segment_ID']?.toString() ??
        properties['id']?.toString() ??
        'Feature $index';
  }
}

/// Parse a GeoJSON FeatureCollection into SubBasinFeatures.
ParsedGeoJson parseGeoJson(Map<String, dynamic> geojson) {
  final features = <SubBasinFeature>[];
  final rawFeatures = geojson['features'] as List? ?? [];

  double minLat = 90, maxLat = -90, minLng = 180, maxLng = -180;
  bool hasPoints = false;

  for (int i = 0; i < rawFeatures.length; i++) {
    final feature = rawFeatures[i] as Map<String, dynamic>;
    final geometry = feature['geometry'] as Map<String, dynamic>?;
    final properties =
        Map<String, dynamic>.from(feature['properties'] as Map? ?? {});

    if (geometry == null) continue;

    final type = geometry['type'] as String;
    final coordinates = geometry['coordinates'];

    List<List<List<dynamic>>> polygonCoords = [];

    if (type == 'Polygon') {
      polygonCoords = [
        (coordinates as List).map((ring) => List<List<dynamic>>.from(
            (ring as List).map((c) => List<dynamic>.from(c as List)))).first ==
                null
            ? <List<dynamic>>[]
            : (coordinates as List)
                .map((ring) => (ring as List)
                    .map((c) => List<dynamic>.from(c as List))
                    .toList())
                .toList()
      ];
      // Simpler approach:
      polygonCoords = (coordinates as List)
          .map((ring) => (ring as List)
              .map((c) => List<dynamic>.from(c as List))
              .toList())
          .toList()
          .cast<List<List<dynamic>>>();
      polygonCoords = [polygonCoords]; // Wrap in list for uniform handling
    } else if (type == 'MultiPolygon') {
      polygonCoords = (coordinates as List)
          .map((polygon) => (polygon as List)
              .map((ring) => (ring as List)
                  .map((c) => List<dynamic>.from(c as List))
                  .toList())
              .toList())
          .toList()
          .cast<List<List<List<dynamic>>>>();
    } else {
      continue; // Skip non-polygon geometries
    }

    // Process each polygon part
    for (final polygon in polygonCoords) {
      final rings = <List<LatLng>>[];

      for (final ring in polygon) {
        final points = <LatLng>[];
        for (final coord in ring) {
          final lng = (coord[0] as num).toDouble();
          final lat = (coord[1] as num).toDouble();
          points.add(LatLng(lat, lng));

          // Track bounds
          if (lat < minLat) minLat = lat;
          if (lat > maxLat) maxLat = lat;
          if (lng < minLng) minLng = lng;
          if (lng > maxLng) maxLng = lng;
          hasPoints = true;
        }
        rings.add(points);
      }

      if (rings.isNotEmpty && rings[0].isNotEmpty) {
        features.add(SubBasinFeature(
          index: i,
          rings: rings,
          properties: properties,
        ));
      }
    }
  }

  LatLngBounds? bounds;
  if (hasPoints) {
    // Add small buffer around bounds
    final latBuffer = (maxLat - minLat) * 0.05;
    final lngBuffer = (maxLng - minLng) * 0.05;
    bounds = LatLngBounds(
      LatLng(minLat - latBuffer, minLng - lngBuffer),
      LatLng(maxLat + latBuffer, maxLng + lngBuffer),
    );
  }

  return ParsedGeoJson(features: features, bounds: bounds);
}

/// Get hazard-based color for a sub-basin based on debris-flow probability.
Color getHazardColor(Map<String, dynamic> props) {
  // Use P_3 (debris-flow probability at 40mm/hr rainfall)
  final p3 = props['P_3'];

  if (p3 == null) return Colors.blue.withOpacity(0.3);

  final probability = p3 is num ? p3.toDouble() : double.tryParse(p3.toString()) ?? 0.0;

  // USGS hazard thresholds
  if (probability >= 0.7) return Colors.red.withOpacity(0.6);      // High hazard
  if (probability >= 0.4) return Colors.orange.withOpacity(0.6);   // Moderate hazard
  if (probability >= 0.2) return Colors.yellow.withOpacity(0.5);   // Low hazard
  return Colors.green.withOpacity(0.4);                             // Very low hazard
}

/// Build flutter_map Polygon objects from parsed features.
///
/// [dimmed] reduces opacity of all polygons (used when a zone result is active
/// on top, so the full-fire basins fade into the background).
List<Polygon> buildPolygons({
  required List<SubBasinFeature> features,
  int? selectedIndex,
  required void Function(int index) onTap,
  bool dimmed = false,
}) {
  return features.map<Polygon>((feature) {
    final isSelected = feature.index == selectedIndex;

    // Color by hazard level if P_3 exists, otherwise use default blue
    Color defaultColor = getHazardColor(feature.properties);
    if (dimmed) {
      // Halve the alpha when dimmed to push full-fire basins into background
      defaultColor = defaultColor.withValues(alpha: defaultColor.a * 0.4);
    }

    return Polygon(
      points: feature.rings[0], // outer ring
      holePointsList: feature.rings.length > 1
          ? feature.rings.sublist(1)
          : null,

      // Use hazard color for non-selected, orange for selected
      color: isSelected
          ? Colors.deepOrange.withValues(alpha: 0.7)
          : defaultColor,

      borderColor: isSelected
          ? Colors.deepOrange
          : dimmed
              ? Colors.white.withValues(alpha: 0.2)
              : Colors.white70,

      borderStrokeWidth: isSelected ? 3.0 : 1.0,
    );
  }).toList();
}