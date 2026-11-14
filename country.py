"""Identify a retailer's country from its own published location."""

from collections import OrderedDict
from functools import lru_cache
import json
import re
from threading import Lock
from time import monotonic
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


HEADERS = {"User-Agent": "ShopCheckoutLite/2.0", "Accept": "text/html,application/json"}
_CACHE = OrderedDict()
_STATES = (
    "Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|"
    "Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|"
    "Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|"
    "Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|"
    "North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|"
    "South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|"
    "Wisconsin|Wyoming|District of Columbia"
)
_ABBREVIATIONS = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
_US_ADDRESS = re.compile(r"\b(?:" + _STATES + "|" + "|".join(_ABBREVIATIONS) + r")\s*,?\s+\d{5}(?:-\d{4})?\b", re.I)
_LOCATION = re.compile(r"\b(?:located|based)\s+in\s+[A-Za-z .'-]{2,45},\s*(?:" + _STATES + r")\b", re.I)
_ORGANIZATIONS = {"Organization", "Corporation", "LocalBusiness", "Store", "OnlineStore", "ProfessionalService"}
_COUNTRIES = {"united states": "US", "united states of america": "US", "usa": "US", "canada": "CA", "united kingdom": "GB", "uk": "GB", "australia": "AU", "germany": "DE", "france": "FR", "new zealand": "NZ"}


def _host(url):
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


@lru_cache(maxsize=128)
def _origin_lock(origin):
    return Lock()


def _country_code(value):
    if isinstance(value, dict):
        value = value.get("name", "")
    value = str(value or "").strip()
    return _COUNTRIES.get(value.casefold(), value.upper() if re.fullmatch(r"[A-Za-z]{2}", value) else "")


def _page_country(html, url, location_page=False):
    soup = BeautifulSoup(html, "html.parser")
    nodes = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text())
        except (ValueError, TypeError):
            continue
        roots = data if isinstance(data, list) else [data]
        for root in roots:
            if isinstance(root, dict):
                graph = root.get("@graph")
                nodes.extend(graph if isinstance(graph, list) else [graph] if isinstance(graph, dict) else [root])
    by_id = {node.get("@id"): node for node in nodes if isinstance(node, dict) and node.get("@id")}
    countries = set()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        kinds = node.get("@type", [])
        kinds = [kinds] if isinstance(kinds, str) else kinds
        if not isinstance(kinds, list) or not any(isinstance(kind, str) and kind in _ORGANIZATIONS for kind in kinds):
            continue
        identity = node.get("url") or node.get("@id") or url
        if not isinstance(identity, str) or _host(urljoin(url, identity)) != _host(url):
            continue
        addresses = node.get("address", [])
        addresses = addresses if isinstance(addresses, list) else [addresses]
        for address in addresses:
            if isinstance(address, dict) and address.get("@id") in by_id:
                address = by_id[address["@id"]]
            if not isinstance(address, dict):
                continue
            code = _country_code(address.get("addressCountry"))
            if not code and _US_ADDRESS.search(f"{address.get('addressRegion', '')} {address.get('postalCode', '')}"):
                code = "US"
            if code:
                countries.add(code)
    if countries:
        return "US" if "US" in countries else next(iter(countries)) if len(countries) == 1 else ""
    for node in soup.select("script, style, nav, select"):
        node.decompose()
    regions = soup.select("footer, address, [role='contentinfo']")
    if location_page:
        regions.append(soup.select_one("main") or soup.body or soup)
    for region in regions:
        text = region.get_text(" ", strip=True)
        if _US_ADDRESS.search(text) or (location_page and _LOCATION.search(text)):
            return "US"
    return ""


def _fetch(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        response.raise_for_status()
        return response.url, response.text
    except requests.RequestException:
        return url, ""


def merchant_country(url, html=""):
    """Return a country code from retailer evidence, or an empty string."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ""
    suffix = _host(url).rsplit(".", 1)[-1]
    if len(suffix) == 2 and suffix not in {"us", "co", "io", "ai", "me", "tv"}:
        return "GB" if suffix == "uk" else suffix.upper()
    origin = f"{parsed.scheme}://{parsed.netloc}"
    with _origin_lock(origin):
        return _lookup_country(origin, url, html)


def _lookup_country(origin, url, html):
    cached = _CACHE.get(origin)
    code = _page_country(html, url) if html else ""
    if not code and cached and monotonic() - cached[0] < 300:
        return cached[1]
    if not code:
        home_url, home_html = _fetch(origin + "/")
        code = _page_country(home_html, home_url)
        if not code and home_html:
            soup = BeautifulSoup(home_html, "html.parser")
            links = []
            for anchor in soup.select("a[href]"):
                link = urljoin(home_url, anchor["href"]).split("#")[0]
                label = anchor.get_text(" ", strip=True) + " " + urlparse(link).path
                same_origin = urlparse(link)[:2] == urlparse(home_url)[:2]
                if same_origin and re.search(r"\b(?:contact|about|locations?|customer.support)\b", label, re.I) and link not in links:
                    links.append(link)
            for link in links[:2]:
                page_url, page_html = _fetch(link)
                code = _page_country(page_html, page_url, location_page=True)
                if code:
                    break
    _CACHE[origin] = (monotonic(), code)
    _CACHE.move_to_end(origin)
    if len(_CACHE) > 128:
        _CACHE.popitem(last=False)
    return code
