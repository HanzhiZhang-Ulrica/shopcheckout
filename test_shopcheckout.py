from decimal import Decimal
import csv
from io import StringIO
import pytest
from offers import Offer, Promotion, create_offer, edit_offer
from comparison import compare_offers, compare_and_rank, export_comparison_csv, normalize_quantity, rank_purchases, sample_offers

def test_all_sample_scenarios():
    expected = [("17.63", "15.65", "10.79"), ("17.63", "15.65", "21.58"), ("30.25", "31.30", "32.37")]
    for need, totals, winner in zip((30, 50, 100), expected, ("C", "B", "A")):
        options, ranking = compare_and_rank(sample_offers(), need, "us fl oz")
        assert tuple(str(x.total) for x in options) == totals
        assert ranking["winner_ids"] == (winner,)
    options = compare_offers(sample_offers(), 100, "US FL OZ")
    assert [x.packages for x in options] == [2, 2, 3]
    assert [x.purchased_quantity for x in options] == [Decimal("128"), Decimal("128"), Decimal("120")]
    assert [x.surplus for x in options] == [Decimal("28"), Decimal("28"), Decimal("20")]
    assert options[0].discount == Decimal("2.60") and options[0].tax == Decimal("1.87")
    assert options[1].tax == Decimal("2.32") and options[2].tax == Decimal("2.40")

def test_unit_equivalence_and_exact_fl_oz():
    assert normalize_quantity(1, "l") == normalize_quantity(1000, "ml")
    assert normalize_quantity(1, "lb") == normalize_quantity(16, "oz")
    assert normalize_quantity(1, "us fl oz") == Decimal("29.5735295625")
    offers = [offer("x", "A", 1, "l", 2), offer("x", "B", 1000, "ml", 2)]
    assert [o.packages for o in compare_offers(offers, 1, "l")] == [1, 1]

def offer(group="x", retailer="R", size=1, unit="item", price=1, **kwargs):
    size = kwargs.pop("package_size", size)
    unit = kwargs.pop("unit", unit)
    price = kwargs.pop("price", price)
    return create_offer(group, "Thing", retailer, size, unit, price, offer_id=retailer, **kwargs)

def test_exact_package_boundary_and_just_over():
    o = offer(size=10, unit="g")
    assert compare_offers([o], "20", "g")[0].packages == 2
    assert compare_offers([o], "20.0001", "g")[0].packages == 3

def test_discount_rounding_shipping_threshold_and_tax_excludes_shipping():
    a = offer(price="44.99", promotion=Promotion("percent", 10), shipping=0, tax_percent=0)
    assert compare_offers([a], 1, "item")[0].discount == Decimal("4.50")
    b = offer(price="50", promotion=Promotion("percent", 10), shipping=5, tax_percent=8, free_shipping_threshold=50)
    result = compare_offers([b], 1, "item")[0]
    assert (result.discounted_merchandise, result.shipping, result.tax, result.total) == (Decimal("45.00"), Decimal("5"), Decimal("3.60"), Decimal("53.60"))
    c = offer(size=1, unit="item", price=10, shipping=5, tax_percent=0)
    assert compare_offers([c], 2, "item")[0].total == Decimal("25.00")

def test_fixed_discount_once_and_cap():
    o = offer(size=1, price=10, promotion=Promotion("fixed", 3), shipping=0, tax_percent=0)
    r = compare_offers([o], 2, "item")[0]
    assert r.discount == 3 and r.total == 17
    capped = compare_offers([offer(price=2, promotion=Promotion("fixed", 5), shipping=0, tax_percent=0)], 1, "item")[0]
    assert capped.discount == 2 and capped.total == 0

def test_unknown_zero_and_threshold_shipping():
    unknown = offer(price=2)
    zero = offer(retailer="Z", price=2, shipping=0, tax_percent=0)
    threshold = offer(retailer="T", price=10, free_shipping_threshold=10, tax_percent=0)
    opts = compare_offers([unknown, zero, threshold], 1, "item")
    assert opts[0].total is None and opts[0].effective_unit_price is None
    assert opts[1].total == 2
    assert opts[2].shipping == 0 and opts[2].total == 10
    rank = rank_purchases(opts)
    assert rank["winner_ids"] == ("Z",) and rank["incomplete"]

def test_ties_and_incomplete_winner_flag():
    opts = compare_offers([offer(retailer="A", price=1, shipping=0, tax_percent=0), offer(retailer="B", price=1, shipping=0, tax_percent=0), offer(retailer="C", price=1)], 1, "item")
    result = rank_purchases(opts)
    assert result["winner_ids"] == ("A", "B") and result["incomplete"]

def test_edits_recompute_and_keep_stable_id():
    original = offer(size=1, price=2, shipping=0, tax_percent=0)
    changed = edit_offer(original, price="5", package_size="2")
    assert changed.offer_id == original.offer_id
    assert compare_offers([original], 2, "item")[0].total == 4
    assert compare_offers([changed], 2, "item")[0].total == 5
    with pytest.raises(ValueError): edit_offer(original, offer_id="new")

@pytest.mark.parametrize("kwargs", [
    {"package_size": 0}, {"price": -1}, {"price": True}, {"price": "NaN"},
    {"shipping": -1}, {"tax_percent": 101}, {"free_shipping_threshold": -1},
    {"unit": "gallon"}, {"retailer": " "}, {"price": "0.005"},
    {"shipping": "0.005"}, {"free_shipping_threshold": "1.005"},
    {"source_url": 4}, {"updated_at": 4},
])
def test_reject_invalid_offer_values(kwargs):
    with pytest.raises(ValueError): offer(**kwargs)

def test_mixed_groups_dimensions_and_bad_required_quantity():
    with pytest.raises(ValueError): compare_offers([offer(), offer(group="other", retailer="B")], 1, "item")
    with pytest.raises(ValueError): compare_offers([offer(unit="item"), offer(retailer="B", unit="g")], 1, "item")
    for value in (0, -1, True, "Infinity"):
        with pytest.raises(ValueError): compare_offers([offer()], value, "item")
    with pytest.raises(ValueError): Promotion("percent", 101)


def test_explicit_required_unit_is_independent_of_offer_order():
    liter = offer(retailer="L", size=1, unit="L", price=2)
    half_liter = offer(retailer="H", size=500, unit="mL", price=1)
    expected = {"L": 1, "H": 2}
    for offers in ((liter, half_liter), (half_liter, liter)):
        options = compare_offers(offers, 750, " mL ")
        assert {option.offer.retailer: option.packages for option in options} == expected


def test_count_quantities_must_be_whole_numbers():
    with pytest.raises(ValueError):
        offer(size="1.5")
    with pytest.raises(ValueError):
        compare_offers([offer()], "1.2", "item")


def test_empty_offer_requests_still_validate_quantity_and_unit():
    assert compare_offers([], "750", "ML") == ()
    for quantity, unit in ((0, "ml"), (1, "gallon"), (True, "ml")):
        with pytest.raises(ValueError):
            compare_offers([], quantity, unit)


def test_fixed_discount_is_capped_at_subtotal_in_whole_cents():
    value = offer(price="0.01", promotion=Promotion("fixed", "1.00"), shipping=0, tax_percent=0)
    result = compare_offers([value], 1, "item")[0]
    assert result.discount == Decimal("0.01")
    assert result.discounted_merchandise == Decimal("0.00")
    assert result.total == Decimal("0.00")


def test_edit_refreshes_timestamp_and_preserves_id():
    original = offer(updated_at="2020-01-01T00:00:00+00:00")
    edited = edit_offer(original, price="2.00")
    assert edited.offer_id == original.offer_id
    assert edited.updated_at != original.updated_at


def test_rank_generator_matches_tuple_for_incomplete_flag():
    options = compare_offers(
        [offer(retailer="Known", shipping=0, tax_percent=0), offer(retailer="Unknown")],
        1,
        "item",
    )
    tuple_result = rank_purchases(options)
    iterator_result = rank_purchases(iter(options))
    assert iterator_result == tuple_result
    assert iterator_result["incomplete"] is True


def test_unit_price_denominators_use_package_and_actual_purchased_quantity():
    options = compare_offers(sample_offers(), 100, "us fl oz")
    offer_a = options[0]
    package_liters = normalize_quantity(64, "us fl oz") / Decimal("1000")
    purchased_liters = normalize_quantity(128, "us fl oz") / Decimal("1000")
    required_liters = normalize_quantity(100, "us fl oz") / Decimal("1000")
    assert offer_a.shelf_unit_price == Decimal("12.99") / package_liters
    assert offer_a.effective_unit_price == offer_a.total / purchased_liters
    assert offer_a.effective_unit_price != offer_a.total / required_liters


def test_one_kg_equals_one_thousand_grams_and_mixed_results_use_required_unit():
    assert normalize_quantity(1, "kg") == normalize_quantity(1000, "g")
    one_liter = offer(retailer="Liter", size=1, unit="l", price=2)
    half_liter = offer(retailer="Half", size=500, unit="ml", price=1)
    options = compare_offers([one_liter, half_liter], 750, "ml")
    assert [(item.purchased_quantity, item.surplus, item.quantity_unit) for item in options] == [
        (Decimal("1000"), Decimal("250"), "ml"),
        (Decimal("1000"), Decimal("250"), "ml"),
    ]


def test_unknown_tax_with_known_shipping_has_unknown_total():
    option = compare_offers([offer(price=5, shipping=3, tax_percent=None)], 1, "item")[0]
    assert option.shipping == Decimal("3")
    assert option.tax is None
    assert option.total is None


def test_csv_parity_unicode_commas_and_configured_shipping():
    special = offer(
        group="coffee, café",
        retailer="Market, 東京",
        price="50.00",
        shipping="5.00",
        free_shipping_threshold="40.00",
        tax_percent="8",
        source_url="https://example.test/item?a=one,two",
    )
    unknown_shipping = offer(
        group="coffee, café",
        retailer="Threshold store",
        price="50.00",
        shipping=None,
        free_shipping_threshold="40.00",
        tax_percent="8",
    )
    options = compare_offers([special, unknown_shipping], 1, "item")
    rows = list(csv.DictReader(StringIO(export_comparison_csv(options, 1, "item", "coffee, café"))))
    assert rows[0]["product_group"] == "coffee, café"
    assert rows[0]["retailer"] == "Market, 東京"
    assert rows[0]["source_url"] == "https://example.test/item?a=one,two"
    assert rows[0]["configured_shipping"] == "5.00"
    assert rows[0]["shipping"] == "0.00"
    assert rows[0]["free_shipping_threshold"] == "40.00"
    assert rows[1]["configured_shipping"] == ""
    assert rows[1]["shipping"] == "0.00"
    assert rows[0]["packages"] == "1"
    assert Decimal(rows[0]["total"]) == options[0].total
    assert Decimal(rows[0]["purchased_quantity"]) == options[0].purchased_quantity
    assert rows[0]["normalized_purchased_quantity"] == "1"


def test_sqlite_save_load_update_delete_and_environment_path(tmp_path, monkeypatch):
    from storage import delete_comparison, list_comparisons, load_comparison, save_comparison, update_comparison

    database_file = tmp_path / "isolated" / "shopping.sqlite3"
    monkeypatch.setenv("SHOPCHECKOUT_DB", str(database_file))
    offers = [offer(retailer="Zero", shipping=0, tax_percent=0, source_url="https://example.test/zero")]
    record_id = save_comparison("Coffee list", "x", "2", "item", offers)
    loaded = load_comparison(record_id)
    assert loaded["required_quantity"] == Decimal("2")
    assert loaded["required_unit"] == "item"
    assert loaded["offers"][0].shipping == Decimal("0")
    assert loaded["offers"][0].free_shipping_threshold is None
    assert loaded["offers"][0].source_url == "https://example.test/zero"

    update_comparison(record_id, "Updated", "x", "3", "item", offers)
    assert load_comparison(record_id)["name"] == "Updated"
    assert load_comparison(record_id)["required_quantity"] == Decimal("3")
    assert list_comparisons()[0]["id"] == record_id
    delete_comparison(record_id)
    assert list_comparisons() == []
    with pytest.raises(KeyError):
        load_comparison(record_id)


def test_storage_rejects_empty_or_invalid_comparisons(tmp_path):
    from storage import save_comparison, update_comparison

    path = tmp_path / "saved.sqlite3"
    with pytest.raises(ValueError):
        save_comparison("Empty", "x", 1, "item", [], path)
    offer_id = save_comparison("Valid", "x", 1, "item", [offer()], path)
    with pytest.raises(ValueError):
        update_comparison(offer_id, "Invalid", "x", 1, "g", [offer()], path)
    with pytest.raises(ValueError):
        update_comparison(offer_id, "Empty", "x", 1, "item", [], path)


def test_streamlit_app_compare_crud_reset_and_saved_record_workflow(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("SHOPCHECKOUT_DB", str(tmp_path / "app.sqlite3"))
    app = AppTest.from_file("app.py")
    app.run(timeout=20)
    assert not app.exception
    assert "Recommended store: B" in [item.value for item in app.success]
    assert "$15.65" in [item.value for item in app.metric]

    app.number_input(key="required_quantity").set_value(30).run(timeout=20)
    assert "Recommended store: C" in [item.value for item in app.success]
    assert "$10.79" in [item.value for item in app.metric]
    app.number_input(key="required_quantity").set_value(100).run(timeout=20)
    assert "Recommended store: A" in [item.value for item in app.success]
    assert "$30.25" in [item.value for item in app.metric]

    app.selectbox(key="offer_selection").set_value("A · Liquid hand soap refill").run(timeout=20)
    app.text_input(key="price_A").set_value("99.00").run(timeout=20)
    next(button for button in app.button if button.label == "Save edits").click().run(timeout=20)
    next(button for button in app.button if button.label == "Compare Deals").click().run(timeout=20)
    assert "Recommended store: B" in [item.value for item in app.success]
    next(button for button in app.button if button.label == "Restore sample offers").click().run(timeout=20)
    assert app.session_state["offers"][0].price == Decimal("12.99")
    app.selectbox(key="offer_selection").set_value("A · Liquid hand soap refill").run(timeout=20)
    assert app.text_input(key="price_A").value == "12.99"

    app.text_input(key="product_group").set_value("coffee, café").run(timeout=20)
    assert all(item.product_group == "coffee, café" for item in app.session_state["offers"])
    app.text_input(key="comparison_name").set_value("Coffee, morning").run(timeout=20)
    next(button for button in app.button if button.label == "Save new").click().run(timeout=20)
    record_id = app.session_state["active_saved_id"]
    saved = __import__("storage").load_comparison(record_id)
    assert saved["product_group"] == "coffee, café"
    assert saved["name"] == "Coffee, morning"

    app.number_input(key="required_quantity").set_value(30).run(timeout=20)
    next(button for button in app.button if button.label == "Update active").click().run(timeout=20)
    assert __import__("storage").load_comparison(record_id)["required_quantity"] == Decimal("30.0")
    app.number_input(key="required_quantity").set_value(100).run(timeout=20)
    app.selectbox(key="saved_selection").set_value("Coffee, morning").run(timeout=20)
    next(button for button in app.button if button.label == "Load selected").click().run(timeout=20)
    assert app.number_input(key="required_quantity").value == 30.0
    next(button for button in app.button if button.label == "Delete active").click().run(timeout=20)
    assert __import__("storage").list_comparisons() == []


def test_streamlit_save_rejects_invalid_unit_and_empty_offers(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    import storage

    monkeypatch.setenv("SHOPCHECKOUT_DB", str(tmp_path / "invalid.sqlite3"))
    app = AppTest.from_file("app.py").run(timeout=20)
    app.selectbox(key="required_unit").set_value("g").run(timeout=20)
    next(button for button in app.button if button.label == "Save new").click().run(timeout=20)
    assert storage.list_comparisons() == []
    assert any("compatible" in item.value.lower() for item in app.error)


def test_streamlit_trims_group_and_suppresses_invalid_comparison_and_csv(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("SHOPCHECKOUT_DB", str(tmp_path / "group.sqlite3"))
    app = AppTest.from_file("app.py").run(timeout=20)
    app.text_input(key="product_group").set_value(" soap-refill ").run(timeout=20)
    assert app.session_state["product_group"] == "soap-refill"
    assert all(offer.product_group == "soap-refill" for offer in app.session_state["offers"])

    app.text_input(key="product_group").set_value("   ").run(timeout=20)
    assert not any("Recommended store" in item.value for item in app.success)
    assert not any("Lowest known total" in item.value for item in app.success)
    assert not app.get("download_button")


def test_streamlit_can_add_and_remove_an_offer(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("SHOPCHECKOUT_DB", str(tmp_path / "crud.sqlite3"))
    app = AppTest.from_file("app.py").run(timeout=20)
    app.text_input(key="retailer___new_offer__").set_value("Local Market")
    app.text_input(key="product___new_offer__").set_value("Hand soap, unscented")
    app.text_input(key="price___new_offer__").set_value("7.25")
    next(button for button in app.button if button.label == "Add offer").click().run(timeout=20)
    assert len(app.session_state["offers"]) == 4
    added = app.session_state["offers"][-1]
    assert added.retailer == "Local Market"
    assert added.product == "Hand soap, unscented"

    app.selectbox(key="offer_selection").set_value("Local Market · Hand soap, unscented").run(timeout=20)
    next(button for button in app.button if button.label == "Remove offer").click().run(timeout=20)
    assert len(app.session_state["offers"]) == 3


def test_streamlit_single_enabled_offer_submit_edits_loaded_offer(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("SHOPCHECKOUT_DB", str(tmp_path / "single_submit.sqlite3"))
    app = AppTest.from_file("app.py").run(timeout=20)
    submit_labels = [
        button.label for button in app.button
        if button.label in ("Add offer", "Save edits")
    ]
    assert submit_labels == ["Add offer"]

    app.selectbox(key="offer_selection").set_value("B · Liquid hand soap refill").run(timeout=20)
    app.text_input(key="price_B").set_value("15.49").run(timeout=20)
    submit_labels = [
        button.label for button in app.button
        if button.label in ("Add offer", "Save edits")
    ]
    assert submit_labels == ["Save edits"]
    next(button for button in app.button if button.label == "Save edits").click().run(timeout=20)

    assert app.session_state["offers"][1].price == Decimal("15.49")
    assert "Recommended store: B" in [item.value for item in app.success]
    assert "$16.73" in [item.value for item in app.metric]
