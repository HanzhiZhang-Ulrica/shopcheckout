from decimal import Decimal
from html import escape

import streamlit as st

from shopping import ProductInputError, search_prices


st.set_page_config(page_title="ShopCheckout Lite", page_icon="🛍️", layout="wide")
st.markdown(
    """
    <style>
        .block-container {max-width: 1100px; padding-top: 3rem; padding-bottom: 2rem;}
        h1 {letter-spacing: -0.04em;}
        div[data-testid="stForm"] {padding: 1.25rem; border-radius: 14px;}
        div[data-testid="stMetric"] {
            padding: 1rem 1.25rem;
            border: 1px solid #cfe6da;
            border-radius: 12px;
            background: #f0faf4;
            color: #173e2a;
        }
        .offers {width: 100%; border-collapse: collapse; font-size: 0.95rem;}
        .offers th {text-align: left; background: #f7f9fa; color: #52606a;}
        .offers th, .offers td {padding: 0.85rem; border-bottom: 1px solid #e7ebee;}
        .offers .lowest {background: #edf8f1; color: #173e2a; font-weight: 600;}
        .offers td:nth-child(3), .offers td:nth-child(4) {white-space: nowrap;}
        .offers a {color: #176644; text-decoration: none;}
        .offers-wrap {overflow-x: auto;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.session_state.setdefault("product_query", "")
st.session_state.setdefault("search_result", None)

st.title("ShopCheckout Lite")
st.caption("Find products, compare store prices, and open the best offer.")

with st.form("product_search"):
    st.markdown("**Product name or product link**")
    input_column, button_column = st.columns([6, 1])
    with input_column:
        st.text_input(
            "Product name or product link",
            key="product_query",
            label_visibility="collapsed",
            placeholder="Enter a product name or paste a product link",
        )
    with button_column:
        submitted = st.form_submit_button("Search", type="primary", use_container_width=True)
    filter_columns = st.columns(2)
    with filter_columns[0]:
        hide_sold_out = st.checkbox("Hide sold-out items", value=True)
    with filter_columns[1]:
        us_only = st.checkbox("US stores only", value=True)

if submitted:
    query = st.session_state.product_query.strip()
    if not query:
        st.info("Enter a product name or product link.")
    else:
        st.session_state.search_result = None
        try:
            with st.spinner("Finding prices…"):
                st.session_state.search_result = search_prices(query, hide_sold_out=hide_sold_out, us_only=us_only)
                st.session_state.result_us_only = us_only
        except ProductInputError as error:
            st.error(str(error))
        except Exception:
            st.error("Search failed. Please try again.")

result = st.session_state.search_result
if result is not None:
    st.subheader(result.query)
    offers = list(result.offers)
    if not offers:
        st.info("No offers found.")
    else:
        lowest_by_currency: dict[str, Decimal] = {}
        for offer in offers:
            if offer.available is not False and offer.price is not None:
                currency = offer.currency.strip().upper()
                lowest_by_currency[currency] = min(
                    lowest_by_currency.get(currency, offer.price), offer.price
                )

        for currency, lowest in sorted(lowest_by_currency.items()):
            stores = sorted(
                {
                    offer.store
                    for offer in offers
                    if offer.available is not False
                    and offer.currency.strip().upper() == currency
                    and offer.price == lowest
                }
            )
            st.metric(
                label=f"Lowest listed price · {', '.join(stores)}",
                value=f"{currency} {lowest:,.2f}",
            )

        sorted_offers = sorted(
            offers,
            key=lambda offer: (
                offer.price is None,
                offer.available is False,
                offer.currency.strip().upper(),
                offer.price if offer.price is not None else Decimal(0),
                offer.store.casefold(),
            ),
        )
        rows = []
        for offer in sorted_offers:
            currency = offer.currency.strip().upper()
            is_lowest = False
            if offer.price is None:
                price = "Price unavailable"
            else:
                price = f"{currency} {offer.price:,.2f}"
                if offer.available is not False and offer.price == lowest_by_currency.get(currency):
                    price += " · Lowest"
                    is_lowest = True
            if offer.available is False:
                price += " · Sold out"
            elif offer.available is None:
                price += " · Stock unknown"
            row_class = ' class="lowest"' if is_lowest else ""
            rows.append(f'<tr{row_class}><td>{escape(offer.title)}</td>'
                        f'<td>{escape(offer.store)}</td><td>{escape(price)}</td>'
                        f'<td><a href="{escape(offer.url, quote=True)}" target="_blank" '
                        'rel="noopener noreferrer">View offer ↗</a></td></tr>')
        store_count = len({offer.store.casefold() for offer in offers})
        region = "US " if st.session_state.get("result_us_only") else ""
        st.caption(f"{len(offers)} results · {store_count} {region}{'store' if store_count == 1 else 'stores'}")
        st.markdown('<div class="offers-wrap"><table class="offers"><thead><tr>'
                    '<th>Product</th><th>Store</th><th>Price</th><th>Link</th>'
                    '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>',
                    unsafe_allow_html=True)
