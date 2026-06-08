# Startup Risk Scanner

A web platform where founders paste a public GitHub repository URL, select their industry vertical, and receive evidence-backed compliance and security findings — powered by a combination of deterministic static-analysis scanners and LLMs.

**Core design principles:**
- Evidence first — every finding cites a file and line number, not a generic warning
- Severity and confidence are always shown separately
- Cautious language throughout — "possible trigger", "needs review", never "violation" or "illegal"
- Industry routing — don't run HIPAA rules on a fintech repo; route the right scanner pack to the right repo
- Static analysis only — the scanner never executes code from the target repository

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
  └─ analysis/          LLM summary layer (Anthropic)
  └─ outputs/           JSON and text report formatters
```

The frontend posts `POST /api/scan` with `{ repo_url, industry, product_name }`. Vite proxies `/api` → `http://localhost:8000`. When the backend is not running, the frontend falls back to illustrative placeholder findings with a visible disclaimer.

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

**API keys** (add to `.env`):
- `ANTHROPIC_API_KEY` — LLM-assisted license classification and finding summaries
- `OPENAI_API_KEY` — alternative provider (optional)

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

## Existing scanners

### 1. Static Hygiene Scanner
`startup-risk/startup_risk/scanners/static_hygiene.py`

Always runs. Checks for missing standard files and suspicious committed filenames.

**Checks:**
- Missing `README.md` — repo not safe to share
- Missing `LICENSE` — ambiguous usage rights
- Missing `.gitignore` — risk of accidentally committing secrets or build artifacts
- Missing `SECURITY.md` — no vulnerability disclosure path; enterprise buyers expect this
- Suspicious filenames — `.env`, `.env.*` (except template variants), `.key`, `.pem`, `.p12`, `.pfx`, `id_rsa`, `id_ed25519`, `*credential*`, `*secret*`, `*token*`, `*private_key*`

Severity scales by file location: root-level is `high`, test/docs/examples directories are `low`, everything else is `medium`.

---

### 2. License Risk Scanner
`startup-risk/startup_risk/scanners/license_scanner/`

Always runs. Multi-language dependency license inventory with deterministic SPDX identification plus optional LLM classification for ambiguous cases.

**Supported manifest parsers:**
- Node.js — `package.json`, `package-lock.json`, `yarn.lock`
- Python — `requirements.txt`, `pyproject.toml`, `setup.py`, `Pipfile`
- Go — `go.mod`
- Rust — `Cargo.toml`, `Cargo.lock`
- Java/Kotlin — `pom.xml`, `build.gradle`
- Ruby — `Gemfile`, `Gemfile.lock`
- PHP — `composer.json`, `composer.lock`
- .NET — `*.csproj`, `packages.config`

**License risk tiers flagged:**
- `copyleft_strong` — GPL-2.0, GPL-3.0, AGPL-3.0 — may require source disclosure of the combined work
- `copyleft_weak` — LGPL-2.1, LGPL-3.0, MPL-2.0 — linking and attribution obligations
- `non_commercial` — CC-BY-NC and variants — non-commercial-only restrictions
- `no_known_license` — no license file found — all rights reserved by default

---

### 3. Repository Inventory Scanner
`startup-risk/startup_risk/scanners/repo_inventory.py`

Runs as a metadata pass; produces `RepositoryInventory` used by downstream scanners rather than `Finding` objects directly.

**Catalogues:**
- Languages detected (Go, Java, JavaScript, Kotlin, Python, Ruby, Rust, TypeScript)
- Manifest and lockfile presence
- Schema files (`.sql`, `.prisma`, `.proto`, `.graphql`, `.jsonschema`)
- Infrastructure files (`Dockerfile`, `docker-compose.yml`, `.tf`, `.tfvars`)
- Config files (`.env.example`, `.gitignore`, `vercel.json`, `netlify.toml`)

---

### 4. Secret Scanner *(branch: `add-secret-scanner` — pending merge)*
`startup-risk/startup_risk/scanners/secret_scanner.py`

Scans source file text (not just filenames) for committed secrets. Skips binary, lock, and asset files. Suppresses placeholder patterns like `your-key-here`, `changeme`, `${VAR}`.

**Checks:**
- PEM private key headers — `-----BEGIN PRIVATE KEY-----` and variants — severity `critical`
- AWS access key IDs — `AKIA/AGPA/AIDA/AROA/AIPA/ANPA/ANVA/ASIA` + 16-char body — severity `critical`
- Hardcoded secrets via keyword assignment — `api_key =`, `password =`, `client_secret =`, `db_password =`, etc. with a string literal value ≥16 chars — severity `high`
- Credentials in connection URLs — `postgres://user:PASSWORD@`, `redis://user:PASSWORD@`, etc. — severity `high`

Severity drops one tier for findings in test, examples, or docs directories.

---

### 5. Dependency Vulnerability Scanner *(branch: `add-dependency-vuln-scanner` — pending merge)*
`startup-risk/startup_risk/scanners/dependency_vuln_scanner.py`

Parses all dependency manifests, then batch-queries the [OSV vulnerability database](https://osv.dev) for every pinned dependency version. Returns one finding per CVE/advisory per affected package, linking to the OSV entry and citing the manifest file + line number.

**Supported ecosystems:** PyPI · npm · crates.io · Go · Maven · RubyGems · Packagist · NuGet

Severity is derived from the OSV record's `database_specific.severity` field (GitHub Advisory style), falling back to `high` if any CVSS score is present.

---

### 6. Outdated Dependencies Scanner *(branch: `add-outdated-deps-scanner` — pending merge)*
`startup-risk/startup_risk/scanners/outdated_deps_scanner.py`

Checks pinned dependency versions against live registry APIs. Flags anything where the pinned version is behind the current latest release. Capped at 30 packages per ecosystem to stay within registry rate limits.

**Supported registries:** PyPI · npm · crates.io · RubyGems

---

### 7. Code Compliance Scanner *(branch: `add-code-compliance-scanner` — pending merge)*
`startup-risk/startup_risk/scanners/code_compliance_scanner.py`

Scans source files (JS, TS, Python, Go, Ruby, Java, Kotlin, C#, Swift, PHP, Rust, Scala) for privacy and security compliance patterns. Uses a ±4-line context window to check for nearby controls before flagging.

**Checks:**
- **Auth token in browser storage** — `localStorage.setItem(…token…)` — severity `high` (XSS attack vector)
- **Cookie set without security flags** — `document.cookie =`, `res.cookie()`, `response.set_cookie()` without `HttpOnly`/`Secure`/`SameSite` in surrounding code — severity `high`
- **Minor-user code path without consent handling** — references to `child`, `minor`, `under-13`, `coppa` without a nearby age gate, parental consent, or verification check — severity `high`
- **Health data without PHI safeguards** — `patient`, `diagnosis`, `ehr`, `fhir`, `phi` etc. without nearby `encrypt`, `audit`, `hipaa`, `access_control` — severity `high`
- **Third-party tracking SDK** — PostHog, Mixpanel, Amplitude, Segment, GTM, Facebook Pixel, Heap, FullStory, Hotjar, Clarity — severity `medium`
- **PII field without data-governance handling** — `email`, `phone`, `ssn`, `date_of_birth`, `geolocation`, `ip_address` etc. without nearby deletion, retention, consent, or encryption logic — severity `medium`

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
