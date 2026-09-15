# M7 Pattern Library Expansion & Import Studio

M7 is infrastructure for scaling the library without fabricating pattern content.

Pipeline:
structured bundle -> conservative normalization -> canonical structural validation -> duplicate/version check ->
provenance/license review -> explicit acceptance -> SQLite library + canonical pattern file + audit record.

The importer does NOT convert arbitrary natural-language knitting instructions into stitch semantics.
That would require a separate reviewed parser because ambiguous prose can change the pattern.

Accepted imports require `source_reference` and `license_id`. Structurally valid records lacking these fields
remain review-required and cannot be accepted from the web UI.

Batch inspection supports up to 1000 records per request. It performs validation only; acceptance remains explicit.

Normalization may standardize IDs, casing, row numbering defaults, token form, tags and technique lists.
It does not invent operations, repeat dimensions or source rights.
