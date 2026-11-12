"""Streamlit shopping cart and checkout interface."""

import streamlit as st

from catalog import PRODUCTS
from checkout import calculate_checkout


def format_receipt(receipt, coupon):
    """Format the submitted checkout as a downloadable text receipt."""
    method = receipt["shipping_method"].title()
    lines = ["ShopCheckout Lite", f"Order summary - {method} shipping", ""]
    for item in receipt["items"]:
        lines.append(
            f"{item['product']} x {item['quantity']} @ ${item['unit_price']:.2f}"
            f" = ${item['line_total']:.2f}"
        )
    lines.extend([
        "",
        f"Subtotal: ${receipt['subtotal']:.2f}",
        f"Coupon: {coupon or 'None'}",
        f"Discount: -${receipt['discount']:.2f}",
        f"{method} shipping: ${receipt['shipping']:.2f}",
        f"Tax (8%): ${receipt['tax']:.2f}",
        f"Total: ${receipt['total']:.2f}",
    ])
    return "\n".join(lines) + "\n"


st.set_page_config(page_title="ShopCheckout Lite", page_icon="🛍️", layout="centered")
st.title("ShopCheckout Lite")
st.write("Choose your products, add a coupon, and select your delivery method.")

with st.form("checkout_form", border=True):
    st.subheader("Your cart")
    cart = {}
    for column, (product, price) in zip(st.columns(3), PRODUCTS.items()):
        with column:
            cart[product] = st.number_input(
                f"{product} — ${price:.2f}", min_value=0, step=1, value=0,
                key=f"quantity_{product}",
            )
    coupon_column, shipping_column = st.columns(2)
    with coupon_column:
        coupon = st.text_input("Coupon code (optional)", placeholder="SAVE10", key="coupon")
    with shipping_column:
        shipping_method = st.selectbox(
            "Shipping method", ("Standard", "Express"), key="shipping_method",
        ).lower()
    st.caption(r"Standard: free from \$50 after discount, otherwise \$5. Express: \$12.")
    calculate = st.form_submit_button("Calculate checkout", type="primary", use_container_width=True)

if calculate:
    try:
        receipt = calculate_checkout(cart, coupon, shipping_method)
    except ValueError as error:
        st.session_state.pop("last_receipt", None)
        st.session_state.pop("receipt_coupon", None)
        st.session_state.pop("receipt_text", None)
        st.error(str(error))
    else:
        st.session_state["last_receipt"] = receipt
        st.session_state["receipt_coupon"] = coupon
        st.session_state["receipt_text"] = format_receipt(receipt, coupon)

if "last_receipt" in st.session_state:
    receipt = st.session_state["last_receipt"]
    receipt_coupon = st.session_state["receipt_coupon"]
    method = receipt["shipping_method"].title()
    st.subheader("Order summary")
    st.caption(f"{method} shipping · Coupon: {receipt_coupon or 'None'}")
    st.dataframe(
        [{
            "Product": item["product"],
            "Qty": item["quantity"],
            "Unit price": f"${item['unit_price']:.2f}",
            "Line total": f"${item['line_total']:.2f}",
        } for item in receipt["items"]],
        hide_index=True, use_container_width=True,
        height=35 * (len(receipt["items"]) + 1) + 3,
    )
    labels, amounts = st.columns([3, 1])
    for label, value, prefix in (
        ("Subtotal", receipt["subtotal"], ""),
        (f"Discount ({receipt_coupon})" if receipt_coupon else "Discount", receipt["discount"], "-"),
        (f"{method} shipping", receipt["shipping"], ""),
        ("Tax (8%)", receipt["tax"], ""),
    ):
        labels.write(label)
        amounts.write(f"{prefix}${value:.2f}")
    st.metric("Total", f"${receipt['total']:.2f}")
    st.download_button(
        "Download receipt (.txt)", data=st.session_state["receipt_text"],
        file_name="shopcheckout-receipt.txt", mime="text/plain", key="download_receipt",
    )
