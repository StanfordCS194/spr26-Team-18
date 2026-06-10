"""
Accessibility Compliance Scanner
==================================
Static checks for WCAG 2.1 Level AA compliance signals in frontend code.
Targets ADA Title III (US), Section 508 (federal contractors), and
California Unruh Civil Rights Act — all of which have been applied to
web applications through active litigation.

All findings are medium severity. Checks are purely regex-based — they
flag structural patterns that commonly indicate accessibility gaps, but
cannot replace a full automated or manual audit.

Seven checks:

  Repo-level (fire at most once):
    1. No skip navigation link — keyboard users cannot bypass repeated nav.

  Per-file:
    2. <img> without alt attribute — screen readers announce the filename.
    3. <input> without accessible name — form field purpose is undiscoverable.
    4. Clickable non-semantic element without role — div/span with onClick
       and no role or tabIndex makes the control unreachable by keyboard.
    5. <iframe> without title — frame purpose is undescribed to assistive tech.
    6. <html> without lang attribute — screen readers cannot select the right
       voice/language profile.
    7. Empty or icon-only interactive element — link or button with no
       accessible label leaves purpose unknown to screen readers.
"""
from __future__ import annotations

import re

from startup_risk.core.ids import stable_finding_id
from startup_risk.core.models import (
    FileSnapshot,
    Finding,
    FindingEvidence,
    RepositorySnapshot,
    SourceLocation,
)

# ---------------------------------------------------------------------------
# Extension sets
# ---------------------------------------------------------------------------

# Markup / component files where accessibility attributes live
_MARKUP_EXTENSIONS = frozenset({".jsx", ".tsx", ".html", ".vue", ".svelte"})
# JS/TS files also scanned for lang and skip-nav
_SOURCE_EXTENSIONS = frozenset({".js", ".ts", ".jsx", ".tsx", ".vue", ".svelte"})
# HTML-only for lang check
_HTML_EXTENSIONS = frozenset({".html", ".htm"})

_CONTEXT_RADIUS = 4

# ---------------------------------------------------------------------------
# Repo-level patterns
# ---------------------------------------------------------------------------

# Skip navigation / skip-to-main-content link
_SKIP_NAV_PATTERN = re.compile(
    r"""(?:
        skip(?:[-\s](?:to[-\s])?)?(?:main|nav|content|navigation|link)
        | href\s*=\s*['"]#(?:main|content|maincontent|primary)['"]
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# Signals that a site has a navigational structure worth skipping
_NAV_PRESENCE_PATTERN = re.compile(
    r"""<(?:nav|header)\b|role\s*=\s*['"](?:navigation|banner)['"]""",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Per-file patterns
# ---------------------------------------------------------------------------

# -- Check 2: <img> missing alt -------------------------------------------

# Matches <img or JSX <img anywhere on the line
_IMG_TAG_PATTERN = re.compile(r"<img\b", re.IGNORECASE)
# An alt attribute present anywhere on the same line (or attribute block)
_ALT_PRESENT_PATTERN = re.compile(r'\balt\s*=', re.IGNORECASE)
# role="presentation" or role="none" exempts decorative images
_DECORATIVE_ROLE_PATTERN = re.compile(
    r"""role\s*=\s*['"](?:presentation|none)['"]""", re.IGNORECASE
)

# -- Check 3: <input> missing accessible name -----------------------------

_INPUT_TAG_PATTERN = re.compile(r"<input\b", re.IGNORECASE)
# Any of these on the same line means the input has an accessible name
_INPUT_LABEL_PATTERN = re.compile(
    r"""(?:
        \baria-label\s*=
        | \baria-labelledby\s*=
        | \baria-describedby\s*=
        | \bid\s*=\s*['"][^'"]+['"]   # will match label's htmlFor
        | \btype\s*=\s*['"](?:hidden|submit|reset|button|image)['"]
        | \bplaceholder\s*=           # not ideal but suppresses noise
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# -- Check 4: clickable non-semantic element without role -----------------

# div or span (or li, td) carrying an onClick / onPress handler
_DIV_CLICK_PATTERN = re.compile(
    r"""<(?:div|span|li|td|tr|p)\b[^>]*\bon(?:Click|Press|Tap|MouseDown)\s*=""",
    re.IGNORECASE,
)
# Suppressed if role or tabIndex is also present on the same line
_ROLE_OR_TABINDEX_PATTERN = re.compile(
    r"""(?:\brole\s*=|\btabIndex\s*=|\btabindex\s*=)""",
    re.IGNORECASE,
)

# -- Check 5: <iframe> missing title --------------------------------------

_IFRAME_TAG_PATTERN = re.compile(r"<iframe\b", re.IGNORECASE)
_IFRAME_TITLE_PATTERN = re.compile(r"\btitle\s*=", re.IGNORECASE)

# -- Check 6: <html> missing lang attribute -------------------------------

_HTML_TAG_PATTERN = re.compile(r"<html\b", re.IGNORECASE)
_LANG_ATTR_PATTERN = re.compile(r"\blang\s*=", re.IGNORECASE)

# -- Check 7: empty / icon-only interactive element -----------------------

# <a> or <button> that appears to have no visible text (empty tags or
# icon-only content) and no aria-label/aria-labelledby
_EMPTY_INTERACTIVE_PATTERN = re.compile(
    r"""<(?:a|button)\b(?:[^>]*)>\s*(?:<[^/][^>]*/?>\s*)*</(?:a|button)>""",
    re.IGNORECASE,
)
_ARIA_LABEL_PATTERN = re.compile(
    r"""\baria-label(?:ledby)?\s*=""", re.IGNORECASE
)
# Suppress if the element contains visible text (rough heuristic: any word char)
_HAS_TEXT_PATTERN = re.compile(r">\s*\w", re.IGNORECASE)


def _context(lines: list[str], index: int, radius: int = _CONTEXT_RADIUS) -> str:
    start = max(0, index - radius)
    end = min(len(lines), index + radius + 1)
    return "\n".join(lines[start:end])


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class AccessibilityScanner:
    """
    Static checks for WCAG 2.1 AA / ADA Title III compliance signals in
    frontend markup and component files.
    """

    id = "accessibility"
    name = "Accessibility Compliance"
    version = "1.0.0"

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        findings: list[Finding] = []

        # Only run on repos that have markup / frontend files
        has_markup = any(
            f.extension in _MARKUP_EXTENSIONS for f in snapshot.files
        )
        if not has_markup:
            return []

        # Repo-level: skip navigation
        if self._repo_has_nav(snapshot) and not self._repo_has_skip_nav(snapshot):
            findings.append(self._no_skip_nav_finding(snapshot))

        # Per-file checks
        for file in snapshot.files:
            if file.text is None:
                continue
            if file.extension in _MARKUP_EXTENSIONS:
                findings.extend(self._check_img_no_alt(file))
                findings.extend(self._check_input_no_label(file))
                findings.extend(self._check_div_click_no_role(file))
                findings.extend(self._check_iframe_no_title(file))
                findings.extend(self._check_empty_interactive(file))
            if file.extension in _HTML_EXTENSIONS:
                findings.extend(self._check_html_no_lang(file))

        return findings

    # ------------------------------------------------------------------
    # Repo-level helpers
    # ------------------------------------------------------------------

    def _repo_has_nav(self, snapshot: RepositorySnapshot) -> bool:
        return any(
            file.text and _NAV_PRESENCE_PATTERN.search(file.text)
            for file in snapshot.files
            if file.extension in _MARKUP_EXTENSIONS
        )

    def _repo_has_skip_nav(self, snapshot: RepositorySnapshot) -> bool:
        return any(
            file.text and _SKIP_NAV_PATTERN.search(file.text)
            for file in snapshot.files
        )

    def _no_skip_nav_finding(self, snapshot: RepositorySnapshot) -> Finding:
        nav_files = [
            file.path for file in snapshot.files
            if file.text and _NAV_PRESENCE_PATTERN.search(file.text)
            and file.extension in _MARKUP_EXTENSIONS
        ][:3]
        seed = "skip_nav|" + "|".join(sorted(nav_files))
        evidence = [
            FindingEvidence(
                location=SourceLocation(path=path, line_start=1, line_end=1),
                description="Navigation structure detected with no skip link found in the repository.",
            )
            for path in nav_files
        ]
        return Finding(
            id=stable_finding_id(self.id, "no_skip_navigation", seed),
            title="No skip navigation link found",
            description=(
                "The repository contains navigation elements but no skip-to-main-content "
                "link. Keyboard and screen reader users must tab through every navigation "
                "item on every page to reach the main content. WCAG 2.1 Success Criterion "
                "2.4.1 (Bypass Blocks, Level A) requires a mechanism to skip repeated "
                "navigation. This is one of the most commonly cited issues in ADA "
                "Title III web accessibility lawsuits."
            ),
            category="accessibility",
            severity="medium",
            confidence="medium",
            evidence=evidence,
            recommendation=(
                "Add a visually hidden 'Skip to main content' link as the first focusable "
                "element on every page, pointing to the id of the main content area "
                "(e.g., <a href=\"#main-content\" className=\"sr-only focus:not-sr-only\">). "
                "Ensure the link becomes visible on keyboard focus."
            ),
            scanner_id=self.id,
            scanner_version=self.version,
        )

    # ------------------------------------------------------------------
    # Check 2 — <img> without alt
    # ------------------------------------------------------------------

    def _check_img_no_alt(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        lines = file.text.splitlines()  # type: ignore[union-attr]

        for i, line in enumerate(lines):
            if not _IMG_TAG_PATTERN.search(line):
                continue
            ctx = _context(lines, i)
            if _ALT_PRESENT_PATTERN.search(ctx):
                continue
            if _DECORATIVE_ROLE_PATTERN.search(ctx):
                continue
            findings.append(Finding(
                id=stable_finding_id(self.id, "img_no_alt", f"{file.path}:{i}"),
                title="Image missing alt attribute",
                description=(
                    "An <img> element has no alt attribute. Screen readers announce the "
                    "filename instead, which is meaningless to users who cannot see the image. "
                    "WCAG 2.1 SC 1.1.1 (Non-text Content, Level A) requires all images to "
                    "have a text alternative. Decorative images should use alt=\"\" to be "
                    "ignored by assistive technology."
                ),
                category="accessibility",
                severity="medium",
                confidence="high",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    excerpt=line.strip()[:120],
                    description="<img> tag with no alt attribute detected.",
                )],
                recommendation=(
                    "Add an alt attribute to every <img> element. Use a descriptive string "
                    "for meaningful images (alt=\"Company logo\"), or an empty string for "
                    "decorative images (alt=\"\"). In JSX, also accept alt={undefined} only "
                    "when paired with role=\"presentation\"."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            ))
        return findings

    # ------------------------------------------------------------------
    # Check 3 — <input> without accessible name
    # ------------------------------------------------------------------

    def _check_input_no_label(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        lines = file.text.splitlines()  # type: ignore[union-attr]

        for i, line in enumerate(lines):
            if not _INPUT_TAG_PATTERN.search(line):
                continue
            ctx = _context(lines, i)
            if _INPUT_LABEL_PATTERN.search(ctx):
                continue
            findings.append(Finding(
                id=stable_finding_id(self.id, "input_no_label", f"{file.path}:{i}"),
                title="Form input without an accessible label",
                description=(
                    "An <input> element has no aria-label, aria-labelledby, or visible "
                    "<label> association. Screen readers announce only the input type, "
                    "leaving the field's purpose unknown to non-visual users. WCAG 2.1 "
                    "SC 1.3.1 (Info and Relationships, Level A) and SC 4.1.2 (Name, Role, "
                    "Value, Level A) require all form controls to have a programmatic label."
                ),
                category="accessibility",
                severity="medium",
                confidence="medium",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    excerpt=line.strip()[:120],
                    description="<input> with no accessible name attribute detected.",
                )],
                recommendation=(
                    "Associate every input with a visible <label htmlFor=\"id\"> that matches "
                    "the input's id, or add aria-label=\"Field purpose\" directly on the input. "
                    "Placeholder text is not a substitute — it disappears on focus and is not "
                    "reliably announced by all screen readers."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            ))
        return findings

    # ------------------------------------------------------------------
    # Check 4 — clickable non-semantic element without role
    # ------------------------------------------------------------------

    def _check_div_click_no_role(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        lines = file.text.splitlines()  # type: ignore[union-attr]

        for i, line in enumerate(lines):
            if not _DIV_CLICK_PATTERN.search(line):
                continue
            if _ROLE_OR_TABINDEX_PATTERN.search(line):
                continue
            findings.append(Finding(
                id=stable_finding_id(self.id, "div_click_no_role", f"{file.path}:{i}"),
                title="Clickable non-semantic element missing role and tabIndex",
                description=(
                    "A <div>, <span>, or similar non-interactive element has an onClick "
                    "handler but no role attribute or tabIndex, making it unreachable by "
                    "keyboard navigation and invisible to screen readers. WCAG 2.1 SC 4.1.2 "
                    "(Name, Role, Value, Level A) requires that all UI components have an "
                    "accessible role, and SC 2.1.1 (Keyboard, Level A) requires all "
                    "functionality be operable without a mouse."
                ),
                category="accessibility",
                severity="medium",
                confidence="medium",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    excerpt=line.strip()[:120],
                    description="Non-semantic element with click handler and no role or tabIndex.",
                )],
                recommendation=(
                    "Replace with a semantic <button> element, which is keyboard-focusable and "
                    "announced correctly by screen readers with no extra attributes. If a <div> "
                    "must be used, add role=\"button\", tabIndex={0}, and an onKeyDown handler "
                    "that triggers the action on Enter and Space."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            ))
        return findings

    # ------------------------------------------------------------------
    # Check 5 — <iframe> without title
    # ------------------------------------------------------------------

    def _check_iframe_no_title(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        lines = file.text.splitlines()  # type: ignore[union-attr]

        for i, line in enumerate(lines):
            if not _IFRAME_TAG_PATTERN.search(line):
                continue
            ctx = _context(lines, i)
            if _IFRAME_TITLE_PATTERN.search(ctx):
                continue
            findings.append(Finding(
                id=stable_finding_id(self.id, "iframe_no_title", f"{file.path}:{i}"),
                title="<iframe> missing title attribute",
                description=(
                    "An <iframe> element has no title attribute. Screen readers enter "
                    "the frame without announcing its purpose, disorienting users. WCAG 2.1 "
                    "SC 4.1.2 (Name, Role, Value, Level A) requires frames to have "
                    "a descriptive title. This also applies to embedded maps, videos, "
                    "payment widgets, and third-party components delivered in iframes."
                ),
                category="accessibility",
                severity="medium",
                confidence="high",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    excerpt=line.strip()[:120],
                    description="<iframe> with no title attribute detected.",
                )],
                recommendation=(
                    "Add a descriptive title attribute that summarises the frame's content: "
                    "<iframe title=\"Payment form\" ...>. For purely decorative iframes, "
                    "add title=\"\" and aria-hidden=\"true\"."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            ))
        return findings

    # ------------------------------------------------------------------
    # Check 6 — <html> without lang attribute (HTML files only)
    # ------------------------------------------------------------------

    def _check_html_no_lang(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        lines = file.text.splitlines()  # type: ignore[union-attr]

        for i, line in enumerate(lines):
            if not _HTML_TAG_PATTERN.search(line):
                continue
            ctx = _context(lines, i)
            if _LANG_ATTR_PATTERN.search(ctx):
                continue
            findings.append(Finding(
                id=stable_finding_id(self.id, "html_no_lang", f"{file.path}:{i}"),
                title="<html> element missing lang attribute",
                description=(
                    "The root <html> element has no lang attribute. Screen readers use the "
                    "language tag to select the correct voice profile, pronunciation rules, "
                    "and Braille table. Without it, the content may be announced in the "
                    "user's default language setting regardless of the page's actual language. "
                    "WCAG 2.1 SC 3.1.1 (Language of Page, Level A) requires this attribute."
                ),
                category="accessibility",
                severity="medium",
                confidence="high",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    excerpt=line.strip()[:120],
                    description="<html> tag with no lang attribute detected.",
                )],
                recommendation=(
                    "Add a BCP 47 language tag to the <html> element: <html lang=\"en\"> "
                    "for English. Use a regional subtag where relevant (lang=\"en-US\", "
                    "lang=\"pt-BR\"). In Next.js or frameworks that generate the <html> tag, "
                    "set it in the root layout or _document component."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            ))
        return findings

    # ------------------------------------------------------------------
    # Check 7 — empty or icon-only interactive element
    # ------------------------------------------------------------------

    def _check_empty_interactive(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        lines = file.text.splitlines()  # type: ignore[union-attr]

        for i, line in enumerate(lines):
            match = _EMPTY_INTERACTIVE_PATTERN.search(line)
            if not match:
                continue
            # Suppress if visible text exists inside the tag
            if _HAS_TEXT_PATTERN.search(match.group(0)):
                continue
            # Suppress if aria-label is present on the same line
            if _ARIA_LABEL_PATTERN.search(line):
                continue
            findings.append(Finding(
                id=stable_finding_id(self.id, "empty_interactive_element", f"{file.path}:{i}"),
                title="Interactive element with no accessible label",
                description=(
                    "A <button> or <a> element appears to have no visible text content "
                    "and no aria-label or aria-labelledby attribute. Icon-only buttons "
                    "and empty links are announced only by their role ('button' or 'link') "
                    "with no purpose, making them unusable for screen reader users. WCAG 2.1 "
                    "SC 4.1.2 (Name, Role, Value, Level A) and SC 2.4.6 require interactive "
                    "elements to have descriptive accessible names."
                ),
                category="accessibility",
                severity="medium",
                confidence="medium",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    excerpt=line.strip()[:120],
                    description="Interactive element with no visible text or aria-label detected.",
                )],
                recommendation=(
                    "Add aria-label=\"Action description\" to icon-only buttons and links. "
                    "Alternatively, include a visually hidden text label using a screen-reader-only "
                    "CSS class (e.g., <span className=\"sr-only\">Close dialog</span>). "
                    "For <a> tags, ensure the href destination or purpose is described."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            ))
        return findings
