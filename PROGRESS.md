# ShopCheckout Lite - Progress

- [x] Requirements, architecture, function contract, and four-step plan recorded in SPEC.md.
- [x] Implemented the six maintained files; checkout.py owns all monetary calculations.
- [x] Ran python -m pytest -q once: 4 passed in 0.06s.
- [x] Changed app.py to a Streamlit form so quantities and coupon submit together.
- [x] Browser verified: two Notebook, no coupon -> subtotal 50.00, discount 0.00, shipping 0.00, tax 4.00, total 54.00.
- [x] Browser verified: two Notebook, SAVE10 -> subtotal 50.00, discount 5.00, shipping 5.00, tax 3.60, total 53.60.
- [x] Browser verified: all-zero quantities and SAVE20 display useful errors.
- Environment: C:\Users\ulric\anaconda3\python.exe; existing streamlit and pytest used; no packages installed.
- Verification completed: 2026-11-05. Ready for the workshop demonstration.
- Run from this folder: python -m streamlit run app.py --server.address 127.0.0.1 --server.headless true
- Open: http://127.0.0.1:8501
