"""Tests for repo2readme.services.cache_manager — summary cache management."""

from __future__ import annotations

import json
import os
import time

import pytest

from repo2readme.services.cache_manager import (
    CacheEntryInfo,
    CacheOperation,
    CacheStats,
    clear_cache,
    get_cache_stats,
    get_entry_detail,
    list_entries,
    prune_stale_entries,
)


def _make_cache(dir_path: str, entries: list[dict] | None = None) -> str:
    """Create a cache file with the given entries and return its path."""
    os.makedirs(dir_path, exist_ok=True)
    cache_file = os.path.join(dir_path, "summaries.json")
    data = {
        "schema_version": "1.0",
        "config_hash": "abc123",
        "entries": entries or [],
    }
    with open(cache_file, "w") as f:
        json.dump(data, f)
    return cache_file


def _entry(file_path: str = "/repo/src/main.py", language: str = "python",
           content_hash: str = "hash123", mtime: float | None = None,
           description: str = "A module") -> dict:
    if mtime is None:
        mtime = time.time()
    return {
        "file_path": file_path,
        "language": language,
        "content_hash": content_hash,
        "mtime": mtime,
        "summary": {"description": description},
    }


# ---------------------------------------------------------------------------
# CacheEntryInfo
# ---------------------------------------------------------------------------

class TestCacheEntryInfo:
    def test_age_just_now(self):
        e = CacheEntryInfo("/a.py", "python", "abc", time.time(), "Mod")
        assert e.age_display == "just now"

    def test_age_minutes(self):
        e = CacheEntryInfo("/a.py", "python", "abc", time.time() - 300, "Mod")
        assert "m ago" in e.age_display

    def test_age_hours(self):
        e = CacheEntryInfo("/a.py", "python", "abc", time.time() - 7200, "Mod")
        assert "h ago" in e.age_display

    def test_age_days(self):
        e = CacheEntryInfo("/a.py", "python", "abc", time.time() - 172800, "Mod")
        assert "d ago" in e.age_display

    def test_age_unknown(self):
        e = CacheEntryInfo("/a.py", "python", "abc", 0, "Mod")
        assert e.age_display == "unknown"


# ---------------------------------------------------------------------------
# get_cache_stats
# ---------------------------------------------------------------------------

class TestGetCacheStats:
    def test_no_cache(self, tmp_path):
        stats = get_cache_stats(str(tmp_path / "no-cache"))
        assert stats.cache_exists is False
        assert stats.total_entries == 0

    def test_empty_cache(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        _make_cache(cache_dir, entries=[])
        stats = get_cache_stats(cache_dir)
        assert stats.cache_exists is True
        assert stats.total_entries == 0

    def test_with_entries(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        entries = [
            _entry("/repo/a.py", "python", description="Module A"),
            _entry("/repo/b.js", "javascript", description="Module B"),
            _entry("/repo/c.py", "python", description="Module C"),
        ]
        _make_cache(cache_dir, entries)
        stats = get_cache_stats(cache_dir)
        assert stats.total_entries == 3
        assert stats.languages == {"python": 2, "javascript": 1}
        assert len(stats.entries) == 3

    def test_schema_and_config(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        _make_cache(cache_dir)
        stats = get_cache_stats(cache_dir)
        assert stats.schema_version == "1.0"
        assert stats.config_hash.startswith("abc123")

    def test_cache_size(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        _make_cache(cache_dir, entries=[_entry()])
        stats = get_cache_stats(cache_dir)
        assert stats.cache_size_bytes > 0


# ---------------------------------------------------------------------------
# list_entries
# ---------------------------------------------------------------------------

class TestListEntries:
    def test_no_cache(self, tmp_path):
        assert list_entries(str(tmp_path / "no-cache")) == []

    def test_list_all(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        entries = [_entry("/a.py", "python"), _entry("/b.js", "javascript")]
        _make_cache(cache_dir, entries)
        result = list_entries(cache_dir)
        assert len(result) == 2

    def test_filter_by_language(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        entries = [_entry("/a.py", "python"), _entry("/b.js", "javascript")]
        _make_cache(cache_dir, entries)
        result = list_entries(cache_dir, language="python")
        assert len(result) == 1
        assert result[0].language == "python"

    def test_limit(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        entries = [_entry(f"/repo/{i}.py") for i in range(10)]
        _make_cache(cache_dir, entries)
        result = list_entries(cache_dir, limit=3)
        assert len(result) == 3

    def test_preview_from_summary(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        _make_cache(cache_dir, [_entry(description="Core module logic")])
        result = list_entries(cache_dir)
        assert result[0].summary_preview == "Core module logic"

    def test_preview_from_string_summary(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        entry = _entry()
        entry["summary"] = "A string summary"
        _make_cache(cache_dir, [entry])
        result = list_entries(cache_dir)
        assert result[0].summary_preview == "A string summary"


# ---------------------------------------------------------------------------
# clear_cache
# ---------------------------------------------------------------------------

class TestClearCache:
    def test_clear_existing(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        _make_cache(cache_dir, [_entry(), _entry("/b.py")])
        result = clear_cache(cache_dir)
        assert result.success is True
        assert result.entries_affected == 2
        assert not os.path.exists(os.path.join(cache_dir, "summaries.json"))

    def test_clear_nonexistent(self, tmp_path):
        result = clear_cache(str(tmp_path / "empty"))
        assert result.success is True
        assert result.entries_affected == 0

    def test_clear_removes_temp_files(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        _make_cache(cache_dir, [_entry()])
        # Create a temp file
        with open(os.path.join(cache_dir, "summaries_123.json.tmp"), "w") as f:
            f.write("temp")
        clear_cache(cache_dir)
        assert not os.path.exists(os.path.join(cache_dir, "summaries_123.json.tmp"))


# ---------------------------------------------------------------------------
# prune_stale_entries
# ---------------------------------------------------------------------------

class TestPruneStaleEntries:
    def test_prune_deleted_files(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        entries = [
            _entry("/repo/exists.py"),
            _entry("/repo/deleted.py"),
        ]
        _make_cache(cache_dir, entries)
        result = prune_stale_entries(cache_dir, current_files={"/repo/exists.py"})
        assert result.success is True
        assert result.entries_affected == 1
        # Verify only exists.py remains
        remaining = list_entries(cache_dir)
        assert len(remaining) == 1
        assert remaining[0].file_path == "/repo/exists.py"

    def test_prune_old_entries(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        old_time = time.time() - 86400 * 10  # 10 days ago
        entries = [
            _entry("/repo/old.py", mtime=old_time),
            _entry("/repo/new.py", mtime=time.time()),
        ]
        _make_cache(cache_dir, entries)
        result = prune_stale_entries(cache_dir, max_age_seconds=86400 * 7)
        assert result.success is True
        assert result.entries_affected == 1

    def test_prune_nothing_to_prune(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        _make_cache(cache_dir, [_entry()])
        result = prune_stale_entries(cache_dir, current_files={"/repo/src/main.py"})
        assert result.success is True
        assert result.entries_affected == 0

    def test_prune_no_cache(self, tmp_path):
        result = prune_stale_entries(str(tmp_path / "empty"))
        assert result.success is False

    def test_prune_combined(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        old_time = time.time() - 86400 * 20
        entries = [
            _entry("/repo/exists.py", mtime=time.time()),
            _entry("/repo/deleted.py", mtime=time.time()),
            _entry("/repo/old.py", mtime=old_time),
        ]
        _make_cache(cache_dir, entries)
        result = prune_stale_entries(
            cache_dir,
            current_files={"/repo/exists.py", "/repo/old.py"},
            max_age_seconds=86400 * 7,
        )
        assert result.entries_affected == 2  # deleted + old


# ---------------------------------------------------------------------------
# get_entry_detail
# ---------------------------------------------------------------------------

class TestGetEntryDetail:
    def test_found(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        _make_cache(cache_dir, [_entry("/repo/main.py", description="Main module")])
        detail = get_entry_detail(cache_dir, "/repo/main.py")
        assert detail is not None
        assert detail.file_path == "/repo/main.py"

    def test_not_found(self, tmp_path):
        cache_dir = str(tmp_path / "cache")
        _make_cache(cache_dir, [_entry("/repo/main.py")])
        detail = get_entry_detail(cache_dir, "/repo/other.py")
        assert detail is None

    def test_no_cache(self, tmp_path):
        detail = get_entry_detail(str(tmp_path / "empty"), "/repo/main.py")
        assert detail is None
