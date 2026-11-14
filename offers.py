"""Validated offer and promotion value objects."""

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional
from uuid import uuid4


CENT = Decimal("0.01")


def decimal_value(value, name="value"):
    """Parse a finite number through its string representation."""
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{name} must be a finite number") from None
    if not result.is_finite():
        raise ValueError(f"{name} must be a finite number")
    return result


def _money_value(value, name):
    result = decimal_value(value, name)
    if result != result.quantize(CENT):
        raise ValueError(f"{name} must use whole cents")
    return result


def _timestamp_now():
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Promotion:
    kind: str = "none"
    value: Decimal = Decimal("0")

    def __post_init__(self):
        kind = self.kind.lower() if isinstance(self.kind, str) else self.kind
        if kind not in ("none", "percent", "fixed"):
            raise ValueError("promotion kind must be none, percent, or fixed")
        value = decimal_value(self.value, "promotion value")
        if kind == "percent" and not Decimal("0") <= value <= Decimal("100"):
            raise ValueError("percent promotion must be between 0 and 100")
        if kind == "fixed":
            value = _money_value(value, "fixed promotion")
            if value < 0:
                raise ValueError("fixed promotion cannot be negative")
        if kind == "none" and value != 0:
            raise ValueError("none promotion must have value zero")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "value", value)


@dataclass(frozen=True)
class Offer:
    product_group: str
    product: str
    retailer: str
    package_size: Decimal
    unit: str
    price: Decimal
    offer_id: str
    promotion: Promotion = Promotion()
    source_url: Optional[str] = None
    updated_at: Optional[str] = None
    shipping: Optional[Decimal] = None
    tax_percent: Optional[Decimal] = None
    free_shipping_threshold: Optional[Decimal] = None

    def __post_init__(self):
        for field in ("product_group", "product", "retailer", "offer_id"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} is required")
            object.__setattr__(self, field, value.strip())

        unit = self.unit.strip().lower() if isinstance(self.unit, str) else self.unit
        if unit not in {"ml", "l", "us fl oz", "g", "kg", "oz", "lb", "item"}:
            raise ValueError("unsupported unit")
        object.__setattr__(self, "unit", unit)

        package_size = decimal_value(self.package_size, "package_size")
        if package_size <= 0:
            raise ValueError("package_size must be positive")
        if unit == "item" and package_size != package_size.to_integral_value():
            raise ValueError("item package size must be a whole count")
        object.__setattr__(self, "package_size", package_size)

        price = _money_value(self.price, "price")
        if price < 0:
            raise ValueError("price must be nonnegative")
        object.__setattr__(self, "price", price)

        if not isinstance(self.promotion, Promotion):
            raise ValueError("promotion must be a Promotion")

        for field in ("shipping", "free_shipping_threshold"):
            value = getattr(self, field)
            if value is not None:
                value = _money_value(value, field)
                if value < 0:
                    raise ValueError(f"{field} must be nonnegative")
                object.__setattr__(self, field, value)

        if self.tax_percent is not None:
            tax_percent = decimal_value(self.tax_percent, "tax_percent")
            if not Decimal("0") <= tax_percent <= Decimal("100"):
                raise ValueError("tax_percent must be between 0 and 100")
            object.__setattr__(self, "tax_percent", tax_percent)

        if self.source_url is not None:
            if not isinstance(self.source_url, str) or not self.source_url.strip():
                raise ValueError("source_url must be a nonblank string")
            object.__setattr__(self, "source_url", self.source_url.strip())

        if self.updated_at is not None:
            if not isinstance(self.updated_at, str) or not self.updated_at.strip():
                raise ValueError("updated_at must be a nonblank string")
            object.__setattr__(self, "updated_at", self.updated_at.strip())


def create_offer(
    product_group,
    product,
    retailer,
    package_size,
    unit,
    price,
    *,
    offer_id=None,
    promotion=None,
    source_url=None,
    updated_at=None,
    shipping=None,
    tax_percent=None,
    free_shipping_threshold=None,
):
    """Create an offer, generating its stable ID and timestamp when absent."""
    return Offer(
        product_group=product_group,
        product=product,
        retailer=retailer,
        package_size=package_size,
        unit=unit,
        price=price,
        offer_id=offer_id or str(uuid4()),
        promotion=promotion or Promotion(),
        source_url=source_url,
        updated_at=updated_at or _timestamp_now(),
        shipping=shipping,
        tax_percent=tax_percent,
        free_shipping_threshold=free_shipping_threshold,
    )


def edit_offer(offer, **changes):
    """Return a validated edit, keeping the ID and refreshing its timestamp."""
    if "offer_id" in changes and changes["offer_id"] != offer.offer_id:
        raise ValueError("offer_id is stable and cannot be edited")
    changes["offer_id"] = offer.offer_id
    changes["updated_at"] = _timestamp_now()
    return replace(offer, **changes)
