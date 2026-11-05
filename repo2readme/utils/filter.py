from __future__ import annotations
import fnmatch
import os
from pathlib import Path
from typing import Iterable


# ---------------------------------------------------------------------------
# Directory rules
# ---------------------------------------------------------------------------
#
# Ignored directories fall into two groups. Names like ``node_modules`` or
# ``__pycache__`` are unambiguous: wherever they appear in a tree they hold
# dependencies or generated output. Names like ``bin``, ``pkg`` or ``public``
# are only build output *at the repository root* - deeper in the tree they are
# ordinary source directories (``src/bin/run.py``, ``pkg/server/main.go``,
# ``app/public/routes.rb``), and matching them at any depth silently removes
# large parts of a repository from the analysis.

# Ignored wherever they appear in the path.
NESTED_IGNORE_DIRS = frozenset(
    {
        "node_modules",
        ".next",
        ".npm",
        ".yarn",
        ".pnpm",
        "bower_components",
        "__pycache__",
        ".venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "build",
        "target",
        "obj",
        "dist",
        "coverage",
        ".gradle",
        ".mvn",
        ".nuget",
        ".bundle",
        ".cargo",
        ".firebase",
        ".git",
        ".idea",
        ".vscode",
        ".cache",
    }
)

# Ignored only when they are the first component of the repository-relative
# path. These names are ordinary source directories once nested.
#
# ``pkg`` and ``packages`` were dropped from the ignore rules entirely: inside a
# checked-out repository ``pkg/`` is the standard Go project layout and
# ``packages/`` is where a JavaScript monorepo keeps its workspaces. Ignoring
# them removed most of the source of the projects that use those conventions.
ROOT_IGNORE_DIRS = frozenset(
    {
        "venv",
        "env",
        "bin",
        "vendor",
        "public",
        "logs",
        "out",
    }
)

# Directory rules expressed as a path or a glob rather than a bare name.
IGNORE_DIR_PATTERNS = (
    "src/generated/prisma",
    "*.egg-info",
)

# Kept as the union of both sets so callers that introspect the ignore list
# keep working.
IGNORE_DIRS = NESTED_IGNORE_DIRS | ROOT_IGNORE_DIRS

IGNORE_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "__init__.py",
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.test",
    ".gitignore",
}

IGNORE_EXTENSIONS = {
    ".exe",
    ".dll",
    ".bin",
    ".class",
    ".o",
    ".so",
    ".dylib",
    ".zip",
    ".tar",
    ".gz",
    ".jar",
    ".war",
    ".ear",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".txt",
    ".log",
    ".lock",
    ".db",
    ".sqlite",
    ".pdf",
    ".csv",
    ".json",
    ".ipynb",
}

PROTECTED_LARGE_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
}

# ---------------------------------------------------------------------------
# Manifest allowlist
# ---------------------------------------------------------------------------
#
# The blanket ``.json`` / ``.txt`` extension ban above exists to keep fixtures,
# data dumps and lock files out of the model's context. It also removed the
# files that describe the project: what it depends on, how it is installed and
# which environment variables it needs - which is exactly what the README
# prompt asks for. These names are therefore exempt from the *file* level rules
# (basename and extension). Directory rules still win, so a
# ``node_modules/package.json`` stays ignored, and the lock files are
# deliberately absent from this list.

MANIFEST_FILES = frozenset(
    {
        # JavaScript / TypeScript
        "package.json",
        "bower.json",
        "deno.json",
        "deno.jsonc",
        "jsr.json",
        "tsconfig.json",
        "jsconfig.json",
        "angular.json",
        "nest-cli.json",
        "lerna.json",
        "turbo.json",
        "nx.json",
        # PHP
        "composer.json",
        # Python
        "pipfile",
        "constraints.txt",
        # Environment variable documentation. The real ``.env`` files stay in
        # IGNORE_FILES; only the checked-in templates are read.
        ".env.example",
        ".env.sample",
        ".env.template",
    }
)

# Glob variants, matched against the basename and against the
# repository-relative path, so both ``requirements-dev.txt`` and
# ``requirements/base.txt`` are picked up.
MANIFEST_PATTERNS = (
    "requirements*.txt",
    "requirements/*.txt",
)


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").lower().strip()


def _matches_any(path: str, patterns: Iterable[str] | None) -> bool:
    if not patterns:
        return False

    normalized_path = _normalize_path(path)
    basename = os.path.basename(normalized_path)

    for pattern in patterns:
        normalized_pattern = _normalize_path(pattern)

        if fnmatch.fnmatch(normalized_path, normalized_pattern):
            return True

        if fnmatch.fnmatch(basename, normalized_pattern):
            return True

    return False


def _matches_protected_include(path: str, patterns: Iterable[str] | None) -> bool:
    """
    Prevent broad patterns like '*.json' from accidentally including large lock files.
    A protected file should only be included if the user names that exact file.
    """
    if not patterns:
        return False

    normalized_path = _normalize_path(path)
    basename = os.path.basename(normalized_path)

    for pattern in patterns:
        normalized_pattern = _normalize_path(pattern)
        pattern_basename = os.path.basename(normalized_pattern)

        if pattern_basename != basename:
            continue

        if "/" not in normalized_pattern:
            return True

        if fnmatch.fnmatch(normalized_path, normalized_pattern):
            return True

    return False


def is_manifest_file(path: str) -> bool:
    """
    Whether ``path`` names a dependency, build or environment manifest.

    Manifests describe the project rather than implement it, so they are worth
    reading even when their extension is otherwise ignored.
    """
    normalized_path = _normalize_path(path)
    basename = os.path.basename(normalized_path)

    if basename in MANIFEST_FILES:
        return True

    for pattern in MANIFEST_PATTERNS:
        if fnmatch.fnmatch(basename, pattern):
            return True
        if fnmatch.fnmatch(normalized_path, pattern):
            return True
        if fnmatch.fnmatch(normalized_path, f"*/{pattern}"):
            return True

    return False


def _ignored_directory(path_parts: list[str], normalized_path: str) -> str | None:
    """
    Return the offending directory name when ``path`` sits under an ignored
    directory, otherwise None.
    """
    for part in path_parts:
        if part in NESTED_IGNORE_DIRS:
            return part

    if path_parts and path_parts[0] in ROOT_IGNORE_DIRS:
        return path_parts[0]

    for pattern in IGNORE_DIR_PATTERNS:
        if fnmatch.fnmatch(normalized_path, pattern):
            return pattern
        if fnmatch.fnmatch(normalized_path, f"{pattern}/*"):
            return pattern
        if any(fnmatch.fnmatch(part, pattern) for part in path_parts):
            return pattern

    return None


def classify_default_ignore(path: str) -> str | None:
    """
    Categorise why ``path`` is ignored by the built-in rules, or return None
    when it is not ignored.

    The category is one of ``"build_directory"``, ``"ignored_file"`` or
    ``"ignored_extension"``. It is finer grained than the single
    "ignored by default rules" skip reason and makes a large skip count
    explainable.

    Directory rules are evaluated first so the manifest allowlist can never
    resurrect a file from inside ``node_modules`` or ``dist``.
    """
    normalized_path = _normalize_path(path)
    basename = os.path.basename(normalized_path)
    path_parts = [part for part in normalized_path.split("/") if part]

    if _ignored_directory(path_parts, normalized_path) is not None:
        return "build_directory"

    if is_manifest_file(normalized_path):
        return None

    # IGNORE_FILES enumerates a handful of dotenv names, which left the rest
    # (.env.staging, .env.prod, .env.development.local, .envrc) to fall through
    # to the extension check - and their suffix is not in IGNORE_EXTENSIONS
    # either, so files holding real secrets reached the model. Match the whole
    # family instead. The three checked-in templates are exempted by the
    # manifest check above, and an explicit --include still wins, as it does
    # for every default rule.
    if basename.startswith(".env"):
        return "ignored_file"

    if basename in IGNORE_FILES:
        return "ignored_file"

    _, ext = os.path.splitext(basename)
    if ext in IGNORE_EXTENSIONS:
        return "ignored_extension"

    return None


def is_default_ignored(path: str) -> bool:
    return classify_default_ignore(path) is not None


def is_file_size_allowed(
    path: str,
    root_path: str | None = None,
    max_file_size_kb: int | None = 200,
) -> tuple[bool, str | None]:
    """
    Check if a file is within the configured size limit.

    Returns (allowed, reason). When allowed is True, reason is None.
    When allowed is False, reason describes why the file was rejected.
    """
    if max_file_size_kb is None:
        return True, None

    if max_file_size_kb < 0:
        raise ValueError(
            f"max_file_size_kb must be non-negative, got {max_file_size_kb}"
        )

    file_path = Path(root_path) / path if root_path else Path(path)

    try:
        size = file_path.stat().st_size
    except OSError as exc:
        return False, f"cannot determine file size: {exc}"

    limit_bytes = max_file_size_kb * 1024
    if size > limit_bytes:
        return False, (
            f"exceeds maximum file size ({size} B > {limit_bytes} B limit)"
        )

    return True, None


def github_file_filter(
    path: str,
    include_patterns: Iterable[str] | None = None,
    exclude_patterns: Iterable[str] | None = None,
    root_path: str | None = None,
    max_file_size_kb: int | None = 200,
) -> tuple[bool, str]:
    normalized_path = _normalize_path(path)
    basename = os.path.basename(normalized_path)

    # When a root_path is provided, match include/exclude patterns against
    # the path relative to that root so patterns like `src/*` work as
    # expected for absolute file paths.
    match_path = normalized_path
    if root_path and os.path.isabs(path):
        try:
            rel = os.path.relpath(path, root_path)
            match_path = _normalize_path(rel)
        except (OSError, ValueError):
            match_path = normalized_path

    if _matches_any(match_path, exclude_patterns):
        return False, "excluded by pattern"

    explicitly_included = _matches_any(match_path, include_patterns)

    if basename in PROTECTED_LARGE_FILES:
        if not _matches_protected_include(match_path, include_patterns):
            return False, "protected large file"

    if explicitly_included:
        allowed, reason = is_file_size_allowed(
            path,
            root_path=root_path,
            max_file_size_kb=max_file_size_kb,
        )
        if not allowed:
            return False, reason or "exceeds maximum file size"
        return True, ""

    # Check default ignore rules against the match path (relative when
    # possible) so directory patterns like `node_modules` are detected.
    if is_default_ignored(match_path):
        return False, "ignored by default rules"

    allowed, reason = is_file_size_allowed(
        path,
        root_path=root_path,
        max_file_size_kb=max_file_size_kb,
    )
    if not allowed:
        return False, reason or "exceeds maximum file size"

    return True, ""
