"""SQLite persistence for saved shopping comparisons."""

import json
import os
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal

from offers import Offer, Promotion


def _validate_saved_inputs(name, product_group, required_quantity, required_unit, offers):
    if not isinstance(name, str) or not name.strip():
        raise ValueError("comparison name is required")
    if not isinstance(product_group, str) or not product_group.strip():
        raise ValueError("product group is required")
    if not offers:
        raise ValueError("at least one offer is required")
    from comparison import compare_offers

    compare_offers(offers, required_quantity, required_unit)
    if any(offer.product_group != product_group for offer in offers):
        raise ValueError("saved offers must match the comparison product group")


def database_path(path=None):
    """Return an explicit path, environment override, or default database."""
    return path or os.environ.get("SHOPCHECKOUT_DB", "shopcheckout.sqlite3")


def connect(path=None):
    """Connect to the selected database, creating its parent directory."""
    selected_path = database_path(path)
    parent = os.path.dirname(os.path.abspath(selected_path))
    os.makedirs(parent, exist_ok=True)
    connection = sqlite3.connect(selected_path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize(path=None):
    """Create the saved-comparisons table if needed."""
    with connect(path) as database:
        database.execute(
            """
            CREATE TABLE IF NOT EXISTS comparisons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                product_group TEXT NOT NULL,
                required_quantity TEXT NOT NULL,
                required_unit TEXT NOT NULL,
                offers_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def _offer_to_dict(offer):
    return {
        "offer_id": offer.offer_id,
        "product_group": offer.product_group,
        "product": offer.product,
        "retailer": offer.retailer,
        "package_size": str(offer.package_size),
        "unit": offer.unit,
        "price": str(offer.price),
        "promotion_kind": offer.promotion.kind,
        "promotion_value": str(offer.promotion.value),
        "shipping": None if offer.shipping is None else str(offer.shipping),
        "tax_percent": None if offer.tax_percent is None else str(offer.tax_percent),
        "free_shipping_threshold": (
            None if offer.free_shipping_threshold is None
            else str(offer.free_shipping_threshold)
        ),
        "source_url": offer.source_url,
        "updated_at": offer.updated_at,
    }


def _offer_from_dict(data):
    return Offer(
        product_group=data["product_group"],
        product=data["product"],
        retailer=data["retailer"],
        package_size=Decimal(data["package_size"]),
        unit=data["unit"],
        price=Decimal(data["price"]),
        offer_id=data["offer_id"],
        promotion=Promotion(
            data["promotion_kind"], Decimal(data["promotion_value"])
        ),
        source_url=data["source_url"],
        updated_at=data["updated_at"],
        shipping=None if data["shipping"] is None else Decimal(data["shipping"]),
        tax_percent=(
            None if data["tax_percent"] is None else Decimal(data["tax_percent"])
        ),
        free_shipping_threshold=(
            None if data["free_shipping_threshold"] is None
            else Decimal(data["free_shipping_threshold"])
        ),
    )


def save_comparison(name, product_group, required_quantity, required_unit, offers, path=None):
    """Insert a new saved comparison and return its database ID."""
    initialize(path)
    _validate_saved_inputs(name, product_group, required_quantity, required_unit, offers)
    offer_data = [_offer_to_dict(offer) for offer in offers]
    now = datetime.now(timezone.utc).isoformat()
    with connect(path) as database:
        cursor = database.execute(
            """INSERT INTO comparisons
               (name, product_group, required_quantity, required_unit,
                offers_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                name, product_group, str(required_quantity), required_unit,
                json.dumps(offer_data, ensure_ascii=False), now, now,
            ),
        )
        return cursor.lastrowid


def list_comparisons(path=None):
    """List saved comparison IDs and names, newest edited first."""
    initialize(path)
    with connect(path) as database:
        rows = database.execute(
            "SELECT id, name, updated_at FROM comparisons ORDER BY updated_at DESC, id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def load_comparison(comparison_id, path=None):
    """Load and validate a saved comparison, returning offers as dataclasses."""
    initialize(path)
    with connect(path) as database:
        row = database.execute(
            "SELECT * FROM comparisons WHERE id = ?", (comparison_id,)
        ).fetchone()
    if row is None:
        raise KeyError(f"saved comparison {comparison_id} does not exist")
    offers = [_offer_from_dict(data) for data in json.loads(row["offers_json"])]
    _validate_saved_inputs(
        row["name"], row["product_group"], row["required_quantity"],
        row["required_unit"], offers,
    )
    return {
        "id": row["id"],
        "name": row["name"],
        "product_group": row["product_group"],
        "required_quantity": Decimal(row["required_quantity"]),
        "required_unit": row["required_unit"],
        "offers": offers,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def update_comparison(comparison_id, name, product_group, required_quantity,
                      required_unit, offers, path=None):
    """Replace a saved comparison's current inputs."""
    initialize(path)
    _validate_saved_inputs(name, product_group, required_quantity, required_unit, offers)
    offer_data = [_offer_to_dict(offer) for offer in offers]
    now = datetime.now(timezone.utc).isoformat()
    with connect(path) as database:
        cursor = database.execute(
            """UPDATE comparisons
               SET name = ?, product_group = ?, required_quantity = ?,
                   required_unit = ?, offers_json = ?, updated_at = ?
               WHERE id = ?""",
            (
                name, product_group, str(required_quantity), required_unit,
                json.dumps(offer_data, ensure_ascii=False), now, comparison_id,
            ),
        )
        if cursor.rowcount == 0:
            raise KeyError(f"saved comparison {comparison_id} does not exist")


def delete_comparison(comparison_id, path=None):
    """Delete one saved comparison."""
    initialize(path)
    with connect(path) as database:
        cursor = database.execute(
            "DELETE FROM comparisons WHERE id = ?", (comparison_id,)
        )
        if cursor.rowcount == 0:
            raise KeyError(f"saved comparison {comparison_id} does not exist")
