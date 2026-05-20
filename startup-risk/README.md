# startup-risk

`startup-risk` is a headless Python CLI for statically scanning public startup repositories.

Current constraints:

- No frontend.
- No web server.
- No GitHub App integration.
- Only public GitHub repositories are supported as remote targets.
- Scanned repository code is never executed.
- Scanning is static parsing only.

## Usage

```bash
startup-risk scan https://github.com/org/repo --format text
startup-risk scan /path/to/local/repo --format json
```

Local paths are supported for development and tests. Remote scans must use public GitHub HTTPS URLs.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
```

