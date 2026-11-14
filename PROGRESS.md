# Progress

## Round 2 complete
- Built a compact Streamlit dashboard with editable product group, live comparison refresh, Compare Deals button, offer CRUD in a collapsed expander, recommendation metrics, all-store cost breakdown, and SQLite save/load/update/delete controls in the sidebar.
- Added SQLite serialization for complete comparison inputs and offers, preserving Decimal strings and `None` versus zero; `SHOPCHECKOUT_DB` selects an isolated database.
- Added current-input CSV export with normalized and required-unit quantities, cost components, source fields, and separate configured/charged shipping.
- Repaired UI regressions for group trimming/validation, sample form reset, promotion None, and active-record update targeting.
- Updated README and SPEC with concise setup, calculation, persistence, and interface details.
- Offer editing now has one enabled form submit button whose action label follows the selected offer; removal is a separate control. A stable placeholder keeps transient notices from shifting the editor.
- Browser checks reported for 30/50/100 US fl oz: C/$10.79, B/$15.65, A/$30.25; Save new, Load selected, and Update active followed by Load selected also passed.
- Added a regression for editing B from $14.49 to $15.49 at 50 US fl oz; the updated recommendation is B at $16.73.
- Final browser recheck passed: loaded the saved 50 US fl oz sample, changed B from $14.49 to $15.49, clicked Save edits once, saw “Offer updated” and $16.73, and confirmed the editor stayed open after selecting B. Reloading the saved comparison restored B at $14.49 and $15.65.
- Verification: `C:/Users/ulric/anaconda3/python.exe -m pytest -q` — **40 passed in 12.38s** (one upstream protobuf deprecation warning).
- Server remains running at `http://127.0.0.1:8501`.
