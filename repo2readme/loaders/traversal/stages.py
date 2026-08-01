"""
Pipeline stages for repository traversal.

Defines the data structures passed between stages and the pure functions
that implement each stage of the pipeline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterable, Optional
from collections import OrderedDict

from repo2readme.utils.filter import github_file_filter
from repo2readme.utils.gitignore import is_gitignored


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiscoveryResult:
    """Result of the repository discovery stage (os.walk)."""

    files: tuple[str, ...]  # absolute paths, sorted for determinism
    root_path: str


@dataclass(frozen=True)
class FilteredFile:
    """A file that passed filtering, ready for metadata extraction."""

    absolute_path: str
    relative_path: str
    file_name: str


@dataclass(frozen=True)
class FileMetadata:
    """Extracted metadata for a single file."""

    absolute_path: str
    relative_path: str
    file_name: str
    file_type: str
    file_size: int
    language: str


@dataclass(frozen=True)
class DocumentResult:
    """Final document with content and metadata."""

    page_content: str
    metadata: dict


@dataclass
class PipelineContext:
    """
    Shared context that flows through the pipeline.

    Retains skip information for reporting and a reference to the
    root path used during traversal.
    """

    root_path: str
    skipped: list[tuple[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 1: Repository discovery – walk the directory tree
# ---------------------------------------------------------------------------


def discover_files(
    folder_path: str,
    include_patterns: Iterable[str] | None = None,
    exclude_patterns: Iterable[str] | None = None,
    max_file_size_kb: int | None = 200,
    respect_gitignore: bool = False,
) -> tuple[list[str], PipelineContext]:
    """
    Walk the directory tree, apply directory-level filtering, and collect
    file paths that pass.
    """
    root_resolved = os.path.realpath(folder_path)
    visited_dirs: set[str] = {root_resolved}
    discovered: list[str] = []
    skipped: list[tuple[str, str]] = []

    for current, dirs, files in os.walk(folder_path):
        # --- Filter directories in-place (os.walk convention) ---
        new_dirs: list[str] = []
        dirs.sort(key=lambda d: (os.path.islink(os.path.join(current, d)), d))
        for directory in dirs:
            full_dir_path = os.path.join(current, directory)
            rel_dir_path = os.path.relpath(full_dir_path, folder_path).replace(
                "\\", "/"
            )

            allowed, reason = github_file_filter(
                rel_dir_path,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
                root_path=folder_path,
                max_file_size_kb=None,
            )

            if not allowed:
                skipped.append((rel_dir_path + "/", reason))
                continue

            if respect_gitignore and is_gitignored(full_dir_path, folder_path):
                skipped.append((rel_dir_path + "/", "ignored by gitignore"))
                continue

            resolved_path = os.path.realpath(full_dir_path)

            if resolved_path in visited_dirs:
                skipped.append(
                    (rel_dir_path + "/", "circular or duplicate symbolic link")
                )
                continue

            if os.path.islink(full_dir_path):
                if not os.path.isdir(resolved_path):
                    skipped.append((rel_dir_path + "/", "broken symbolic link"))
                    continue
                if not _is_within_root(resolved_path, root_resolved):
                    skipped.append(
                        (rel_dir_path + "/", "symbolic link outside repository")
                    )
                    continue

            visited_dirs.add(resolved_path)
            new_dirs.append(directory)

        dirs[:] = new_dirs

        # --- Collect file candidates ---
        for file_name in files:
            full_path = os.path.join(current, file_name)
            rel_path = os.path.relpath(full_path, folder_path).replace("\\", "/")

            if os.path.islink(full_path):
                resolved_path = os.path.realpath(full_path)
                if not os.path.exists(resolved_path):
                    skipped.append((rel_path, "broken symbolic link"))
                    continue
                if not _is_within_root(resolved_path, root_resolved):
                    skipped.append(
                        (rel_path, "symbolic link outside repository")
                    )
                    continue

            # Skip non-regular files (FIFOs, sockets, etc.)
            if not os.path.isfile(full_path):
                continue

            discovered.append(full_path)

    # Sort for deterministic ordering
    discovered.sort()
    return discovered, PipelineContext(root_path=folder_path, skipped=skipped)


def _is_within_root(path: str, root: str) -> bool:
    try:
        common = os.path.commonpath([path, root])
        return common == root
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Stage 2: File filtering – apply include/exclude/size/gitignore rules
# ---------------------------------------------------------------------------


def filter_file(
    absolute_path: str,
    folder_path: str,
    include_patterns: Iterable[str] | None = None,
    exclude_patterns: Iterable[str] | None = None,
    max_file_size_kb: int | None = 200,
    respect_gitignore: bool = False,
) -> tuple[Optional[FilteredFile], Optional[str]]:
    """
    Apply all filtering rules to a single file.

    Returns (FilteredFile, None) if the file passes, or
    (None, skip_reason) if it is rejected.
    """
    rel_path = os.path.relpath(absolute_path, folder_path).replace("\\", "/")
    file_name = os.path.basename(absolute_path)

    allowed, reason = github_file_filter(
        rel_path,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        root_path=folder_path,
        max_file_size_kb=max_file_size_kb,
    )
    if not allowed:
        return None, reason

    if respect_gitignore and is_gitignored(absolute_path, folder_path):
        return None, "ignored by gitignore"

    return (
        FilteredFile(
            absolute_path=absolute_path,
            relative_path=rel_path,
            file_name=file_name,
        ),
        None,
    )


# ---------------------------------------------------------------------------
# Stage 3: Metadata extraction
# ---------------------------------------------------------------------------


def extract_file_metadata(
    filtered: FilteredFile,
    content: str,
) -> FileMetadata:
    """Extract metadata from a filtered file."""
    _, ext = os.path.splitext(filtered.file_name)
    try:
        file_size = os.path.getsize(filtered.absolute_path)
    except OSError:
        file_size = len(content.encode("utf-8"))

    return FileMetadata(
        absolute_path=filtered.absolute_path,
        relative_path=filtered.relative_path,
        file_name=filtered.file_name,
        file_type=ext.lower(),
        file_size=file_size,
        language="unknown",  # populated in the language detection stage
    )


# ---------------------------------------------------------------------------
# Stage 4: Language detection (can be parallelised per file)
# ---------------------------------------------------------------------------


def detect_file_language(metadata: FileMetadata, content: str) -> str:
    """Detect the programming language for a file."""
    from repo2readme.utils.detect_language import detect_lang

    # Pass the content so the detector can use shebang / content analysis
    return detect_lang(metadata.absolute_path, content=content)


# ---------------------------------------------------------------------------
# Stage 5: Document creation
# ---------------------------------------------------------------------------


def create_document(metadata: FileMetadata, content: str) -> DocumentResult:
    """Build the final DocumentResult from metadata and content."""
    return DocumentResult(
        page_content=content,
        metadata=OrderedDict(
            [
                ("file_path", metadata.absolute_path.replace("\\", "/")),
                ("file_name", metadata.file_name),
                ("file_type", metadata.file_type),
                ("relative_path", metadata.relative_path),
            ]
        ),
    )


# ---------------------------------------------------------------------------
# File content loader (I/O bound, can be parallelised)
# ---------------------------------------------------------------------------


def load_file_content(
    absolute_path: str,
) -> tuple[Optional[str], Optional[str]]:
    """
    Safely read the content of a file.

    When TextLoader is available (not None), uses it as the primary path
    for backward compatibility with tests. Otherwise, uses plain file
    reading first (fast, no heavy dependencies) and falls back to TextLoader
    only if the plain read fails with a UnicodeDecodeError.

    Returns (content, None) on success, or (None, error_message) on failure.
    """
    # When TextLoader is patched in tests, use it as the primary path to
    # preserve backward-compatible behavior. In normal operation TextLoader
    # is None, so fall back to plain open() to avoid eagerly importing
    # langchain for ordinary UTF-8 files.
    try:
        from repo2readme.loaders.loader import TextLoader as _TextLoader
        if _TextLoader is not None:
            loader = _TextLoader(absolute_path, autodetect_encoding=True)
            docs = loader.load()
            if docs:
                return docs[0].page_content, None
            return "", None
    except UnicodeDecodeError:
        # TextLoader failed due to encoding; fall back to plain open()
        pass
    except OSError as error:
        msg = f"permission_error: {error}"
        print(f"[ERROR] Permission/OS error loading {absolute_path}: {error}")
        return None, msg
    except Exception as error:
        msg = f"load_error: {error}"
        print(f"[ERROR] Cannot load {absolute_path}: {error}")
        return None, msg

    # Fast path: plain UTF-8 read without importing langchain.
    try:
        with open(absolute_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content, None
    except UnicodeDecodeError:
        msg = "encoding_error"
        print(f"[ERROR] Encoding error loading {absolute_path}")
        return None, msg
    except OSError as error:
        msg = f"permission_error: {error}"
        print(f"[ERROR] Permission/OS error loading {absolute_path}: {error}")
        return None, msg
    except Exception as error:
        msg = f"load_error: {error}"
        print(f"[ERROR] Cannot load {absolute_path}: {error}")
        return None, msg
