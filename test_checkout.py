from decimal import Decimal

import pytest

from checkout import calculate_checkout


def test_two_notebooks_without_coupon():
    result = calculate_checkout({"Notebook": 2})
    assert result == {
        "subtotal": Decimal("50.00"), "discount": Decimal("0.00"),
        "shipping": Decimal("0.00"), "tax": Decimal("4.00"),
        "total": Decimal("54.00"),
    }
    assert all(type(value) is Decimal for value in result.values())


def test_two_notebooks_with_save10():
    result = calculate_checkout({"Notebook": 2}, "SAVE10")
    assert result == {
        "subtotal": Decimal("50.00"), "discount": Decimal("5.00"),
        "shipping": Decimal("5.00"), "tax": Decimal("3.60"),
        "total": Decimal("53.60"),
    }
    assert all(type(value) is Decimal for value in result.values())


def test_one_wireless_mouse():
    result = calculate_checkout({"Wireless Mouse": 1})
    assert result == {
        "subtotal": Decimal("19.99"), "discount": Decimal("0.00"),
        "shipping": Decimal("5.00"), "tax": Decimal("1.60"),
        "total": Decimal("26.59"),
    }
    assert all(type(value) is Decimal for value in result.values())


def test_empty_cart_raises_value_error():
    with pytest.raises(ValueError, match="at least one item"):
        calculate_checkout({})
