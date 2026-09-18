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

Each archetype's profile starts (t = 0) at the magic ring, in the order the
piece is worked — an ear starts at its tip and widens. Closed pieces stop at 6
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

## What it cannot do

A photo shows one side of a finished object. It cannot show the back, the
inside, how the pieces are joined, or where the stuffing goes, and the reading
of proportions is an estimate from a single viewpoint. The generated pattern is
a starting point sized to your gauge — the app says so on screen rather than
implying the result is a verified pattern.
