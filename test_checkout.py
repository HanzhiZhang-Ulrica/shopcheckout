from decimal import Decimal

import pytest

from checkout import calculate_checkout


def assert_receipt(result, items, method, amounts):
    assert set(result) == {"items", "shipping_method", *amounts}
    assert result["items"] == items
    assert result["shipping_method"] == method
    for field, expected in amounts.items():
        assert type(result[field]) is Decimal
        assert result[field] == Decimal(expected)
        assert result[field].as_tuple().exponent == -2
    for item in result["items"]:
        assert type(item["quantity"]) is int
        assert item["quantity"] > 0
        assert type(item["unit_price"]) is Decimal
        assert type(item["line_total"]) is Decimal
        assert item["line_total"] == item["unit_price"] * item["quantity"]


def test_standard_without_coupon():
    result = calculate_checkout({"Notebook": 2, "USB Cable": 0})
    assert_receipt(result, [{
        "product": "Notebook", "quantity": 2,
        "unit_price": Decimal("25.00"), "line_total": Decimal("50.00"),
    }], "standard", {
        "subtotal": "50.00", "discount": "0.00", "shipping": "0.00",
        "tax": "4.00", "total": "54.00",
    })


def test_standard_with_save10():
    result = calculate_checkout({"Notebook": 2}, "SAVE10", "standard")
    assert_receipt(result, [{
        "product": "Notebook", "quantity": 2,
        "unit_price": Decimal("25.00"), "line_total": Decimal("50.00"),
    }], "standard", {
        "subtotal": "50.00", "discount": "5.00", "shipping": "5.00",
        "tax": "3.60", "total": "53.60",
    })


def test_express_with_save10():
    result = calculate_checkout({"Notebook": 2}, "SAVE10", "express")
    assert_receipt(result, [{
        "product": "Notebook", "quantity": 2,
        "unit_price": Decimal("25.00"), "line_total": Decimal("50.00"),
    }], "express", {
        "subtotal": "50.00", "discount": "5.00", "shipping": "12.00",
        "tax": "3.60", "total": "60.60",
    })


def test_mixed_cart_rounding():
    result = calculate_checkout({"Notebook": 1, "Wireless Mouse": 1}, "SAVE10", "standard")
    assert_receipt(result, [
        {"product": "Notebook", "quantity": 1,
         "unit_price": Decimal("25.00"), "line_total": Decimal("25.00")},
        {"product": "Wireless Mouse", "quantity": 1,
         "unit_price": Decimal("19.99"), "line_total": Decimal("19.99")},
    ], "standard", {
        "subtotal": "44.99", "discount": "4.50", "shipping": "5.00",
        "tax": "3.24", "total": "48.73",
    })


def test_empty_cart_raises_value_error():
    for cart in ({}, {"Notebook": 0, "USB Cable": 0, "Wireless Mouse": 0}):
        with pytest.raises(ValueError, match="at least one item"):
            calculate_checkout(cart)


def test_negative_quantity_raises_value_error():
    with pytest.raises(ValueError, match="nonnegative integer"):
        calculate_checkout({"Notebook": -1})


def test_invalid_coupon_raises_value_error():
    with pytest.raises(ValueError, match="Unknown coupon"):
        calculate_checkout({"Notebook": 1}, "SAVE20")


def test_invalid_shipping_method_raises_value_error():
    with pytest.raises(ValueError, match="Unknown shipping method"):
        calculate_checkout({"Notebook": 1}, shipping_method="overnight")
