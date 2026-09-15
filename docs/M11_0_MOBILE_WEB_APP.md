# M11.0 Mobile Web Application

Added responsive mobile layout, PWA manifest, service worker application-shell caching, Home Screen metadata, Docker deployment, generic process deployment files, and public health endpoint compatibility.

Supported delivery model: one HTTPS YarnEngine server, accessed from Android, iOS, tablets and desktop browsers.

No phone needs Python. Python runs only on the server.

The service worker caches the application shell. API requests remain network-first and are deliberately not cached, preventing stale calibration or production results from being silently served.

A public URL is not included because this artifact has not been deployed to a hosting account.
