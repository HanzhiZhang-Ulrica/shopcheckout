"""Pure checkout calculations for ShopCheckout Lite."""

from collections.abc import Mapping
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
PRODUCTS = {
    "Notebook": Decimal("25.00"),
    "USB Cable": Decimal("12.50"),
    "Wireless Mouse": Decimal("19.99"),
}


def _money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_checkout(cart, coupon=""):
    """Return the five cent-quantized checkout amounts for a product cart."""
    if not isinstance(cart, Mapping):
        raise ValueError("Cart must be a mapping of product names to quantities.")
    if not cart:
        raise ValueError("Cart must contain at least one item.")
    if not isinstance(coupon, str) or coupon not in ("", "SAVE10"):
        raise ValueError("Unknown coupon. Use SAVE10 or leave the coupon blank.")

    subtotal = Decimal("0.00")
    has_quantity = False
    for product, quantity in cart.items():
        if product not in PRODUCTS:
            raise ValueError(f"Unknown product: {product!r}.")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
            raise ValueError(f"Quantity for {product} must be a nonnegative integer.")
        subtotal += PRODUCTS[product] * quantity
        has_quantity = has_quantity or quantity > 0
    if not has_quantity:
        raise ValueError("Cart must contain at least one item.")

    subtotal = _money(subtotal)
    discount = _money(subtotal * Decimal("0.10")) if coupon == "SAVE10" else Decimal("0.00")
    merchandise = _money(subtotal - discount)
    shipping = Decimal("0.00") if merchandise >= Decimal("50.00") else Decimal("5.00")
    tax = _money(merchandise * Decimal("0.08"))
    total = _money(merchandise + shipping + tax)
    return {"subtotal": subtotal, "discount": discount, "shipping": shipping, "tax": tax, "total": total}
