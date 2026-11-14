"""Web product discovery and prices read from public retailer pages."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from functools import lru_cache
import json
import re
from time import monotonic
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from country import merchant_country


HEADERS = {"User-Agent": "ShopCheckoutLite/2.0", "Accept": "text/html,application/json"}
PROFILE = "https://shopify.dev/ucp/agent-profiles/examples/2026-08-25/valid-with-capabilities.json"
TIMEOUT = 8
_SEARCH_CACHE = {}


@dataclass(frozen=True)
class Offer:
    title: str
    store: str
    url: str
    price: Decimal | None = None
    currency: str = ""
    available: bool | None = None
    checked_at: str = ""


@dataclass(frozen=True)
class SearchResult:
    query: str
    offers: list[Offer]


class ProductInputError(ValueError):
    """The input link is invalid or does not identify a product."""


def _get(url, **kwargs):
    for attempt in range(2):
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, **kwargs)
        if response.status_code not in (502, 503, 504) or attempt:
            break
    response.raise_for_status()
    return response


def _money(value):
    try:
        amount = Decimal(str(value).replace(",", "").strip())
        return amount if amount.is_finite() and amount > 0 else None
    except (InvalidOperation, ValueError):
        return None


def _stock(value):
    value = str(value or "").lower()
    if any(word in value for word in ("outofstock", "out of stock", "soldout", "discontinued")):
        return False
    if any(word in value for word in ("instock", "in stock", "limitedavailability")):
        return True
    return None


def _host(url):
    return urlparse(url).netloc.lower().removeprefix("www.")


def _valid_url(url):
    try:
        parsed = urlparse(url)
        parsed.port
        return (parsed.scheme in ("https", "http") and bool(parsed.hostname)
                and not any(character.isspace() for character in url))
    except ValueError:
        return False


def _challenge_title(title):
    return any(text in title.casefold() for text in (
        "access denied", "robot check", "captcha", "just a moment",
        "attention required", "verify you are human", "security check",
    ))


def search_web(query):
    """Use a public web search, without a merchant or product allowlist."""
    cache_key = query.strip().casefold()
    cached = _SEARCH_CACHE.get(cache_key)
    if cached and monotonic() - cached[0] < 300:
        return list(cached[1])
    response = _get("https://lite.duckduckgo.com/lite/", params={"q": query + " buy", "kl": "us-en"})
    results = []
    seen = set()
    visited_pages = set()
    while True:
        soup = BeautifulSoup(response.text, "html.parser")
        previous_count = len(results)
        for anchor in soup.select("a.result-link"):
            url = urljoin(response.url, anchor.get("href", ""))
            redirect = parse_qs(urlparse(url).query).get("uddg")
            if redirect:
                url = redirect[0]
            if not _valid_url(url) or _host(url).endswith("duckduckgo.com") or url in seen:
                continue
            seen.add(url)
            results.append((anchor.get_text(" ", strip=True), url))
        if len(results) == previous_count:
            if not results and ("anomaly" in response.text.lower() or response.status_code == 202):
                raise RuntimeError("Web search is temporarily unavailable.")
            break
        next_form = next((form for form in soup.find_all("form") if any(
            "next page" in str(button.get("value", "")).casefold()
            for button in form.select('input[type="submit"]')
        )), None)
        if next_form is None:
            break
        endpoint = urljoin(response.url, next_form.get("action", ""))
        fields = {field["name"]: field.get("value", "") for field in next_form.select("input[name]")}
        method = str(next_form.get("method", "get")).lower()
        signature = (endpoint, method, tuple(sorted(fields.items())))
        if signature in visited_pages:
            break
        visited_pages.add(signature)
        try:
            if method == "post":
                response = requests.post(endpoint, data=fields, headers=HEADERS, timeout=TIMEOUT)
                response.raise_for_status()
            else:
                response = _get(endpoint, params=fields)
        except requests.RequestException:
            break
    _SEARCH_CACHE[cache_key] = (monotonic(), tuple(results))
    if len(_SEARCH_CACHE) > 128:
        del _SEARCH_CACHE[min(_SEARCH_CACHE, key=lambda key: _SEARCH_CACHE[key][0])]
    return results


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def parse_page(html, url, fallback_title=""):
    """Read Product JSON-LD, product meta tags, or an Amazon purchase price."""
    soup = BeautifulSoup(html, "html.parser")

    def meta(key):
        node = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        return node.get("content", "") if node else ""

    title = meta("og:title") or (soup.title.get_text(" ", strip=True) if soup.title else fallback_title)
    title = title.split(" | ")[0].strip() or fallback_title
    store = meta("og:site_name") or _host(url)
    def product_name(value):
        return re.sub(r"\s+[-–—|]\s*" + re.escape(store) + r"\s*$", "", str(value), flags=re.I).strip()
    title = product_name(title)
    checked = datetime.now(timezone.utc).isoformat(timespec="seconds")
    products = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            document = json.loads(script.string or script.get_text())
        except (ValueError, TypeError):
            continue
        for product in _walk(document):
            kinds = product.get("@type", [])
            kinds = [kinds] if isinstance(kinds, str) else kinds
            if not isinstance(kinds, list) or "Product" not in kinds:
                continue
            products.append(product)

    def primary_score(product):
        entries = product.get("offers") or []
        entries = [entries] if isinstance(entries, dict) else entries
        links = [product.get("url"), product.get("@id")]
        if isinstance(entries, list):
            links.extend(entry.get("url") for entry in entries if isinstance(entry, dict))
        same_page = any(
            _host(urljoin(url, link)) == _host(url)
            and urlparse(urljoin(url, link)).path.rstrip("/") == urlparse(url).path.rstrip("/")
            for link in links if isinstance(link, str) and link
        )
        name = str(product.get("name") or "")
        return same_page, SequenceMatcher(None, title.casefold(), name.casefold()).ratio()

    offers = []
    if products:
        # Recommendation widgets can contain their own Product records.
        primary = max(products, key=primary_score)
        title = product_name(primary.get("name") or title)
        models = primary.get("model") or primary.get("hasVariant") or []
        models = [models] if isinstance(models, dict) else models
        candidates = [primary] + [model for model in models if isinstance(model, dict)] if isinstance(models, list) else [primary]
    else:
        candidates = []
    for product in candidates:
        name = product_name(product.get("name") or title)
        entries = product.get("offers") or []
        entries = [entries] if isinstance(entries, dict) else entries
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict):
                continue
            specifications = entry.get("priceSpecification") or {}
            if isinstance(specifications, list):
                specifications = next((item for item in specifications if isinstance(item, dict)), {})
            if not isinstance(specifications, dict):
                specifications = {}
            price = _money(entry.get("price", specifications.get("price")))
            currency = str(entry.get("priceCurrency") or specifications.get("priceCurrency") or "").upper()
            link = urljoin(url, str(entry.get("url") or product.get("url") or primary.get("url") or url))
            if price is not None and currency and _valid_url(link):
                offers.append(Offer(name, store, link, price, currency, _stock(entry.get("availability")), checked))
    if offers:
        return product_name(primary.get("name") or title), offers

    def item_value(scope, key):
        node = scope.select_one(f'[itemprop="{key}"]')
        return str(node.get("content") or node.get("href") or node.get_text(" ", strip=True)) if node else ""

    scopes = soup.select('[itemscope][itemtype$="/Product"]') or soup.select('[itemscope][itemtype$="/Offer"]')
    if scopes:
        scope = max(scopes, key=lambda node: SequenceMatcher(
            None, title.casefold(), item_value(node, "name").casefold()).ratio())
        price = _money(item_value(scope, "price"))
        currency = item_value(scope, "priceCurrency").upper()
        if price is not None and currency:
            return title, [Offer(title, store, url, price, currency, _stock(item_value(scope, "availability")), checked)]
    else:
        price_node = soup.select_one('meta[itemprop="price"]')
        currency_node = soup.select_one('meta[itemprop="priceCurrency"]')
        price = _money(price_node.get("content", "")) if price_node else None
        currency = str(currency_node.get("content", "")).upper() if currency_node else ""
        if price is not None and currency:
            return title, [Offer(title, store, url, price, currency, None, checked)]

    price = _money(meta("product:price:amount") or meta("og:price:amount"))
    currency = (meta("product:price:currency") or meta("og:price:currency")).upper()
    if price is not None and currency:
        return title, [Offer(title, store, url, price, currency, _stock(meta("product:availability")), checked)]

    if "amazon." in _host(url):
        name = soup.select_one("#productTitle")
        title = name.get_text(" ", strip=True) if name else title
        purchase = soup.select("#apex_desktop_newAccordionRow, #corePrice_feature_div, #corePriceDisplay_desktop_feature_div")
        price_nodes = [node for scope in purchase for node in scope.select(".priceToPay, .apexPriceToPay")]
        if not price_nodes:
            price_nodes = [node for scope in purchase for node in scope.select(".a-price")]
        for price_node in price_nodes:
            markers = " ".join(str(node.get("id", "")) + " " + " ".join(node.get("class", []))
                               for node in [price_node, *price_node.parents] if getattr(node, "attrs", None)).lower()
            if any(marker in markers for marker in ("priceperunit", "price-per-unit", "unitprice", "unit-price", "a-price-unit", "basisprice", "a-text-price")):
                continue
            text = next((node.get_text(strip=True) for node in price_node.select(".a-offscreen")
                         if node.get_text(strip=True)), "")
            if not text:
                whole = price_node.select_one(".a-price-whole")
                fraction = price_node.select_one(".a-price-fraction")
                symbol = price_node.select_one(".a-price-symbol")
                if whole and symbol:
                    text = symbol.get_text(strip=True) + whole.get_text(strip=True).rstrip(".,")
                    if fraction:
                        text += "." + fraction.get_text(strip=True)
            if re.search(r"(?:/|\bper\b)\s*(?:oz|ounce|lb|pound|count|item|gram|kg|ml|liter)", text, re.I):
                continue
            match = re.search(r"[\d,]+(?:\.\d{2})?", text)
            currency = "USD" if _host(url).endswith("amazon.com") and "$" in text else "GBP" if "£" in text else "EUR" if "€" in text else ""
            if match and currency:
                availability = soup.select_one("#availability")
                return title, [Offer(title, store, url, _money(match.group()), currency, _stock(availability.get_text() if availability else ""), checked)]
    return title, []


@lru_cache(maxsize=128)
def discover_catalog(origin):
    """Discover a retailer's advertised public catalog; no stored merchant list."""
    try:
        discovery = _get(origin + "/.well-known/ucp").json()
        services = discovery.get("ucp", {}).get("services", {}).get("dev.ucp.shopping", [])
        services = [services] if isinstance(services, dict) else services
        for service in services:
            endpoint = service.get("endpoint", "")
            if service.get("transport") == "mcp" and endpoint.startswith("https://"):
                return endpoint
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        pass
    return None


def _catalog_call(endpoint, name, catalog):
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": name, "arguments": {"meta": {"ucp-agent": {"profile": PROFILE}}, "catalog": catalog}}}
    response = requests.post(endpoint, json=payload, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    result = response.json().get("result", {})
    data = result.get("structuredContent")
    if data is None:
        data = next((json.loads(item["text"]) for item in result.get("content", []) if item.get("type") == "text"), {})
    if result.get("isError") or data.get("ucp", {}).get("status") == "error":
        raise ValueError("Catalog request failed.")
    return data


def catalog_offers(url):
    parsed = urlparse(url)
    match = re.search(r"/products/([^/?]+)", parsed.path)
    if not match:
        return []
    endpoint = discover_catalog(f"{parsed.scheme}://{parsed.netloc}")
    if not endpoint:
        return []
    handle = unquote(match.group(1))
    context = {"address_country": "US", "currency": "USD"}
    data = _catalog_call(endpoint, "search_catalog", {"query": handle.replace("-", " "), "context": context, "pagination": {"limit": 10}})
    products = data.get("products", [])
    product = next((p for p in products if urlparse(p.get("url", "")).path.rstrip("/").endswith("/products/" + handle)), None)
    if not product:
        return []
    variant_id = parse_qs(parsed.query).get("variant", [None])[0]
    if variant_id:
        data = _catalog_call(endpoint, "lookup_catalog", {"ids": ["gid://shopify/ProductVariant/" + variant_id], "context": context})
        product = next(iter(data.get("products", [])), data.get("product", product))
    if not product.get("variants"):
        detail = _catalog_call(endpoint, "get_product", {"id": product["id"], "selected": [], "context": context})
        product = detail.get("product", detail)
    offers = []
    for variant in product.get("variants", []):
        number = str(variant.get("id", "")).rsplit("/", 1)[-1]
        if variant_id and number != variant_id:
            continue
        price = variant.get("price") or {}
        amount = _money(price.get("amount"))
        if amount is None or price.get("currency") != "USD" or variant.get("requires", {}).get("selling_plan"):
            continue
        label = variant.get("title") or ""
        name = product.get("title", handle)
        if label and label != "Default Title":
            name += " · " + label
        link = product.get("url", url).split("?")[0] + "?" + urlencode({"variant": number})
        offers.append(Offer(name, _host(url), link, amount / 100, "USD", variant.get("availability", {}).get("available"), datetime.now(timezone.utc).isoformat(timespec="seconds")))
    return offers


def read_product(url, fallback_title=""):
    title = fallback_title
    offers = []
    try:
        response = _get(url)
        if "html" in response.headers.get("Content-Type", ""):
            title, offers = parse_page(response.text, response.url, fallback_title)
            if _challenge_title(title):
                title, offers = fallback_title, []
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        pass
    # A public catalog can supply an exact variant when the page is dynamic.
    if "/products/" in urlparse(url).path and (not offers or "variant=" in urlparse(url).query):
        try:
            catalog = catalog_offers(url)
            if catalog:
                offers = catalog
                title = catalog[0].title
        except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError):
            pass
    return title, offers


def relevance(query, title):
    """Soft token matching tolerates incomplete names and minor misspellings."""
    ignored = {"the", "a", "an", "and", "of", "for", "buy", "price", "with"}
    measurements = {"kg", "g", "oz", "ounce", "ounces", "lb", "lbs", "pound", "pounds",
                    "ml", "l", "liter", "litre", "liters", "litres", "fl", "pk", "ct", "mm", "cm"}

    def tokens(text):
        text = text.casefold()
        text = re.sub(r"(?<=[a-z])(?=\d+(?:[.,]\d+)?(?:kg|g|oz|lbs?|ml|l)\b)", " ", text)
        text = re.sub(r"(?<=\d)(?=(?:kg|g|oz|lbs?|ml|l)\b)", " ", text)
        return [w for w in re.findall(r"[\w]+", text) if w not in ignored]

    wanted, found = tokens(query), tokens(title)
    if not wanted or not found:
        return 0.0
    # Model codes distinguish products; ordinary words still allow typos.
    units = r"\d+(?:kg|g|oz|lbs?|ml|l|pk|ct|mm|cm)"
    models = [word for word in wanted if any(c.isdigit() for c in word)
              and any(c.isalpha() for c in word) and not re.fullmatch(units, word)]
    if any(model not in found for model in models):
        return 0.0
    extras = {"accessory", "accessories", "replacement", "bundle", "bundles"}
    if extras.intersection(found) and not extras.intersection(wanted):
        return 0.0
    words = [word for word in wanted if not word.isdigit() and word not in measurements]
    if not words:
        return 0.0
    scores = [max(SequenceMatcher(None, word, candidate).ratio() for candidate in found) for word in words]
    return sum(scores) / len(scores) if min(scores) >= 0.70 else 0.0


def search_prices(user_input, hide_sold_out=True, us_only=True):
    query = user_input.strip()
    if not query:
        raise ProductInputError("Enter a product name or product link.")
    if re.match(r"^(?:www\.)?[\w.-]+\.[a-z]{2,}/", query, re.I):
        query = "https://" + query
    direct_offers = []
    direct_url = query if _valid_url(query) else None
    if not direct_url and (re.match(r"^[a-z][\w+.-]*://", query, re.I)
                           or query.lower().startswith(("http:", "https:", "www."))):
        raise ProductInputError("Enter a valid HTTP or HTTPS product link.")
    if direct_url:
        title, direct_offers = read_product(direct_url)
        if not title.strip() or title.casefold() == _host(direct_url) or _challenge_title(title):
            raise ProductInputError(
                "Could not identify a product from this link. Check the product page or search by name."
            )
        query = title
        if us_only and merchant_country(direct_url) != "US":
            direct_offers = []
        if hide_sold_out:
            direct_offers = [offer for offer in direct_offers if offer.available is not False]
    try:
        links = search_web(query)
    except (requests.RequestException, RuntimeError):
        if not direct_offers:
            raise
        links = []

    def inspect(item):
        title, url = item
        if us_only and merchant_country(url) != "US":
            return []
        name, found = read_product(url, title)
        indexed_relevance = relevance(query, title) if not query.isascii() else 0.0
        if found:
            return [offer for offer in found if (not hide_sold_out or offer.available is not False)
                    and max(relevance(query, offer.title), indexed_relevance) >= 0.60]
        if max(relevance(query, name or title), indexed_relevance) >= 0.60:
            return [Offer(name or title, _host(url), url)]
        return []

    with ThreadPoolExecutor(max_workers=6) as pool:
        batches = list(pool.map(inspect, links))
    rows = direct_offers + [offer for batch in batches for offer in batch]
    unique = {}
    for offer in rows:
        key = (_host(offer.url), urlparse(offer.url).path,
               parse_qs(urlparse(offer.url).query).get("variant", [""])[0], offer.title.casefold())
        if key not in unique or offer.price is not None:
            unique[key] = offer
    return SearchResult(query, sorted(unique.values(), key=lambda offer: -relevance(query, offer.title)))
