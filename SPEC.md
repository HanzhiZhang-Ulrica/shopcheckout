# ShopCheckout Lite

## Requirements
- Streamlit checkout for Notebook ($25.00), USB Cable ($12.50), and Wireless Mouse ($19.99).
- Quantities are nonnegative integers (not booleans); the cart must contain an item.
- Blank coupon gives no discount; exact `SAVE10` gives 10% off merchandise, rounded half up to cents.
- Shipping is free when discounted merchandise is at least $50.00; otherwise it is $5.00.
- Tax is 8% of discounted merchandise, excludes shipping, rounded half up to cents.
- Invalid cart, quantity, product, or coupon raises a clear `ValueError`.
- Core project files: `SPEC.md`, `PROGRESS.md`, `checkout.py`, `app.py`, `test_checkout.py`, `requirements.txt`.

## Architecture
- `checkout.py` owns prices and calculations using `Decimal` values.
- `app.py` collects quantities and coupon through Streamlit, calls `calculate_checkout`, and renders a receipt.
- `test_checkout.py` contains exactly four pytest functions for the acceptance cases.
- `requirements.txt` lists only `streamlit` and `pytest`.

## Function contract
`calculate_checkout(cart, coupon="")` accepts a mapping of exact product names to nonnegative integer quantities. It returns exactly five `Decimal` amounts: `subtotal`, `discount`, `shipping`, `tax`, and `total`, quantized to cents. Invalid input raises `ValueError`.

## Acceptance cases
1. Two Notebook, no coupon: subtotal 50.00, discount 0.00, shipping 0.00, tax 4.00, total 54.00.
2. Two Notebook, `SAVE10`: subtotal 50.00, discount 5.00, shipping 5.00, tax 3.60, total 53.60.
3. One Wireless Mouse: subtotal 19.99, discount 0.00, shipping 5.00, tax 1.60, total 26.59.
4. Empty cart raises `ValueError`.

## Four-step plan
1. Define checkout validation, prices, rounding, discount, shipping, and tax.
2. Add the four acceptance tests and project requirements.
3. Build the Streamlit quantity, coupon, calculation, and receipt interface.
4. Run the four pytest cases, launch Streamlit, and verify checkout and errors in the browser.

## Scope
- Local checkout demo only; no database, login, inventory, payment, or deployment.
