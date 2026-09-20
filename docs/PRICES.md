# Real prices

A yarn's price in this app was a number somebody typed. It goes out of date the
day after it is typed, and nothing on the screen tells you which day that was —
so a maker costs a bear off a figure from last season and does not know it.

## Where a price now comes from

Each shop on a yarn's list can be asked what it charges, from its own product
page. The answer is stored with the date it was read, the shop it came from and
how the page stated it, and the old figure is kept in a history rather than
overwritten.

Costing then uses **the cheapest price you could actually buy today**, and says
which shop said so and when — because a costing sheet nobody can trace is one
nobody can defend to a customer.

## What is read, and what is refused

Only a price the shop has **published in machine-readable form**: schema.org
`Product`/`Offer` as JSON-LD, the same as microdata, or Open Graph product
tags. Every serious shop platform emits one of these, because search engines
require it. That is a *stated* price — the shop itself saying "this costs 4.75
GBP" in a field it maintains.

What is never done is lifting a number off the visible page because it sits
next to a pound sign. A page with no published price gets "this page does not
publish a price in a form that can be read reliably", and nothing changes. A
wrong price in a costing sheet is worse than no price, because a maker prices
a piece from it.

The same rule the rest of the app follows about colours, gauges and stitch
counts: use what was stated, and say so when there is nothing to use.

## The details that decide whether a figure is right

- **Several prices on one page** — variants, a sale price beside the old one, an
  `AggregateOffer` range — take the lowest, which is what a shopper is offered,
  and say how many there were.
- **Decimal commas.** Half the world writes `1.234,56` and the other half
  `1,234.56`; `4,75` means four seventy-five. The separator that comes last is
  the decimal one, and a lone group of three digits is thousands.
- **Ranges.** `£4.75 – £6.00` starts at 4.75, and the dash has to be normalised
  first or the two glue into 4756.
- **Out of stock.** A price at a shop that has run out is passed over, and used
  only when it is the only one on file — saying so.
- **Other currencies** are listed but never converted, because converting means
  inventing a rate. Costing happens in one currency and names the rest.
- **Age.** Counted in calendar days, the way a person means it: a price read
  last night was read yesterday. Past 30 days it is still used — it is the best
  thing there is — but it is called out, because quietly under-pricing off a
  season-old figure is the failure this exists to stop.
- **A failed check keeps the last good price.** A shop being down for an
  afternoon is not a reason to lose what it charged yesterday.

## Being a good guest

The URL is one a person typed in, which makes this one of the few places the
app reaches an address it did not choose. So: http and https only, never an
address on the server's own network, a 12-second timeout, a 3 MB cap, one page
and no crawling, and a user agent that says who is calling and why.

Prices are checked when somebody presses the button, never on a schedule, and
the same page is not asked twice within five minutes. A shop generous enough to
publish structured prices should not be repaid with traffic.
