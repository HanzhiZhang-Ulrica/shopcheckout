"""Pure checkout calculations for ShopCheckout Lite."""

from collections.abc import Mapping
from decimal import Decimal, ROUND_HALF_UP

from catalog import PRODUCTS

CENT = Decimal("0.01")


def _money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_checkout(cart, coupon="", shipping_method="standard"):
    """Validate a cart and return its itemized receipt and Decimal amounts."""
    if not isinstance(cart, Mapping):
        raise ValueError("Cart must be a mapping of product names to quantities.")
    if not cart:
        raise ValueError("Cart must contain at least one item.")
    if not isinstance(coupon, str) or coupon not in ("", "SAVE10"):
        raise ValueError("Unknown coupon. Use SAVE10 or leave the coupon blank.")
    if not isinstance(shipping_method, str) or shipping_method not in ("standard", "express"):
        raise ValueError("Unknown shipping method. Choose Standard or Express.")

    items = []
    for product, quantity in cart.items():
        if product not in PRODUCTS:
            raise ValueError(f"Unknown product: {product!r}.")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
            raise ValueError(f"Quantity for {product} must be a nonnegative integer.")
        if quantity > 0:
            items.append({
                "product": product,
                "quantity": quantity,
                "unit_price": PRODUCTS[product],
                "line_total": _money(PRODUCTS[product] * quantity),
            })
    if not items:
        raise ValueError("Cart must contain at least one item.")

    subtotal = _money(sum((item["line_total"] for item in items), Decimal("0.00")))
    discount = _money(subtotal * Decimal("0.10")) if coupon == "SAVE10" else Decimal("0.00")
    merchandise = _money(subtotal - discount)
    if shipping_method == "express":
        shipping = Decimal("12.00")
    else:
        shipping = Decimal("0.00") if merchandise >= Decimal("50.00") else Decimal("5.00")
    tax = _money(merchandise * Decimal("0.08"))
    total = _money(merchandise + shipping + tax)
    return {
        "items": items,
        "shipping_method": shipping_method,
        "subtotal": subtotal,
        "discount": discount,
        "shipping": shipping,
        "tax": tax,
        "total": total,
    }
