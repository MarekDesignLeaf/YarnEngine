# How a piece is built

The consumption engine only ever needs operation counts, so it does not care
whether a piece is a stuffed head or a sleeve. Everything *around* it cares a
great deal: a stitch count is a circumference on one piece and a width on
another, "round 1" is a magic ring here and a cast-on there, and sixty stitches
is thirty centimetres across flat but nineteen of diameter in the round.

That, not the engine, is what limited this app to toys. So a construction is
named once, in `src/construction/types.py`, and the rest of the app asks it
rather than assuming. Adding a way of building something is adding an entry.

| id | worked | starts from | stitches are | for |
|---|---|---|---|---|
| `round_closed` | rounds | magic ring | circumference | amigurumi, a hat crown, a ball |
| `round_open` | rounds | a ring of stitches | circumference | a sleeve, a sock, a cowl, a bag |
| `flat_rows` | rows | a foundation row | width | a blanket, a scarf, a panel |
| `flat_shaped` | rows | a foundation row | width, changing | a jumper front, a shawl, a triangle |
| `motif_joined` | rounds | a motif | the layout | a granny square blanket |
| `branched` | rows | held stitches | mixed | a yoke, a body split for sleeves |

## What each construction decides

- **How the piece starts**, and therefore what row one is called. The rounds
  editor labels its first row from the construction — "magic ring", "ring of
  stitches", "foundation row" — and the written pattern and the make-mode use
  the same words. A closed start with nothing to work into is refused; an open
  one with no starting stitches is refused.
- **What the stitch counts mean**, and therefore the finished size. A closed
  round piece reports height and diameter, an open one length and
  circumference, a flat one width and length, a shaped one the range of widths
  and the outline row by row.
- **Which starting shapes exist.** A sphere is something a closed round piece
  can be and a blanket cannot, so the template list changes with the
  construction. So does the second field: "widest stitch count" where the piece
  grows, "how many rows" where it does not.
- **Round or row**, everywhere the app says it.

## Where it stays quiet

A branched piece has no single width or circumference, so no finished size is
offered — each branch has its own, and a confident number there would be a
fiction. The diameter of a closed round piece assumes it is roughly round in
section, which is true of a stuffed toy and less true of a tube pressed flat;
that is said rather than hidden. For flat rows, turning chains are not in the
operation counts, and the written pattern says so instead of quietly costing a
piece short.

## Compatibility

`program_type: "amigurumi"` still means `round_closed` and `"branch"` still
means `branched`, so everything calculated before this existed reads and costs
exactly as it did.
