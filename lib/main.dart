import 'package:flutter/material.dart';
import 'screens/enhanced_map_screen.dart';

void main() {
  runApp(const FireDashboardApp());
}

class FireDashboardApp extends StatelessWidget {
  const FireDashboardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Post-Wildfire Debris Flow Dashboard',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: Colors.blueGrey,
        brightness: Brightness.light,
        useMaterial3: true,
      ),
      home: const MapScreen(),
    );
  }
}