# ShopCheckout Lite Specification

## Workflow

1. Enter a product name, partial name, misspelling, or product URL.
2. Search public web result pages for matching retailers, without a preset merchant list.
3. Read prices from product pages and public retailer catalogs.
4. Display product names, stores, prices, and clickable purchase links.
5. Apply the selected stock and country filters and highlight the lowest listed price in each currency, including ties.

## Result rules

- Resolve a product URL to its name before searching other stores.
- Keep matching links visible when a price is unavailable.
- Offer independent "Hide sold-out items" and "US stores only" checkboxes, both enabled by default.
- Exclude sold-out offers when the stock filter is enabled.
- Establish a retailer's US location from its business address when the US filter is enabled.
- Use one-time purchase prices and preserve each offer's currency.

## Files

- `shopping.py`: web search, product matching, and price extraction.
- `country.py`: retailer location lookup.
- `app.py`: one search field and the results table.
- `test_shopcheckout.py`: parsing, search, and interface tests.
