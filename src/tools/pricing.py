"""What a finished piece costs to make, and what it might sell for.

The numbers that matter here are the ones people leave out: their own hours,
the yarn left on the ball, and the difference between a margin and a markup.
A 50% markup is a third of the price; a 50% margin is half of it. Getting that
backwards is the difference between a business and a hobby that loses money, so
both are worked out and named rather than one being quietly chosen.
"""
from __future__ import annotations

import math


def price_piece(*, length_m: float, package_length_m: float | None = None,
                price_per_package: float | None = None, currency: str = "GBP",
                hours: float = 0.0, hourly_rate: float = 0.0,
                extras: list | None = None, overhead_percent: float = 0.0,
                margin_percent: float = 0.0, vat_percent: float = 0.0,
                whole_packages: bool = False, pieces: int = 1) -> dict:
    """Costs first, then a price. Every line is shown so it can be argued with."""
    pieces = max(1, int(pieces))
    extras = [{"name": str(e.get("name") or "extra"), "amount": float(e.get("amount") or 0)}
              for e in (extras or []) if float(e.get("amount") or 0) != 0]

    yarn_cost = None
    packages_used = None
    if price_per_package is not None and package_length_m:
        if package_length_m <= 0:
            raise ValueError("the ball's length must be more than zero")
        packages_used = float(length_m) / float(package_length_m)
        billed = math.ceil(packages_used) if whole_packages else packages_used
        yarn_cost = billed * float(price_per_package)

    # Every line is rounded to the penny and the total is the sum of those
    # lines, the way an invoice works: a column that does not add up when
    # someone checks it with a calculator is a column they stop trusting.
    yarn_cost = round(yarn_cost, 2) if yarn_cost is not None else None
    extras_total = round(sum(e["amount"] for e in extras), 2)
    materials = round((yarn_cost or 0.0) + extras_total, 2)
    labour = round(max(0.0, float(hours)) * max(0.0, float(hourly_rate)), 2)
    direct = round(materials + labour, 2)
    overhead = round(direct * max(0.0, float(overhead_percent)) / 100, 2)
    cost = round(direct + overhead, 2)

    margin = max(0.0, min(95.0, float(margin_percent)))
    # Rounded to the penny before anything is derived from it, so that the
    # figures in the table add up when someone checks them with a calculator.
    price_at_margin = round(cost / (1 - margin / 100) if margin else cost, 2)
    price_at_markup = round(cost * (1 + margin / 100), 2)
    vat = round(price_at_margin * max(0.0, float(vat_percent)) / 100, 2)

    notes = []
    if yarn_cost is None:
        notes.append("No price is set for this yarn, so the yarn is not in these figures — "
                     "add what a ball costs you on the Yarns page, or type it in here.")
    if labour == 0:
        notes.append("No time is costed here. A piece that takes four hours and sells for the "
                     "price of the yarn is being given away.")
    if margin:
        notes.append(
            f"A {margin:g}% margin means {margin:g}% of the selling price is profit "
            f"({currency} {price_at_margin - cost:.2f} on this piece). A {margin:g}% markup "
            f"would add {margin:g}% to the cost instead, giving {currency} {price_at_markup:.2f} "
            "— a smaller number, and the one people usually set by mistake.")
    if whole_packages and packages_used is not None and packages_used < 1:
        notes.append(f"Costed as a whole ball, though the piece only uses "
                     f"{packages_used * 100:.0f}% of one — right for a one-off, wrong per item "
                     "if the rest of the ball gets used.")

    return {
        "currency": currency, "pieces": pieces,
        "length_m": round(float(length_m), 2),
        "packages_used": round(packages_used, 3) if packages_used is not None else None,
        "yarn_cost": yarn_cost,
        "extras": extras, "extras_total": extras_total,
        "materials": materials,
        "hours": round(float(hours), 2), "labour": labour,
        "overhead": overhead, "cost": cost,
        "cost_each": round(cost / pieces, 2),
        "price": price_at_margin,
        "price_each": round(price_at_margin / pieces, 2),
        "price_if_markup": price_at_markup,
        "profit": round(price_at_margin - cost, 2),
        "vat": vat,
        "price_with_vat": round(price_at_margin + vat, 2),
        "hourly_return": (round((price_at_margin - materials) / float(hours), 2)
                          if hours and float(hours) > 0 else None),
        "notes": notes,
    }
