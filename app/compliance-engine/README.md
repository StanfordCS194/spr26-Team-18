# Compliance Engine

PRD compliance triage for US-focused product review.

The engine has three layers:

1. Extract factual product signals from a PRD.
2. Match those facts against an explicit compliance rule catalog.
3. Render an evidence-backed report with missing facts and suggested controls.

The output is intentionally framed as product/legal review guidance, not a final
legal determination.

## Local usage

```bash
python app/compliance-engine/cli.py path/to/prd.pdf
python app/compliance-engine/cli.py path/to/prd.md --include-not-flagged
```

Supported inputs:

- PDF
- TXT
- Markdown
- DOCX if `python-docx` is installed

## Programmatic usage

```python
from pathlib import Path
import sys

sys.path.append("app/compliance-engine")

from engine import analyze_prd_text
from report import render_markdown_report

report = analyze_prd_text(Path("prd.md").read_text(), source="prd.md")
print(render_markdown_report(report))
```

## Current rule areas

- COPPA / children's privacy
- Teen / minor privacy and safety
- Age verification / age assurance
- HIPAA
- FTC health privacy and security
- State consumer privacy
- Biometric privacy
- FERPA / education privacy
- Marketing / messaging consent
