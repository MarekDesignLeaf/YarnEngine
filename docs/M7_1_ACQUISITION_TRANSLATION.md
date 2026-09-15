# M7.1 Pattern Acquisition & Translation Pipeline

M7.1 adds a conservative text-to-canonical bridge for structured knitting abbreviations.

Accepted examples include `K 4`, `P2`, `K2TOG`, `YO`, `C2/2R`, and comma/semicolon separated sequences.
Mappings target only operation IDs already present in the engine registry.

The parser deliberately rejects repeat prose, grouped expressions, brackets, asterisks, `to end`,
`until`, and similar control language. Those constructions are not guessed. They are returned as
review items because an incorrect interpretation would change stitch topology and yarn consumption.

The pipeline stages are:
1. abbreviation translation
2. translation review when ambiguity exists
3. canonical structural validation
4. provenance/license review
5. Import Studio acceptance

No external pattern text or copyrighted catalogue is bundled with M7.1.
