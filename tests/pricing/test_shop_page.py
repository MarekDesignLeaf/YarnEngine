"""Reading a price off a shop's page — only where the shop published one.

A wrong price in a costing sheet is worse than no price, because a maker
prices a piece from it. So the rule these tests hold is narrow: take the
price the shop states in machine-readable form, and otherwise say there is
none. Never lift a number out of the visible page because it sits next to a
pound sign.
"""
from pathlib import Path

import pytest

from src.pricing.shop_page import parse_amount, parse_currency, read_price

SHOPIFY = """<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org/","@type":"Product","name":"Cotton Aran 100g",
 "offers":[{"@type":"Offer","price":"4.75","priceCurrency":"GBP","availability":"https://schema.org/InStock"},
           {"@type":"Offer","price":"5.95","priceCurrency":"GBP","availability":"https://schema.org/InStock"}]}
</script></head><body>Buy now</body></html>"""

WOOCOMMERCE_DE = """<html><head>
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[
 {"@type":"WebSite","name":"Wollladen"},
 {"@type":"Product","name":"Merino DK",
  "offers":{"@type":"AggregateOffer","lowPrice":"3,95","highPrice":"6,50","priceCurrency":"EUR"}}]}
</script></head><body></body></html>"""

MICRODATA = """<html><body><div itemscope itemtype="http://schema.org/Product">
 <span itemprop="name">Baby Alpaca</span>
 <div itemprop="offers" itemscope itemtype="http://schema.org/Offer">
   <meta itemprop="priceCurrency" content="GBP">
   <span itemprop="price" content="7.20">£7.20</span></div></div></body></html>"""

OPEN_GRAPH = """<html><head><meta property="product:price:amount" content="12.99">
<meta property="product:price:currency" content="USD"></head><body></body></html>"""

SOLD_OUT = """<html><head><script type="application/ld+json">
{"@type":"Product","name":"Sold out yarn","offers":{"@type":"Offer","price":"8.00",
"priceCurrency":"GBP","availability":"http://schema.org/OutOfStock"}}</script></head><body></body></html>"""


@pytest.mark.parametrize("text,expected", [
    ("4.75", 4.75), ("£4.75", 4.75), ("4,75", 4.75),            # both halves of the world
    ("1,234.56", 1234.56), ("1.234,56", 1234.56),
    ("1,234", 1234.0), ("1.234", 1234.0),                        # a lone group of three is thousands
    ("  € 3,99 ", 3.99), ("GBP 4.75", 4.75), (3.5, 3.5),
    ("4.75-6.00", 4.75), ("£4.75 – £6.00", 4.75),                # a range starts at the low end
    ("0", None), ("-2", None), ("−2", None),                     # not prices
    ("abc", None), ("", None), (None, None),
    ("99999", None),                                             # a ball of yarn is not £99,999
])
def test_a_number_out_of_whatever_the_page_wrote(text, expected):
    assert parse_amount(text) == expected


def test_a_currency_symbol_is_read_but_an_ambiguous_one_is_flagged():
    assert parse_currency("GBP") == ("GBP", False)
    assert parse_currency(None, "£4.75") == ("GBP", False)
    assert parse_currency(None, "$9.99") == ("USD", True)        # could be six countries
    assert parse_currency(None, "nothing here") == (None, False)


def test_the_common_shop_platforms_are_read():
    shopify = read_price(SHOPIFY)
    assert shopify["found"] and shopify["amount"] == 4.75        # the cheapest variant
    assert shopify["currency"] == "GBP" and shopify["availability"] == "in stock"
    assert any("2 prices" in n for n in shopify["notes"])

    german = read_price(WOOCOMMERCE_DE)
    assert german["amount"] == 3.95 and german["currency"] == "EUR"

    micro = read_price(MICRODATA)
    assert micro["amount"] == 7.20 and micro["currency"] == "GBP"

    og = read_price(OPEN_GRAPH)
    assert og["amount"] == 12.99 and og["currency"] == "USD"


def test_a_price_you_cannot_buy_at_is_marked_as_such():
    sold_out = read_price(SOLD_OUT)
    assert sold_out["amount"] == 8.00
    assert sold_out["availability"] == "out of stock"
    assert any("out of stock" in n for n in sold_out["notes"])


def test_a_price_only_in_the_visible_text_is_not_a_price():
    """This is the whole discipline. The page plainly says £4.75; guessing it
    from the prose is how a costing sheet ends up quoting a postage charge."""
    page = read_price("<html><body><p>Yarn, £4.75 a ball, lovely stuff</p></body></html>")
    assert page["found"] is False
    assert "does not publish a price" in page["reason"]
    assert "£" not in page["reason"] and "4.75" not in page["reason"]


def test_one_broken_block_does_not_lose_the_whole_page():
    page = read_price("""<html><head><script type="application/ld+json">{oops,</script>
      <meta property="og:price:amount" content="6.40">
      <meta property="og:price:currency" content="GBP"></head><body></body></html>""")
    assert page["amount"] == 6.40 and page["currency"] == "GBP"


def test_an_empty_page_says_so_rather_than_failing():
    assert read_price("")["found"] is False
    assert read_price("<html></html>")["found"] is False


# ---------------------------------------------------------- real shop pages --
# Trimmed from pages actually fetched from the shops, so a redesign that breaks
# the reader shows up here rather than in somebody's costing sheet.
PAGES = Path(__file__).parent / "pages"


def page(name: str) -> str:
    return (PAGES / f"{name}.html").read_text(encoding="utf-8")


def test_a_real_shopify_style_variant_page_reads():
    """LoveCrafts publishes a ProductGroup whose prices sit two levels down,
    under hasVariant → offers — which is why the reader walks the whole
    document instead of looking at the top level."""
    found = read_price(page("lovecrafts"), "https://www.lovecrafts.com/en-gb/p/x")
    assert found["amount"] == 8.13 and found["currency"] == "GBP"
    assert found["availability"] == "in stock"
    assert "JSON-LD" in found["source"]


def test_a_real_shop_that_publishes_nothing_is_read_by_a_rule_written_for_it():
    """Wool Warehouse — the biggest yarn shop in the UK — publishes no JSON-LD,
    no microdata and no product tags. The first pound sign on its page belongs
    to a navigation filter reading "Up to £2.50", which is exactly what a
    generic scraper would grab.
    """
    html = page("woolwarehouse")
    assert "Up to &pound;2.50" in html                 # the trap is in the fixture
    found = read_price(html, "https://www.woolwarehouse.co.uk/yarn/stylecraft-special-dk-black")
    assert found["amount"] == 2.35                     # the product, not the filter
    assert found["currency"] == "GBP" and found["availability"] == "in stock"
    assert "rule written for this shop" in found["source"]


def test_a_named_shops_rule_only_applies_to_that_shop():
    """Otherwise a selector written for one shop starts reading another's page."""
    found = read_price(page("woolwarehouse"), "https://some-other-shop.example/p")
    assert found["found"] is False


def test_when_a_named_shops_page_changes_it_says_so_rather_than_guessing():
    broken = page("woolwarehouse").replace("gbp-price-value", "whatever-they-renamed-it-to")
    found = read_price(broken, "https://www.woolwarehouse.co.uk/yarn/x")
    assert found["found"] is False
    assert "no longer looks the way this app expects" in found["reason"]
    assert "2.50" not in found["reason"]               # and never quotes the filter at you


def test_a_named_rule_finding_several_different_prices_is_treated_as_broken():
    """One price is what the rule promises. Two means the page moved on, and
    picking one of them is how a wrong price gets into a costing sheet."""
    doubled = page("woolwarehouse").replace(
        "</div>\n<div class=\"instockmessage\">",
        "<span class='gbp-price-value'>£9.99</span></div>\n<div class=\"instockmessage\">")
    found = read_price(doubled, "https://www.woolwarehouse.co.uk/yarn/x")
    assert found["found"] is False


def test_published_data_is_preferred_over_a_rule_written_by_hand():
    """A rule is a weaker thing than the shop stating its own price."""
    with_both = page("woolwarehouse").replace("<body>", """<body>
      <script type="application/ld+json">{"@type":"Product","offers":
      {"@type":"Offer","price":"3.10","priceCurrency":"GBP"}}</script>""")
    found = read_price(with_both, "https://www.woolwarehouse.co.uk/yarn/x")
    assert found["amount"] == 3.10 and "JSON-LD" in found["source"]
