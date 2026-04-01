import 'package:flutter/material.dart';
import 'wildcat_dolan_screen.dart';
import 'retro_detection_screen.dart';
import 'ml_comparison_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.blueGrey.shade900,
        title: const Row(
          children: [
            Icon(Icons.local_fire_department, color: Colors.orangeAccent),
            SizedBox(width: 10),
            Text('Debris Flow Dashboard',
                style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
          ],
        ),
      ),
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Colors.blueGrey.shade900,
              Colors.blueGrey.shade700,
            ],
          ),
        ),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header
                const Text(
                  'Dolan Fire (2020)  ·  Big Sur, CA',
                  style: TextStyle(
                    color: Colors.white70,
                    fontSize: 13,
                    letterSpacing: 0.5,
                  ),
                ),
                const SizedBox(height: 4),
                const Text(
                  'Post-Wildfire Debris Flow Analysis',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 24),

                // Module 1: Dolan Fire × Real Wildcat
                _buildModuleCard(
                  context,
                  title: 'Dolan Fire  ×  Real Wildcat',
                  subtitle:
                      'Genuine USGS Wildcat v1.1.0 (pfdf) — flow-path slope, segment delineation, '
                      'Staley M1 / Gartner G14 / Cannon C10 hazard models. '
                      'Draw a zone to run analysis on a sub-area.',
                  badge: 'pfdf',
                  badgeColor: const Color(0xFF26C6DA),
                  cardColor: const Color(0xFF0D1B2A),
                  borderColor: const Color(0xFF26C6DA),
                  icon: Icons.science,
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const WildcatDolanScreen()),
                  ),
                ),

                const SizedBox(height: 14),

                // Module 2: Dolan Fire × Retro Detection
                _buildModuleCard(
                  context,
                  title: 'Dolan Fire  ×  Retro Detection',
                  subtitle:
                      'Pre/post spectral change via GEE (dNDWI, dBSI, dNBR) along stream corridors. '
                      'Composite debris-flow likelihood score per sub-basin, '
                      'with storm event discovery from ERA5.',
                  badge: 'GEE',
                  badgeColor: const Color(0xFFEF5350),
                  cardColor: const Color(0xFF1A0D0D),
                  borderColor: const Color(0xFFEF5350),
                  icon: Icons.satellite_alt,
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const RetroDetectionScreen()),
                  ),
                ),

                const SizedBox(height: 14),

                // Module 3: Dolan Fire × Wildcat vs ML
                _buildModuleCard(
                  context,
                  title: 'Dolan Fire  ×  Wildcat vs ML',
                  subtitle:
                      'Side-by-side: Staley M1 step-by-step on 886 Wildcat segments '
                      'vs Random Forest v3 (AUC-ROC 91%) on 492 GIS basins. '
                      'Optionally run live GEE feature extraction.',
                  badge: 'ML v3',
                  badgeColor: const Color(0xFF7C4DFF),
                  cardColor: const Color(0xFF130D2E),
                  borderColor: const Color(0xFF7C4DFF),
                  icon: Icons.compare_arrows,
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const MlComparisonScreen()),
                  ),
                ),

                const SizedBox(height: 28),

                // Footer
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.07),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.info_outline, color: Colors.white38, size: 16),
                      SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          'USGS Wildcat v1.1.0 · WhiteboxTools · Google Earth Engine · Random Forest v3',
                          style: TextStyle(color: Colors.white38, fontSize: 11),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildModuleCard(
    BuildContext context, {
    required String title,
    required String subtitle,
    required String badge,
    required Color badgeColor,
    required Color cardColor,
    required Color borderColor,
    required IconData icon,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        decoration: BoxDecoration(
          color: cardColor,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: borderColor.withValues(alpha: 0.40)),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: borderColor.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: borderColor, size: 26),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        title,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 15,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 7, vertical: 2),
                        decoration: BoxDecoration(
                          color: badgeColor,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          badge,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            letterSpacing: 0.5,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 5),
                  Text(
                    subtitle,
                    style: const TextStyle(
                      color: Colors.white54,
                      fontSize: 11,
                      height: 1.4,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            Icon(Icons.arrow_forward_ios, color: borderColor, size: 16),
          ],
        ),
      ),
    );
  }
}
