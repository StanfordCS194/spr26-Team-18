# Legi-Bill

Enterprise solution for California environmental policy impact analysis, powered by LLMs.

## Setup

**1. Install Python dependencies**
```bash
pip install -r requirements.txt
```

**2. Install frontend dependencies**
```bash
cd frontend && npm install
```

**3. Configure API keys**
```bash
cp .env.example .env
```
Fill in `.env` with your keys:
- `LEGISCAN_API_KEY` — we have this in gihub secrets
- `ANTHROPIC_API_KEY` — or OPENAI_API_KEY (gpt 4o mini works well for summaries)

---

## Running the app

**Terminal 1 — Python backend:**
```bash
python3 -m uvicorn legi_bill.api:app --reload --port 8000
```

**Terminal 2 — React frontend:**
```bash
cd frontend && npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

---

## Data pipeline mainly feature 1 for now

### 1. Scrape bills (LegiScan API only)
```bash
python3 -m legi_bill.cli scrape --session 2025 --limit 50
```

### 2. Summarize bills (Anthropic API)
Generates plain-language summaries and compliance questions for each bill:
```bash
python3 -m legi_bill.cli summarize --all
```

### 3. Inspect results
```bash
# List all bills in the DB
python3 -m legi_bill.cli list

# View a single bill with summary and compliance questions
python3 -m legi_bill.cli show --bill AB1234

# Export everything to JSON
python3 -m legi_bill.cli export --output bills.json
```

---

## API keys needed per step

| Step | LegiScan | Anthropic |
|---|---|---|
| `scrape` | Yes | No |
| `summarize` | No | Yes |
| `show` / `list` / `export` | No | No |
| Backend + Frontend | No | No |

---

## Features

- **Bill Lookup** — Browse and search California environmental bills with plain-language summaries and compliance questions
- **Legislator Tracker** *(coming soon)* — Voting history and pattern analysis per legislator
- **Company Match** *(coming soon)* — Upload a 10-K and get a ranked list of bills relevant to your operations
