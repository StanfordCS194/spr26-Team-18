# License Scanner

Static third-party dependency license scanner for `startup-risk`.

## Safety

- Does not run package managers, install hooks, lifecycle scripts, build commands, or dependency code.
- Batch LLM review uses provider batch APIs only; no synchronous LLM fallback is used.
- Artifact helpers extract archives as data only and reject traversal, absolute paths, links, special files, and oversized archives.

## Coverage

Parsers currently cover:

- npm: `package.json`, `package-lock.json`
- Python: `requirements.txt`, `pyproject.toml`, `poetry.lock`
- Rust: `Cargo.toml`, `Cargo.lock`
- Go: `go.mod`
- Java/JVM: `pom.xml`, Gradle dependency declarations
- Ruby: `Gemfile`, `Gemfile.lock`, `*.gemspec`
- PHP: `composer.json`, `composer.lock`
- .NET: `*.csproj`, `packages.lock.json`
- Vendored code under `vendor/`, `third_party/`, `external/`, and `deps/`

## CLI

```bash
startup-risk scan /path/to/repo
startup-risk scan /path/to/repo --deterministic-only
startup-risk scan /path/to/repo --license-llm-provider openai
startup-risk scan /path/to/repo --license-llm-provider gemini --license-llm-model gemini-3.5-flash
startup-risk scan /path/to/repo --license-registry-metadata
startup-risk scan /path/to/repo --license-registry-metadata --license-artifact-inspection --license-source-repo
```

Normal scans require one LLM provider key: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY`.
The central LLM gateway auto-detects the configured key unless `LLM_PROVIDER` or `--license-llm-provider`
is set. `--deterministic-only` is for local debugging and tests.

Batch defaults:

- prompt token budget: `200000`
- requests per batch: `50000`
- input file bytes: `200000000`

These can be overridden with CLI flags or `LICENSE_SCANNER_LLM_*` environment variables.
Model defaults can be overridden with `LLM_MODEL`, provider-specific model env vars, or `--license-llm-model`.
