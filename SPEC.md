# ShopCheckout Lite

## Purpose
Compare personal-shopping offers by compatible unit price and actual checkout cost, including package counts, promotions, shipping, tax, and surplus. The Streamlit dashboard includes offer CRUD, saved comparisons, and CSV export.

## Offers and validation
An offer has a stable ID, product group and specification, retailer, package size and unit, price, promotion, optional source URL and update timestamp, shipping, tax percentage, and optional free-shipping threshold. Offers are immutable; edits preserve the ID and refresh the timestamp. Promotions are none, percent (0–100), or fixed dollars (nonnegative and capped at subtotal). Missing shipping or tax means unknown; zero is known zero. A qualifying discounted subtotal resolves shipping to zero.

All numeric inputs use `Decimal(str(value))`; booleans and nonfinite values are rejected. Item package and required quantities must be whole counts. Prices, shipping, fixed discounts, and shipping thresholds must be whole cents. Percentages retain decimal precision. Units are case-insensitive: mL, L, US fl oz; g, kg, oz, lb; item. Volume converts to mL (1, 1000, 29.5735295625); weight to g (1, 1000, 28.349523125, 453.59237); count to item (1). Comparisons require an explicit required unit, matching dimensions, and one product group.

Package and required quantities must be greater than zero, currency inputs must be nonnegative, and tax must be between 0% and 100%.

## Calculations
Each purchase option buys whole packages from one retailer. Packages are ceiling(required/package); purchased quantity and surplus display in the selected required unit. Currency calculations round HALF_UP to cents. Discount is applied once to subtotal; free shipping checks discounted merchandise; shipping is once per order; tax rounds on discounted merchandise and excludes shipping. Total is merchandise after discount + shipping + tax. Shelf price divides package price by package quantity; effective price divides known total by actual purchased quantity. Unknown total costs are excluded from ranking. Ties are reported; incomplete costs mark the result as the lowest known total.

## Persistence and export
SQLite stores named comparisons and all offer fields as JSON, with `Decimal` values serialized as text. `None` remains distinct from zero. The database is created automatically at `SHOPCHECKOUT_DB` or `shopcheckout.sqlite3`. Loading validates offers and requirements; calculations are recomputed from restored inputs. Save creates and activates a record; Update and Delete target only the active record.

CSV includes source inputs, explicit requirement and normalized quantities, package counts, purchased quantity and surplus, per-L/kg/item shelf and effective prices, cost components, configured and charged shipping, URLs, and offer timestamps. Unknown fields export blank; comma and Unicode text is CSV-escaped.

## Public calculation interfaces
`offers.py`: `Promotion`, `Offer`, `create_offer(...)`, `edit_offer(offer, **changes)`.
`comparison.py`: `normalize_quantity(quantity, unit)`, `compare_offers(offers, required_quantity, required_unit)`, `rank_purchases(options)`, `compare_and_rank(offers, required_quantity, required_unit)`, `export_comparison_csv(...)`, `sample_offers()`.
`storage.py`: `save_comparison(...)`, `list_comparisons(...)`, `load_comparison(...)`, `update_comparison(...)`, `delete_comparison(...)`.

## Sample
The included A/B/C liquid hand-soap refill offers compare at 30, 50, and 100 US fl oz. The checkout totals are A/B/C = $17.63/$15.65/$10.79, $17.63/$15.65/$21.58, and $30.25/$31.30/$32.37. Recommended stores are C, B, and A.
