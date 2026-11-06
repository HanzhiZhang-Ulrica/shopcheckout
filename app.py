"""Streamlit interface for ShopCheckout Lite."""

import streamlit as st

from checkout import PRODUCTS, calculate_checkout

st.set_page_config(page_title="ShopCheckout Lite", page_icon="🛍️", layout="centered")
st.title("ShopCheckout Lite")
st.write("Build a small cart, add an optional coupon, and see a clear checkout receipt.")

with st.form("checkout_form", border=True):
    st.subheader("Your items")
    cart = {
        product: st.number_input(
            f"{product} — ${price:.2f}", min_value=0, step=1, value=0,
            key=f"quantity_{product}",
        )
        for product, price in PRODUCTS.items()
    }
    coupon = st.text_input("Coupon code (optional)", placeholder="SAVE10")
    calculate = st.form_submit_button("Calculate checkout", type="primary", use_container_width=True)

if calculate:
    try:
        receipt = calculate_checkout(cart, coupon.strip())
    except ValueError as error:
        st.error(str(error))
    else:
        st.subheader("Checkout receipt")
        st.write(f"**Subtotal** · ${receipt['subtotal']:.2f}")
        st.write(f"**Discount** · -${receipt['discount']:.2f}")
        st.write(f"**Shipping** · ${receipt['shipping']:.2f}")
        st.write(f"**Tax** · ${receipt['tax']:.2f}")
        st.divider()
        st.markdown(f"### Total · ${receipt['total']:.2f}")
