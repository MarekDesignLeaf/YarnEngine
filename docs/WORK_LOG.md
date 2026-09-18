# The work log

Every calculation that succeeds is written down, by the server, as it happens.
Nobody has to remember to press Save, because the thing people want back later
— what did that bear cost me in yarn? — is exactly the thing they never think
to save at the time.

## What a line holds

The figures a person actually looks up (piece name, kind, yarn, shade, length,
weight, balls, stitches, pieces, hook and gauge) are columns, so a log can be
searched and added up. The full request and result are kept alongside, so an
entry can be reopened with everything it was calculated from and run again
after a change, rather than retyped.

Figures are stored at the precision they are read at — 27.17 m, not
27.16741497698143 — and the result panel rounds to the same place before
displaying, so the same piece cannot read 26.0 m on one screen and 25.9 m on
the other.

## Clicks are not pieces

Pressing Calculate again on the same piece does not add a second line. An
identical request from the same person within a day folds into the entry
already there and counts the repeat, so the log is a list of work, not of
button presses. The same piece calculated again next week is genuinely new work
and gets its own line.

`fingerprint()` is what decides "the same piece": the kind of calculation plus
every input, hashed. Change the gauge, the yarn, a single round — it is a
different piece.

## Whose log is it

A log belongs to the person who made it and is invisible to everyone else. It
becomes readable by naming one colleague at a time on the *Sharing* card, and
stops being readable the moment that is switched off. Sharing is never
transitive: naming Eva does not let Eva's colleagues in.

What is shared is read-only. Notes, the private flag and deletion belong to the
owner alone, and a `403`/`404` — not a filtered-out row — is what the API gives
anyone else, so nothing about an unshared log leaks through its error
behaviour.

Individual entries can be held back with *private* while the rest of the log is
shared, for work that happens to be someone else's business. A private entry is
absent from the shared list, from the shared totals, and from a direct fetch by
its id.

`/api/colleagues` lists who may be picked: names and roles only, never email
addresses.

## Endpoints

- `GET /api/worklog` — my log, or `?owner=<user_id>` for a colleague's when it
  has been shared; `q`, `kind`, `yarn_id`, `limit`, `offset` narrow it, and the
  answer carries the totals.
- `GET /api/worklog/{id}` — one entry with its request and result.
- `PATCH`/`DELETE /api/worklog/{id}` — note, title, private flag; owner only.
- `GET`/`POST /api/worklog/shares`, `DELETE /api/worklog/shares/{user_id}`.
- `GET /api/colleagues`.

Recording is deliberately best-effort: a failure to write the log is swallowed,
because a missing line is a nuisance and a 500 on a calculation that actually
succeeded is not. `tests/worklog/` and `tests/web/test_worklog_api.py` cover
the writing, the folding, and every rule above about who can see what.
