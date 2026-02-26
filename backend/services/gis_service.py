"""
GIS Service - Spatial filtering for custom polygon analysis.

Instead of clipping rasters and running Wildcat (which requires private dependencies),
we spatially filter the pre-computed Franklin Fire basins to user-defined polygons.
"""

import json
from pathlib import Path
from typing import Dict, Any, List
from shapely.geometry import shape, Polygon
from shapely.ops import unary_union


class GISService:
    """Service for spatial filtering of debris-flow analysis results"""

    def __init__(self, source_results_file: Path):
        """
        Initialize service with source analysis results.

        Args:
            source_results_file: Path to source basins.geojson
        """
        self.source_results_file = Path(source_results_file)

    def filter_basins_by_polygon(
        self,
        polygon_geojson: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Filter Franklin Fire basins to only those intersecting user polygon.

        Args:
            polygon_geojson: GeoJSON polygon from user
                            {"type": "Polygon", "coordinates": [...]}

        Returns:
            Filtered GeoJSON FeatureCollection
        """
        # Load source basins
        if not self.source_results_file.exists():
            raise FileNotFoundError(
                f"Source results not found: {self.source_results_file}"
            )

        with open(self.source_results_file, 'r', encoding='utf-8') as f:
            basins_geojson = json.load(f)

        # Convert user polygon to shapely geometry (WGS84)
        user_polygon = shape(polygon_geojson)

        # Filter features that intersect the user polygon
        filtered_features = []

        for feature in basins_geojson.get("features", []):
            basin_geom = shape(feature["geometry"])

            # Check if basin intersects user polygon
            if basin_geom.intersects(user_polygon):
                # Optionally clip the basin geometry to user polygon
                # For now, we keep the full basin if it intersects
                filtered_features.append(feature)

        # Return filtered GeoJSON
        return {
            "type": "FeatureCollection",
            "name": "filtered_basins",
            "crs": basins_geojson.get("crs"),
            "features": filtered_features
        }

    def get_polygon_statistics(
        self,
        polygon_geojson: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get statistics about basins within user polygon.

        Args:
            polygon_geojson: User-defined polygon

        Returns:
            Statistics dictionary
        """
        filtered_basins = self.filter_basins_by_polygon(polygon_geojson)
        features = filtered_basins["features"]

        if not features:
            return {
                "basin_count": 0,
                "total_area_km2": 0,
                "hazard_distribution": {}
            }

        # Calculate statistics
        total_area = sum(f["properties"].get("Area_km2", 0) for f in features)

        # Hazard distribution at 40mm/hr rainfall (P_3)
        hazard_counts = {"High": 0, "Moderate": 0, "Low": 0, "Very Low": 0}

        for feature in features:
            p3 = feature["properties"].get("P_3", 0)
            if p3 >= 0.7:
                hazard_counts["High"] += 1
            elif p3 >= 0.4:
                hazard_counts["Moderate"] += 1
            elif p3 >= 0.2:
                hazard_counts["Low"] += 1
            else:
                hazard_counts["Very Low"] += 1

        return {
            "basin_count": len(features),
            "total_area_km2": round(total_area, 4),
            "hazard_distribution": hazard_counts,
            "average_probability_p3": round(
                sum(f["properties"].get("P_3", 0) for f in features) / len(features),
                4
            ) if features else 0
        }
