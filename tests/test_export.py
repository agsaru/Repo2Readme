"""Tests for repo2readme.services.exporter — structured export of repository analysis."""

from __future__ import annotations

import csv
import io
import json

import pytest

from repo2readme.services.exporter import (
    ExportResult,
    FileEntry,
    build_export_result,
    export_csv,
    export_json,
    export_markdown,
    write_export,
)


def _make_doc(content: str = "x = 1", file_path: str = "/repo/src/main.py",
              relative_path: str = "src/main.py") -> dict:
    return {"content": content, "metadata": {"file_path": file_path, "relative_path": relative_path}}


def _make_summary(file_path: str, description: str = "A module") -> dict:
    return {"file_path": file_path, "description": description, "purpose": "Core logic"}


# ---------------------------------------------------------------------------
# FileEntry
# ---------------------------------------------------------------------------

class TestFileEntry:
    def test_to_dict_basic(self):
        e = FileEntry("/repo/a.py", "a.py", "python", 100, 10)
        d = e.to_dict()
        assert d["file_path"] == "/repo/a.py"
        assert d["language"] == "python"
        assert d["size_bytes"] == 100
        assert "description" not in d

    def test_to_dict_with_summary(self):
        e = FileEntry("/repo/a.py", "a.py", "python", 100, 10,
                      summary={"description": "Module", "key_classes": ["Foo"]})
        d = e.to_dict()
        assert d["description"] == "Module"
        assert d["key_classes"] == ["Foo"]


# ---------------------------------------------------------------------------
# ExportResult
# ---------------------------------------------------------------------------

class TestExportResult:
    def test_add_entry(self):
        r = ExportResult()
        r.add_entry(FileEntry("/a", "a.py", "python", 50, 5))
        r.add_entry(FileEntry("/b", "b.js", "javascript", 30, 3))
        assert r.total_files == 2
        assert r.total_size_bytes == 80
        assert r.languages == {"python": 1, "javascript": 1}

    def test_filtered_by_language(self):
        r = ExportResult()
        r.add_entry(FileEntry("/a", "a.py", "python", 50, 5))
        r.add_entry(FileEntry("/b", "b.js", "javascript", 30, 3))
        filtered = r.filtered(languages={"python"})
        assert len(filtered) == 1
        assert filtered[0].language == "python"

    def test_filtered_by_path(self):
        r = ExportResult()
        r.add_entry(FileEntry("/a", "src/main.py", "python", 50, 5))
        r.add_entry(FileEntry("/b", "tests/test.py", "python", 30, 3))
        filtered = r.filtered(path_pattern=r"^tests/")
        assert len(filtered) == 1
        assert "tests" in filtered[0].relative_path

    def test_filtered_combined(self):
        r = ExportResult()
        r.add_entry(FileEntry("/a", "src/main.py", "python", 50, 5))
        r.add_entry(FileEntry("/b", "src/app.js", "javascript", 30, 3))
        r.add_entry(FileEntry("/c", "tests/test.py", "python", 20, 2))
        filtered = r.filtered(languages={"python"}, path_pattern=r"^src/")
        assert len(filtered) == 1
        assert filtered[0].relative_path == "src/main.py"

    def test_empty_result(self):
        r = ExportResult()
        assert r.total_files == 0
        assert r.filtered() == []


# ---------------------------------------------------------------------------
# build_export_result
# ---------------------------------------------------------------------------

class TestBuildExportResult:
    def test_basic(self):
        docs = [_make_doc("hello", "/repo/a.py", "a.py")]
        result = build_export_result(docs)
        assert result.total_files == 1
        assert result.entries[0].language == "python"

    def test_with_summaries(self):
        docs = [_make_doc("x = 1", "/repo/a.py", "a.py")]
        summaries = [_make_summary("/repo/a.py", "Main module")]
        result = build_export_result(docs, summaries)
        assert result.entries[0].summary is not None
        assert result.entries[0].summary["description"] == "Main module"

    def test_empty_metadata_skipped(self):
        docs = [{"content": "hi", "metadata": {}}]
        result = build_export_result(docs)
        assert result.total_files == 0

    def test_language_detection(self):
        docs = [
            _make_doc("console.log('hi')", "/repo/a.js", "a.js"),
            _make_doc("<h1>Hi</h1>", "/repo/b.html", "b.html"),
        ]
        result = build_export_result(docs)
        assert "javascript" in result.languages

    def test_size_calculation(self):
        content = "x = 1\n" * 100
        docs = [_make_doc(content, "/repo/big.py", "big.py")]
        result = build_export_result(docs)
        assert result.entries[0].line_count == 100


# ---------------------------------------------------------------------------
# export_json
# ---------------------------------------------------------------------------

class TestExportJson:
    def test_basic_structure(self):
        result = ExportResult()
        result.add_entry(FileEntry("/a", "a.py", "python", 50, 5))
        output = export_json(result)
        data = json.loads(output)
        assert data["total_files"] == 1
        assert len(data["files"]) == 1
        assert data["files"][0]["relative_path"] == "a.py"

    def test_compact_mode(self):
        result = ExportResult()
        result.add_entry(FileEntry("/a", "a.py", "python", 50, 5))
        output = export_json(result, pretty=False)
        assert "\n" not in output or output.count("\n") < 3

    def test_with_summaries(self):
        result = ExportResult()
        result.add_entry(FileEntry("/a", "a.py", "python", 50, 5,
                                   summary={"description": "Mod"}))
        output = export_json(result, include_summaries=True)
        data = json.loads(output)
        assert "summary" in data["files"][0]

    def test_without_summaries(self):
        result = ExportResult()
        result.add_entry(FileEntry("/a", "a.py", "python", 50, 5,
                                   summary={"description": "Mod"}))
        output = export_json(result, include_summaries=False)
        data = json.loads(output)
        assert "summary" not in data["files"][0]

    def test_multiple_languages(self):
        result = ExportResult()
        result.add_entry(FileEntry("/a", "a.py", "python", 50, 5))
        result.add_entry(FileEntry("/b", "b.js", "javascript", 30, 3))
        data = json.loads(export_json(result))
        assert data["languages"] == {"python": 1, "javascript": 1}


# ---------------------------------------------------------------------------
# export_csv
# ---------------------------------------------------------------------------

class TestExportCsv:
    def test_header_and_row(self):
        result = ExportResult()
        result.add_entry(FileEntry("/a", "a.py", "python", 50, 10))
        output = export_csv(result)
        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["relative_path"] == "a.py"
        assert rows[0]["language"] == "python"

    def test_with_description(self):
        result = ExportResult()
        result.add_entry(FileEntry("/a", "a.py", "python", 50, 10,
                                   summary={"description": "Main module"}))
        output = export_csv(result)
        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)
        assert rows[0]["description"] == "Main module"

    def test_empty_result(self):
        result = ExportResult()
        output = export_csv(result)
        reader = csv.DictReader(io.StringIO(output))
        assert list(reader) == []

    def test_filtered_subset(self):
        result = ExportResult()
        result.add_entry(FileEntry("/a", "src/a.py", "python", 50, 5))
        result.add_entry(FileEntry("/b", "tests/b.py", "python", 30, 3))
        filtered = result.filtered(path_pattern=r"^tests/")
        output = export_csv(result, entries=filtered)
        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)
        assert len(rows) == 1
        assert "tests" in rows[0]["relative_path"]


# ---------------------------------------------------------------------------
# export_markdown
# ---------------------------------------------------------------------------

class TestExportMarkdown:
    def test_title(self):
        result = ExportResult()
        result.add_entry(FileEntry("/a", "a.py", "python", 50, 10))
        output = export_markdown(result, title="My Manifest")
        assert "# My Manifest" in output

    def test_language_sections(self):
        result = ExportResult()
        result.add_entry(FileEntry("/a", "a.py", "python", 50, 10))
        result.add_entry(FileEntry("/b", "b.js", "javascript", 30, 5))
        output = export_markdown(result)
        assert "## Python" in output
        assert "## Javascript" in output

    def test_file_listing(self):
        result = ExportResult()
        result.add_entry(FileEntry("/a", "src/main.py", "python", 500, 50))
        output = export_markdown(result)
        assert "`src/main.py`" in output
        assert "50 lines" in output

    def test_with_description(self):
        result = ExportResult()
        result.add_entry(FileEntry("/a", "a.py", "python", 50, 10,
                                   summary={"description": "Core module"}))
        output = export_markdown(result)
        assert "Core module" in output

    def test_empty_result(self):
        result = ExportResult()
        output = export_markdown(result)
        assert "# Repository File Manifest" in output

    def test_summary_table(self):
        result = ExportResult()
        result.add_entry(FileEntry("/a", "a.py", "python", 50, 10))
        result.add_entry(FileEntry("/b", "b.py", "python", 60, 20))
        output = export_markdown(result)
        assert "2" in output  # file count in summary table
        assert "Language Summary" in output

    def test_sorted_output(self):
        result = ExportResult()
        result.add_entry(FileEntry("/c", "c.py", "python", 50, 5))
        result.add_entry(FileEntry("/a", "a.py", "python", 50, 5))
        result.add_entry(FileEntry("/b", "b.js", "javascript", 30, 3))
        output = export_markdown(result)
        lines = output.split("\n")
        py_lines = [l for l in lines if l.startswith("- `") and ".py" in l]
        assert "`a.py`" in py_lines[0]
        assert "`c.py`" in py_lines[1]


# ---------------------------------------------------------------------------
# write_export
# ---------------------------------------------------------------------------

class TestWriteExport:
    def test_write_and_read(self, tmp_path):
        out = tmp_path / "out.json"
        write_export('{"ok": true}', str(out))
        assert out.read_text() == '{"ok": true}'

    def test_no_overwrite(self, tmp_path):
        out = tmp_path / "out.json"
        write_export("first", str(out))
        with pytest.raises(FileExistsError):
            write_export("second", str(out))

    def test_force_overwrite(self, tmp_path):
        out = tmp_path / "out.json"
        write_export("first", str(out))
        write_export("second", str(out), force=True)
        assert out.read_text() == "second"

    def test_creates_parent_dirs(self, tmp_path):
        out = tmp_path / "sub" / "dir" / "out.json"
        write_export("data", str(out))
        assert out.exists()

    def test_relative_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        write_export("test", "output.txt")
        assert (tmp_path / "output.txt").exists()
