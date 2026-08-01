import hashlib
import json
import logging
import os
import tempfile
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

CACHE_SCHEMA_VERSION = "1.0"

# Expected fields for each cache entry
EXPECTED_ENTRY_FIELDS = {
    "file_path",
    "content_hash",
    "language",
    "summary",
    "mtime",
}


def _validate_cache_structure(data: Any) -> bool:
    """
    Validate that the loaded cache data has the expected structure.

    Returns True if valid, False otherwise.
    """
    if not isinstance(data, dict):
        logger.warning("Cache root is not a dictionary, got %s", type(data).__name__)
        return False

    if "schema_version" not in data:
        logger.warning("Cache missing 'schema_version'")
        return False

    if "config_hash" not in data:
        logger.warning("Cache missing 'config_hash'")
        return False

    entries = data.get("entries")
    if not isinstance(entries, list):
        logger.warning(
            "Cache 'entries' is not a list, got %s", type(entries).__name__
        )
        return False

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            logger.warning("Cache entry %d is not a dictionary, got %s", i, type(entry).__name__)
            return False
        missing = EXPECTED_ENTRY_FIELDS - set(entry.keys())
        if missing:
            logger.warning(
                "Cache entry %d missing fields: %s", i, ", ".join(sorted(missing))
            )
            return False

    return True


class SummaryCache:
    """
    File-level summary cache with configuration-aware invalidation.

    Cache entries are keyed by file path and content hash. The cache is
    invalidated when summarization configuration (provider, model, base_url,
    prompt template) changes or when the cache schema version changes.

    Thread-safe: all public methods acquire an instance-level lock.
    """

    def __init__(self, cache_dir: str, config: dict, prompt_template_hash: str):
        self.cache_dir = cache_dir
        self.config = config
        self.prompt_template_hash = prompt_template_hash
        self.cache_file = os.path.join(cache_dir, "summaries.json")
        self.schema_version = CACHE_SCHEMA_VERSION
        self._data: Optional[dict] = None
        self._lock = threading.Lock()

    def _ensure_cache_dir(self) -> None:
        os.makedirs(self.cache_dir, exist_ok=True)

    def _compute_config_hash(self) -> str:
        config_str = json.dumps(
            {
                "provider": self.config.get("provider"),
                "model": self.config.get("model"),
                "base_url": self.config.get("base_url"),
                "prompt_template_hash": self.prompt_template_hash,
            },
            sort_keys=True,
        )
        return hashlib.sha256(config_str.encode()).hexdigest()

    @staticmethod
    def _compute_content_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _rebuild(self) -> None:
        """Reset cache data to a fresh state."""
        self._data = {
            "schema_version": self.schema_version,
            "config_hash": self._compute_config_hash(),
            "entries": [],
        }

    def _load(self) -> None:
        if self._data is not None:
            return

        self._ensure_cache_dir()
        if not os.path.exists(self.cache_file):
            self._rebuild()
            return

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not _validate_cache_structure(data):
                logger.warning("Cache structure validation failed, rebuilding")
                self._rebuild()
                return

            self._data = data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Cache file corrupted or unreadable, rebuilding: {e}")
            self._rebuild()

    def _save(self) -> None:
        """Atomically write cache to a temporary file, then replace the original."""
        self._ensure_cache_dir()
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=self.cache_dir, prefix="summaries_", suffix=".json.tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.cache_file)
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError as e:
            logger.warning(f"Failed to write cache file: {e}")

    def _find_entry(self, file_path: str) -> Optional[dict]:
        for entry in self._data.get("entries", []):
            if entry.get("file_path") == file_path:
                return entry
        return None

    def get(self, file_path: str, content: str, language: str) -> Optional[dict]:
        """
        Return cached summary if valid, otherwise None.
        """
        with self._lock:
            self._load()

            # Invalidate if configuration changed
            current_config_hash = self._compute_config_hash()
            if self._data.get("config_hash") != current_config_hash:
                logger.info("Configuration changed, invalidating cache")
                self._data["entries"] = []
                self._data["config_hash"] = current_config_hash
                return None

            # Invalidate if schema version changed
            if self._data.get("schema_version") != self.schema_version:
                logger.info(
                    "Cache schema version changed from %s to %s, invalidating cache",
                    self._data.get("schema_version"),
                    self.schema_version,
                )
                self._data["entries"] = []
                self._data["schema_version"] = self.schema_version
                self._data["config_hash"] = current_config_hash
                return None

            entry = self._find_entry(file_path)
            if entry is None:
                return None

            content_hash = self._compute_content_hash(content)
            if entry.get("content_hash") != content_hash:
                return None

            # Language mismatch could indicate detection logic changed
            if entry.get("language") != language:
                logger.debug(
                    "Language mismatch for %s: cached=%s, current=%s",
                    file_path,
                    entry.get("language"),
                    language,
                )
                return None

            return entry.get("summary")

    def put(
        self, file_path: str, content: str, language: str, summary: dict, mtime: float
    ) -> None:
        """
        Store summary in cache.
        """
        with self._lock:
            self._load()

            # Remove existing entry for this file
            self._data["entries"] = [
                e
                for e in self._data.get("entries", [])
                if e.get("file_path") != file_path
            ]

            self._data["entries"].append(
                {
                    "file_path": file_path,
                    "content_hash": self._compute_content_hash(content),
                    "language": language,
                    "summary": summary,
                    "mtime": mtime,
                }
            )

            self._save()

    def get_deleted_files(self, current_files: set) -> list:
        """
        Return cache entries for files that no longer exist in current_files.
        """
        with self._lock:
            self._load()
            return [
                entry
                for entry in self._data.get("entries", [])
                if entry.get("file_path") not in current_files
            ]

    def remove_entries(self, file_paths: list) -> None:
        """
        Remove specific entries from cache.
        """
        with self._lock:
            self._load()
            paths_to_remove = set(file_paths)
            self._data["entries"] = [
                e
                for e in self._data.get("entries", [])
                if e.get("file_path") not in paths_to_remove
            ]
            self._save()