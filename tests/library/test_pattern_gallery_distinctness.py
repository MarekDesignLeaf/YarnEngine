"""Regression guard for the pattern gallery data-quality bug fixed in M12.2.

The M12 bulk pattern import added hundreds of "different" crochet patterns
that were combinatorial variants of the same fabric with only the declared
repeat width changed (e.g. "solid single crochet, repeat 1" through
"repeat 16"). Because the gallery tiles a pattern's minimal repeat out to
fill a thumbnail, all of those variants rendered as pixel-identical stitch
charts -- 613 of the 735 crochet patterns turned out to be indistinguishable
duplicates of another pattern already in the library.

This test computes each active crochet pattern's true visual signature (its
rows, reduced to their minimal repeating stitch sequence) and fails if two
different pattern_ids share one, so a future bulk import can't reintroduce
silent, un-browsable duplicates.
"""
from collections import defaultdict
from pathlib import Path

from src.library.loader import load_library

ROOT = Path(__file__).resolve().parents[2]


def _minimal_period(ops):
    n = len(ops)
    for p in range(1, n + 1):
        if n % p == 0 and all(ops[i] == ops[i % p] for i in range(n)):
            return tuple(ops[:p])
    return tuple(ops)


def _row_ops(row):
    ops = []
    for token in row.sequence:
        ops.extend([token.op] * token.n)
    return ops


def visual_signature(pattern):
    """The fabric a pattern actually produces, independent of its declared
    (and possibly redundant) repeat width/height."""
    row_sigs = [(row.side, _minimal_period(_row_ops(row))) for row in pattern.rows]
    n = len(row_sigs)
    for p in range(1, n + 1):
        if n % p == 0 and all(row_sigs[i] == row_sigs[i % p] for i in range(n)):
            return tuple(row_sigs[:p])
    return tuple(row_sigs)


def test_no_two_active_crochet_patterns_render_identically():
    reg = load_library(ROOT)
    by_signature = defaultdict(list)
    for key, pattern in reg.patterns.items():
        meta = reg.pattern_metadata[key]
        if not meta.active:
            continue
        if "crochet" not in [str(t).lower() for t in meta.techniques]:
            continue
        by_signature[visual_signature(pattern)].append(meta.pattern_id)

    duplicates = {sig: ids for sig, ids in by_signature.items() if len(ids) > 1}
    assert not duplicates, (
        f"{sum(len(v) - 1 for v in duplicates.values())} pattern(s) render identically "
        f"to another pattern already in the gallery: {duplicates}"
    )
