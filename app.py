"""ShopCheckout Lite Streamlit dashboard."""

from decimal import Decimal

import streamlit as st

from comparison import compare_and_rank, export_comparison_csv, sample_offers
from offers import Promotion, create_offer, edit_offer
from storage import (
    delete_comparison,
    list_comparisons,
    load_comparison,
    save_comparison,
    update_comparison,
)


st.set_page_config(page_title="ShopCheckout Lite", page_icon="🛍️", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background: #fff; color: #17251e; }
    [data-testid="stHeader"] { background: rgba(255,255,255,.96); }
    .block-container { padding-top: 1.15rem; padding-bottom: .8rem; }
    h1, h2, h3 { color: #173a2a; }
    div.stButton > button[kind="primary"] { background: #16834b; border-color: #16834b; }
    div[data-testid="stMetricValue"] { color: #146c3c; }
    </style>
    """,
    unsafe_allow_html=True,
)


UNIT_LABELS = {
    "us fl oz": "US fl oz", "ml": "mL", "l": "L", "g": "g",
    "kg": "kg", "oz": "oz", "lb": "lb", "item": "items",
}
UNIT_CODES = {label: code for code, label in UNIT_LABELS.items()}
UNIT_OPTIONS = list(UNIT_CODES)
NEW_OFFER = "__new_offer__"
EDITOR_PREFIXES = (
    "retailer_", "product_", "size_", "offer_unit_", "price_",
    "promotion_kind_", "promotion_value_", "shipping_", "threshold_",
    "tax_", "source_",
)


def _set_notice(message, kind="success"):
    st.session_state["notice"] = (kind, message)


def _group_changed():
    group = st.session_state["product_group"].strip()
    if not group:
        _set_notice("Product group cannot be blank.", "error")
        return
    st.session_state["product_group"] = group
    st.session_state["offers"] = [
        edit_offer(offer, product_group=group)
        for offer in st.session_state.get("offers", [])
    ]


def _current_group():
    return st.session_state.get("product_group", "shopping-list")


def _unit_code(label):
    return UNIT_CODES.get(label, label.strip().lower())


def _saved_labels(records):
    labels = {}
    counts = {}
    for record in records:
        name = record["name"]
        counts[name] = counts.get(name, 0) + 1
        suffix = f" · {counts[name]}" if sum(r["name"] == name for r in records) > 1 else ""
        labels[f"{name}{suffix}"] = record["id"]
    return labels


def _selected_saved_id():
    selected_label = st.session_state.get("saved_selection")
    records = list_comparisons()
    return _saved_labels(records).get(selected_label)


def _validate_current_inputs():
    if not isinstance(_current_group(), str) or not _current_group().strip():
        raise ValueError("Product group cannot be blank.")
    offers = st.session_state.get("offers", [])
    if not offers:
        raise ValueError("Add at least one offer before comparing or saving.")
    compare_and_rank(
        offers,
        st.session_state["required_quantity"],
        _unit_code(st.session_state["required_unit"]),
    )
    if any(offer.product_group != _current_group() for offer in offers):
        raise ValueError("All offers must match the selected product group.")


def _restore_samples():
    for key in list(st.session_state):
        if key == "offer_selection" or key.startswith(EDITOR_PREFIXES):
            del st.session_state[key]
    st.session_state["offers"] = list(sample_offers())
    st.session_state["product_group"] = "soap-refill"
    st.session_state["required_quantity"] = 50.0
    st.session_state["required_unit"] = UNIT_LABELS["us fl oz"]
    st.session_state["active_saved_id"] = None
    st.session_state["compare_clicked"] = True
    _set_notice("Sample offers restored.")


def _compare_clicked():
    try:
        _validate_current_inputs()
        st.session_state["compare_clicked"] = True
        _set_notice("Comparison updated.")
    except ValueError as error:
        st.session_state["compare_clicked"] = False
        _set_notice(str(error), "error")


def _offer_form_action(action, selected_id, form_key):
    offers = list(st.session_state.get("offers", []))
    if action == "delete":
        st.session_state["offers"] = [
            offer for offer in offers if offer.offer_id != selected_id
        ]
        _set_notice("Offer removed.")
        return

    try:
        retailer = st.session_state[f"retailer_{form_key}"].strip()
        product = st.session_state[f"product_{form_key}"].strip()
        package_size = st.session_state[f"size_{form_key}"]
        unit = _unit_code(st.session_state[f"offer_unit_{form_key}"])
        price = st.session_state[f"price_{form_key}"].strip()
        promotion_kind = st.session_state[f"promotion_kind_{form_key}"]
        promotion_text = st.session_state[f"promotion_value_{form_key}"].strip() or "0"
        shipping_text = st.session_state[f"shipping_{form_key}"].strip()
        threshold_text = st.session_state[f"threshold_{form_key}"].strip()
        tax_text = st.session_state[f"tax_{form_key}"].strip()
        source_url = st.session_state[f"source_{form_key}"].strip()

        promotion = Promotion("none", 0)
        if promotion_kind != "none":
            promotion = Promotion(promotion_kind, promotion_text)
        changes = {
            "retailer": retailer,
            "product": product,
            "package_size": package_size,
            "unit": unit,
            "price": price,
            "promotion": promotion,
            "shipping": shipping_text or None,
            "free_shipping_threshold": threshold_text or None,
            "tax_percent": tax_text or None,
            "source_url": source_url or None,
        }
        if action == "add":
            offers.append(create_offer(_current_group(), **changes))
            _set_notice("Offer added.")
        else:
            index = next(
                index for index, offer in enumerate(offers)
                if offer.offer_id == selected_id
            )
            offers[index] = edit_offer(offers[index], **changes)
            _set_notice("Offer updated.")
        st.session_state["offers"] = offers
    except (ValueError, TypeError, StopIteration) as error:
        _set_notice(str(error), "error")


def _save_current():
    try:
        _validate_current_inputs()
        name = st.session_state.get("comparison_name", "").strip()
        if not name:
            raise ValueError("Enter a comparison name before saving.")
        comparison_id = save_comparison(
            name, _current_group(), st.session_state["required_quantity"],
            _unit_code(st.session_state["required_unit"]), st.session_state["offers"],
        )
        st.session_state["active_saved_id"] = comparison_id
        records = list_comparisons()
        label = next(
            label for label, saved_id in _saved_labels(records).items()
            if saved_id == comparison_id
        )
        st.session_state["saved_selection"] = label
        _set_notice("Comparison saved and activated.")
    except (ValueError, KeyError) as error:
        _set_notice(str(error), "error")


def _load_selected():
    comparison_id = _selected_saved_id()
    if comparison_id is None:
        _set_notice("Choose a saved comparison to load.", "error")
        return
    saved = load_comparison(comparison_id)
    for key in list(st.session_state):
        if key == "offer_selection" or key.startswith(EDITOR_PREFIXES):
            del st.session_state[key]
    st.session_state["offers"] = saved["offers"]
    st.session_state["product_group"] = saved["product_group"]
    st.session_state["required_quantity"] = float(saved["required_quantity"])
    st.session_state["required_unit"] = UNIT_LABELS.get(
        saved["required_unit"], saved["required_unit"]
    )
    st.session_state["comparison_name"] = saved["name"]
    st.session_state["active_saved_id"] = saved["id"]
    st.session_state["compare_clicked"] = True
    _set_notice("Saved comparison loaded and activated.")


def _update_active():
    comparison_id = st.session_state.get("active_saved_id")
    if comparison_id is None:
        _set_notice("Load or save a comparison before updating it.", "error")
        return
    try:
        _validate_current_inputs()
        update_comparison(
            comparison_id,
            st.session_state.get("comparison_name", "").strip(),
            _current_group(),
            st.session_state["required_quantity"],
            _unit_code(st.session_state["required_unit"]),
            st.session_state["offers"],
        )
        _set_notice("Active saved comparison updated.")
    except (KeyError, ValueError) as error:
        _set_notice(str(error), "error")


def _delete_active():
    comparison_id = st.session_state.get("active_saved_id")
    if comparison_id is None:
        _set_notice("Load or save a comparison before deleting it.", "error")
        return
    try:
        delete_comparison(comparison_id)
        st.session_state["active_saved_id"] = None
        st.session_state.pop("saved_selection", None)
        _set_notice("Active saved comparison deleted.")
    except KeyError as error:
        _set_notice(str(error), "error")


if "offers" not in st.session_state:
    st.session_state["offers"] = list(sample_offers())
if "product_group" not in st.session_state:
    st.session_state["product_group"] = st.session_state["offers"][0].product_group
if "required_quantity" not in st.session_state:
    st.session_state["required_quantity"] = 50.0
if "required_unit" not in st.session_state:
    st.session_state["required_unit"] = UNIT_LABELS["us fl oz"]
if "comparison_name" not in st.session_state:
    st.session_state["comparison_name"] = "Hand soap refill"
if "compare_clicked" not in st.session_state:
    st.session_state["compare_clicked"] = True


st.title("ShopCheckout Lite")
st.caption("Compare package value and checkout totals before you shop.")

notice_slot = st.empty()
notice = st.session_state.pop("notice", None)
if notice:
    kind, message = notice
    if kind == "error":
        notice_slot.error(message)
    else:
        notice_slot.success(message)

with st.sidebar:
    st.header("Saved comparisons")
    st.text_input("Comparison name", key="comparison_name")
    saved_records = list_comparisons()
    saved_labels = _saved_labels(saved_records)
    saved_options = list(saved_labels)
    if saved_options:
        st.selectbox(
            "Saved record to load",
            saved_options,
            key="saved_selection",
        )
    else:
        st.caption("No saved comparisons yet.")

    active_id = st.session_state.get("active_saved_id")
    active_record = next((record for record in saved_records if record["id"] == active_id), None)
    if active_record:
        st.caption(f"Active record: {active_record['name']}")
    else:
        st.caption("No active record. Save new or load a record to activate it.")
    st.button("Save new", on_click=_save_current, use_container_width=True)
    st.button("Load selected", on_click=_load_selected, disabled=not saved_options, use_container_width=True)
    st.button("Update active", on_click=_update_active, disabled=active_id is None, use_container_width=True)
    st.button("Delete active", on_click=_delete_active, disabled=active_id is None, use_container_width=True)


group_col, quantity_col, unit_col, compare_col = st.columns([1.4, 1, 1, 1])
with group_col:
    st.text_input("Product group", key="product_group", on_change=_group_changed)
with quantity_col:
    st.number_input("Required quantity", min_value=0.001, step=1.0, key="required_quantity")
with unit_col:
    st.selectbox(
        "Required unit", UNIT_OPTIONS, key="required_unit",
    )
with compare_col:
    st.write("")
    st.button("Compare Deals", type="primary", on_click=_compare_clicked, use_container_width=True)

offers = st.session_state["offers"]
product_label = offers[0].product if offers else "No offers yet"
st.caption(f"Specification: {product_label}")

st.subheader("Offers")
offer_rows = []
for offer in offers:
    if offer.promotion.kind == "percent":
        promotion_text = f"{offer.promotion.value}% off"
    elif offer.promotion.kind == "fixed":
        promotion_text = f"${offer.promotion.value} off"
    else:
        promotion_text = "None"
    shipping_text = "Unknown" if offer.shipping is None else f"${offer.shipping:.2f}"
    tax_text = "Unknown" if offer.tax_percent is None else f"{offer.tax_percent}%"
    offer_rows.append({
        "Store": offer.retailer,
        "Product / specification": offer.product,
        "Package": f"{offer.package_size} {UNIT_LABELS[offer.unit]}",
        "Price": f"${offer.price:.2f}",
        "Promotion": promotion_text,
        "Shipping / tax": f"{shipping_text} / {tax_text}",
    })
st.dataframe(offer_rows, hide_index=True, use_container_width=True)

options = ()
ranking = {"ranked": (), "winner_ids": (), "incomplete": False}
comparison_error = None
try:
    _validate_current_inputs()
    options, ranking = compare_and_rank(
        st.session_state["offers"],
        st.session_state["required_quantity"],
        _unit_code(st.session_state["required_unit"]),
    )
except ValueError as error:
    comparison_error = str(error)

if comparison_error:
    st.error(f"Review the required quantity and compatible offer units: {comparison_error}")
elif options:
    offer_by_id = {option.offer.offer_id: option.offer for option in options}
    winners = [offer_by_id[offer_id] for offer_id in ranking["winner_ids"]]
    if winners:
        recommendation = ", ".join(offer.retailer for offer in winners)
        if ranking["incomplete"]:
            st.success(f"Lowest known total: {recommendation}")
        else:
            st.success(f"Recommended store: {recommendation}")
        recommended_option = next(
            option for option in options
            if option.offer.offer_id == ranking["winner_ids"][0]
        )
        metric_columns = st.columns(5)
        metric_columns[0].metric("Recommended total", f"${recommended_option.total:.2f}")
        metric_columns[1].metric("Packages", str(recommended_option.packages))
        metric_columns[2].metric(
            f"Purchased ({UNIT_LABELS[recommended_option.quantity_unit]})",
            str(recommended_option.purchased_quantity),
        )
        metric_columns[3].metric(
            f"Surplus ({UNIT_LABELS[recommended_option.quantity_unit]})",
            str(recommended_option.surplus),
        )
        metric_columns[4].metric("Recommended store", recommendation)

    sorted_options = list(ranking["ranked"])
    sorted_options.extend(option for option in options if option.total is None)
    if ranking["incomplete"]:
        st.caption("Offers with unknown shipping or tax are excluded from the known-total ranking.")

    comparison_rows = []
    for option in sorted_options:
        comparison_rows.append({
            "Store": option.offer.retailer,
            "Packages": option.packages,
            f"Purchased ({UNIT_LABELS[option.quantity_unit]})": str(option.purchased_quantity),
            f"Surplus ({UNIT_LABELS[option.quantity_unit]})": str(option.surplus),
            f"Shelf price per {option.display_unit}": f"${option.shelf_unit_price:.4f}",
            f"Effective price per {option.display_unit}": (
                "Unknown" if option.effective_unit_price is None
                else f"${option.effective_unit_price:.4f}"
            ),
            "Total": "Unknown" if option.total is None else f"${option.total:.2f}",
        })
    st.dataframe(comparison_rows, hide_index=True, use_container_width=True)

    st.markdown("**Checkout cost by store**")
    cost_rows = []
    for option in sorted_options:
        cost_rows.append({
            "Store": option.offer.retailer,
            "Subtotal": f"${option.subtotal:.2f}",
            "Discount": f"-${option.discount:.2f}",
            "Shipping": "Unknown" if option.shipping is None else f"${option.shipping:.2f}",
            "Tax": "Unknown" if option.tax is None else f"${option.tax:.2f}",
            "Total": "Unknown" if option.total is None else f"${option.total:.2f}",
        })
    st.dataframe(cost_rows, hide_index=True, use_container_width=True)

    csv_data = export_comparison_csv(
        options,
        st.session_state["required_quantity"],
        _unit_code(st.session_state["required_unit"]),
        _current_group(),
    )
    st.download_button(
        "Download current comparison (CSV)",
        data=csv_data,
        file_name="shopcheckout-comparison.csv",
        mime="text/csv",
    )

with st.expander("Manage offers · add, edit, or remove"):
    offer_by_id = {offer.offer_id: offer for offer in st.session_state["offers"]}
    offer_labels = {"Add a new offer": NEW_OFFER}
    label_counts = {}
    for offer in st.session_state["offers"]:
        base_label = f"{offer.retailer} · {offer.product}"
        label_counts[base_label] = label_counts.get(base_label, 0) + 1
        label = f"{base_label} · {label_counts[base_label]}" if sum(
            item.retailer == offer.retailer and item.product == offer.product
            for item in st.session_state["offers"]
        ) > 1 else base_label
        offer_labels[label] = offer.offer_id
    selected_label = st.selectbox(
        "Offer to manage",
        list(offer_labels),
        key="offer_selection",
    )
    selected_id = offer_labels[selected_label]
    editing = offer_by_id.get(selected_id)
    form_key = selected_id.replace("-", "_")
    if editing:
        defaults = {
            "retailer": editing.retailer,
            "product": editing.product,
            "size": float(editing.package_size),
            "unit": editing.unit,
            "price": str(editing.price),
            "promotion_kind": editing.promotion.kind,
            "promotion_value": str(editing.promotion.value),
            "shipping": "" if editing.shipping is None else str(editing.shipping),
            "threshold": "" if editing.free_shipping_threshold is None else str(editing.free_shipping_threshold),
            "tax": "" if editing.tax_percent is None else str(editing.tax_percent),
            "source": editing.source_url or "",
        }
    else:
        defaults = {
            "retailer": "", "product": product_label, "size": 1.0,
            "unit": UNIT_LABELS.get(st.session_state["required_unit"], st.session_state["required_unit"]), "price": "",
            "promotion_kind": "none", "promotion_value": "0", "shipping": "",
            "threshold": "", "tax": "", "source": "",
        }

    with st.form("offer_editor", clear_on_submit=False):
        retailer_col, product_col = st.columns(2)
        retailer_col.text_input("Retailer", value=defaults["retailer"], key=f"retailer_{form_key}")
        product_col.text_input("Product / specification", value=defaults["product"], key=f"product_{form_key}")
        size_col, unit_col, price_col = st.columns(3)
        size_col.number_input("Package size", min_value=0.001, step=1.0, value=defaults["size"], key=f"size_{form_key}")
        unit_col.selectbox(
            "Package unit", UNIT_OPTIONS,
            index=UNIT_OPTIONS.index(UNIT_LABELS.get(defaults["unit"], defaults["unit"])),
            key=f"offer_unit_{form_key}",
        )
        price_col.text_input("Package price ($)", value=defaults["price"], key=f"price_{form_key}")

        st.markdown("**Promotion, fees, and source**")
        promotion_col, promotion_value_col, source_col = st.columns(3)
        kinds = ["none", "percent", "fixed"]
        promotion_col.selectbox(
            "Promotion", kinds, index=kinds.index(defaults["promotion_kind"]),
            key=f"promotion_kind_{form_key}",
        )
        promotion_value_col.text_input(
            "Promotion value", value=defaults["promotion_value"],
            key=f"promotion_value_{form_key}",
        )
        source_col.text_input("Source URL (optional)", value=defaults["source"], key=f"source_{form_key}")
        shipping_col, threshold_col, tax_col = st.columns(3)
        shipping_col.text_input("Shipping ($; blank = unknown)", value=defaults["shipping"], key=f"shipping_{form_key}")
        threshold_col.text_input("Free shipping at ($; optional)", value=defaults["threshold"], key=f"threshold_{form_key}")
        tax_col.text_input("Tax % (blank = unknown)", value=defaults["tax"], key=f"tax_{form_key}")

        submit_label = "Save edits" if editing is not None else "Add offer"
        st.form_submit_button(
            submit_label,
            on_click=_offer_form_action,
            args=("edit", selected_id, form_key) if editing is not None
            else ("add", None, form_key),
        )

    st.button(
        "Remove offer",
        disabled=editing is None,
        on_click=_offer_form_action,
        args=("delete", selected_id, form_key),
    )

    st.button("Restore sample offers", on_click=_restore_samples)
