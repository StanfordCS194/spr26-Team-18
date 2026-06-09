# Startup Risk Scanner

A web platform where founders paste a public GitHub repository URL, select their industry vertical, and receive evidence-backed compliance and security findings — powered by **LLM reasoning agents** for judgment-heavy analysis and **deterministic scanners** for fact-retrieval (secrets, CVEs, versions).

**Core design principles:**
- Evidence first — every finding cites a file and line number, not a generic warning
- Severity and confidence are always shown separately
- Cautious language throughout — "possible trigger", "needs review", never "violation" or "illegal"
- Industry routing — don't run HIPAA rules on a fintech repo; route the right scanner pack to the right repo
- No code execution — agents and scanners read the target repository, never run it
- Agents reason; deterministic tools ground them — CVE/secret facts come from OSV and pattern checks, never from model recall, so findings are not hallucinated

---

## The pivot

The project began as **Legi-Bill**, a California environmental legislation tracker for mid-market companies. After validating that product, the team pivoted to a broader compliance opportunity: founders routinely ship compliance debt into production because they have no affordable way to audit their codebase before a legal review, SOC 2 audit, or enterprise deal.

The scanner addresses this by running a suite of static analysis checks against any public GitHub repository and returning findings with enough evidence that a founder — not just a compliance attorney — can understand and act on them.

The **Benchmark** feature demonstrates the value proposition concretely: the same scanners are run against repos that later had advisories filed in the GitHub Advisory Database, showing how many days before disclosure the scanner already flagged a related risk signal.

---

## Architecture

```
frontend/               React 18 + Vite + Tailwind CSS
  └─ RepoScanner        3-step UI: form → scanning animation → findings
  └─ Benchmark          Advisory Database benchmark page

startup-risk/           Python scanner backend (FastAPI)
  └─ core/              Finding, RepositorySnapshot, RepositoryInventory models
  └─ ingest/            GitHub repo fetcher — clones public repos into a snapshot
  └─ scanners/          Scanner implementations (see below)
  └─ analysis/          LLM summary layer via central provider gateway
  └─ outputs/           JSON and text report formatters
```

The frontend posts `POST /api/scan` with `{ repo_url, industry, product_name, questionnaire }`. Vite proxies `/api` → `http://localhost:8000`. If the backend is unreachable the frontend shows a real error — it never fabricates findings.

---

## Running the app

**Terminal 1 — Python backend:**
```bash
cd startup-risk
pip install -r requirements.txt
uvicorn startup_risk.api:app --reload --port 8000
```

**Terminal 2 — React frontend:**
```bash
cd frontend && npm install && npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

**LLM API keys** (add one to `.env`; optional `LLM_PROVIDER` / `LLM_MODEL` can force routing):
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`

When OpenAI is selected, repo LLM calls use OpenAI Batch API requests targeting `/v1/chat/completions`
by default. No embedding calls are used.

---

## Industry verticals and scanner routing

| Vertical | Always-on scanners | Industry-specific |
|---|---|---|
| Health & MedTech | Static Hygiene, License, Dependency, Analytics & Privacy | HIPAA data-type scanner |
| Fintech | Static Hygiene, License, Dependency, Analytics & Privacy | PCI DSS patterns |
| Consumer SaaS | Static Hygiene, License, Dependency, Analytics & Privacy | GDPR/CCPA consent patterns |
| EdTech | Static Hygiene, License, Dependency, Analytics & Privacy | FERPA/COPPA data-type scanner |
| Developer Tools | Static Hygiene, License, Dependency, Analytics & Privacy | OSS license obligations |
| AI / ML | Static Hygiene, License, Dependency, Analytics & Privacy | AI data use and retention |
| Enterprise B2B | Static Hygiene, License, Dependency, Analytics & Privacy | SOC 2 / disclosure hygiene |
| Other | Static Hygiene, License, Dependency, Analytics & Privacy | — |

---

## Agents and scanners

Every check runs through the shared `Scanner` protocol (`scan(snapshot) -> list[Finding]`) and is wired in `scanners/registry.py`. Two kinds:

- **Agents** — LLM-driven reasoning (`scanners/llm_agent.py` base). They read line-numbered source, batched under a char budget across calls so large repos are covered, and emit findings tied to a real file+line. **No-op safe:** without an LLM key (`OPENAI_API_KEY`) they return nothing. Where facts matter, they are grounded by deterministic tools so they reason rather than hallucinate.
- **Scanners** — deterministic checks for fact-retrieval tasks (secrets, CVE lookups, version/registry checks) where regex / DB / registry lookups are more reliable than a model.

### Agents (LLM-driven)

| Agent | id | What it does |
|---|---|---|
| Code Compliance Agent | `code_compliance` | Reviews source for privacy/security risk: auth tokens in browser storage, insecure cookies, minor/child consent (COPPA), PHI handling, tracking SDKs, PII governance |
| Auth & Access-Control Agent | `auth_access_control` | Authn/authz flow defects: IDOR / broken object-level authorization, missing auth on sensitive routes, client-only checks, privilege escalation |
| PII Data-Flow Agent | `pii_data_flow` | Traces personal data entry → storage → logging → egress; flags retention/consent/encryption gaps and unsafe handling of sensitive categories |
| Vuln Exploitability Agent | `vuln_exploitability` | **Tool-grounded:** OSV provides ground-truth CVEs for pinned deps; the agent judges real reachability (is the vulnerable package actually used?) to cut noise |
| Infra / IaC Misconfig Agent | `infra_misconfig` | Dockerfiles, compose, k8s, Terraform, CI, nginx/env configs: root containers, baked secrets, open CORS/ports, disabled TLS, `latest` tags |
| AI-Tailored Custom Agent | `custom_compliance` | Generates a startup-specific ruleset from the onboarding profile (stage, customers, data sensitivity, GTM) + repo facts, then grades the repo against it |

### Scanners (deterministic)

| Scanner | id | What it does |
|---|---|---|
| Repository Hygiene | `static_hygiene` | Missing `README`/`LICENSE`/`.gitignore`/`SECURITY.md`; suspicious committed filenames (`.env`, `.pem`, `id_rsa`, `*secret*`…). Severity scales by location |
| Dependency Risk | `dependency_risk` | Multi-language manifest parsing / dependency inventory |
| Secret Scanner | `secret_scanner` | PEM private keys (`critical`), AWS key IDs (`critical`), hardcoded secret literals & creds-in-URLs (`high`); suppresses placeholders |
| License Risk | `license_risk` | SPDX license inventory across 8 ecosystems; flags copyleft / non-commercial / no-license. Optional LLM classification for ambiguous cases |
| Dependency Vulnerability | `dependency_vuln` | Batch-queries [OSV](https://osv.dev) for pinned versions; one finding per CVE, severity from the OSV record |
| Outdated Dependencies | `outdated_deps` | Pinned vs latest via live registry APIs (PyPI · npm · crates.io · RubyGems), capped per ecosystem |

Plus **Repository Inventory** (`repo_inventory`) — a metadata pass producing `RepositoryInventory` (languages, manifests, schema/infra/config files) consumed by the others rather than emitting findings.

> Note: the `dependency_vuln` scanner and the `vuln_exploitability` agent are complementary — the scanner reports every OSV match; the agent triages which are actually reachable.

---

## Development phases

### Phase 1 — Foundations ✅
- [x] Repository ingestion — fetch a public GitHub repo into a static snapshot
- [x] `Finding` model — stable IDs, severity, confidence, evidence with file + line
- [x] Static Hygiene Scanner
- [x] License Risk Scanner
- [x] Repository Inventory Scanner
- [x] CLI — `startup-risk scan <repo_url>`
- [x] JSON and text output formatters

### Phase 2 — Frontend and demo ✅
- [x] React frontend — form → scanning animation → findings
- [x] Industry vertical selector — 8 verticals
- [x] `FindingCard` — expandable, severity badge, confidence badge, evidence
- [x] Placeholder findings fallback when backend is not running
- [x] Benchmark page — 12 repos benchmarked against GitHub Advisory Database classes
- [x] Advisory correlation framing — "flagged N days before advisory was filed"
- [x] Industry filter, stats strip, expandable repo cards

### Phase 3 — Scanner coverage *(PRs open, pending merge)*
- [x] Secret Scanner — PEM keys, AWS key IDs, hardcoded secrets, credentials in URLs
- [x] Dependency Vulnerability Scanner — OSV database, 8 ecosystems, CVE per finding
- [x] Outdated Dependencies Scanner — live registry check, PyPI/npm/crates/RubyGems
- [x] Code Compliance Scanner — XSS vectors, insecure cookies, HIPAA, COPPA, tracking SDKs, PII
- [x] Frontend updated to reflect all 6 scanners, real evidence schema, scanner attribution badges
- [ ] FastAPI backend endpoint wired to return real scanner output to the frontend
- [ ] Industry routing — select scanner pack based on the `industry` field in the request

### Phase 4 — Industry-specific scanners
- [ ] HIPAA scanner — PHI field names + healthcare context co-presence
- [ ] PCI DSS scanner — cardholder data field patterns
- [ ] GDPR/CCPA scanner — consent patterns, data subject request flows
- [ ] FERPA/COPPA scanner — student/minor data fields + analytics SDK co-presence
- [ ] SOC 2 scanner — logging signals, access control patterns, encryption config
- [ ] AI data use scanner — LLM API calls without retention policy

### Phase 5 — Accuracy and real benchmark
- [ ] Run scanners against the real GitHub Advisory Database corpus
- [ ] Compute precision/recall vs advisory severity classifications
- [ ] Publish benchmark results with live data (replacing illustrative placeholders)
- [ ] LLM-assisted finding triage — reduce false positives

### Phase 6 — Polish and scale
- [ ] Save scan history per user
- [ ] Scan comparison — diff findings between two commits
- [ ] GitHub App — run scanner automatically on pull requests
- [ ] Weekly compliance digest — Slack or email
- [ ] Export — PDF report, CSV, SARIF for GitHub Code Scanning

---

## Future scanner ideas

### Security hygiene
- [x] Hard-coded secret patterns — SecretScanner covers AWS keys, PEM certs, API key literals, connection string passwords
- [ ] Default credentials — `admin:admin`, `root:root` in config or test files
- [ ] Dockerfile security — running as root, no `HEALTHCHECK`, `latest` image tag

### Privacy and compliance
- [x] Tracking SDK detection — CodeComplianceScanner covers PostHog, Mixpanel, Amplitude, Segment, GTM, Facebook Pixel, Heap, FullStory, Hotjar, Clarity
- [x] Cookie flags — CodeComplianceScanner flags cookies set without HttpOnly/Secure/SameSite
- [x] HIPAA / health data — CodeComplianceScanner flags health field names without PHI controls
- [x] COPPA / minor flows — CodeComplianceScanner flags minor-user code paths without consent handling
- [ ] Pre-consent analytics — SDK calls that fire before any consent signal (context window approach)
- [ ] No data retention policy — entities with no `deleted_at`, soft-delete, or TTL field
- [ ] Third-party data sharing — data sent to more than 3 external domains
- [ ] Breach notification readiness — no incident response runbook or SECURITY.md

### Supply chain
- [x] Known CVEs — DependencyVulnScanner covers all pinned deps via OSV batch API
- [x] Behind-latest packages — OutdatedDepsScanner checks PyPI/npm/crates.io/RubyGems
- [ ] Dependency age — packages with no release in 24+ months
- [ ] Single-maintainer packages — high bus-factor risk
- [ ] `postinstall` scripts — packages that execute arbitrary code on install
- [ ] Unofficial fork detection — dependencies pointing to non-canonical repos

### Infrastructure
- [ ] Public S3 bucket name patterns in config
- [ ] Secrets passed as Docker build args
- [ ] Terraform — open security groups, unencrypted storage, no MFA on root

### LLM-assisted
- [ ] Plain-language risk summary — "why this matters for your stage"
- [ ] Suggested fix — diff-level code suggestion per finding
- [ ] False-positive filter — LLM reviewer pass before findings are surfaced

---

## PR workflow

Each feature lives on its own branch and goes through a GitHub pull request before merging to `main`.

```
main
  feature/frontend-ready          ← all 6 scanners wired in UI, fixed evidence schema (this PR)
  feature/benchmark-page          ← advisory benchmark UI
  feature/github-scanner-frontend ← original scanner frontend
  add-secret-scanner              ← SecretScanner backend (pending merge)
  add-dependency-vuln-scanner     ← DependencyVulnScanner via OSV (pending merge)
  add-outdated-deps-scanner       ← OutdatedDepsScanner via registries (pending merge)
  add-code-compliance-scanner     ← CodeComplianceScanner privacy/security (pending merge)
  analytics_scanner               ← analytics scanner (pending merge)
  create-dependency-scanner       ← dependency scanner (pending merge)
  datatype-scanner                ← data type scanner (pending merge)
```
