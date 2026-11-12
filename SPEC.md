# ShopCheckout Lite

## Requirements

Build a local Python and Streamlit shopping cart and checkout application.

- Catalog: Notebook $25.00, USB Cable $12.50, Wireless Mouse $19.99.
- Input cart: exact product names mapped to nonnegative integer quantities. Booleans are invalid. At least one quantity must be positive.
- Coupon: blank or exactly `SAVE10`. The coupon discounts merchandise by 10%.
- Standard shipping: free when merchandise after discount is at least $50.00; otherwise $5.00.
- Express shipping: $12.00 at every order value.
- Tax: 8% of merchandise after discount, excluding shipping.
- Total: subtotal minus discount plus shipping plus tax.
- Use `Decimal` throughout. Round discount and tax to cents with `ROUND_HALF_UP`; return cent-quantized amounts.
- Invalid cart, product, quantity, coupon, or shipping method raises a clear `ValueError`.

## Acceptance criteria

1. Submit quantities, coupon, and shipping choice together.
2. List selected products with quantity, unit price, and line total.
3. Apply the selected shipping rule and show its name.
4. Display subtotal, discount, shipping, tax, and total to two decimals.
5. Match the eight core test cases below and verify Standard and Express in the browser.

## Architecture

| File | Responsibility |
| --- | --- |
| `catalog.py` | Product names and Decimal prices in `PRODUCTS` |
| `checkout.py` | Input validation, item rows, and pricing rules |
| `app.py` | Streamlit form, itemized receipt, session state, and optional text download |
| `test_checkout.py` | Eight core pytest tests |
| `SPEC.md` | Requirements, data contract, architecture, and plan |
| `PROGRESS.md` | Verified results and next action |
| `requirements.txt` | `streamlit` and `pytest` |

The UI and pricing engine import the catalog. The UI passes cart, coupon, and shipping method to the engine and renders the returned receipt. Tests call the engine directly.

## Function contract

```python
calculate_checkout(cart, coupon="", shipping_method="standard")
```

`cart` is a mapping such as `{"Notebook": 1, "USB Cable": 2}`.
Shipping values are `"standard"` and `"express"`.

Return exactly these fields:

- `items`: a list of positive-quantity entries in input order. Each contains `product` (string), `quantity` (integer), `unit_price` (Decimal), and `line_total` (Decimal). Line totals are before the order-level discount.
- `shipping_method`: the chosen lowercase method.
- `subtotal`, `discount`, `shipping`, `tax`, `total`: five Decimal amounts with two decimal places.

Zero-quantity products are validated but omitted from the receipt. An empty or all-zero cart raises `ValueError`. The default shipping method preserves the original Standard checkout behavior.

## Eight core tests

| Case | Cart | Coupon | Shipping | Subtotal | Discount | Shipping fee | Tax | Total/result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2 Notebooks | Blank | Standard | 50.00 | 0.00 | 0.00 | 4.00 | 54.00 |
| 2 | 2 Notebooks | SAVE10 | Standard | 50.00 | 5.00 | 5.00 | 3.60 | 53.60 |
| 3 | 2 Notebooks | SAVE10 | Express | 50.00 | 5.00 | 12.00 | 3.60 | 60.60 |
| 4 | 1 Notebook + 1 Wireless Mouse | SAVE10 | Standard | 44.99 | 4.50 | 5.00 | 3.24 | 48.73 |
| 5 | Empty/all-zero cart | Blank | Standard | | | | | ValueError |
| 6 | Negative quantity | Blank | Standard | | | | | ValueError |
| 7 | 1 Notebook | SAVE20 | Standard | | | | | ValueError |
| 8 | 1 Notebook | Blank | overnight | | | | | ValueError |

Normal-case tests check every amount, Decimal type and cent precision, item rows, and shipping method. The first case also checks the default shipping method and omission of a zero-quantity product.

## UI state and optional extension

A successful submission stores the receipt, submitted coupon, and formatted receipt text in `st.session_state`. The summary and download use that submitted snapshot. Editing form inputs does not relabel the previous receipt. An invalid submission clears the previous receipt and download.

The optional receipt download is implemented in the reference app. `st.download_button` sits outside `st.form` and serves a plain-text receipt containing item quantities, unit prices, line totals, coupon, shipping method, and all five amounts. Session state holds the result for the current Streamlit session.

## Four development rounds

1. **Requirements:** create SPEC.md and PROGRESS.md; agree on products, shipping, coupon, amounts, and acceptance criteria.
2. **Design:** define seven core files, cart and receipt structures, and the pricing function contract.
3. **Logic and tests:** implement catalog.py, checkout.py, and eight tests; run pytest and resolve failures.
4. **UI and browser:** implement app.py, submit Standard and Express checkouts, compare the receipt with expected values, and update progress.

After the core workflow, add the optional receipt download and verify that it matches the displayed submitted receipt.
