"""Gitignore support for repository traversal.

``is_gitignored`` used to reload and recompile the ignore rules on every call:
it opened ``.gitignore``, opened ``.git/info/exclude`` and asked ``pathspec``
to compile every pattern into a regex, once per path. Traversal asks about
every directory and every file, so a 400-file repository opened and compiled
the same file 420 times, and the cost grew with the length of ``.gitignore``.

Rules are now compiled once per directory and cached for the life of the
process, keyed on each file's modification time and size so a long-running
caller cannot serve stale rules.

Only the repository root was consulted, too. Git applies a ``.gitignore`` in
any directory to that directory's subtree, which is how a JavaScript project
keeps ``frontend/build/`` out of the repository - and generated bundles are
exactly the files that waste the most tokens. Every level from the root down to
the path being tested is now consulted, in git's order.

Deliberately not supported: ``core.excludesFile``. A per-machine ignore list
would make the same repository produce a different README on a different
machine.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass

try:
    import pathspec
except ImportError:
    pathspec = None


# The ignore sources git reads, per directory, in the order it reads them.
# ``.git/info/exclude`` is repository-wide and is therefore only read at the
# root.
GITIGNORE_FILE = ".gitignore"
GIT_INFO_EXCLUDE = os.path.join(".git", "info", "exclude")


@dataclass(frozen=True)
class _Stamp:
    """Identity of a rules file, used to notice edits without re-reading it."""

    mtime: float
    size: int


def _stamp(path: str) -> _Stamp | None:
    try:
        stat_result = os.stat(path)
    except OSError:
        return None
    return _Stamp(mtime=stat_result.st_mtime, size=stat_result.st_size)


def _read_patterns(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.readlines()
    except OSError:
        return []


class GitignoreMatcher:
    """Compiled ignore rules for one repository root.

    A matcher is bound to a root and answers questions about paths beneath it.
    Each directory's rules are compiled on first use and reused afterwards, so
    a traversal pays for a ``.gitignore`` once rather than once per path.

    Thread safe: the traversal pipeline asks from worker threads.
    """

    def __init__(self, root_path: str):
        self.root_path = root_path
        self._lock = threading.Lock()
        # directory relative to the root ("" for the root itself) ->
        # (stamps of its rules files, compiled spec or None)
        self._specs: dict[str, tuple[tuple[_Stamp | None, ...], object | None]] = {}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _sources_for(self, relative_dir: str) -> list[str]:
        """Absolute paths of the rules files that apply *at* ``relative_dir``."""
        directory = (
            os.path.join(self.root_path, relative_dir)
            if relative_dir
            else self.root_path
        )
        if relative_dir:
            return [os.path.join(directory, GITIGNORE_FILE)]

        # .git/info/exclude has lower precedence than the root .gitignore.
        return [
            os.path.join(self.root_path, GIT_INFO_EXCLUDE),
            os.path.join(directory, GITIGNORE_FILE),
        ]

    def _spec_for(self, relative_dir: str):
        """Compiled spec for one directory, or None when it has no rules.

        The stamps are re-read on every call - that is two ``stat`` calls, not
        two ``open`` calls and a regex compilation - so an edit made while a
        process is alive is picked up without leaving the cache stale.
        """
        sources = self._sources_for(relative_dir)
        stamps = tuple(_stamp(source) for source in sources)

        with self._lock:
            cached = self._specs.get(relative_dir)
            if cached is not None and cached[0] == stamps:
                return cached[1]

        patterns: list[str] = []
        for source, stamp in zip(sources, stamps):
            if stamp is not None:
                patterns.extend(_read_patterns(source))

        spec = (
            pathspec.PathSpec.from_lines("gitignore", patterns) if patterns else None
        )

        with self._lock:
            self._specs[relative_dir] = (stamps, spec)

        return spec

    def _relative(self, path: str) -> str | None:
        """``path`` relative to the root, or None when it is not beneath it."""
        try:
            relative = os.path.relpath(path, self.root_path).replace("\\", "/")
        except ValueError:
            return None
        if relative == "." or relative == ".." or relative.startswith("../"):
            return None
        return relative

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_ignored(self, path: str, is_dir: bool | None = None) -> bool:
        """Whether ``path`` is ignored by any rules between the root and it.

        ``is_dir`` avoids a ``stat`` when the caller already knows. Git matches
        a directory against both ``name`` and ``name/``, and only the second
        form matches a rule written as ``build/``.
        """
        if pathspec is None:
            return False

        relative = self._relative(path)
        if relative is None:
            return False

        parts = [part for part in relative.split("/") if part]
        if not parts:
            return False

        if is_dir is None:
            is_dir = os.path.isdir(path)

        # Rules in a directory apply to everything below it, expressed relative
        # to that directory - so the path is re-relativized at each level, the
        # way git evaluates them.
        directories = [""] + [
            "/".join(parts[:depth]) for depth in range(1, len(parts))
        ]

        ignored = False
        for relative_dir in directories:
            spec = self._spec_for(relative_dir)
            if spec is None:
                continue

            candidate = relative[len(relative_dir) + 1:] if relative_dir else relative
            if not candidate:
                continue

            results = [spec.check_file(candidate)]
            if is_dir:
                results.append(spec.check_file(candidate + "/"))

            matches = [result for result in results if result.include is not None]
            if matches:
                # For directories, both "name" and "name/" can match. The
                # later matching rule wins, just as it does within one file.
                latest = max(
                    matches,
                    key=lambda result: (
                        result.index if result.index is not None else -1
                    ),
                )
                ignored = not latest.include

        return ignored

    def clear(self) -> None:
        """Forget every compiled spec."""
        with self._lock:
            self._specs.clear()


# ---------------------------------------------------------------------------
# Process-level matcher cache
# ---------------------------------------------------------------------------

_matchers: dict[str, GitignoreMatcher] = {}
_matchers_lock = threading.Lock()


def get_matcher(root_path: str) -> GitignoreMatcher:
    """Return the shared matcher for ``root_path``, creating it if needed."""
    key = os.path.abspath(root_path)
    with _matchers_lock:
        matcher = _matchers.get(key)
        if matcher is None:
            matcher = GitignoreMatcher(root_path)
            _matchers[key] = matcher
        return matcher


def clear_matcher_cache() -> None:
    """Drop every cached matcher.

    A cloned repository lives in a temporary directory that is removed at the
    end of a run, and a test suite creates and deletes roots constantly. The
    stamps already prevent stale *rules*; this keeps the dictionary itself from
    growing over the life of a long-running process.
    """
    with _matchers_lock:
        _matchers.clear()


def is_gitignored(path: str, root_path: str) -> bool:
    """Whether ``path`` is ignored by the gitignore rules under ``root_path``.

    Unchanged signature and return value for callers; the rules behind it are
    now compiled once per directory and nested ``.gitignore`` files are
    honoured.
    """
    if not root_path or not os.path.isdir(root_path):
        return False

    return get_matcher(root_path).is_ignored(path)
