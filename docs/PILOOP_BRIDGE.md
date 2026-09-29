# PILOOP owner bridge (OpenCrochet Pro side)

Optional. Disabled unless `PILOOP_BRIDGE_SECRET` (>= 32 bytes, identical to PILOOP's) is set. An invalid value disables only the bridge; the app and normal login keep running.

| Variable | Meaning |
|---|---|
| `PILOOP_BRIDGE_SECRET` | Shared HMAC key. Never commit it. |
| `PILOOP_SSO_ADMIN_USERNAME` | Existing, active admin linked to the PILOOP owner. Required for SSO and bridge calls. |
| `PILOOP_SSO_ORIGIN` | Allowed SSO `Origin`, default `https://piloop.co.uk`. |

- `POST /api/auth/piloop-sso`: one-minute, single-use signed assertion in a form body. It must carry an exact `Origin` and signs in the linked admin.
- `POST /api/piloop-bridge/v1`: HMAC-signed server-to-server account management (list/create/update/catalogue_roles) on the real `UserStore`, with timestamp, body hash and nonce.
- The replay database is `piloop_bridge.sqlite` in `YARNENGINE_DATA_DIR`. It persists across restarts.
- The linked owner holds every catalogue authority, even without the bridge. It cannot be demoted, deactivated or deleted through the bridge or through `/api/admin/users`.

Full audit, staging procedure, deployment and rollback: `piloop-private-website` → `AUDIT_2026-09-29.md`, `ADMIN_RUNBOOK.md`.

## Administration moved to PILOOP

While the bridge is enabled, the OpenCrochet **Admin** tab is hidden (`/api/auth/me` returns `admin_console: "piloop"`). The following routes return 403 to browser sessions:
- `/api/admin/users*`
- `/api/admin/catalogue-roles`
- `/api/admin/backup`
- `/api/admin/logs`
- `/api/admin/ingestion/*`
- `/api/admin/settings/vision*`
- `PUT /api/admin/settings/company`

PILOOP administration performs these through signed bridge actions:
- `logs`, `ingestion_stats`
- `vision_get`, `vision_set`, `vision_test`, `vision_clear`
- `company_get`, `company_set`
- user `update` / `delete`
- `POST /api/piloop-bridge/v1/backup` (signed for that exact path)

Business routes stay in OpenCrochet: product lines, production stages, product photos, yarn and supplier edits.

**Break-glass:** remove `PILOOP_BRIDGE_SECRET` and redeploy. The local Admin tab and routes return automatically.
