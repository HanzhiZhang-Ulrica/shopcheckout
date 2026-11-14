from decimal import Decimal
import json

import pytest
import requests

from shopping import Offer, SearchResult, parse_page, read_product, relevance, search_prices, search_web


def web_response(html, status=200):
    response = requests.Response()
    response.status_code = status
    response.url = "https://lite.duckduckgo.com/lite/"
    response._content = html.encode("utf-8")
    return response


@pytest.fixture(autouse=True)
def isolated_search_cache(monkeypatch):
    monkeypatch.setattr("shopping._SEARCH_CACHE", {})
    monkeypatch.setattr("shopping.merchant_country", lambda url, html="": "US")


def test_product_jsonld_uses_the_actual_offer_and_stock():
    html = '''<script type="application/ld+json">{"@type":"Product","name":"Camera X5",
    "offers":{"@type":"Offer","price":"249.99","priceCurrency":"USD",
    "availability":"https://schema.org/InStock"}}</script>'''
    _, rows = parse_page(html, "https://shop.example/camera")
    assert rows[0].price == Decimal("249.99")
    assert rows[0].available is True
    assert rows[0].url == "https://shop.example/camera"


def test_meta_price_and_missing_price():
    html = '''<title>Camera X5</title><meta property="product:price:amount" content="249.00">
    <meta property="product:price:currency" content="USD">'''
    assert parse_page(html, "https://shop.example/camera")[1][0].price == Decimal("249")
    assert parse_page("<title>Camera X5</title>", "https://shop.example/camera")[1] == []


def test_amazon_uses_one_time_purchase_not_the_subscription_price():
    html = '''<span id="productTitle">Coffee 1 lb</span>
    <div id="subscription"><span class="a-price"><span class="a-offscreen">$12.00</span></span></div>
    <div id="apex_desktop_newAccordionRow"><span class="a-price"><span class="a-offscreen"></span>
    <span class="a-offscreen">$15.00</span></span></div>
    <div id="availability">In Stock</div>'''
    assert parse_page(html, "https://www.amazon.com/dp/EXAMPLE")[1][0].price == Decimal("15")


def test_amazon_uses_the_full_purchase_price_not_unit_or_list_prices():
    html = '''<span id="productTitle">Coffee 2.2 lb</span>
    <div id="corePriceDisplay_desktop_feature_div">
      <span class="a-price a-text-price"><span class="a-offscreen">$30.99</span></span>
      <span class="pricePerUnit"><span class="a-price"><span class="a-offscreen">$0.71</span></span></span>
      <span class="a-price priceToPay"><span class="a-offscreen"></span>
        <span class="a-price-symbol">$</span><span class="a-price-whole">26.</span>
        <span class="a-price-fraction">99</span></span>
    </div>'''
    assert parse_page(html, "https://www.amazon.com/dp/EXAMPLE")[1][0].price == Decimal("26.99")


@pytest.mark.parametrize("marker", ["pricePerUnit", "unitPrice", "basisPrice", "a-text-price"])
def test_amazon_does_not_use_unit_or_list_price_when_purchase_price_is_missing(marker):
    html = f'''<span id="productTitle">Coffee 2.2 lb</span>
    <div id="corePrice_feature_div"><div class="{marker}">
    <span class="a-price"><span class="a-offscreen">$0.71</span></span></div></div>'''
    assert parse_page(html, "https://www.amazon.com/dp/EXAMPLE")[1] == []


def test_zero_placeholder_does_not_become_the_lowest_offer():
    html = '''<script type="application/ld+json">{"@type":"Product","name":"Camera X5",
    "offers":{"price":"0","priceCurrency":"USD","availability":"https://schema.org/InStock"}}</script>'''
    assert parse_page(html, "https://shop.example/camera")[1] == []


def test_fuzzy_matching_tolerates_typo_and_incomplete_name():
    assert relevance("lavaza supar crema", "Lavazza Super Crema Coffee") > 0.8
    assert relevance("headphone sony", "Sony Wireless Headphones") > 0.8
    assert relevance("red running shoe", "Coffee beans") < 0.6


def test_measurements_do_not_outweigh_the_requested_product_series():
    query = "lavaza supar crema 2.2 lb"
    assert relevance(query, "Lavazza Super Crema Whole Bean Coffee 2.2 lb") > 0.8
    assert relevance("lavaza supar crema2.2lb", "Lavazza Super Crema Whole Bean Coffee 2.2 lb") > 0.8
    assert relevance(query, "Lavazza Gran Crema Whole Bean Coffee 2.2 lb") == 0
    assert relevance(query, "Lavazza Gran Riserva Coffee 2.2 lb") == 0


def test_model_codes_and_product_extras_do_not_match_the_main_product():
    assert relevance("Sony WH-1000XM5", "Sony WH-1000XM4 Wireless Headphones") == 0
    assert relevance("Sony WH-1000XM5", "Sony WH-1000XM5 Replacement Ear Pads") == 0
    assert relevance("MX Mechanical", "MX Mechanical Keyboard and Mouse Bundle") == 0
    assert relevance("Sony WH-1000XM5 replacement pads", "Replacement Pads for Sony WH-1000XM5") > 0.8
    assert relevance("Lavazza Super Crema 2.2 lb", "Lavazza Super Crema Coffee 2.2 lb") > 0.8
    assert relevance("Lavazza Super Crema 2.2lb", "Lavazza Super Crema Coffee 2.2 lb") > 0.6


@pytest.mark.parametrize("include_urls", [False, True])
def test_only_the_primary_product_is_read_not_recommended_accessories(include_urls):
    products = [
        {"@type": "Product", "name": "Sony WH-1000XM5 Replacement Ear Pads",
         "offers": {"price": "12.00", "priceCurrency": "USD"}},
        {"@type": "Product", "name": "Sony WH-1000XM5",
         "offers": {"price": "299.00", "priceCurrency": "USD"}},
    ]
    if include_urls:
        products[0]["url"] = "https://shop.example/pads"
        products[1]["url"] = "https://shop.example/headphones"
    html = '<title>Sony WH-1000XM5</title><script type="application/ld+json">' + json.dumps(products) + '</script>'
    _, rows = parse_page(html, "https://shop.example/headphones")
    assert [(row.title, row.price) for row in rows] == [("Sony WH-1000XM5", Decimal("299"))]


def test_product_links_use_the_product_name_without_the_store_page_title():
    html = '''<title>Buy Camera X5 at Example Retailer</title>
    <script type="application/ld+json">{"@type":"Product","name":"Camera X5",
    "offers":{"price":"249.99","priceCurrency":"USD"}}</script>'''
    assert parse_page(html, "https://shop.example/camera")[0] == "Camera X5"


def test_page_title_drops_only_the_exact_trailing_store_name():
    html = '<title>Azul Mini - Dryad Games</title><meta property="og:site_name" content="Dryad Games">'
    assert parse_page(html, "https://dryad.example/azul-mini")[0] == "Azul Mini"
    other = '<title>Azul Mini - Travel Edition</title><meta property="og:site_name" content="Dryad Games">'
    assert parse_page(other, "https://dryad.example/azul-mini")[0] == "Azul Mini - Travel Edition"


def test_malformed_jsonld_records_do_not_hide_a_valid_offer():
    products = [
        {"@type": None},
        {"@type": 7},
        {"@type": "Product", "name": "Camera X5", "offers": [
            None, "invalid", {"priceSpecification": True},
            {"priceSpecification": [None, {"price": "249.99", "priceCurrency": "USD"}]},
        ]},
    ]
    html = '<title>Camera X5</title><script type="application/ld+json">' + json.dumps(products) + '</script>'
    _, rows = parse_page(html, "https://shop.example/camera")
    assert [row.price for row in rows] == [Decimal("249.99")]


def test_product_models_use_concrete_prices_not_aggregate_or_list_prices():
    product = {"@type": "Product", "name": "MX Master 3S", "url": "https://shop.example/mouse",
               "offers": {"@type": "AggregateOffer", "lowPrice": "70", "highPrice": "100", "priceCurrency": "USD"},
               "model": [
                   {"@type": "ProductModel", "name": "MX Master 3S Black", "offers": {
                       "price": "89.99", "priceCurrency": "USD", "availability": "https://schema.org/InStock",
                       "priceSpecification": {"price": "99.99", "priceCurrency": "USD"}}},
                   {"@type": "ProductModel", "name": "MX Master 3S Graphite", "offers": {
                       "price": "94.99", "priceCurrency": "USD", "availability": "https://schema.org/InStock"}},
               ]}
    html = '<title>MX Master 3S</title><script type="application/ld+json">' + json.dumps(product) + '</script>'
    _, rows = parse_page(html, "https://shop.example/mouse")
    assert [row.price for row in rows] == [Decimal("89.99"), Decimal("94.99")]
    assert all(row.url == "https://shop.example/mouse" for row in rows)


@pytest.mark.parametrize("markup", [
    '<div itemscope itemtype="https://schema.org/Product"><span itemprop="name">Camera X5</span>'
    '<div itemscope itemtype="https://schema.org/Offer"><meta itemprop="price" content="249.00">'
    '<meta itemprop="priceCurrency" content="USD"></div></div>',
    '<meta itemprop="price" content="249.00"><meta itemprop="priceCurrency" content="USD">',
])
def test_microdata_price_requires_its_currency(markup):
    _, rows = parse_page("<title>Camera X5</title>" + markup, "https://shop.example/camera")
    assert rows[0].price == Decimal("249")
    assert rows[0].currency == "USD"
    assert parse_page(markup.replace('content="USD"', 'content=""'), "https://shop.example/camera")[1] == []


def test_product_link_resolves_name_then_searches_the_web(monkeypatch):
    seen = []
    monkeypatch.setattr("shopping.read_product", lambda url, fallback_title="": (
        "Camera X5", [Offer("Camera X5", "Store", url, Decimal("20"), "USD", True)]))
    monkeypatch.setattr("shopping.search_web", lambda query: seen.append(query) or [("Camera X5", "https://second.example/x5")])
    result = search_prices("https://first.example/x5")
    assert seen == ["Camera X5"]
    assert len(result.offers) == 2


def test_unpriced_results_stay_visible_and_are_not_invented(monkeypatch):
    monkeypatch.setattr("shopping.search_web", lambda query: [("Camera X5", "https://store.example/x5")])
    monkeypatch.setattr("shopping.read_product", lambda url, fallback_title="": (fallback_title, []))
    assert search_prices("camera x5").offers[0].price is None


@pytest.mark.parametrize("failure", [RuntimeError("Search challenge"), requests.Timeout()])
def test_a_direct_offer_survives_web_search_failure(monkeypatch, failure):
    offer = Offer("Camera X5", "Store", "https://shop.example/x5", Decimal("20"), "USD", True)
    monkeypatch.setattr("shopping.read_product", lambda url, fallback_title="": (offer.title, [offer]))

    def fail(query):
        raise failure

    monkeypatch.setattr("shopping.search_web", fail)
    assert search_prices(offer.url).offers == [offer]


@pytest.mark.parametrize("title", ["Just a moment...", "Attention Required! | Cloudflare", "Verify you are human"])
def test_challenge_pages_search_using_the_product_url_instead(monkeypatch, title):
    class Response:
        text = f"<title>{title}</title>"
        url = "https://shop.example/products/azul-mini"
        headers = {"Content-Type": "text/html"}

    monkeypatch.setattr("shopping._get", lambda url: Response())
    monkeypatch.setattr("shopping.catalog_offers", lambda url: [])
    queries = []
    monkeypatch.setattr("shopping.search_web", lambda query: queries.append(query) or [])
    assert search_prices(Response.url).query == "azul mini"
    assert queries == ["azul mini"]


@pytest.mark.parametrize("payload", [
    {"result": None},
    {"result": {"structuredContent": []}},
    {"result": {"structuredContent": {"products": ["invalid"]}}},
    {"result": {"content": [{"type": "text", "text": "not JSON"}]}},
])
def test_malformed_public_catalog_does_not_crash_product_reading(monkeypatch, payload):
    class Page:
        text = "<title>Camera X5</title>"
        url = "https://shop.example/products/camera-x5"
        headers = {"Content-Type": "text/html"}

    class CatalogResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    monkeypatch.setattr("shopping._get", lambda url: Page())
    monkeypatch.setattr("shopping.discover_catalog", lambda origin: "https://shop.example/catalog")
    monkeypatch.setattr("shopping.requests.post", lambda *args, **kwargs: CatalogResponse())
    assert read_product(Page.url) == ("Camera X5", [])


def test_non_ascii_query_still_filters_unrelated_results(monkeypatch):
    monkeypatch.setattr("shopping.search_web", lambda query: [("Winter Coat", "https://shop.example/coat")])
    monkeypatch.setattr("shopping.read_product", lambda url, fallback_title="": (
        "Winter Coat", [Offer("Winter Coat", "Store", url, Decimal("30"), "USD", True)]))
    assert search_prices("Pokémon cards").offers == []


def test_non_ascii_search_title_can_match_an_english_product_record(monkeypatch):
    query = "\u5b9d\u53ef\u68a6\u5361\u724c"
    offer = Offer("Pokemon Cards", "Store", "https://shop.example/cards", Decimal("30"), "USD", True)
    monkeypatch.setattr("shopping.search_web", lambda text: [(query, offer.url)])
    monkeypatch.setattr("shopping.read_product", lambda url, fallback_title="": (offer.title, [offer]))
    assert search_prices(query).offers == [offer]


def test_distinct_concrete_models_with_the_same_page_link_are_retained(monkeypatch):
    offers = [
        Offer("MX Master 3S Black", "Store", "https://shop.example/mouse", Decimal("89.99"), "USD", True),
        Offer("MX Master 3S Graphite", "Store", "https://shop.example/mouse", Decimal("94.99"), "USD", True),
    ]
    monkeypatch.setattr("shopping.search_web", lambda query: [("MX Master 3S", "https://shop.example/mouse")])
    monkeypatch.setattr("shopping.read_product", lambda url, fallback_title="": ("MX Master 3S", offers))
    assert search_prices("MX Master 3S").offers == offers


def test_web_search_follows_next_forms_and_preserves_all_unique_results(monkeypatch):
    anchors = ''.join(f'<a class="result-link" href="https://shop{i}.example/item">Camera X5</a>' for i in range(13))

    def next_form(offset):
        return f'''<form action="/lite/" method="post"><input name="q" value="camera buy">
        <input name="s" value="{offset}"><input name="vqd" value="dynamic-token-{offset}">
        <input name="nextParams" value=""><input type="submit" value="Next Page &gt;"></form>'''

    first = web_response(anchors + '<form><input type="submit" value="Previous Page"></form>' + next_form(10))
    new_anchor = '<a class="result-link" href="https://new.example/item">Camera X5</a>'
    pages = iter([web_response(anchors + new_anchor + next_form(20)), web_response(new_anchor + next_form(30))])
    calls = []
    monkeypatch.setattr("shopping._get", lambda *args, **kwargs: first)

    def post(url, **kwargs):
        calls.append((url, kwargs["data"]))
        return next(pages)

    monkeypatch.setattr("shopping.requests.post", post)
    rows = search_web("camera")
    assert len(rows) == 14
    assert len(calls) == 2
    assert calls[0] == ("https://lite.duckduckgo.com/lite/", {
        "q": "camera buy", "s": "10", "vqd": "dynamic-token-10", "nextParams": ""})
    assert calls[1][1]["vqd"] == "dynamic-token-20"


def test_later_search_challenge_preserves_results_already_found(monkeypatch):
    first = web_response('<a class="result-link" href="https://shop.example/item">Camera X5</a>'
                         '<form action="/lite/" method="post"><input name="s" value="10">'
                         '<input type="submit" value="Next Page &gt;"></form>')
    monkeypatch.setattr("shopping._get", lambda *args, **kwargs: first)
    monkeypatch.setattr("shopping.requests.post", lambda *args, **kwargs: web_response("anomaly", 202))
    assert search_web("camera") == [("Camera X5", "https://shop.example/item")]


def test_transient_server_error_is_retried_once(monkeypatch):
    from shopping import _get

    responses = iter([web_response("Unavailable", 503), web_response("Product page")])
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return next(responses)

    monkeypatch.setattr("shopping.requests.get", get)
    assert _get("https://shop.example/item").text == "Product page"
    assert len(calls) == 2


def test_discovery_cache_expires_and_product_prices_are_read_fresh(monkeypatch):
    clock = [1000]
    discovery_calls = []
    prices = iter(["20", "18", "17"])
    page = web_response('<a class="result-link" href="https://shop.example/x5">Camera X5</a>')
    monkeypatch.setattr("shopping.monotonic", lambda: clock[0])

    def discover(*args, **kwargs):
        discovery_calls.append(args[0])
        return page

    def read(url, fallback_title=""):
        return "Camera X5", [Offer("Camera X5", "Store", url, Decimal(next(prices)), "USD", True)]

    monkeypatch.setattr("shopping._get", discover)
    monkeypatch.setattr("shopping.read_product", read)
    assert search_prices("camera x5").offers[0].price == Decimal("20")
    assert search_prices("camera x5").offers[0].price == Decimal("18")
    assert len(discovery_calls) == 1
    clock[0] += 301
    assert search_prices("camera x5").offers[0].price == Decimal("17")
    assert len(discovery_calls) == 2


def test_simple_ui_highlights_lowest_price_and_keeps_links(monkeypatch):
    from streamlit.testing.v1 import AppTest

    result = SearchResult("Camera X5", [
        Offer("Camera X5", "First", "https://first.example/x5", Decimal("25"), "USD", True),
        Offer("Camera X5 <script>alert(1)</script>", "Second", "https://second.example/x5", Decimal("20"), "USD", None),
        Offer("Camera X5", "Sold out", "https://third.example/x5", Decimal("10"), "USD", False),
    ])
    calls = []
    def find_prices(query, **filters):
        calls.append(filters)
        return result
    monkeypatch.setattr("shopping.search_prices", find_prices)
    app = AppTest.from_file("app.py").run()
    app.text_input[0].set_value("camra x5")
    app.button[0].click().run()
    assert not app.exception
    assert calls[-1] == {"hide_sold_out": True, "us_only": True}
    assert app.metric[0].value == "USD 20.00"
    assert "Second" in app.metric[0].label
    html = "\n".join(item.value for item in app.markdown)
    assert 'class="lowest"' in html
    assert "Second" in html and "View offer" in html
    assert 'href="https://second.example/x5"' in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    app.checkbox[0].uncheck()
    app.checkbox[1].uncheck()
    app.button[0].click().run()
    assert calls[-1] == {"hide_sold_out": False, "us_only": False}


@pytest.mark.parametrize("hide_sold_out,us_only,expected", [
    (True, True, {"us"}),
    (False, True, {"us", "sold"}),
    (True, False, {"us", "ca"}),
    (False, False, {"us", "sold", "ca"}),
])
def test_stock_and_country_filters_are_independent(monkeypatch, hide_sold_out, us_only, expected):
    urls = {name: f"https://{name}.example/x5" for name in ("us", "sold", "ca")}
    monkeypatch.setattr("shopping.search_web", lambda query: [("Camera X5", u) for u in urls.values()])
    monkeypatch.setattr("shopping.merchant_country", lambda url: "CA" if url == urls["ca"] else "US")
    monkeypatch.setattr("shopping.read_product", lambda url, fallback_title="": (
        "Camera X5", [Offer("Camera X5", url.split("//")[1].split(".")[0], url,
                            Decimal("20"), "USD", url != urls["sold"])]))
    result = search_prices("camera x5", hide_sold_out=hide_sold_out, us_only=us_only)
    assert {offer.store for offer in result.offers} == expected


def test_jsonld_product_name_does_not_add_store_to_cross_store_query():
    html = '''<meta property="og:site_name" content="Dryad Games">
    <script type="application/ld+json">{"@type":"Product","name":"Azul Mini - Dryad Games",
    "offers":{"price":"19.99","priceCurrency":"USD"}}</script>'''
    title, offers = parse_page(html, "https://dryad-games.com/shop/azul-mini/")
    assert title == "Azul Mini"
    assert offers[0].title == "Azul Mini"
