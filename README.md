# spr26-Team-18
tanvi
nicholas
lauren

## Running the Streamlit mockup (Feature 3)

The mockup has three sidebar entries: **Bill Summaries** (Feature 1, wired to
the real SQLite DB populated by `feature_1`'s CLI), **Legislator Tracker**
(Feature 2 — static placeholder until that branch lands), and **Match my
company** (Feature 3 — upload a 10-K or paste a description to get a ranked
list of relevant California environmental bills).

```bash
pip install -r requirements.txt

# Populate the DB (requires LEGISCAN_API_KEY and ANTHROPIC_API_KEY in .env)
cp .env.example .env
python -m legi_bill.cli scrape --session 2025 --limit 30
python -m legi_bill.cli summarize --all

# Launch the app (from the repo root)
streamlit run streamlit_app.py

# Or seed with mock data to preview the UI without API keys:
python scripts/seed_mock_data.py
streamlit run streamlit_app.py
```

Ranking is a deterministic keyword-overlap heuristic — no Anthropic API calls
are made from the UI. Override the DB location with `LEGI_BILL_DB_PATH`.
