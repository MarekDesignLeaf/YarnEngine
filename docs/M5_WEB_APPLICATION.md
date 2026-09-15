# M5 Web Application

## Purpose
Expose the accumulated Yarn Consumption Engine as a usable local web application without weakening the evidence rules built into M0 to M4.1.

## Stack
FastAPI backend with a responsive static HTML/CSS/JavaScript frontend. SQLite remains the local persistence backend.

## User workflow
1. Select pattern and optional yarn.
2. Enter project width and height.
3. Enter gauge in stitches and rows per 10 cm.
4. Configure edge stitches and partial-repeat policy.
5. Select calculation mode.
6. Calculate.
7. Review yarn length, mass, package count, stitch/row grid, warnings and audit trace.

## Calculation modes
### Measured swatch
Production-oriented Tier A path. Requires swatch stitch count, row count and measured yarn length. The estimate is valid only when pattern, yarn behaviour, gauge and knitting conditions are sufficiently equivalent.

### Research geometry
Tier B path. Restricted in the web application to STOCKINETTE. It uses the published weft-knit geometric baseline already implemented in M1 and is explicitly labelled unvalidated for hand knitting.

## Library
The web app bootstraps its SQLite database from the M4.1 pattern and yarn library when the web database is empty.

## Safety and evidence boundary
The current repository contains synthetic yarn fixtures for testing. They are visibly labelled TEST in the UI. No synthetic calibration model is exposed as production evidence.

## Running locally
```bash
python -m pip install -r requirements-web.txt
python run_web.py
```
Then open `http://127.0.0.1:8000`.

## API
* `GET /api/health`
* `GET /api/patterns`
* `GET /api/yarns`
* `POST /api/calculate`

Interactive API documentation is available through FastAPI at `/docs`.

## Next stage
M5.1 can add authenticated projects, saved calculations, real yarn CRUD/import, real swatch capture forms and calibration record persistence.
