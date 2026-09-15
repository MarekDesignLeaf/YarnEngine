# M4 Pattern & Yarn Library Infrastructure

## Purpose
Scale the engine from a calculation prototype into a searchable, versioned knowledge library.

## Added
* typed yarn registry
* typed pattern metadata
* pattern families
* pattern tags and techniques
* pattern version registry
* yarn and pattern search
* broad yarn/gauge compatibility screening
* provenance/evidence fields
* JSON schema for yarn records
* non-commercial synthetic yarn fixtures for tests

## Standards boundary
CYC yarn weight categories 0–7 and their stockinette gauge ranges are stored only as broad screening guidance.
They are not treated as interchangeability rules. Gauge swatches remain authoritative for project compatibility.

## Yarn identity
The library separates:
* CYC weight category
* package mass and length
* derived or measured tex
* optional nominal diameter
* optional WPI
* fibre composition
* declared needle range
* provenance and evidence level

This prevents a category such as “4 Medium” from being mistaken for a complete physical yarn model.

## Pattern identity
A pattern is identified by `(pattern_id, version)`.
Metadata is separate from the executable pattern definition, allowing names, tags, classification and licensing metadata to evolve without modifying calculation semantics.

## Scaling
The registry interface is currently in-memory and file-backed for transparency.
The domain API is intentionally storage-neutral, so M4.1 can replace the file backend with SQLite/PostgreSQL without changing the calculation engine.

## Next
M4.1 should add:
* SQLite persistence
* indexes and full-text search
* import validation and quarantine
* duplicate detection
* source/licence audit
* bulk pattern import
* migration/version tooling
