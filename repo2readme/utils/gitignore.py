from __future__ import annotations

import os

try:
    import pathspec
except ImportError:
    pathspec = None


def _load_gitignore_patterns(root_path: str):
    if pathspec is None:
        return None

    patterns = []

    gitignore_path = os.path.join(root_path, ".gitignore")
    if os.path.isfile(gitignore_path):
        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                patterns.extend(f.readlines())
        except OSError:
            pass

    git_info_exclude = os.path.join(root_path, ".git", "info", "exclude")
    if os.path.isfile(git_info_exclude):
        try:
            with open(git_info_exclude, "r", encoding="utf-8") as f:
                patterns.extend(f.readlines())
        except OSError:
            pass

    if not patterns:
        return None

    return pathspec.PathSpec.from_lines("gitignore", patterns)


def is_gitignored(path: str, root_path: str) -> bool:
    if not root_path or not os.path.isdir(root_path):
        return False

    spec = _load_gitignore_patterns(root_path)
    if spec is None:
        return False

    try:
        rel_path = os.path.relpath(path, root_path).replace("\\", "/")
    except ValueError:
        return False

    if spec.match_file(rel_path):
        return True

    if os.path.isdir(path):
        if spec.match_file(rel_path + "/"):
            return True

    return False
