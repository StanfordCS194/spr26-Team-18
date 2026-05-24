# startup-risk Agent Rules

This project is a headless CLI product for static startup repository risk scanning.

## Product Constraints

- Do not build a frontend.
- Do not add a web server.
- Do not add GitHub App integration.
- Support only public GitHub repositories as remote targets for now.
- Never execute code from scanned repositories.
- Use static parsing only.
- Do not call external legal APIs.

## Development Rules

- Use Typer for CLI commands.
- Use Pydantic for schemas and data contracts.
- Use pytest for tests.
- Keep scanner infrastructure boring and testable.
- Keep ingestion, scanning, analysis, and output formatting separated.
- Scanners should consume static snapshots, not raw live repository processes.
- New checks should produce structured findings with stable rule IDs.
- Prefer deterministic behavior over heuristic side effects.

