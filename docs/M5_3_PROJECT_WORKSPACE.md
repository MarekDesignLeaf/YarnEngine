# M5.3 Project Workspace

A project stores a complete calculation session rather than only a result.

Stored fields include:
- project name and description
- pattern ID and version
- yarn ID
- physical dimensions
- gauge
- edge settings
- partial-repeat policy
- calculation mode
- measured swatch or geometry input
- allowance
- complete calculation result snapshot
- warnings, confidence and audit contained in the result
- status and timestamps

Projects are version-safe because the selected pattern version is persisted explicitly.

## API
GET /api/projects
GET /api/projects/{id}
POST /api/projects
PUT /api/projects/{id}
DELETE /api/projects/{id}

## Current scope
Projects are local single-user records in SQLite.
Authentication, cloud sync and collaborative editing are intentionally deferred.
