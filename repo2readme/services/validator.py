"""Comprehensive README validation and quality linting.

Checks a README (or any Markdown file) for structural problems, style
issues, broken internal references, placeholder content, and common
documentation anti-patterns. Pure static analysis — no API keys required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Severity and issue model
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Issue:
    """A single validation finding."""

    severity: Severity
    rule: str
    message: str
    line: int | None = None

    def __str__(self) -> str:
        loc = f"L{self.line}" if self.line else "---"
        return f"[{self.severity.value}] {self.rule} ({loc}): {self.message}"


@dataclass
class ValidationResult:
    """Aggregated results from a full validation pass."""

    issues: list[Issue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.INFO)

    @property
    def passed(self) -> bool:
        return self.error_count == 0

    def add(self, severity: Severity, rule: str, message: str, line: int | None = None) -> None:
        self.issues.append(Issue(severity, rule, message, line))


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*([A-Za-z0-9_+-]*)\s*$")
_MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
_BADGE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
_ANCHOR_STRIP = re.compile(r"[^\w\- ]", re.UNICODE)
_TRAILING_WS = re.compile(r"[ \t]+$")

# Common sections expected in a good README
_EXPECTED_SECTIONS = [
    "about",
    "feature",
    "installation",
    "install",
    "usage",
    "getting started",
    "quick start",
    "documentation",
    "config",
    "contributing",
    "license",
]

# Placeholder patterns in links and images
_PLACEHOLDER_TARGETS = (
    "path/to", "path_to", "your-", "your_", "yourusername",
    "your-username", "example.com", "<url>", "url-here",
    "insert-", "todo", "placeholder", "xxx", "changeme",
    "lorem", "sample",
)


# ---------------------------------------------------------------------------
# Inline helpers
# ---------------------------------------------------------------------------

def _github_anchor(heading: str) -> str:
    text = heading.strip().lower()
    text = _MD_LINK.sub(r"\1", text)
    text = text.replace("`", "")
    text = _ANCHOR_STRIP.sub("", text)
    return text.strip().replace(" ", "-")


def _iter_prose_lines(text: str):
    """Yield (line_number, line) for lines outside fenced code blocks."""
    fence: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        m = _FENCE.match(line)
        if m:
            marker = m.group(1)[0]
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            continue
        if fence is None:
            yield number, line


def _is_placeholder_target(target: str) -> bool:
    lowered = target.strip().lower()
    if not lowered:
        return True
    return any(p in lowered for p in _PLACEHOLDER_TARGETS)


# ---------------------------------------------------------------------------
# Individual rule checkers
# ---------------------------------------------------------------------------

def _check_structure(text: str, result: ValidationResult) -> None:
    """Check heading structure and required sections."""
    lines = text.splitlines()
    headings: list[tuple[int, str, int]] = []

    for i, line in enumerate(lines, 1):
        m = _HEADING.match(line)
        if m:
            headings.append((i, m.group(2).strip(), len(m.group(1))))

    # Must have exactly one H1
    h1s = [(ln, txt) for ln, txt, lvl in headings if lvl == 1]
    if not h1s:
        result.add(Severity.ERROR, "missing-h1", "No top-level heading (H1) found")
    elif len(h1s) > 1:
        names = ", ".join(f'"{t}"' for _, t in h1s)
        result.add(Severity.WARNING, "multiple-h1",
                   f"Multiple H1 headings found: {names}")

    # No heading should skip levels (e.g. H1 → H3)
    for i in range(1, len(headings)):
        prev_lvl = headings[i - 1][2]
        curr_lvl = headings[i][2]
        if curr_lvl > prev_lvl + 1:
            result.add(Severity.WARNING, "heading-skip",
                       f"Heading level jumps from H{prev_lvl} to H{curr_lvl}",
                       line=headings[i][0])

    # Check for expected sections
    all_headings_lower = " ".join(t.lower() for _, t, _ in headings)
    for section in _EXPECTED_SECTIONS:
        if section not in all_headings_lower:
            result.add(Severity.INFO, "missing-section",
                       f'Consider adding a "{section.title()}" section')


def _check_links(text: str, result: ValidationResult) -> None:
    """Check internal anchor links and placeholder targets."""
    headings = {_github_anchor(t): t for _, t, _ in
                ((m.group(2).strip(),) for line in text.splitlines()
                 if (m := _HEADING.match(line)))}
    # Rebuild properly
    heading_anchors: dict[str, str] = {}
    seen: dict[str, int] = {}
    for line in text.splitlines():
        m = _HEADING.match(line)
        if m:
            anchor = _github_anchor(m.group(2).strip())
            count = seen.get(anchor, 0)
            seen[anchor] = count + 1
            if count:
                anchor = f"{anchor}-{count}"
            heading_anchors[anchor] = m.group(2).strip()

    for line_no, line in _iter_prose_lines(text):
        # Check markdown links
        for m in _MD_LINK.finditer(line):
            label, target = m.group(1), m.group(2).strip()
            if target.startswith("#"):
                anchor = target.lstrip("#")
                if anchor not in heading_anchors:
                    result.add(Severity.ERROR, "broken-anchor",
                               f'Link "{label}" → {target} matches no heading',
                               line=line_no)
            elif target.startswith(("http://", "https://", "mailto:")):
                if _is_placeholder_target(target):
                    result.add(Severity.WARNING, "placeholder-link",
                               f'Link "{label}" has placeholder URL: {target}',
                               line=line_no)
            elif not target:
                result.add(Severity.WARNING, "empty-link",
                           f'Link "{label}" has empty target', line=line_no)

        # Check images
        for m in _MD_IMAGE.finditer(line):
            alt, target = m.group(1), m.group(2).strip()
            if _is_placeholder_target(target):
                result.add(Severity.WARNING, "placeholder-image",
                           f'Image "{alt}" has placeholder target: {target}',
                           line=line_no)


def _check_style(text: str, result: ValidationResult) -> None:
    """Check Markdown style and formatting issues."""
    lines = text.splitlines()

    for i, line in enumerate(lines, 1):
        # Trailing whitespace (except intentional line breaks with two spaces)
        if line.rstrip() != line and not line.endswith("  "):
            result.add(Severity.INFO, "trailing-whitespace",
                       "Trailing whitespace", line=i)

        # Inconsistent heading style (ATX vs Setext not checked — just trailing #)
        m = _HEADING.match(line)
        if m and m.group(2) != m.group(2).rstrip("#").rstrip():
            result.add(Severity.INFO, "trailing-hash",
                       "Heading has trailing # characters", line=i)

    # Check for bare URLs that should be links
    url_re = re.compile(r"(?<!\()(https?://[^\s\)\]>]+)")
    for line_no, line in _iter_prose_lines(text):
        # Skip lines that are already inside markdown links
        if "[" in line:
            for m in url_re.finditer(line):
                url = m.group(1)
                # Check it's not already part of a markdown link
                start = m.start()
                before = line[:start]
                if before.count("[") > before.count("]"):
                    continue  # inside a link
                result.add(Severity.INFO, "bare-url",
                           f"URL should be wrapped in a link: {url}",
                           line=line_no)

    # Table consistency
    in_table = False
    table_cols = 0
    for i, line in enumerate(lines, 1):
        is_row = bool(_TABLE_ROW.match(line))
        if is_row:
            if not in_table:
                in_table = True
                table_cols = line.count("|") - 1
            else:
                cols = line.count("|") - 1
                if cols != table_cols:
                    result.add(Severity.WARNING, "table-columns",
                               f"Table row has {cols} columns, expected {table_cols}",
                               line=i)
        else:
            in_table = False


def _check_content(text: str, result: ValidationResult) -> None:
    """Check for content quality issues."""
    # Empty document
    if not text.strip():
        result.add(Severity.ERROR, "empty", "Document is empty")
        return

    # Code block balance
    fence_count = 0
    for line in text.splitlines():
        if _FENCE.match(line):
            fence_count += 1
    if fence_count % 2:
        result.add(Severity.ERROR, "unclosed-fence",
                   f"Unmatched code fence ({fence_count} fence markers found)")

    # TODO / FIXME / HACK markers
    todo_re = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
    for line_no, line in _iter_prose_lines(text):
        m = todo_re.search(line)
        if m:
            result.add(Severity.WARNING, "todo-marker",
                       f"Found {m.group(0)} marker", line=line_no)

    # Long lines (> 120 chars) — info only
    for line_no, line in enumerate(text.splitlines(), 1):
        if len(line) > 120 and not _FENCE.match(line):
            result.add(Severity.INFO, "long-line",
                       f"Line exceeds 120 characters ({len(line)})", line=line_no)

    # Excessive blank lines (> 2 consecutive)
    blank_count = 0
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            blank_count += 1
            if blank_count > 2:
                result.add(Severity.INFO, "excessive-blanks",
                           "More than 2 consecutive blank lines", line=i)
        else:
            blank_count = 0


def _check_badges(text: str, result: ValidationResult) -> None:
    """Validate badge image links."""
    for line_no, line in _iter_prose_lines(text):
        for m in _BADGE.finditer(line):
            alt, target = m.group(1), m.group(2).strip()
            # Badges are images, so placeholder check already covered by _check_links
            # Check for common badge anti-patterns
            if alt and not target:
                result.add(Severity.WARNING, "badge-no-url",
                           f"Badge \"{alt}\" has no image URL", line=line_no)
            if target and not alt:
                result.add(Severity.INFO, "badge-no-alt",
                           f"Badge has no alt text", line=line_no)


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------

def validate_readme(text: str) -> ValidationResult:
    """Run all validation rules against the README content.

    Returns a :class:`ValidationResult` with all issues found.
    """
    result = ValidationResult()

    _check_structure(text, result)
    _check_links(text, result)
    _check_style(text, result)
    _check_content(text, result)
    _check_badges(text, result)

    return result


def validate_file(path: str) -> ValidationResult:
    """Read a file and validate it."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        result = ValidationResult()
        result.add(Severity.ERROR, "file-not-found", f"File not found: {path}")
        return result
    except UnicodeDecodeError:
        result = ValidationResult()
        result.add(Severity.ERROR, "encoding-error",
                   f"Cannot read file (encoding issue): {path}")
        return result

    return validate_readme(content)


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_result(result: ValidationResult, source_name: str = "README") -> str:
    """Render validation results as a human-readable string."""
    lines: list[str] = []
    lines.append(f"Validating {source_name}")
    lines.append("=" * (len(source_name) + 11))

    if not result.issues:
        lines.append("[PASS] All checks passed!")
        return "\n".join(lines)

    for issue in sorted(result.issues, key=lambda i: (i.severity.value, i.line or 0)):
        icon = {"error": "[ERROR]", "warning": "[WARN] ", "info": "[INFO] "}[issue.severity.value]
        lines.append(f"  {icon} {issue}")

    lines.append("")
    total = len(result.issues)
    lines.append(f"Found {total} issue(s): "
                 f"{result.error_count} error(s), "
                 f"{result.warning_count} warning(s), "
                 f"{result.info_count} info")

    return "\n".join(lines)
