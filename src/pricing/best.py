"""Which price a costing should actually use, and where it came from.

A yarn can have a price somebody typed in months ago, and several prices read
off shops' own pages on different days, possibly in different currencies, some
of them for something the shop has since run out of. Picking one silently is
how a maker ends up pricing a bear off a figure nobody can account for.

So one is picked by stated rules -- the cheapest you could actually buy today,
in one currency, and the freshest of those -- and it comes back saying which
shop, on what day, and what was passed over. A figure you cannot trace is a
figure you cannot argue with a customer about.
"""
from __future__ import annotations

from datetime import datetime, timezone

# After this long a price is still used -- it is the best thing available --
# but it is called out, because yarn prices move and a season-old figure
# quietly under-pricing a piece is the failure this whole thing exists to stop.
STALE_AFTER_DAYS = 30


def _parsed(when: str | None) -> datetime | None:
    if not when:
        return None
    try:
        text = str(when).replace("Z", "+00:00")
        moment = datetime.fromisoformat(text)
        return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def age_in_days(when: str | None, now: datetime | None = None) -> int | None:
    moment = _parsed(when)
    if not moment:
        return None
    now = now or datetime.now(timezone.utc)
    # Calendar days, not periods of 24 hours: a price read last night was read
    # yesterday, whatever the clock makes of it.
    return max(0, (now.date() - moment.date()).days)


def describe_age(days: int | None) -> str:
    if days is None:
        return "never checked"
    if days == 0:
        return "checked today"
    if days == 1:
        return "checked yesterday"
    if days < 14:
        return f"checked {days} days ago"
    if days < 60:
        return f"checked {days // 7} weeks ago"
    return f"checked {days // 30} months ago"


def best_price(suppliers: list[dict], *, typed_amount=None, typed_currency=None,
               now: datetime | None = None, stale_after_days: int = STALE_AFTER_DAYS) -> dict:
    """The price to cost with, named."""
    now = now or datetime.now(timezone.utc)
    checked = []
    for row in suppliers or []:
        amount = row.get("checked_price")
        if amount in (None, "") or float(amount) <= 0:
            continue
        checked.append({
            "supplier": row.get("name") or "a shop",
            "supplier_id": row.get("id"),
            "amount": round(float(amount), 2),
            "currency": (row.get("checked_currency") or typed_currency or "").upper() or None,
            "checked_at": row.get("checked_at"),
            "age_days": age_in_days(row.get("checked_at"), now),
            "availability": row.get("availability"),
            "url": row.get("product_url"),
        })

    if not checked:
        amount = None if typed_amount in (None, "") else round(float(typed_amount), 2)
        return {
            "amount": amount,
            "currency": (typed_currency or "GBP").upper() if amount is not None else None,
            "from": "typed" if amount is not None else None,
            "supplier": None, "checked_at": None, "age_days": None, "stale": False,
            "alternatives": [], "other_currencies": [],
            "note": ("This is the price on file for the yarn, typed in by hand — nothing has "
                     "been checked against a shop, so it is as current as whoever typed it."
                     if amount is not None else
                     "No price is set for this yarn and no shop has been checked, so the yarn "
                     "is not in these figures."),
        }

    # Prices in different currencies are not comparable, and converting them
    # would be inventing a rate. Cost in one currency and list the rest.
    wanted = (typed_currency or "").upper() or None
    by_currency: dict[str, list[dict]] = {}
    for row in checked:
        by_currency.setdefault(row["currency"] or "unknown", []).append(row)
    if wanted and wanted in by_currency:
        currency = wanted
    else:
        currency = max(by_currency, key=lambda k: (len(by_currency[k]), k != "unknown"))
    same = by_currency[currency]
    others = [row for key, rows in by_currency.items() if key != currency for row in rows]

    # A price at a shop that has run out is not a price you can pay, so it is
    # only used when it is the only one there is.
    in_stock = [r for r in same if r.get("availability") != "out of stock"]
    only_out_of_stock = not in_stock
    buyable = in_stock or same
    cheapest = min(buyable, key=lambda r: (r["amount"], r["age_days"] if r["age_days"] is not None else 999))
    stale = cheapest["age_days"] is not None and cheapest["age_days"] > stale_after_days

    bits = [f"{cheapest['supplier']}, {describe_age(cheapest['age_days'])}"]
    if len(buyable) > 1:
        dearest = max(buyable, key=lambda r: r["amount"])
        if dearest["amount"] > cheapest["amount"]:
            bits.append(f"cheapest of {len(buyable)} shops checked "
                        f"({cheapest['amount']:.2f}–{dearest['amount']:.2f} {currency})")
    if only_out_of_stock:
        bits.append("the only shop on file lists it out of stock")
    if stale:
        bits.append("worth checking again before you quote from it")
    if others:
        bits.append(f"{len(others)} price{'' if len(others) == 1 else 's'} in another currency "
                    f"{'was' if len(others) == 1 else 'were'} left out rather than converted at "
                    f"a rate nobody stated")
    note = "Read from " + "; ".join(bits) + "."

    return {
        "amount": cheapest["amount"], "currency": currency, "from": "checked",
        "supplier": cheapest["supplier"], "supplier_id": cheapest.get("supplier_id"),
        "url": cheapest.get("url"),
        "checked_at": cheapest["checked_at"], "age_days": cheapest["age_days"],
        "age": describe_age(cheapest["age_days"]), "stale": stale,
        "alternatives": sorted(same, key=lambda r: r["amount"]),
        "other_currencies": others,
        "typed_amount": None if typed_amount in (None, "") else round(float(typed_amount), 2),
        "note": note,
    }
