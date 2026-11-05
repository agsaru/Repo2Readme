"""What the cache does when the disk says no.

``flush()`` used to clear the dirty flag before attempting the write, and
``_write`` swallowed the ``OSError``. So a failed write reported success and the
pending work could never be written by a later call either. The CLI flushes
exactly once, in the ``finally`` block of a run, which made one unwritable cache
file enough to silently discard every summary the run had paid for.
"""

import json
import os
import tempfile
import threading

import pytest

from repo2readme.cache import SummaryCache


@pytest.fixture
def config():
    return {"provider": "groq", "model": "test-model", "base_url": None}


def _cache(tmp_path, config, **kwargs):
    return SummaryCache(
        cache_dir=str(tmp_path / "cache"),
        config=config,
        prompt_template_hash="hash-1",
        **kwargs,
    )


def _put(cache, name="a.py", content="x = 1"):
    cache.put(name, content, "python", {"file_path": name, "description": "d"}, 1.0)


class Failing:
    """Fails the first ``times`` calls, then delegates to the real function."""

    def __init__(self, real, times=1, error=None):
        self.real = real
        self.times = times
        self.calls = 0
        self.error = error or OSError("No space left on device")

    def __call__(self, *args, **kwargs):
        self.calls += 1
        if self.calls <= self.times:
            raise self.error
        return self.real(*args, **kwargs)


@pytest.fixture
def break_writes(monkeypatch):
    """Make the next ``times`` cache writes fail, at the chosen syscall."""

    def _break(target="mkstemp", times=1, error=None):
        if target == "mkstemp":
            failing = Failing(tempfile.mkstemp, times=times, error=error)
            monkeypatch.setattr(tempfile, "mkstemp", failing)
        else:
            failing = Failing(os.replace, times=times, error=error)
            monkeypatch.setattr(os, "replace", failing)
        return failing

    return _break


class TestFlushReportsTheTruth:
    def test_flush_returns_false_when_the_write_failed(
        self, tmp_path, config, break_writes
    ):
        break_writes()
        cache = _cache(tmp_path, config, autosave=False)
        _put(cache)

        assert cache.flush() is False

    def test_no_cache_file_is_left_behind(self, tmp_path, config, break_writes):
        break_writes()
        cache = _cache(tmp_path, config, autosave=False)
        _put(cache)
        cache.flush()

        assert not os.path.exists(cache.cache_file)

    def test_a_successful_flush_still_returns_true(self, tmp_path, config):
        cache = _cache(tmp_path, config, autosave=False)
        _put(cache)

        assert cache.flush() is True

    def test_a_failure_at_the_rename_step_is_reported_too(
        self, tmp_path, config, break_writes
    ):
        break_writes(target="replace")
        cache = _cache(tmp_path, config, autosave=False)
        _put(cache)

        assert cache.flush() is False

    def test_no_temporary_files_are_left_behind(
        self, tmp_path, config, break_writes
    ):
        break_writes(target="replace")
        cache = _cache(tmp_path, config, autosave=False)
        _put(cache)
        cache.flush()

        leftovers = [
            name
            for name in os.listdir(cache.cache_dir)
            if name.endswith(".tmp")
        ]
        assert leftovers == []


class TestPendingWorkSurvives:
    def test_a_later_flush_retries_and_succeeds(
        self, tmp_path, config, break_writes
    ):
        failing = break_writes(times=1)
        cache = _cache(tmp_path, config, autosave=False)
        _put(cache, "a.py")

        assert cache.flush() is False
        assert cache.flush() is True
        assert failing.calls == 2

        with open(cache.cache_file, encoding="utf-8") as f:
            entries = json.load(f)["entries"]
        assert [entry["file_path"] for entry in entries] == ["a.py"]

    def test_every_entry_survives_the_failed_write(
        self, tmp_path, config, break_writes
    ):
        break_writes(times=1)
        cache = _cache(tmp_path, config, autosave=False)
        for name in ("a.py", "b.py", "c.py"):
            _put(cache, name)

        cache.flush()
        cache.flush()

        with open(cache.cache_file, encoding="utf-8") as f:
            entries = json.load(f)["entries"]
        assert sorted(e["file_path"] for e in entries) == ["a.py", "b.py", "c.py"]

    def test_entries_added_during_a_failed_write_are_not_lost(
        self, tmp_path, config, break_writes
    ):
        break_writes(times=1)
        cache = _cache(tmp_path, config, autosave=False)
        _put(cache, "a.py")
        cache.flush()

        _put(cache, "b.py")
        assert cache.flush() is True

        with open(cache.cache_file, encoding="utf-8") as f:
            entries = json.load(f)["entries"]
        assert sorted(e["file_path"] for e in entries) == ["a.py", "b.py"]

    def test_in_memory_lookups_keep_working(self, tmp_path, config, break_writes):
        break_writes()
        cache = _cache(tmp_path, config, autosave=False)
        _put(cache, "a.py", "x = 1")
        cache.flush()

        assert cache.get("a.py", "x = 1", "python") == {
            "file_path": "a.py",
            "description": "d",
        }

    def test_an_autosaving_cache_retries_on_the_next_put(
        self, tmp_path, config, break_writes
    ):
        break_writes(times=1)
        cache = _cache(tmp_path, config, autosave=True)

        _put(cache, "a.py")  # write fails
        _put(cache, "b.py")  # write succeeds, carrying both entries

        with open(cache.cache_file, encoding="utf-8") as f:
            entries = json.load(f)["entries"]
        assert sorted(e["file_path"] for e in entries) == ["a.py", "b.py"]

    def test_a_failed_removal_write_is_retried(
        self, tmp_path, config, break_writes
    ):
        # autosave writes as part of remove_entries, so the failure happens
        # inside the removal itself rather than on an explicit flush.
        cache = _cache(tmp_path, config, autosave=True)
        _put(cache, "a.py")
        _put(cache, "b.py")

        break_writes(times=1)
        cache.remove_entries(["a.py"])

        assert cache.flush() is True
        with open(cache.cache_file, encoding="utf-8") as f:
            entries = json.load(f)["entries"]
        assert [entry["file_path"] for entry in entries] == ["b.py"]

    def test_a_failed_invalidation_write_is_retried(
        self, tmp_path, config, break_writes
    ):
        first = _cache(tmp_path, config, autosave=False)
        _put(first, "a.py")
        first.flush()

        # A different model invalidates everything the previous run cached.
        other = SummaryCache(
            cache_dir=str(tmp_path / "cache"),
            config={**config, "model": "another-model"},
            prompt_template_hash="hash-1",
            autosave=True,
        )
        break_writes(times=1)

        assert other.get("a.py", "x = 1", "python") is None
        assert other.flush() is True

        with open(other.cache_file, encoding="utf-8") as f:
            data = json.load(f)
        assert data["entries"] == []


class TestReporting:
    def test_failures_are_counted_and_writes_are_not(
        self, tmp_path, config, break_writes
    ):
        break_writes(times=1)
        cache = _cache(tmp_path, config, autosave=False)
        _put(cache)

        cache.flush()
        stats_after_failure = cache.stats()
        assert stats_after_failure["write_failures"] == 1
        assert stats_after_failure["disk_writes"] == 0

        cache.flush()
        stats_after_success = cache.stats()
        assert stats_after_success["write_failures"] == 1
        assert stats_after_success["disk_writes"] == 1

    def test_the_reason_is_available(self, tmp_path, config, break_writes):
        break_writes(times=1, error=OSError("Read-only file system"))
        cache = _cache(tmp_path, config, autosave=False)
        _put(cache)

        cache.flush()

        assert "Read-only file system" in cache.last_write_error

    def test_the_reason_is_cleared_once_a_write_succeeds(
        self, tmp_path, config, break_writes
    ):
        break_writes(times=1)
        cache = _cache(tmp_path, config, autosave=False)
        _put(cache)

        cache.flush()
        cache.flush()

        assert cache.last_write_error is None

    def test_nothing_is_reported_before_the_first_write(self, tmp_path, config):
        assert _cache(tmp_path, config).last_write_error is None

    def test_the_failure_is_logged_at_error_level(
        self, tmp_path, config, break_writes, caplog
    ):
        break_writes(times=1, error=OSError("Read-only file system"))
        cache = _cache(tmp_path, config, autosave=False)
        _put(cache)

        with caplog.at_level("ERROR"):
            cache.flush()

        messages = [record.getMessage() for record in caplog.records]
        assert any("Read-only file system" in message for message in messages)


class TestLifecycle:
    def test_the_context_manager_does_not_raise_on_a_failed_write(
        self, tmp_path, config, break_writes
    ):
        break_writes()

        with _cache(tmp_path, config, autosave=False) as cache:
            _put(cache)

        assert cache.stats()["write_failures"] == 1

    def test_concurrent_puts_all_survive_a_failed_flush(
        self, tmp_path, config, break_writes
    ):
        break_writes(times=1)
        cache = _cache(tmp_path, config, autosave=False)

        def worker(index):
            _put(cache, f"file_{index}.py", f"x = {index}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert cache.flush() is False
        assert cache.flush() is True

        with open(cache.cache_file, encoding="utf-8") as f:
            entries = json.load(f)["entries"]
        assert len(entries) == 8



def test_unavailable_cache_directory_does_not_break_summary_work(tmp_path, config):
    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("file", encoding="utf-8")
    cache = SummaryCache(
        cache_dir=str(blocked_parent / "cache"),
        config=config,
        prompt_template_hash="hash-1",
    )

    assert cache.get("a.py", "x = 1", "python") is None
    cache.put("a.py", "x = 1", "python", {"description": "summary"}, 1)

    assert cache.stats()["write_failures"] == 1
    assert cache.last_write_error is not None


def test_invalid_utf8_cache_file_is_rebuilt(tmp_path, config):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "summaries.json").write_bytes(b"\\xff\\xfe")

    cache = _cache(tmp_path, config)

    assert cache.get("a.py", "x = 1", "python") is None
    assert cache.stats()["misses"] == 1
