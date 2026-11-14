# Progress

## Completed

- One-field product-name and URL search.
- Fuzzy matching, retailer price extraction, and purchase links.
- Lowest-price highlighting by currency and clickable retailer links.
- Public search pagination with no preset merchant list.
- Independent stock and US-store filters, enabled by default.
- US location checks from retailer business-address information.
- 53 automated tests passed, including all four filter combinations and product-name extraction for cross-store URL searches.

## Live checks — November 13, 2026 (US Central)

- The misspelled query `lavaza supar crema 2.2 lb`, with both filters enabled, returned seven US retailers with prices. Whole Latte Love was the lowest returned offer at USD 23.99; other results included Supermarket Italy, Espresso Machine Experts, Cerini, and Seattle Coffee Gear.
- Pasting `https://dryad-games.com/shop/azul-mini/` identified `Azul Mini` and searched other stores. With both filters enabled, the app returned 10 results from nine US retailers. Cardhaus was the lowest returned offer at USD 17.59. A name search returned the same results.
- Direct extraction returned Amazon's one-time Lavazza 2.2 lb price of USD 26.99 and Logitech MX Master 3S model prices of USD 89.99.
- Location checks identified Dryad, Miniature Market, Cerini, Seattle Coffee Gear, and J.L. Hufford as US retailers.

## Reference alignment — November 14, 2026

- Invalid, unreadable, challenge, or unnamed product pages stop before cross-store discovery. The app explains the failure instead of searching terms derived from the URL path.
- A product identified from page data can still search other stores when its own price is missing.
- Unknown availability displays `Stock unknown` for priced and unpriced offers. Sold-out exclusion and lowest-price selection are unchanged.
- Validation: `python -m pytest -q` — 63 passed, 1 existing dependency warning. Checks use saved responses and Streamlit's UI test runner.
