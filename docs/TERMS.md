# UK or US terms

US "single crochet" and UK "double crochet" are the same stitch. US "double
crochet" is a UK "treble". So `dc` means one thing in an American pattern and
a stitch twice as tall in a British one, and a pattern that does not say which
it uses can quietly ruin a piece.

The app stores stitches as operations, never as words: `SC` is a stitch, not a
name. `src/crochet/terms.py` is the only place that turns an operation into a
word, and it does it twice — once for each side of the Atlantic.

**Switching changes nothing about the piece.** The stitches, the counts, the
yarn, the size and the finished measurements are identical; only the words
move. That is asserted in the tests, because it is the whole promise: if
switching the flag changed a number, the app would be lying about one of them.

Eighteen of the twenty-three stitches the app knows are called something
different either side. Five — chain, the increase, the decrease, puff and
popcorn — are the same, and the switch leaves them alone.

The choice lives in the header as two flags, is remembered between visits, and
carries into everything that prints a stitch: the rounds editor and its typed
lines, the written pattern, the make-mode, the stitch reference (which also
shows what the stitch is called on the other side), the list of stitches a
piece used, and the default dialect for reading an imported pattern.

`GET /api/terms` returns the whole conversion table, including the terms that
are shared, for showing the conversion itself.
