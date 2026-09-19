# Legs, arms and tentacles

A piece worked in the round is one circle, and most toys are not. Somewhere
there has to be a moment where one circle becomes two, or two become one, and
the editor had no way to say it: a pair of legs was two unrelated pieces and
the body they turn into was a third, with nothing recording that they were the
same toy.

There are three ways a crocheter does this, and picking the right one matters
more than the arithmetic.

## Made separately and sewn on

Each part is its own finished piece, stitched on at the end. Ears, arms,
tails, a nose — and an octopus's tentacles, which is the one most people ask
about. A tentacle is not split off anything. There is no arithmetic here at
all, and the app says so rather than inventing some: the stitch counts are
whatever each piece needs, and where the pieces go decides what the toy looks
like.

## Made separately, then joined into one round

The classic start of a two-legged toy. Both legs are worked and left with
their stitches live; one round then goes around the first, straight on around
the next, and from there it is a body.

The thing that goes wrong here is the chains. Going around the outside of the
pieces crosses from one to the next **once per piece** — two legs meet in two
places, front and back — so two chains at each crossing adds four stitches,
not two. Counting them once is how a body comes out short.

    12 + 12, no chains                 → 24 sts, and a small gap to sew up
    12 + 12, ch 2 at each crossing     → 28 sts
    12 + 12 + 12 + 12, ch 2            → 56 sts

Skipping a stitch where the pieces touch, which some patterns do so the join
does not bulge, takes one off each side of every crossing.

## Split off this piece

One round divided, each share bridged with a few chains to close it into its
own ring. Trousers worked downwards, a body that becomes two legs, a mitten
thumb set aside.

Each branch ends up with **its share plus its chains**, which is why splitting
44 stitches in half with two chains gives two tubes of 24 and not of 22. Where
the round does not divide evenly the remainder is spread one stitch at a time,
so the legs match instead of one coming out three stitches fatter.

The split is offered from whichever round is highlighted in the 3D preview —
the round the maker is looking at is the round they mean — and otherwise from
the widest round, because offering to split the last round of a closed ball is
six stitches and an immediate wall of errors.

## Where it says no

Below about four stitches a tube cannot be worked in the round at all, and
below six it is fiddly enough that most people make the piece separately and
sew it on. Both are said in those words, and when a split will not work the
stitch counts are not shown at all: printing `piece 3: 1 st (3)` above "3
stitches cannot be worked in the round" is showing someone a pattern and then
telling them it is not one.

## What it costs

The chains are stitches. They go into the new round's count and they eat yarn,
so they come back as `CH` operations alongside the stitches worked, and the
consumption engine costs them like anything else.
