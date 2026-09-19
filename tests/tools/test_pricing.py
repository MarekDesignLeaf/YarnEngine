"""Pricing: the numbers people leave out, and the one they get backwards."""
from src.tools.pricing import price_piece


def base(**kw):
    args = dict(length_m=120, package_length_m=80, price_per_package=3.5,
                hours=4, hourly_rate=12, overhead_percent=10, margin_percent=50)
    args.update(kw)
    return price_piece(**args)


def test_every_line_of_the_cost_is_shown():
    out = base(extras=[{"name": "Safety eyes", "amount": 0.4},
                       {"name": "Stuffing", "amount": 0.8}])
    assert out["yarn_cost"] == 5.25                 # 1.5 balls at 3.50
    assert out["extras_total"] == 1.2
    assert out["labour"] == 48.0
    assert out["overhead"] == 5.45                  # 10% of 54.45
    assert out["cost"] == 59.9
    assert out["price"] == 119.8                    # cost / (1 - 0.5)
    assert out["profit"] == out["price"] - out["cost"]


def test_the_column_adds_up_when_someone_checks_it():
    """A money table that is a penny out is a table people stop trusting."""
    out = base(extras=[{"name": "Eyes", "amount": 0.4}, {"name": "Stuffing", "amount": 0.8}],
               overhead_percent=13, margin_percent=37, vat_percent=20)
    assert round(out["yarn_cost"] + out["extras_total"] + out["labour"]
                 + out["overhead"], 2) == out["cost"]
    assert round(out["yarn_cost"] + out["extras_total"], 2) == out["materials"]
    assert round(out["cost"] + out["profit"], 2) == out["price"]
    assert round(out["price"] + out["vat"], 2) == out["price_with_vat"]


def test_a_margin_is_not_a_markup_and_the_difference_is_spelled_out():
    out = base()
    assert out["price"] > out["price_if_markup"]
    assert out["price"] == round(out["cost"] / 0.5, 2)
    assert out["price_if_markup"] == round(out["cost"] * 1.5, 2)
    assert out["price"] > out["cost"]
    assert any("markup would add" in note for note in out["notes"])


def test_free_labour_is_pointed_out_rather_than_hidden():
    out = base(hours=0, hourly_rate=0)
    assert out["labour"] == 0
    assert any("being given away" in note for note in out["notes"])


def test_a_yarn_with_no_price_says_so_instead_of_costing_nothing():
    out = base(price_per_package=None)
    assert out["yarn_cost"] is None
    assert any("No price is set" in note for note in out["notes"])
    assert out["cost"] > 0                           # the time still counts


def test_whole_balls_and_the_part_actually_used_are_different_questions():
    used = base(whole_packages=False)
    whole = base(whole_packages=True)
    assert used["yarn_cost"] == 5.25 and whole["yarn_cost"] == 7.0   # 2 balls
    small = price_piece(length_m=20, package_length_m=80, price_per_package=3.5,
                        whole_packages=True)
    assert any("only uses 25% of one" in note for note in small["notes"])


def test_a_batch_is_priced_per_piece():
    out = base(pieces=4)
    assert out["cost_each"] == round(out["cost"] / 4, 2)
    assert out["price_each"] == round(out["price"] / 4, 2)


def test_what_the_hours_actually_return():
    out = base()
    assert out["hourly_return"] == round((out["price"] - out["materials"]) / 4, 2)
    assert price_piece(length_m=10, hours=0)["hourly_return"] is None
