# ShopCheckout Lite Specification

## Workflow

1. Enter a product name, partial name, misspelling, or product URL.
2. Search public web result pages for matching retailers, without a preset merchant list.
3. Read prices from product pages and public retailer catalogs.
4. Display product names, stores, prices, and clickable purchase links.
5. Apply the selected stock and country filters and highlight the lowest listed price in each currency, including ties.

## Result rules

- Validate and read a product URL, then identify its product before searching other stores. If identification fails, stop and explain the failure; do not derive a query from the URL path.
- Keep matching links visible when a price is unavailable.
- Offer independent "Hide sold-out items" and "US stores only" checkboxes, both enabled by default.
- Exclude sold-out offers when the stock filter is enabled.
- Keep unknown-stock offers visible and label them "Stock unknown", including offers without a price.
- Establish a retailer's US location from its business address when the US filter is enabled.
- Use one-time purchase prices and preserve each offer's currency.

## Files

- `shopping.py`: web search, product matching, and price extraction.
- `country.py`: retailer location lookup.
- `app.py`: one search field and the results table.
- `test_shopcheckout.py`: parsing, search, and interface tests.
