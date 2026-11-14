import json
from types import SimpleNamespace

import pytest
import requests

import country


@pytest.fixture(autouse=True)
def isolated_country_cache(monkeypatch):
    country._CACHE.clear()

    def unavailable(*args, **kwargs):
        raise requests.ConnectionError("No network in this test")

    monkeypatch.setattr(country.requests, "get", unavailable)


def markup(value):
    return '<script type="application/ld+json">' + json.dumps(value) + "</script>"


def test_merchant_jsonld_address_and_country_object():
    html = markup({"@graph": [{"@type": "Organization", "url": "https://store.example",
        "address": {"@type": "PostalAddress", "addressCountry": {"name": "United States"}}}]})
    assert country.merchant_country("https://store.example/product", html) == "US"


def test_manufacturer_and_other_organizations_are_not_the_merchant():
    html = markup({"@graph": [
        {"@type": "Product", "manufacturer": {"@type": "Organization", "address": {"addressCountry": "US"}}},
        {"@type": "Organization", "url": "https://manufacturer.example", "address": {"addressCountry": "US"}},
        {"@type": "Organization", "url": "https://store.example", "address": {"addressCountry": "CA"}},
    ]})
    assert country.merchant_country("https://store.example/product", html) == "CA"
    country._CACHE.clear()
    assert country.merchant_country("https://other.example", html) == ""


def test_country_domain_and_currency_are_different_evidence():
    assert country.merchant_country("https://retailer.ca/product") == "CA"
    assert country.merchant_country("https://retailer.co.uk/product") == "GB"
    assert country.merchant_country("https://retailer.com", "<select>United States (US$)</select><p>USD 20</p>") == ""
    assert country.merchant_country("https://retailer.co", "<address>Kirkland, WA 98033</address>") == "US"


@pytest.mark.parametrize("address", ["2334 Arthur Avenue Bronx, New York 10458 USA", "400 Urban Plaza, Kirkland, WA 98033"])
def test_us_footer_accepts_full_state_names_and_abbreviations(address):
    assert country.merchant_country("https://store.example", f"<footer>{address}</footer>") == "US"


def test_home_then_observed_same_origin_about_and_cache(monkeypatch):
    calls = []
    pages = {
        "https://store.example/": '<a href="https://external.example/contact">Contact</a><a href="http://store.example/contact">Contact</a><a href="/about-us">About us</a>',
        "https://store.example/about-us": "<main>Our retail business is located in Littleton, Colorado.</main>",
    }

    def fetch(url, **kwargs):
        calls.append(url)
        assert kwargs["timeout"] == 5
        assert kwargs["headers"] == country.HEADERS
        return SimpleNamespace(url=url, text=pages[url], raise_for_status=lambda: None)

    monkeypatch.setattr(country.requests, "get", fetch)
    assert country.merchant_country("https://store.example/product") == "US"
    assert country.merchant_country("https://store.example/another") == "US"
    assert calls == list(pages)


def test_lookup_is_bounded_and_does_not_invent_contact_urls(monkeypatch):
    calls = []

    def fetch(url, **kwargs):
        calls.append(url)
        html = '<a href="/contact">Contact</a><a href="/about">About</a><a href="/locations">Locations</a>' if url.endswith("/") else "<p>Contact our team</p>"
        return SimpleNamespace(url=url, text=html, raise_for_status=lambda: None)

    monkeypatch.setattr(country.requests, "get", fetch)
    assert country.merchant_country("https://store.example/product") == ""
    assert country.merchant_country("https://store.example/another") == ""
    assert calls == ["https://store.example/", "https://store.example/contact", "https://store.example/about"]


def test_new_address_overrides_cached_unknown_and_us_branch_qualifies():
    assert country.merchant_country("https://store.example/product") == ""
    html = markup({"@type": "Organization", "address": [{"addressCountry": "CA"}, {"addressCountry": "US"}]})
    assert country.merchant_country("https://store.example/another", html) == "US"


def test_malformed_graph_and_type_leave_visible_addresses_usable():
    html = markup({"@graph": {"@type": None}}) + "<footer>Kirkland, WA 98033</footer>"
    assert country.merchant_country("https://store.example", html) == "US"
