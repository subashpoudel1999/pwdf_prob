"""
Wildcat Service - Simplified version that serves pre-computed results.

Since Wildcat requires the private USGS 'pfdf' package, we use pre-computed
Franklin Fire analysis results instead of running Wildcat programmatically.
"""

import json
from pathlib import Path
from typing import Dict, Any


class WildcatService:
    """Service to load and serve Wildcat analysis results"""

    def __init__(self, projects_base_dir: Path):
        """
        Initialize service with projects directory.

        Args:
            projects_base_dir: Path to directory containing fire project folders
        """
        self.projects_base = Path(projects_base_dir)

    def has_results(self, fire_id: str) -> bool:
        """
        Check if pre-computed analysis results exist for a fire.

        Args:
            fire_id: Fire identifier (e.g., 'franklin-fire')

        Returns:
            True if basins.geojson exists
        """
        results_file = self.projects_base / fire_id / "assessment" / "basins.geojson"
        return results_file.exists()

    def get_results(self, fire_id: str) -> Dict[str, Any]:
        """
        Load pre-computed Wildcat analysis results as GeoJSON.

        Args:
            fire_id: Fire identifier

        Returns:
            GeoJSON FeatureCollection with debris-flow hazard analysis

        Raises:
            FileNotFoundError: If basins.geojson doesn't exist
        """
        results_file = self.projects_base / fire_id / "assessment" / "basins.geojson"

        if not results_file.exists():
            raise FileNotFoundError(
                f"No analysis results found for {fire_id}. "
                f"Expected file: {results_file}"
            )

        with open(results_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_status(self, fire_id: str) -> Dict[str, Any]:
        """
        Get analysis status for a fire.

        Args:
            fire_id: Fire identifier

        Returns:
            Status dictionary with has_results, feature_count, etc.
        """
        if not self.has_results(fire_id):
            return {
                "fire_id": fire_id,
                "status": "not_analyzed",
                "has_results": False
            }

        # Count features in basins.geojson
        results = self.get_results(fire_id)
        feature_count = len(results.get("features", []))

        return {
            "fire_id": fire_id,
            "status": "completed",
            "has_results": True,
            "feature_count": feature_count,
            "source": "pre-computed"
        }
