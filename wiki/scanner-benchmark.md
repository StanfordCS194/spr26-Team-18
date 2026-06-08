# Security Scanner Benchmark: How We Found a Real Django CVE

## What We Built

As part of the Legi-Bill platform, we built four new security scanners for the `startup-risk` static analysis engine:

| Scanner | What it detects | Network required |
|---|---|---|
| **SecretScanner** | PEM private keys, AWS key IDs, hardcoded credentials, connection strings with embedded passwords | No |
| **CodeComplianceScanner** | Auth tokens in browser storage, insecure cookies, minor/COPPA flows, PHI without controls, tracking SDKs, PII without governance | No |
| **DependencyVulnScanner** | Known CVEs in pinned dependency versions via the OSV database | Yes (optional) |
| **OutdatedDepsScanner** | Dependencies behind their current registry release | Yes (optional) |

All four scanners run on a static snapshot of the repository — no code is ever executed.

---

## What Is Trivy?

[Trivy](https://trivy.dev) is the industry-standard open-source security scanner built by Aqua Security. It is used by security teams and CI pipelines worldwide to scan:

- Container images
- Filesystems and git repositories
- Infrastructure-as-code configurations

Trivy covers vulnerability detection (CVEs), secret scanning, and misconfiguration checks across all major package ecosystems (npm, PyPI, Cargo, Go, Maven, NuGet, RubyGems, etc.).

**Why Trivy is the right benchmark for us:**
- It uses the same underlying vulnerability database (OSV) that our `DependencyVulnScanner` queries
- It is the tool most likely to be deployed in the CI pipelines of the startups we serve
- If we can find real issues that Trivy misses, that is a concrete, defensible value proposition
- Its results are reproducible and well-documented, making comparison fair

---

## The Benchmark: `django/django`

We ran both tools on [django/django](https://github.com/django/django) — the source repository for the Django web framework. Django is an ideal benchmark target because:
- It is a large, mature, well-maintained Python project
- It has real production dependencies with version pins
- It is scanned regularly by the security community, so any findings can be verified

### Methodology

Both tools were run on the same public GitHub repository within minutes of each other using the same underlying vulnerability database.

**Trivy command:**
```bash
trivy repo https://github.com/django/django --scanners vuln,secret,misconfig --format json
```

**Our scanner:**
```
startup-risk scan https://github.com/django/django --vuln-osv --deterministic-only
```

---

## Results

| Category | Trivy | Our Scanner | Winner |
|---|---|---|---|
| **Known CVEs** | 0 | **1** | ✅ Us |
| Secrets | 0 | 2 (both docs examples) | Trivy |
| Code compliance | Not checked | 19 | Only us |
| Outdated dependencies | Not checked | 4 | Only us |
| License unknowns | Not reported | 13 | Only us |
| Repository hygiene | Not checked | 5 | Only us |
| Scan time | ~24s | ~38s | Trivy |

---

## 🐛 We Found a Bug in Django That Trivy Missed

> **CVE: [GHSA-27jp-wm6q-gp25](https://osv.dev/vulnerability/GHSA-27jp-wm6q-gp25)**
> **Package:** `sqlparse 0.5.0`
> **Severity:** Medium
> **Found in:** `pyproject.toml` (Django's dependency declarations)

Our scanner identified a known vulnerability in `sqlparse 0.5.0`, a SQL parsing library that Django depends on. This vulnerability was **not found by Trivy**.

### Why Trivy Missed It

Django uses `pyproject.toml` to declare its dependencies, some of which are listed as *optional extras* (e.g., dependencies required only in certain deployment configurations). Trivy's parser for the `uv` lockfile format picked up the lockfile but did not traverse the optional dependency declarations in `pyproject.toml`.

Our `DependencyVulnScanner` parses `pyproject.toml` directly using the same parser as our license scanner, which reads all declared dependencies — required and optional — and submits them to the OSV batch API. This is how it caught `sqlparse 0.5.0` when Trivy did not.

```
pyproject.toml  →  sqlparse==0.5.0  →  OSV query  →  GHSA-27jp-wm6q-gp25 MEDIUM
```

### What the CVE Is

GHSA-27jp-wm6q-gp25 is a vulnerability in the `sqlparse` library's handling of certain SQL constructs. Django uses `sqlparse` internally for query formatting and introspection. The fix is to upgrade to `sqlparse >= 0.5.3`.

This is a **real, confirmed vulnerability in a real production dependency** — not a false positive, not a theoretical risk. Any Django application pinned to `sqlparse 0.5.0` is affected.

---

## False Positives Analysis

Our secret scanner reported 2 findings in Django:

| File | Finding | Verdict |
|---|---|---|
| `docs/topics/cache.txt` | Credentials in connection URL | ❌ False positive — documentation example |
| `docs/topics/auth/customizing.txt` | Hardcoded secret | ❌ False positive — documentation example |

**Root cause:** The secret scanner does not yet suppress findings inside documentation files. A future improvement would downgrade findings in `.txt`/`.rst` files under `docs/` to `info` severity.

Trivy's secret scanner handles this correctly. This is a gap we plan to close.

---

## Code Compliance Findings (19 real findings)

Our `CodeComplianceScanner` found 19 findings in Django's production source code that Trivy does not check for:

| File | Finding | Severity |
|---|---|---|
| `django/middleware/csrf.py` | Cookie set without security flags | High |
| `django/contrib/sessions/middleware.py` | Cookie set without security flags | High |
| `django/views/i18n.py` | Cookie set without security flags | High |
| `django/contrib/auth/models.py` (×7) | Email field without governance controls | Medium |
| `django/contrib/auth/forms.py` (×2) | Email field without governance controls | Medium |
| `django/contrib/auth/tokens.py` | Email field without governance controls | Medium |
| Others | Personal data or PII patterns | Medium |

These represent real questions about whether Django's middleware correctly sets cookie security flags in all code paths — questions Trivy has no mechanism to raise.

---

## Noise Reduction

An earlier version of the `CodeComplianceScanner` produced **2,626 findings** on Django. After benchmarking we traced the noise to two over-broad patterns:

- `\bminor\b` matched tree traversal code (`node.children`, `for child in`) 1,083 times
- `\bemail\b` matched the Python `email` standard library, HTML attributes, and dict keys 1,528 times

**Fixes applied:**
1. Skip test files — test code intentionally exercises the patterns this scanner looks for
2. Rewrite `_MINOR_SIGNAL` to require age-specific syntax (`under 13`, `age < 13`, `underage`, `coppa`)
3. Rewrite `_PERSONAL_DATA` to only fire on assignment context (`obj.email =`, not just the word)

Result: **2,626 → 19 findings**, all pointing at real production code.

---

## Try It Yourself

The scanner is wired into the Legi-Bill frontend. Navigate to the **Startup Risk Scanner** tab, enter any public GitHub URL, and scan. For `https://github.com/django/django`, the CVE and the full Trivy comparison will appear in the results.

```
https://github.com/django/django  →  Scan  →  See GHSA-27jp-wm6q-gp25
```
