class FireData {
  final String id;
  final String fireName;
  final int year;
  // We don't strictly need 'date' or 'file' for the dropdown, 
  // but let's keep the model simple.

  FireData({
    required this.id,
    required this.fireName,
    required this.year,
  });

  factory FireData.fromJson(Map<String, dynamic> json) {
    return FireData(
      id: json['id'] as String,
      fireName: json['fire_name'] as String,
      year: json['year'] as int,
    );
  }

  /// Display label for dropdown: "ABNEY (2017)"
  String get displayName => '$fireName ($year)';
}