"""Unit normalization, checkout calculation, and purchase ranking."""

from dataclasses import dataclass
import csv
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from io import StringIO

from offers import Offer, decimal_value


CENT = Decimal("0.01")
CONVERSIONS = {
    "ml": ("volume", Decimal("1")),
    "l": ("volume", Decimal("1000")),
    "us fl oz": ("volume", Decimal("29.5735295625")),
    "g": ("weight", Decimal("1")),
    "kg": ("weight", Decimal("1000")),
    "oz": ("weight", Decimal("28.349523125")),
    "lb": ("weight", Decimal("453.59237")),
    "item": ("count", Decimal("1")),
}
DISPLAY = {
    "volume": ("L", Decimal("1000")),
    "weight": ("kg", Decimal("1000")),
    "count": ("item", Decimal("1")),
}


def money(value):
    """Round a computed currency amount to cents using HALF_UP."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def normalize_unit(unit):
    """Validate a supported unit and return its canonical spelling."""
    if not isinstance(unit, str):
        raise ValueError("unit must be a supported unit string")
    normalized = unit.strip().lower()
    if normalized not in CONVERSIONS:
        raise ValueError("unsupported unit")
    return normalized


def normalize_quantity(quantity, unit):
    """Convert quantity to the base unit for its dimension."""
    normalized_unit = normalize_unit(unit)
    value = decimal_value(quantity, "quantity")
    return value * CONVERSIONS[normalized_unit][1]


@dataclass(frozen=True)
class PurchaseOption:
    offer: Offer
    packages: int
    purchased_quantity: Decimal
    surplus: Decimal
    subtotal: Decimal
    discount: Decimal
    discounted_merchandise: Decimal
    shipping: Decimal | None
    tax: Decimal | None
    total: Decimal | None
    shelf_unit_price: Decimal
    effective_unit_price: Decimal | None
    display_unit: str
    quantity_unit: str
    sufficient: bool = True


def compare_offers(offers, required_quantity, required_unit):
    """Calculate one-retailer package purchases for a required quantity."""
    offers = tuple(offers)
    required = decimal_value(required_quantity, "required quantity")
    if required <= 0:
        raise ValueError("required quantity must be positive")

    required_unit = normalize_unit(required_unit)
    family = CONVERSIONS[required_unit][0]
    if family == "count" and required != required.to_integral_value():
        raise ValueError("required item quantity must be a whole count")

    if any(not isinstance(offer, Offer) for offer in offers):
        raise ValueError("offers must contain Offer values")
    if not offers:
        return ()

    group = offers[0].product_group
    for offer in offers:
        offer_unit = normalize_unit(offer.unit)
        offer_family = CONVERSIONS[offer_unit][0]
        if offer.product_group != group:
            raise ValueError("offers must share a product group")
        if offer_family != family:
            raise ValueError("required and offer units must be compatible")

    needed = normalize_quantity(required, required_unit)
    results = []
    display_unit, display_factor = DISPLAY[family]

    for offer in offers:
        offer_unit = normalize_unit(offer.unit)
        package_quantity = normalize_quantity(offer.package_size, offer_unit)
        package_count = int(
            (needed / package_quantity).to_integral_value(rounding=ROUND_CEILING)
        )
        purchased = package_quantity * package_count
        surplus = purchased - needed
        subtotal = offer.price * package_count

        if offer.promotion.kind == "percent":
            discount = money(subtotal * offer.promotion.value / Decimal("100"))
        elif offer.promotion.kind == "fixed":
            discount = min(offer.promotion.value, subtotal)
        else:
            discount = Decimal("0.00")
        discounted_merchandise = max(Decimal("0.00"), subtotal - discount)

        shipping = offer.shipping
        threshold = offer.free_shipping_threshold
        if threshold is not None and discounted_merchandise >= threshold:
            shipping = Decimal("0.00")

        tax = None
        if offer.tax_percent is not None:
            tax = money(discounted_merchandise * offer.tax_percent / Decimal("100"))

        total = None
        if shipping is not None and tax is not None:
            total = discounted_merchandise + shipping + tax

        shelf_unit_price = offer.price / (package_quantity / display_factor)
        effective_unit_price = None
        if total is not None:
            effective_unit_price = total / (purchased / display_factor)

        required_factor = CONVERSIONS[required_unit][1]
        results.append(
            PurchaseOption(
                offer=offer,
                packages=package_count,
                purchased_quantity=purchased / required_factor,
                surplus=surplus / required_factor,
                subtotal=subtotal,
                discount=discount,
                discounted_merchandise=discounted_merchandise,
                shipping=shipping,
                tax=tax,
                total=total,
                shelf_unit_price=shelf_unit_price,
                effective_unit_price=effective_unit_price,
                display_unit=display_unit,
                quantity_unit=required_unit,
                sufficient=purchased >= needed,
            )
        )

    return tuple(results)


def rank_purchases(options):
    """Rank known sufficient costs and report whether any cost is incomplete."""
    options = tuple(options)
    incomplete = any(option.total is None for option in options)
    sufficient = [
        option for option in options
        if option.sufficient and option.total is not None
    ]
    ordered = tuple(
        sorted(sufficient, key=lambda option: (option.total, option.offer.offer_id))
    )
    if not ordered:
        return {"ranked": (), "winner_ids": (), "incomplete": incomplete}

    best_total = ordered[0].total
    winner_ids = tuple(
        option.offer.offer_id for option in ordered if option.total == best_total
    )
    return {
        "ranked": ordered,
        "winner_ids": winner_ids,
        "incomplete": incomplete,
    }


def compare_and_rank(offers, required_quantity, required_unit):
    """Calculate options and their total-price ranking."""
    options = compare_offers(offers, required_quantity, required_unit)
    return options, rank_purchases(options)


def export_comparison_csv(options, required_quantity, required_unit, product_group):
    """Export current inputs and calculated values as UTF-8-compatible CSV text."""
    required_unit = normalize_unit(required_unit)
    normalized_required = normalize_quantity(required_quantity, required_unit)
    output = StringIO(newline="")
    columns = [
        "product_group", "product", "retailer", "offer_id", "required_quantity",
        "required_unit", "normalized_required_quantity", "package_size", "package_unit",
        "price", "promotion_kind", "promotion_value", "packages", "purchased_quantity",
        "surplus", "quantity_unit", "normalized_purchased_quantity",
        "normalized_surplus", "shelf_unit_price", "shelf_price_unit",
        "effective_unit_price", "effective_price_unit", "subtotal", "discount",
        "discounted_merchandise", "configured_shipping", "shipping", "tax_percent", "tax", "total",
        "free_shipping_threshold", "source_url", "offer_updated_at",
    ]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()

    for option in options:
        offer = option.offer
        normalized_purchased = normalize_quantity(
            option.purchased_quantity, option.quantity_unit
        )
        normalized_surplus = normalize_quantity(option.surplus, option.quantity_unit)
        writer.writerow({
            "product_group": product_group,
            "product": offer.product,
            "retailer": offer.retailer,
            "offer_id": offer.offer_id,
            "required_quantity": str(required_quantity),
            "required_unit": required_unit,
            "normalized_required_quantity": str(normalized_required),
            "package_size": str(offer.package_size),
            "package_unit": offer.unit,
            "price": str(offer.price),
            "promotion_kind": offer.promotion.kind,
            "promotion_value": str(offer.promotion.value),
            "packages": option.packages,
            "purchased_quantity": str(option.purchased_quantity),
            "surplus": str(option.surplus),
            "quantity_unit": option.quantity_unit,
            "normalized_purchased_quantity": str(normalized_purchased),
            "normalized_surplus": str(normalized_surplus),
            "shelf_unit_price": str(option.shelf_unit_price),
        "shelf_price_unit": f"per {option.display_unit}",
            "effective_unit_price": (
                "" if option.effective_unit_price is None
                else str(option.effective_unit_price)
            ),
            "effective_price_unit": f"per {option.display_unit}",
            "subtotal": str(option.subtotal),
            "discount": str(option.discount),
            "discounted_merchandise": str(option.discounted_merchandise),
            "configured_shipping": (
                "" if offer.shipping is None else str(offer.shipping)
            ),
            "shipping": "" if option.shipping is None else str(option.shipping),
            "tax_percent": "" if offer.tax_percent is None else str(offer.tax_percent),
            "tax": "" if option.tax is None else str(option.tax),
            "total": "" if option.total is None else str(option.total),
            "free_shipping_threshold": (
                "" if offer.free_shipping_threshold is None
                else str(offer.free_shipping_threshold)
            ),
            "source_url": offer.source_url or "",
            "offer_updated_at": offer.updated_at or "",
        })

    return output.getvalue()


def sample_offers():
    """Return the three hand-soap offers used in examples and tests."""
    from offers import Promotion, create_offer

    return (
        create_offer(
            "soap-refill", "Liquid hand soap refill", "A", "64", "us fl oz",
            "12.99", offer_id="A", promotion=Promotion("percent", Decimal("10")),
            shipping="5", tax_percent="8",
        ),
        create_offer(
            "soap-refill", "Liquid hand soap refill", "B", "64", "us fl oz",
            "14.49", offer_id="B", shipping="0", tax_percent="8",
        ),
        create_offer(
            "soap-refill", "Liquid hand soap refill", "C", "40", "us fl oz",
            "9.99", offer_id="C", shipping="0", tax_percent="8",
        ),
    )
