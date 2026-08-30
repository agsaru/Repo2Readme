"""Summary cache management — inspect, prune, and clear cached file summaries.

Provides a user-facing interface to the ``SummaryCache`` internals, so
operators can see hit/miss stats, list cached files, remove stale entries,
and clear the cache without guessing at file paths.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CacheEntryInfo:
    """Lightweight view of a single cache entry."""

    file_path: str
    language: str
    content_hash: str
    mtime: float
    summary_preview: str  # first ~80 chars of the description

    @property
    def age_display(self) -> str:
        """Human-readable age estimate based on mtime."""
        if self.mtime <= 0:
            return "unknown"
        import time
        delta = time.time() - self.mtime
        if delta < 60:
            return "just now"
        if delta < 3600:
            return f"{int(delta // 60)}m ago"
        if delta < 86400:
            return f"{int(delta // 3600)}h ago"
        return f"{int(delta // 86400)}d ago"


@dataclass
class CacheStats:
    """Aggregated statistics about the summary cache."""

    cache_exists: bool = False
    cache_file: str = ""
    cache_size_bytes: int = 0
    total_entries: int = 0
    languages: dict[str, int] = field(default_factory=dict)
    schema_version: str = ""
    config_hash: str = ""
    entries: list[CacheEntryInfo] = field(default_factory=list)


@dataclass
class CacheOperation:
    """Result of a cache management operation."""

    success: bool
    message: str
    entries_affected: int = 0


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def _load_raw_cache(cache_dir: str) -> Optional[dict]:
    """Load the raw cache JSON without going through SummaryCache."""
    cache_file = os.path.join(cache_dir, "summaries.json")
    if not os.path.exists(cache_file):
        return None
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _entry_to_info(entry: dict) -> CacheEntryInfo:
    """Convert a raw cache entry to a CacheEntryInfo."""
    summary = entry.get("summary", {})
    preview = ""
    if isinstance(summary, dict):
        preview = summary.get("description", "")[:80]
    elif isinstance(summary, str):
        preview = summary[:80]

    return CacheEntryInfo(
        file_path=entry.get("file_path", ""),
        language=entry.get("language", "unknown"),
        content_hash=entry.get("content_hash", "")[:12],
        mtime=entry.get("mtime", 0),
        summary_preview=preview,
    )


def get_cache_stats(cache_dir: str) -> CacheStats:
    """Load and analyze the cache file, returning aggregate stats."""
    stats = CacheStats()
    cache_file = os.path.join(cache_dir, "summaries.json")
    stats.cache_file = cache_file

    if not os.path.exists(cache_file):
        return stats

    stats.cache_exists = True
    try:
        stats.cache_size_bytes = os.path.getsize(cache_file)
    except OSError:
        pass

    data = _load_raw_cache(cache_dir)
    if data is None:
        return stats

    stats.schema_version = data.get("schema_version", "")
    stats.config_hash = data.get("config_hash", "")[:16]

    entries = data.get("entries", [])
    stats.total_entries = len(entries)

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        lang = entry.get("language", "unknown")
        stats.languages[lang] = stats.languages.get(lang, 0) + 1
        stats.entries.append(_entry_to_info(entry))

    return stats


def list_entries(cache_dir: str, language: Optional[str] = None,
                 limit: int = 50) -> list[CacheEntryInfo]:
    """List cached entries, optionally filtered by language."""
    data = _load_raw_cache(cache_dir)
    if data is None:
        return []

    entries = data.get("entries", [])
    result = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        info = _entry_to_info(entry)
        if language and info.language != language:
            continue
        result.append(info)
        if len(result) >= limit:
            break

    return result


def clear_cache(cache_dir: str) -> CacheOperation:
    """Delete the entire cache file."""
    cache_file = os.path.join(cache_dir, "summaries.json")
    if not os.path.exists(cache_file):
        return CacheOperation(success=True, message="No cache file found.", entries_affected=0)

    data = _load_raw_cache(cache_dir)
    count = len(data.get("entries", [])) if data else 0

    try:
        os.remove(cache_file)
        # Also remove any leftover temp files
        for fname in os.listdir(cache_dir):
            if fname.endswith(".json.tmp"):
                try:
                    os.remove(os.path.join(cache_dir, fname))
                except OSError:
                    pass
        return CacheOperation(success=True, message=f"Cache cleared ({count} entries removed).",
                              entries_affected=count)
    except OSError as e:
        return CacheOperation(success=False, message=f"Failed to remove cache: {e}")


def prune_stale_entries(cache_dir: str, current_files: Optional[set[str]] = None,
                        max_age_seconds: Optional[float] = None) -> CacheOperation:
    """Remove entries for deleted files or entries older than max_age_seconds.

    Parameters
    ----------
    current_files:
        If given, entries whose file_path is not in this set are removed.
    max_age_seconds:
        If given, entries with mtime older than this are removed.
    """
    cache_file = os.path.join(cache_dir, "summaries.json")
    data = _load_raw_cache(cache_dir)
    if data is None or not os.path.exists(cache_file):
        return CacheOperation(success=False, message="No cache file found.")

    entries = data.get("entries", [])
    original_count = len(entries)
    import time
    now = time.time()

    remaining = []
    removed = 0
    for entry in entries:
        if not isinstance(entry, dict):
            remaining.append(entry)
            continue

        should_remove = False

        # Remove if file no longer exists
        if current_files is not None:
            fp = entry.get("file_path", "")
            if fp and fp not in current_files:
                should_remove = True

        # Remove if too old
        if max_age_seconds is not None:
            mtime = entry.get("mtime", 0)
            if mtime > 0 and (now - mtime) > max_age_seconds:
                should_remove = True

        if should_remove:
            removed += 1
        else:
            remaining.append(entry)

    if removed == 0:
        return CacheOperation(success=True, message="No stale entries found.", entries_affected=0)

    # Write back
    data["entries"] = remaining
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return CacheOperation(success=True,
                              message=f"Pruned {removed} stale entries ({original_count - remaining.__len__()} removed).",
                              entries_affected=removed)
    except OSError as e:
        return CacheOperation(success=False, message=f"Failed to write cache: {e}")


def get_entry_detail(cache_dir: str, file_path: str) -> Optional[CacheEntryInfo]:
    """Get detailed info for a specific cached file."""
    data = _load_raw_cache(cache_dir)
    if data is None:
        return None

    for entry in data.get("entries", []):
        if isinstance(entry, dict) and entry.get("file_path") == file_path:
            return _entry_to_info(entry)

    return None
