import 'dart:convert';
import 'package:http/http.dart' as http;

class WildcatService {
  static const String baseUrl = 'http://localhost:8000/api/v1';

  /// Check if a fire has Wildcat analysis results
  static Future<bool> hasResults(String fireId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/fires/$fireId/status'),
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return data['has_results'] == true;
      }
      return false;
    } catch (e) {
      print('Error checking Wildcat status: $e');
      return false;
    }
  }

  /// Get fire information and metadata
  static Future<Map<String, dynamic>> getFireInfo(String fireId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/fires/$fireId/info'),
    );

    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Failed to fetch fire info: ${response.statusCode}');
    }
  }

  /// Fetch Wildcat analysis results (GeoJSON)
  static Future<Map<String, dynamic>> fetchWildcatResults(String fireId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/fires/$fireId/results'),
    );

    if (response.statusCode == 200) {
      return json.decode(response.body) as Map<String, dynamic>;
    } else {
      throw Exception('Failed to fetch Wildcat results: ${response.statusCode}');
    }
  }

  /// Get analysis status (for progress tracking)
  static Future<String> getAnalysisStatus(String fireId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/fires/$fireId/status'),
    );

    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      return data['status'] as String;
    }
    throw Exception('Failed to get status');
  }
}
