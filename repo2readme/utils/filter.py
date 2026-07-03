import fnmatch
import os
from pathlib import Path
from typing import Iterable


IGNORE_DIRS = {
    "node_modules",
    ".next",
    ".npm",
    ".yarn",
    ".pnpm",
    "bower_components",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".mypy_cache",
    ".pytest_cache",
    "build",
    "target",
    ".gradle",
    ".mvn",
    "bin",
    "obj",
    "packages",
    ".nuget",
    ".bundle",
    "vendor",
    "vendor/bundle",
    "pkg",
    ".cargo",
    ".firebase",
    ".git",
    ".idea",
    ".vscode",
    ".cache",
    "coverage",
    "logs",
    "dist",
    "out",
    "public",
    "src/generated/prisma",
}

IGNORE_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "__init__.py",
    ".env",
    ".env.example",
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


def is_default_ignored(path: str) -> bool:
    normalized_path = _normalize_path(path)
    basename = os.path.basename(normalized_path)

    if basename in IGNORE_FILES:
        return True

    _, ext = os.path.splitext(basename)
    if ext in IGNORE_EXTENSIONS:
        return True

    padded_path = f"/{normalized_path}/"
    for directory in IGNORE_DIRS:
        normalized_dir = _normalize_path(directory)
        if f"/{normalized_dir}/" in padded_path:
            return True

    return False


def is_file_size_allowed(
    path: str,
    root_path: str | None = None,
    max_file_size_kb: int | None = 200,
) -> bool:
    if max_file_size_kb is None:
        return True

    file_path = Path(root_path) / path if root_path else Path(path)

    try:
        return file_path.stat().st_size <= max_file_size_kb * 1024
    except OSError:
        return True


def github_file_filter(
    path: str,
    include_patterns: Iterable[str] | None = None,
    exclude_patterns: Iterable[str] | None = None,
    root_path: str | None = None,
    max_file_size_kb: int | None = 200,
) -> bool:
    normalized_path = _normalize_path(path)
    basename = os.path.basename(normalized_path)

    if _matches_any(normalized_path, exclude_patterns):
        return False

    explicitly_included = _matches_any(normalized_path, include_patterns)

    if basename in PROTECTED_LARGE_FILES:
        if not _matches_protected_include(normalized_path, include_patterns):
            return False

    if explicitly_included:
        return is_file_size_allowed(
            path,
            root_path=root_path,
            max_file_size_kb=max_file_size_kb,
        )

    if is_default_ignored(path):
        return False

    return is_file_size_allowed(
        path,
        root_path=root_path,
        max_file_size_kb=max_file_size_kb,
    )