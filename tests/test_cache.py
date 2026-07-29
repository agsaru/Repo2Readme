"""
Comprehensive tests for the summary cache system.

Covers:
- first execution (cache miss)
- second execution (cache hit)
- modified file
- deleted file
- corrupted cache
- configuration change
- empty repository
- partial cache availability
"""
import json
import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

from repo2readme.cache import SummaryCache, CACHE_SCHEMA_VERSION


@pytest.fixture
def cache_dir():
    """Provide a temporary cache directory."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def config():
    """Default summarization configuration."""
    return {
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "base_url": None,
    }


@pytest.fixture
def prompt_hash():
    """A stable prompt template hash."""
    return "abc123def456"


@pytest.fixture
def cache(cache_dir, config, prompt_hash):
    """Provide a fresh SummaryCache instance."""
    return SummaryCache(
        cache_dir=cache_dir,
        config=config,
        prompt_template_hash=prompt_hash,
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_summary(file_path, description="test description"):
    return {
        "file_path": file_path,
        "description": description,
        "functions": ["func_a", "func_b"],
    }


# ===================================================================
# 1. First execution (cache miss)
# ===================================================================

class TestFirstExecution:
    def test_cache_miss_returns_none(self, cache):
        """On first run, no cache entry exists -> get() returns None."""
        result = cache.get(
            file_path="/repo/main.py",
            content="print('hello')",
            language="python",
        )
        assert result is None

    def test_cache_miss_then_put_saves_entry(self, cache):
        """After a miss, put() stores the entry and subsequent get() returns it."""
        file_path = "/repo/main.py"
        content = "print('hello')"
        language = "python"
        summary = _make_summary(file_path)

        # First call: miss
        assert cache.get(file_path, content, language) is None

        # Store
        cache.put(file_path, content, language, summary, mtime=1000.0)

        # Second call: hit
        result = cache.get(file_path, content, language)
        assert result == summary

    def test_cache_persists_across_instances(self, cache_dir, config, prompt_hash):
        """Cache data survives SummaryCache re-creation."""
        c1 = SummaryCache(cache_dir, config, prompt_hash)
        c1.put("/repo/main.py", "content", "python", _make_summary("/repo/main.py"), mtime=1.0)

        c2 = SummaryCache(cache_dir, config, prompt_hash)
        result = c2.get("/repo/main.py", "content", "python")
        assert result is not None
        assert result["description"] == "test description"


# ===================================================================
# 2. Second execution (cache hit)
# ===================================================================

class TestCacheHit:
    def test_cache_hit_returns_cached_summary(self, cache):
        """Unchanged file returns cached summary."""
        file_path = "/repo/utils.py"
        content = "def add(a, b): return a + b"
        language = "python"
        summary = _make_summary(file_path, "utility functions")

        cache.put(file_path, content, language, summary, mtime=2000.0)
        result = cache.get(file_path, content, language)

        assert result == summary

    def test_cache_hit_multiple_files(self, cache):
        """Multiple cached files all return correctly."""
        files = {
            "/repo/main.py": ("print('hi')", "python", _make_summary("/repo/main.py", "entry point")),
            "/repo/utils.py": ("def util(): pass", "python", _make_summary("/repo/utils.py", "utilities")),
            "/repo/config.json": ('{"key": "val"}', "json", _make_summary("/repo/config.json", "config")),
        }
        for fpath, (content, lang, summary) in files.items():
            cache.put(fpath, content, lang, summary, mtime=1.0)

        for fpath, (content, lang, summary) in files.items():
            result = cache.get(fpath, content, lang)
            assert result == summary, f"Mismatch for {fpath}"


# ===================================================================
# 3. Modified file
# ===================================================================

class TestModifiedFile:
    def test_modified_content_returns_none(self, cache):
        """If file content changes, cache returns None (miss)."""
        file_path = "/repo/main.py"
        original_content = "print('hello')"
        new_content = "print('goodbye')"
        language = "python"

        cache.put(file_path, original_content, language, _make_summary(file_path), mtime=1.0)

        # Same path, different content -> miss
        assert cache.get(file_path, new_content, language) is None

    def test_modified_content_then_put_updates_cache(self, cache):
        """After modifying content and re-summarizing, cache reflects new data."""
        file_path = "/repo/main.py"
        language = "python"

        # Original
        cache.put(file_path, "v1", language, _make_summary(file_path, "v1"), mtime=1.0)
        assert cache.get(file_path, "v1", language)["description"] == "v1"

        # Modified
        cache.put(file_path, "v2", language, _make_summary(file_path, "v2"), mtime=2.0)
        assert cache.get(file_path, "v1", language) is None  # old content no longer matches
        assert cache.get(file_path, "v2", language)["description"] == "v2"


# ===================================================================
# 4. Deleted file
# ===================================================================

class TestDeletedFile:
    def test_get_deleted_files_returns_removed_entries(self, cache):
        """get_deleted_files() identifies entries not in current_files."""
        cache.put("/repo/main.py", "a", "python", _make_summary("/repo/main.py"), mtime=1.0)
        cache.put("/repo/utils.py", "b", "python", _make_summary("/repo/utils.py"), mtime=1.0)

        deleted = cache.get_deleted_files({"/repo/main.py"})
        assert len(deleted) == 1
        assert deleted[0]["file_path"] == "/repo/utils.py"

    def test_remove_entries_cleans_up(self, cache):
        """remove_entries() removes specified entries from cache."""
        cache.put("/repo/main.py", "a", "python", _make_summary("/repo/main.py"), mtime=1.0)
        cache.put("/repo/utils.py", "b", "python", _make_summary("/repo/utils.py"), mtime=1.0)

        cache.remove_entries(["/repo/main.py"])
        assert cache.get("/repo/main.py", "a", "python") is None
        assert cache.get("/repo/utils.py", "b", "python") is not None

    def test_no_deleted_files_when_all_present(self, cache):
        """If all cached files are in current_files, get_deleted_files returns empty."""
        cache.put("/repo/main.py", "a", "python", _make_summary("/repo/main.py"), mtime=1.0)
        assert cache.get_deleted_files({"/repo/main.py"}) == []


# ===================================================================
# 5. Corrupted cache
# ===================================================================

class TestCorruptedCache:
    def test_corrupted_json_rebuilds(self, cache_dir, config, prompt_hash):
        """If cache file contains invalid JSON, it is rebuilt silently."""
        os.makedirs(cache_dir, exist_ok=True)
        with open(os.path.join(cache_dir, "summaries.json"), "w") as f:
            f.write("{invalid json!!!!}")

        c = SummaryCache(cache_dir, config, prompt_hash)
        # Should not crash; should return None for any lookup
        result = c.get("/repo/main.py", "content", "python")
        assert result is None

    def test_corrupted_json_does_not_lose_new_data(self, cache_dir, config, prompt_hash):
        """After rebuild, new entries can still be stored and retrieved."""
        os.makedirs(cache_dir, exist_ok=True)
        with open(os.path.join(cache_dir, "summaries.json"), "w") as f:
            f.write("corrupt")

        c = SummaryCache(cache_dir, config, prompt_hash)
        c.put("/repo/main.py", "content", "python", _make_summary("/repo/main.py"), mtime=1.0)
        result = c.get("/repo/main.py", "content", "python")
        assert result is not None

    def test_missing_cache_file_creates_new(self, cache_dir, config, prompt_hash):
        """If cache file doesn't exist, it is created on first put."""
        c = SummaryCache(cache_dir, config, prompt_hash)
        c.put("/repo/main.py", "content", "python", _make_summary("/repo/main.py"), mtime=1.0)
        assert os.path.exists(os.path.join(cache_dir, "summaries.json"))

    def test_cache_dir_created_automatically(self, cache_dir, config, prompt_hash):
        """If cache directory doesn't exist, it is created."""
        nested_dir = os.path.join(cache_dir, "nested", "deep", "cache")
        c = SummaryCache(nested_dir, config, prompt_hash)
        c.put("/repo/main.py", "content", "python", _make_summary("/repo/main.py"), mtime=1.0)
        assert os.path.exists(nested_dir)
        assert os.path.exists(os.path.join(nested_dir, "summaries.json"))


# ===================================================================
# 6. Configuration change
# ===================================================================

class TestConfigurationChange:
    def test_provider_change_invalidates_cache(self, cache_dir, prompt_hash):
        """Changing provider invalidates all cache entries."""
        config_a = {"provider": "groq", "model": "model-a", "base_url": None}
        config_b = {"provider": "openai", "model": "model-a", "base_url": None}

        c1 = SummaryCache(cache_dir, config_a, prompt_hash)
        c1.put("/repo/main.py", "content", "python", _make_summary("/repo/main.py"), mtime=1.0)

        c2 = SummaryCache(cache_dir, config_b, prompt_hash)
        assert c2.get("/repo/main.py", "content", "python") is None

    def test_model_change_invalidates_cache(self, cache_dir, prompt_hash):
        """Changing model invalidates all cache entries."""
        config_a = {"provider": "groq", "model": "model-a", "base_url": None}
        config_b = {"provider": "groq", "model": "model-b", "base_url": None}

        c1 = SummaryCache(cache_dir, config_a, prompt_hash)
        c1.put("/repo/main.py", "content", "python", _make_summary("/repo/main.py"), mtime=1.0)

        c2 = SummaryCache(cache_dir, config_b, prompt_hash)
        assert c2.get("/repo/main.py", "content", "python") is None

    def test_prompt_template_change_invalidates_cache(self, cache_dir, config):
        """Changing prompt template hash invalidates all cache entries."""
        c1 = SummaryCache(cache_dir, config, "hash-v1")
        c1.put("/repo/main.py", "content", "python", _make_summary("/repo/main.py"), mtime=1.0)

        c2 = SummaryCache(cache_dir, config, "hash-v2")
        assert c2.get("/repo/main.py", "content", "python") is None

    def test_same_config_returns_cache_hit(self, cache_dir, config, prompt_hash):
        """Same config across instances returns cached data."""
        c1 = SummaryCache(cache_dir, config, prompt_hash)
        c1.put("/repo/main.py", "content", "python", _make_summary("/repo/main.py"), mtime=1.0)

        c2 = SummaryCache(cache_dir, config, prompt_hash)
        assert c2.get("/repo/main.py", "content", "python") is not None


# ===================================================================
# 7. Empty repository
# ===================================================================

class TestEmptyRepository:
    def test_empty_cache_returns_none(self, cache):
        """Cache with no entries returns None for any lookup."""
        assert cache.get("/nonexistent/file.py", "content", "python") is None

    def test_empty_cache_put_and_get(self, cache):
        """Even with empty cache, put then get works."""
        cache.put("/repo/new.py", "code", "python", _make_summary("/repo/new.py"), mtime=1.0)
        assert cache.get("/repo/new.py", "code", "python") is not None

    def test_get_deleted_files_empty(self, cache):
        """get_deleted_files returns empty list when cache is empty."""
        assert cache.get_deleted_files({"/repo/main.py"}) == []


# ===================================================================
# 8. Partial cache availability
# ===================================================================

class TestPartialCache:
    def test_mixed_hit_and_miss(self, cache):
        """Some files cached, some not -> correct hit/miss behavior."""
        cache.put("/repo/cached.py", "old", "python", _make_summary("/repo/cached.py"), mtime=1.0)

        # Cached file -> hit
        assert cache.get("/repo/cached.py", "old", "python") is not None
        # Uncached file -> miss
        assert cache.get("/repo/new.py", "new", "python") is None
        # Modified cached file -> miss
        assert cache.get("/repo/cached.py", "modified", "python") is None

    def test_partial_cache_after_removal(self, cache):
        """After removing some entries, remaining entries still work."""
        cache.put("/repo/a.py", "a", "python", _make_summary("/repo/a.py"), mtime=1.0)
        cache.put("/repo/b.py", "b", "python", _make_summary("/repo/b.py"), mtime=1.0)

        cache.remove_entries(["/repo/a.py"])
        assert cache.get("/repo/a.py", "a", "python") is None
        assert cache.get("/repo/b.py", "b", "python") is not None


# ===================================================================
# 9. Language mismatch
# ===================================================================

class TestLanguageMismatch:
    def test_language_change_returns_none(self, cache):
        """If detected language changes, cache returns None."""
        file_path = "/repo/script"
        content = "#!/usr/bin/env python\nprint('hello')"

        cache.put(file_path, content, "python", _make_summary(file_path), mtime=1.0)
        # Language changed
        assert cache.get(file_path, content, "javascript") is None

    def test_same_language_returns_hit(self, cache):
        """Same language returns cached summary."""
        file_path = "/repo/main.py"
        content = "print('hello')"
        cache.put(file_path, content, "python", _make_summary(file_path), mtime=1.0)
        assert cache.get(file_path, content, "python") is not None


# ===================================================================
# 10. Schema version change
# ===================================================================

class TestSchemaVersion:
    def test_schema_version_mismatch_invalidates(self, cache_dir, config, prompt_hash):
        """If schema version changes, cache is invalidated."""
        c1 = SummaryCache(cache_dir, config, prompt_hash)
        c1.put("/repo/main.py", "content", "python", _make_summary("/repo/main.py"), mtime=1.0)

        # Manually change schema version in file
        cache_file = os.path.join(cache_dir, "summaries.json")
        with open(cache_file, "r") as f:
            data = json.load(f)
        data["schema_version"] = "0.9"
        with open(cache_file, "w") as f:
            json.dump(data, f)

        c2 = SummaryCache(cache_dir, config, prompt_hash)
        assert c2.get("/repo/main.py", "content", "python") is None

    def test_current_schema_version_used(self, cache):
        """New cache uses current schema version."""
        cache.put("/repo/main.py", "content", "python", _make_summary("/repo/main.py"), mtime=1.0)
        cache_file = os.path.join(cache.cache_dir, "summaries.json")
        with open(cache_file, "r") as f:
            data = json.load(f)
        assert data["schema_version"] == CACHE_SCHEMA_VERSION


# ===================================================================
# 11. Content hash integrity
# ===================================================================

class TestContentHash:
    def test_different_content_different_hash(self):
        """Different content produces different hashes."""
        h1 = SummaryCache._compute_content_hash("hello")
        h2 = SummaryCache._compute_content_hash("world")
        assert h1 != h2

    def test_same_content_same_hash(self):
        """Same content produces same hash."""
        h1 = SummaryCache._compute_content_hash("hello world")
        h2 = SummaryCache._compute_content_hash("hello world")
        assert h1 == h2

    def test_unicode_content(self):
        """Unicode content is handled correctly."""
        h1 = SummaryCache._compute_content_hash("héllo wörld 🔥")
        h2 = SummaryCache._compute_content_hash("héllo wörld 🔥")
        assert h1 == h2


# ===================================================================
# 12. Edge cases
# ===================================================================

class TestEdgeCases:
    def test_empty_content(self, cache):
        """Empty content is handled."""
        cache.put("/repo/empty.py", "", "python", _make_summary("/repo/empty.py"), mtime=1.0)
        result = cache.get("/repo/empty.py", "", "python")
        assert result is not None

    def test_very_long_file_path(self, cache):
        """Long file paths are handled."""
        long_path = "/repo/" + "a" * 500 + "/" + "b" * 500 + ".py"
        cache.put(long_path, "content", "python", _make_summary(long_path), mtime=1.0)
        result = cache.get(long_path, "content", "python")
        assert result is not None

    def test_special_characters_in_path(self, cache):
        """File paths with special characters are handled."""
        path = "/repo/my file (copy) [2024] @test #1.py"
        cache.put(path, "content", "python", _make_summary(path), mtime=1.0)
        result = cache.get(path, "content", "python")
        assert result is not None

    def test_none_summary_handled(self, cache):
        """put() with a None-like summary is stored correctly."""
        file_path = "/repo/main.py"
        cache.put(file_path, "content", "python", {"file_path": file_path}, mtime=1.0)
        result = cache.get(file_path, "content", "python")
        assert result == {"file_path": file_path}

    def test_multiple_puts_same_file(self, cache):
        """Multiple puts for same file only keep latest entry."""
        file_path = "/repo/main.py"
        cache.put(file_path, "v1", "python", _make_summary(file_path, "v1"), mtime=1.0)
        cache.put(file_path, "v2", "python", _make_summary(file_path, "v2"), mtime=2.0)

        # Only one entry should exist
        assert len(cache._data["entries"]) == 1
        assert cache._data["entries"][0]["content_hash"] == SummaryCache._compute_content_hash("v2")


# ===================================================================
# 13. Performance / benchmark
# ===================================================================

class TestCachePerformance:
    def test_cache_hit_is_fast(self, cache):
        """Cache hit should be fast (no API call needed)."""
        import time

        file_path = "/repo/main.py"
        content = "x" * 10000
        language = "python"
        cache.put(file_path, content, language, _make_summary(file_path), mtime=1.0)

        start = time.perf_counter()
        for _ in range(100):
            result = cache.get(file_path, content, language)
            assert result is not None
        elapsed = time.perf_counter() - start

        # 100 lookups should take < 1 second
        assert elapsed < 1.0, f"100 cache lookups took {elapsed:.3f}s, expected < 1s"

    def test_cache_miss_is_fast(self, cache):
        """Cache miss should also be fast."""
        import time

        start = time.perf_counter()
        for _ in range(100):
            result = cache.get("/repo/nonexistent.py", "content", "python")
            assert result is None
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"100 cache misses took {elapsed:.3f}s, expected < 1s"