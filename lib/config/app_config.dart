class AppConfig {
  /// Backend API base URL.
  ///
  /// At build time, pass --dart-define=BACKEND_URL=https://your-server/api/v1
  /// to override for production deployments.
  ///
  /// For local development, mirrors the page's own scheme so Chrome never sees
  /// a mixed-content request (http page → http backend, https page → https
  /// backend).  This matters when VS Code's Flutter extension serves the app
  /// over HTTPS — without this, every fetch to http://localhost:8000 is blocked.
  static String get backendUrl {
    const compiled = String.fromEnvironment('BACKEND_URL', defaultValue: '');
    if (compiled.isNotEmpty) return compiled;

    // Always use plain HTTP for the local backend.
    // Chrome treats localhost as a "potentially trustworthy" origin, so
    // http://localhost requests are allowed even from an https:// page —
    // no mixed-content block applies.  Mirroring the page scheme (https →
    // https://localhost:8000) would fail because uvicorn runs plain HTTP.
    return 'http://localhost:8000/api/v1';
  }
}
