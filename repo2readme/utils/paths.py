"""Repository-relative path handling.

Documents carry an absolute ``file_path`` because the loaders need it for I/O.
Everything downstream - the summarization prompt, the cache key, the directory
roll-up - wants the path *relative to the repository*, and had been using the
absolute one instead. That put ``/Users/<name>/work/app/src/api/routes.py`` (or,
for a ``--url`` run, a temporary clone directory) into the model's context,
where it was echoed back into the generated README; it made the roll-up build a
directory node per filesystem component; and it made the cache miss whenever the
checkout moved.

One helper, used everywhere, so the normalization cannot drift between callers.
"""

from __future__ import annotations

import os


def to_posix(path: str) -> str:
    """Normalize separators and strip a redundant ``./`` prefix."""
    if not path:
        return ""

    normalized = str(path).replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.rstrip("/") or normalized


def to_repo_relative(path: str, root: str) -> str:
    """
    Express ``path`` relative to ``root`` as a POSIX path.

    Returns the normalized ``path`` unchanged when it is already relative, and
    falls back to the basename when the path resolves outside ``root`` - a
    repository-relative path that escapes the repository is not something the
    prompt or the cache key should carry.
    """
    normalized = to_posix(path)
    if not normalized:
        return ""

    if not root:
        return normalized

    normalized_root = to_posix(root)

    # Prefix strip first: it works for a path shape the running platform does
    # not consider absolute, such as a Windows path seen on Linux.
    if normalized_root and normalized.startswith(f"{normalized_root}/"):
        return normalized[len(normalized_root) + 1:]

    if not os.path.isabs(normalized):
        return normalized

    try:
        relative = os.path.relpath(normalized, normalized_root)
    except ValueError:
        # Different drives on Windows.
        return os.path.basename(normalized)

    relative = to_posix(relative)
    if relative == ".." or relative.startswith("../"):
        return os.path.basename(normalized)

    return relative


def display_path(metadata: dict, root: str | None = None) -> str:
    """
    The path to show the user and give to the model for a loaded document.

    Prefers the ``relative_path`` the loaders already record, and derives one
    from ``file_path`` when it is missing so callers that build metadata by
    hand still get a repository-relative result.
    """
    if not metadata:
        return ""

    relative = to_posix(metadata.get("relative_path") or "")
    if relative:
        return relative

    absolute = metadata.get("file_path") or ""
    if root:
        return to_repo_relative(absolute, root)
    return to_posix(absolute)
