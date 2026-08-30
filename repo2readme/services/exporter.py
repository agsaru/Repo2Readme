"""Structured export of repository analysis results.

Provides JSON, CSV, and Markdown manifest exporters for file summaries,
language metadata, and directory structure. Designed for CI/CD pipelines,
documentation generators, and code review tooling — no API keys required.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Any

from repo2readme.utils.detect_language import detect_lang


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class FileEntry:
    """Single file record for export."""

    file_path: str
    relative_path: str
    language: str
    size_bytes: int
    line_count: int
    summary: dict | None = None

    def to_dict(self) -> dict:
        d = {
            "file_path": self.file_path,
            "relative_path": self.relative_path,
            "language": self.language,
            "size_bytes": self.size_bytes,
            "line_count": self.line_count,
        }
        if self.summary:
            # Flatten the summary for structured output
            d["description"] = self.summary.get("description", "")
            d["purpose"] = self.summary.get("purpose", "")
            d["key_classes"] = self.summary.get("key_classes", [])
            d["key_functions"] = self.summary.get("key_functions", [])
            d["dependencies"] = self.summary.get("dependencies", [])
        return d


@dataclass
class ExportResult:
    """Complete export dataset."""

    entries: list[FileEntry] = field(default_factory=list)
    total_files: int = 0
    total_size_bytes: int = 0
    languages: dict[str, int] = field(default_factory=dict)

    def add_entry(self, entry: FileEntry) -> None:
        self.entries.append(entry)
        self.total_files += 1
        self.total_size_bytes += entry.size_bytes
        self.languages[entry.language] = self.languages.get(entry.language, 0) + 1

    def filtered(
        self,
        languages: set[str] | None = None,
        path_pattern: str | None = None,
    ) -> list[FileEntry]:
        """Return entries matching optional language and path filters."""
        result = self.entries
        if languages:
            result = [e for e in result if e.language in languages]
        if path_pattern:
            pat = re.compile(path_pattern)
            result = [e for e in result if pat.search(e.relative_path)]
        return result


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_export_result(
    documents: list[dict],
    summaries: list[dict] | None = None,
) -> ExportResult:
    """Build an ExportResult from loaded documents and optional summaries.

    Parameters
    ----------
    documents:
        List of dicts with ``content`` and ``metadata`` keys, as produced
        by the traversal pipeline.
    summaries:
        Optional list of summary dicts (output of the summarization step).
        If provided, they are matched to documents by file_path.
    """
    result = ExportResult()

    # Index summaries by file_path for O(1) lookup
    summary_map: dict[str, dict] = {}
    if summaries:
        for s in summaries:
            if isinstance(s, dict) and "file_path" in s:
                summary_map[s["file_path"]] = s

    for doc in documents:
        meta = doc.get("metadata", {})
        content = doc.get("content", "")
        file_path = meta.get("file_path", "")
        relative_path = meta.get("relative_path", "")

        if not file_path:
            continue

        language = meta.get("language") or detect_lang(file_path, content)
        size_bytes = len(content.encode("utf-8")) if isinstance(content, str) else 0
        line_count = len(content.splitlines()) if isinstance(content, str) else 0
        summary = summary_map.get(file_path)

        result.add_entry(
            FileEntry(
                file_path=file_path,
                relative_path=relative_path,
                language=language,
                size_bytes=size_bytes,
                line_count=line_count,
                summary=summary,
            )
        )

    return result


# ---------------------------------------------------------------------------
# JSON exporter
# ---------------------------------------------------------------------------

def export_json(
    result: ExportResult,
    pretty: bool = True,
    include_summaries: bool = True,
) -> str:
    """Export the full result as a JSON string."""
    data = {
        "total_files": result.total_files,
        "total_size_bytes": result.total_size_bytes,
        "languages": result.languages,
        "files": [],
    }
    for entry in result.entries:
        d = {
            "file_path": entry.file_path,
            "relative_path": entry.relative_path,
            "language": entry.language,
            "size_bytes": entry.size_bytes,
            "line_count": entry.line_count,
        }
        if include_summaries and entry.summary:
            d["summary"] = entry.summary
        data["files"].append(d)

    return json.dumps(data, indent=2 if pretty else None, default=str)


# ---------------------------------------------------------------------------
# CSV exporter
# ---------------------------------------------------------------------------

_CSV_COLUMNS = [
    "relative_path",
    "language",
    "size_bytes",
    "line_count",
    "description",
]


def export_csv(
    result: ExportResult,
    entries: list[FileEntry] | None = None,
) -> str:
    """Export entries as CSV. Returns a string (no file I/O)."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()

    source = entries if entries is not None else result.entries
    for entry in source:
        row = {
            "relative_path": entry.relative_path,
            "language": entry.language,
            "size_bytes": entry.size_bytes,
            "line_count": entry.line_count,
            "description": (entry.summary or {}).get("description", ""),
        }
        writer.writerow(row)

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Markdown manifest exporter
# ---------------------------------------------------------------------------

def export_markdown(
    result: ExportResult,
    entries: list[FileEntry] | None = None,
    title: str = "Repository File Manifest",
) -> str:
    """Export a Markdown-formatted file manifest with language sections."""
    source = entries if entries is not None else result.entries

    # Group by language
    by_lang: dict[str, list[FileEntry]] = {}
    for entry in source:
        by_lang.setdefault(entry.language, []).append(entry)

    lines = [f"# {title}\n"]
    lines.append(f"> Generated by repo2readme • "
                 f"{result.total_files} files • "
                 f"{result.total_size_bytes:,} bytes\n")

    # Language summary table
    lines.append("## Language Summary\n")
    lines.append("| Language | Files | Total Lines | Avg Lines/File |")
    lines.append("|----------|------:|------------:|---------------:|")
    for lang in sorted(by_lang.keys()):
        entries_lang = by_lang[lang]
        total_lines = sum(e.line_count for e in entries_lang)
        avg = total_lines // len(entries_lang) if entries_lang else 0
        lines.append(f"| {lang} | {len(entries_lang)} | {total_lines:,} | {avg} |")
    lines.append("")

    # Per-language file listings
    for lang in sorted(by_lang.keys()):
        lines.append(f"## {lang.title()}\n")
        lang_entries = sorted(by_lang[lang], key=lambda e: e.relative_path)
        for entry in lang_entries:
            size_kb = entry.size_bytes / 1024
            desc = ""
            if entry.summary:
                desc = entry.summary.get("description", "")
                if desc:
                    desc = f" — {desc[:80]}"
            lines.append(f"- `{entry.relative_path}` "
                         f"({entry.line_count} lines, {size_kb:.1f} KB){desc}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# File writers
# ---------------------------------------------------------------------------

def write_export(
    content: str,
    output_path: str,
    force: bool = False,
) -> None:
    """Write exported content to a file, with optional overwrite protection."""
    path = os.path.abspath(output_path)
    if os.path.exists(path) and not force:
        raise FileExistsError(f"Output file already exists: {path}")

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
