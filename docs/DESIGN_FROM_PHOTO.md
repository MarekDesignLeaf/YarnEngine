# Designing a pattern from a photo

`src/design/` turns "a photo of this, about 24 cm tall" into the pieces to
crochet and the rounds for each one.

## The split that makes it trustworthy

Two different kinds of question are answered by two different things, and they
are deliberately not mixed:

| Question | Answered by | Certainty |
| --- | --- | --- |
| What pieces is this made of, roughly how big is each relative to the whole? | a vision model, from the photo | an estimate |
| How many stitches in each round, how many rounds, which stitch? | `src/design/shapes.py`, from your gauge and the stated height | calculated |

The model is asked for shapes and proportions only, and is told not to return
stitch counts or pattern text. Its answer passes through `validate_parts()`,
which drops anything outside the known archetypes or sensible proportions, so
a confused reply produces fewer parts, never invented instructions. Every
number a person works from is then derived, which is why generated rounds are
always internally consistent — `tests/design/` checks each one against the same
`analyse_rounds` validator the editor uses.

## Rounds follow the surface, not the height

A round advances one row height *along the profile*, not up the vertical axis.
At the crown of a ball the fabric spirals outwards almost flat, so stepping
vertically would jump straight to a wide round and generate a pattern that
opens with a decrease. Walking by arc length is what the hook does, and the
familiar 6 / 12 / 18 / 24 crown falls out of the geometry by itself.

Radius alone does not make a shape round: the height has to follow the same
angle. A ball whose radius follows sin(theta) while its height rises linearly
is a lemon with pointed ends, and it was generating heads with visibly too
little fabric at the crown -- pairing it with h = 1 - cos(theta) makes the
profile an actual circle. Each archetype's profile starts (t = 0) at the magic
ring, in the order the piece is worked — an ear starts at its tip and widens. Closed pieces stop at 6
stitches to be cinched shut; open pieces (limbs, ears, domes) end at the rim to
be stuffed and sewn on.

## Configuration

The key can be set either way; a key saved in the app wins over the
environment, and the admin page says which one is in use.

**In the app (usual way).** Admin -> *Reading photos (AI vision)*: paste the
key, optionally name a model, and press *Test it* to make one tiny real request
that proves the credentials work. The field is write-only — `GET
/api/admin/settings/vision` returns whether a key is set, where it came from
and a masked hint (`sk-ant-...0000`), never the key. It is stored in the
settings table under `secret.anthropic_api_key`, and `src/storage/backup.py`
deletes every `secret.*` setting from the snapshot it zips, so a downloaded
backup can be mailed around without carrying a spendable credential. Restoring
a backup therefore means entering the key again.

**As a platform secret.** `ANTHROPIC_API_KEY` and `YARNENGINE_VISION_MODEL` are
still read when nothing is saved in the app, for anyone who would rather keep
credentials in Railway's own variable store.

Without either, the photo endpoint answers 503 and says so; describing the
parts by hand keeps working. Photo analysis is capped at `PHOTO_MAX_PER_HOUR`
(20) requests per account per hour, because each one costs money at the
provider.

## Endpoints

- `GET /api/design/status` — is photo reading available (and from which
  source), and the known archetypes and part categories.
- `GET`/`PUT /api/admin/settings/vision` — read the masked state / set or clear
  the key, admin only.
- `POST /api/admin/settings/vision/test` — one real request to confirm the key
  works.
- `POST /api/design/generate` — parts + height + gauge -> patterns. Offline and
  deterministic; no API key involved.
- `POST /api/design/from-photo` — images (base64) + approximate height -> the
  same, with a `photo_reading` block stating the model's confidence, what the
  photo could not show, and anything dropped as unusable.

## Yarn length and weight

When a yarn (or just a yarn diameter) is chosen in *Yarn, hook and gauge*, the
designer costs every part with the same engine as the single-piece calculator,
once per part, multiplied by how many of that part are needed. So the per-part
figures and the total can never drift from what the calculator would say for
the same piece — a test asserts they agree to the centimetre.

Weight and ball count need a yarn record with a known tex and package length;
with only a diameter, length alone is reported and the app says why rather than
estimating grams from nothing. The totals, per-part figures and the allowance
also appear at the top of the written pattern.

## Colour

Colour is never typed in. A shade is a row in the `yarn_colours` table, which
holds a yarn's own shade card where one has been captured and the generic craft
palette (`data/colours/standard_palette.json`) everywhere else, and
`GET /api/colours?yarn_id=` is what fills the picker. When a photo is read, the
colour the model describes ("light brown") is *matched* onto that catalogue by
`src/library/colours.py` rather than stored as written -- so the app always
shows a real catalogue entry, already selected, which can then be changed to a
different catalogue entry. A description that matches nothing leaves the colour
unset instead of inventing one.

All 53 Yarnsmiths ranges carry their real shade cards — 1,844 shades in
`data/colours/yarnsmiths/`, read from each range's own page. The name and code
are as the maker lists them; the hex was measured from that shade's ball photo
on the same page (the yarn's own pixels, with the studio background and the
extremes of shadow and highlight discarded), so it is an observation of the
shop's picture rather than a colour invented from the shade's name — which is
why "Bottle Green" comes out `#132a1a` and not a guess. The colour family each
shade is filed under is worked out from its hue, not claimed from the maker:
nearest-neighbour in RGB puts every dark shade next to black, so hue decides
the family and saturation and lightness separate the greys from the browns.
`scripts/import_yarnsmiths_shades.py` replays the capture in
`data/ingestion/yarnsmiths_shades_capture_2026-09-18.txt`. The chosen shade is what the header shows, what
the exploded piece drawings are filled with, and what the 3D preview is
rendered in.

## Reading the figures back

Every part lists its stitches, its metres and its grams, and the yarn bar shows
the grams per metre those grams came from, so a weight can be checked by hand:
grams = metres x g/m, and nothing else. Rounding happens once, at the figure a
person reads, and the totals are built from those rounded figures -- otherwise
"1.9 g each" for two pieces sits next to a 3.9 g total and the table stops
being believable. `tests/web/test_design_weights.py` pins all of that down.

## What it cannot do

A photo shows one side of a finished object. It cannot show the back, the
inside, how the pieces are joined, or where the stuffing goes, and the reading
of proportions is an estimate from a single viewpoint. The generated pattern is
a starting point sized to your gauge — the app says so on screen rather than
implying the result is a verified pattern.
