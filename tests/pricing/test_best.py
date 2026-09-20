"""Which price a costing uses, and whether it can be traced back."""
from datetime import datetime, timezone

from src.pricing.best import age_in_days, best_price, describe_age

NOW = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)


def shop(name, amount, when, currency="GBP", availability="in stock", sid=1):
    return {"id": sid, "name": name, "checked_price": amount, "checked_currency": currency,
            "checked_at": when, "availability": availability, "product_url": "https://x/p"}


def test_the_cheapest_shop_wins_and_is_named():
    out = best_price([shop("Wool Warehouse", 4.75, "2026-09-19T22:00:00Z", sid=1),
                      shop("LoveCrafts", 5.49, "2026-09-18T10:00:00Z", sid=2)],
                     typed_amount=6.00, typed_currency="GBP", now=NOW)
    assert out["amount"] == 4.75 and out["from"] == "checked"
    assert out["supplier"] == "Wool Warehouse"
    assert "Wool Warehouse" in out["note"] and "yesterday" in out["note"]
    assert out["typed_amount"] == 6.00          # the typed one is kept for comparison
    assert [a["supplier"] for a in out["alternatives"]] == ["Wool Warehouse", "LoveCrafts"]


def test_prices_in_another_currency_are_left_out_rather_than_converted():
    """Converting them would mean inventing a rate, which is the one thing
    this app does not do with a number."""
    out = best_price([shop("Wool Warehouse", 4.75, "2026-09-19T10:00:00Z", sid=1),
                      shop("Ein Laden", 4.20, "2026-09-19T10:00:00Z", currency="EUR", sid=2)],
                     typed_currency="GBP", now=NOW)
    assert out["amount"] == 4.75 and out["currency"] == "GBP"
    assert len(out["other_currencies"]) == 1
    assert "another currency" in out["note"] and "converted" in out["note"]


def test_a_shop_that_has_run_out_is_passed_over():
    out = best_price([shop("Cheap but gone", 3.00, "2026-09-19T10:00:00Z",
                           availability="out of stock", sid=1),
                      shop("In stock", 5.00, "2026-09-19T10:00:00Z", sid=2)],
                     typed_currency="GBP", now=NOW)
    assert out["amount"] == 5.00 and out["supplier"] == "In stock"


def test_but_an_out_of_stock_price_is_used_when_it_is_all_there_is_and_it_says_so():
    out = best_price([shop("Only shop", 3.00, "2026-09-19T10:00:00Z",
                           availability="out of stock")], typed_currency="GBP", now=NOW)
    assert out["amount"] == 3.00
    assert "out of stock" in out["note"]


def test_an_old_price_is_still_used_but_flagged():
    """It is the best thing available, and quietly using it is the failure this
    exists to stop."""
    out = best_price([shop("Wool Warehouse", 4.75, "2026-05-01T10:00:00Z")],
                     typed_currency="GBP", now=NOW)
    assert out["amount"] == 4.75 and out["stale"] is True
    assert "4 months ago" in out["note"] and "check it again" in out["note"].lower() or \
           "checking again" in out["note"]


def test_with_nothing_checked_the_typed_price_is_used_and_called_what_it_is():
    out = best_price([], typed_amount=6.00, typed_currency="GBP", now=NOW)
    assert out["amount"] == 6.00 and out["from"] == "typed"
    assert "typed in by hand" in out["note"]
    assert out["stale"] is False


def test_with_nothing_at_all_it_says_the_yarn_is_not_in_the_figures():
    out = best_price([], now=NOW)
    assert out["amount"] is None and out["from"] is None
    assert "not in these figures" in out["note"]


def test_a_supplier_with_no_checked_price_is_ignored_not_treated_as_free():
    out = best_price([{"id": 1, "name": "Never checked", "checked_price": None},
                      shop("Checked", 5.00, "2026-09-20T09:00:00Z", sid=2)],
                     typed_currency="GBP", now=NOW)
    assert out["amount"] == 5.00 and out["supplier"] == "Checked"


def test_age_is_counted_in_calendar_days_the_way_a_person_means_it():
    assert age_in_days("2026-09-20T01:00:00Z", NOW) == 0
    assert age_in_days("2026-09-19T23:00:00Z", NOW) == 1     # last night was yesterday
    assert age_in_days(None, NOW) is None
    assert age_in_days("not a date", NOW) is None
    assert describe_age(None) == "never checked"
    assert describe_age(0) == "checked today"
    assert describe_age(1) == "checked yesterday"
    assert "weeks" in describe_age(21) and "months" in describe_age(120)
