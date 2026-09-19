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

## How tall a piece is

A round is one row-height of fabric *along the surface*, not one row-height
straight up. Where a round grows fast the yarn is travelling outwards, and the
piece gets wider rather than taller — which is why increasing six stitches
every round makes a flat circle and not a tall stack of rings.

So height is walked along the profile: for each round, the radius change is
the spread, and the rise is `sqrt(row² − spread²)`, which goes to zero when a
round spreads faster than a row is tall. A piece whose height stays under a
sixth of its width is reported as a circle with a diameter and no height at
all, because a ten-centimetre coaster is not four centimetres thick.

Multiplying rounds by row height is kept alongside as `height_if_stacked_cm`,
since that is what most calculators do and it is useful to see the difference.
The 3D preview builds its profile the same way, so the picture and the figure
cannot disagree.

## Starting shapes

The rounds editor offers a shape to start from — a ball, an egg, a tube, a
dome, a cone, an arm or leg, a flat circle — and asks for it in centimetres,
because centimetres are what a maker has a feeling for and stitch counts are
what the gauge turns them into.

Those rounds come from `POST /api/shapes/rounds`, which is the same generator
the photo designer uses. The browser used to work them out itself, adding a
fixed number of stitches every round and then working straight. That makes a
drum whatever the option is called: at 7.6 cm across it came out 3.6 cm tall,
because the increases and decreases spread flat and only the straight middle
had any height. A ball is not a stack of equal rounds — it is a profile, and
the stitch count has to follow its radius at every round.

Each shape has a height it is normally made at, as a multiple of its width: a
ball as tall as it is wide, a leg two and a half times as long. That height
follows the width until the maker types one of their own, after which it is
theirs and nothing moves it again — which is how an egg-shaped head is one
number away from a round one.

Nothing is asserted that the geometry does not support. A flat circle is not
asked how tall it is. A piece the generator closes says what it closes down
to, and one left open says how many stitches are waiting to be sewn on.
