# ShopCheckout Lite

Enter a product name or product link to find web offers, compare prices, and open the retailer's purchase page.

## Before class

- Python 3.10+ and internet access.
- Codex CLI installed and signed in with your ChatGPT account.
- No additional accounts or API keys are required.

## Run

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Enter a name or link and click **Search**. Partial names and spelling mistakes work too. The app discovers retailers through web search and highlights the lowest listed price. **Hide sold-out items** and **US stores only** are independent options, both enabled by default.

## Test

```bash
python -m pytest -q
```
