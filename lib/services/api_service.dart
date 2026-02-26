import 'dart:convert';
import 'package:flutter/services.dart' show rootBundle;
import '../models/fire_data.dart';

class ApiService {
  // We no longer need a baseUrl because files are local!
  
  /// Fetch list of all available fires from the local JSON index.
  static Future<List<FireData>> fetchFireList() async {
    try {
      // Load the index file created by your Python script
      final String response = await rootBundle.loadString('assets/data/fires.json');
      final data = json.decode(response);
      
      final List fires = data['fires'];
      return fires.map((f) => FireData.fromJson(f)).toList();
    } catch (e) {
      print("Error loading fire list: $e");
      // Return empty list rather than crashing
      return []; 
    }
  }

  /// Fetch GeoJSON for a specific fire from local assets.
  static Future<Map<String, dynamic>> fetchFireGeoJson(String fireId) async {
    try {
      // Construct the path: assets/data/2017_ABNEY.json
      final String response = await rootBundle.loadString('assets/data/$fireId.json');
      return json.decode(response) as Map<String, dynamic>;
    } catch (e) {
      throw Exception('Failed to load local GeoJSON for $fireId: $e');
    }
  }
}