# M4.1 Database & Import Pipeline

## Added
* SQLite persistent store
* schema version tracking
* indexes for common filters
* FTS5 full-text search for yarns and patterns
* bulk yarn import
* bulk pattern import
* structural pattern validation before persistence
* yarn domain validation before persistence
* SHA-256 canonical checksums
* provenance audit log
* quarantine table for invalid or incomplete records
* structural duplicate detection for patterns
* near-duplicate candidate detection for yarns
* CLI for init/import/search

## Quarantine principle
Bad input is never silently repaired.
Invalid records remain available with source file, raw JSON, error code and error message so the importer is auditable.

## Duplicate principle
Pattern duplicates are detected from structural signatures, not only names.
Yarn duplicate detection is deliberately conservative and returns candidates rather than asserting identity.

## Source and licence audit
Every successful import records source/provenance fields and a checksum.
Pattern records additionally preserve license_id where available.

## Storage boundary
SQLite is the local/default backend for the next product stage.
The domain layer remains storage-neutral so PostgreSQL can be introduced later for multi-user deployment.
