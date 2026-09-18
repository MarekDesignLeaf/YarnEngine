# Importing somebody else's pattern

Written crochet is prose, not a format. The same round turns up as

    R3: [sc, inc] x 6 (18)
    Round 3: *1 sc, 2 sc in next st; rep from * around -- 18 sts
    Round 3: Work (1 single crochet, 1 increase) and repeat this 6 times around.
             You will have 18 stitches.

`src/pattern_import/crochet_rounds.py` reads all three into the operation
counts the calculator, the 3D preview and the make-mode already use.

## It reports rather than guesses

Every line it cannot read comes back as its own issue with the text that
defeated it, and the rounds it did read are checked twice: against the stitch
count the pattern itself states, and against `analyse_rounds`, the same
validator the rounds editor uses. A pattern that half-parses arrives
half-parsed and says so. A pattern whose round does not use up the stitches the
previous one left is called out with both numbers.

That is the whole design principle here: a wrong pattern that looks right
costs someone an evening and a ball of yarn.

## Dialect is not spelling

In UK terms "double crochet" is what US terms call single crochet, so the same
words describe different fabric — read the wrong way round, every stitch in the
piece is the wrong height. The dialect is an explicit choice, and a pattern
whose vocabulary looks like the other one (htr, dtr, never "sc") is flagged
rather than silently reinterpreted.

## Where a pattern can come from

`GET /api/import/sources` answers this in the app, including the nos:

- **Paste the text** — anything you can copy.
- **A file** — plain text, markdown, or a PDF that holds real text. A PDF of
  scanned pages holds pictures, not text; that is said plainly instead of
  returning an empty pattern.
- **From a photo** — the page is transcribed by the vision model and then read
  by the same deterministic parser. The model is asked to transcribe and
  nothing else: what the stitches mean is worked out afterwards, so a
  misreading shows up as an unreadable line rather than as invented rounds.
- **A web address** — not offered. Fetching someone's pattern page and keeping
  it here is their copyright, not ours.
- **Ravelry** — not offered. A Ravelry pattern is licensed to the person who
  bought it, not to this app. Download your own copy and import the file.
- **YouTube** — not offered. A video has no pattern text to read.
