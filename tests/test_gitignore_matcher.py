"""
Tests for the cached, nesting-aware gitignore matcher (issue #129).

Covers:
- rules are read and compiled once, not once per path
- an edit is still picked up, and a cached matcher is not stale
- nested .gitignore files apply to their subtree, the way git applies them
- negation, directory-only rules and root-anchored rules keep working
- the traversal pipeline honours nested rules end to end
"""

from __future__ import annotations

import pytest

from repo2readme.loaders.traversal.pipeline import TraversalPipeline
from repo2readme.utils import gitignore as gitignore_module
from repo2readme.utils.gitignore import (
    GitignoreMatcher,
    clear_matcher_cache,
    get_matcher,
    is_gitignored,
)

# pathspec is an optional dependency; without it gitignore support is a no-op
# and there is nothing here to assert. Declared as a module-level mark rather
# than an importorskip so the imports above can stay at the top of the file.
pytestmark = pytest.mark.skipif(
    gitignore_module.pathspec is None, reason="pathspec is not installed"
)
pathspec = gitignore_module.pathspec


@pytest.fixture(autouse=True)
def _isolated_matcher_cache():
    """Every test starts with an empty process-level cache."""
    clear_matcher_cache()
    yield
    clear_matcher_cache()


@pytest.fixture
def counted_compiles(monkeypatch):
    """Count how many times a PathSpec is compiled."""
    counter = {"n": 0}
    original = pathspec.PathSpec.from_lines

    def counting(*args, **kwargs):
        counter["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(pathspec.PathSpec, "from_lines", staticmethod(counting))
    return counter


def _repo(tmp_path, files: dict[str, str]):
    for relative, body in files.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


class TestCompilationIsCached:
    def test_repeated_queries_compile_once(self, tmp_path, counted_compiles):
        root = _repo(tmp_path, {".gitignore": "*.log\nbuild/\n"})
        for index in range(50):
            is_gitignored(str(root / f"file{index}.py"), str(root))
        assert counted_compiles["n"] == 1

    def test_traversal_compiles_once_per_directory(self, tmp_path, counted_compiles):
        files = {".gitignore": "*.log\n"}
        for package in range(5):
            for module in range(10):
                files[f"pkg{package}/m{module}.py"] = "x = 1\n"
        root = _repo(tmp_path, files)

        TraversalPipeline(folder_path=str(root), respect_gitignore=True).run()

        # One compile for the root; the subdirectories have no rules of their
        # own, so there is nothing to compile for them.
        assert counted_compiles["n"] == 1

    def test_matcher_is_shared_per_root(self, tmp_path):
        root = _repo(tmp_path, {".gitignore": "*.log\n"})
        assert get_matcher(str(root)) is get_matcher(str(root))

    def test_different_roots_get_different_matchers(self, tmp_path):
        a = _repo(tmp_path / "a", {".gitignore": "*.log\n"})
        b = _repo(tmp_path / "b", {".gitignore": "*.tmp\n"})
        assert get_matcher(str(a)) is not get_matcher(str(b))

    def test_relative_and_absolute_roots_share_a_matcher(self, tmp_path, monkeypatch):
        root = _repo(tmp_path, {".gitignore": "*.log\n"})
        monkeypatch.chdir(root)
        assert get_matcher(".") is get_matcher(str(root))

    def test_clear_matcher_cache_drops_everything(self, tmp_path):
        root = _repo(tmp_path, {".gitignore": "*.log\n"})
        first = get_matcher(str(root))
        clear_matcher_cache()
        assert get_matcher(str(root)) is not first


class TestCacheDoesNotGoStale:
    def test_edited_rules_are_picked_up(self, tmp_path):
        root = _repo(tmp_path, {".gitignore": "*.log\n"})
        target = root / "notes.txt"
        target.write_text("hi", encoding="utf-8")

        assert is_gitignored(str(target), str(root)) is False

        # Size differs, so the stamp changes even if mtime resolution is coarse.
        (root / ".gitignore").write_text("*.log\n*.txt\n", encoding="utf-8")
        assert is_gitignored(str(target), str(root)) is True

    def test_rules_file_created_after_the_first_query(self, tmp_path):
        root = tmp_path
        target = root / "notes.log"
        target.write_text("hi", encoding="utf-8")

        assert is_gitignored(str(target), str(root)) is False

        (root / ".gitignore").write_text("*.log\n", encoding="utf-8")
        assert is_gitignored(str(target), str(root)) is True

    def test_rules_file_removed_after_the_first_query(self, tmp_path):
        root = _repo(tmp_path, {".gitignore": "*.log\n"})
        target = root / "notes.log"
        target.write_text("hi", encoding="utf-8")

        assert is_gitignored(str(target), str(root)) is True

        (root / ".gitignore").unlink()
        assert is_gitignored(str(target), str(root)) is False


# ---------------------------------------------------------------------------
# Nested rules
# ---------------------------------------------------------------------------


class TestNestedGitignore:
    def test_subdirectory_rules_apply_to_their_subtree(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                ".gitignore": "*.log\n",
                "frontend/.gitignore": "build/\n",
                "frontend/build/bundle.js": "console.log(1)\n",
                "frontend/src/app.js": "export default 1\n",
            },
        )
        assert is_gitignored(str(root / "frontend/build"), str(root)) is True
        assert is_gitignored(str(root / "frontend/build/bundle.js"), str(root)) is True
        assert is_gitignored(str(root / "frontend/src/app.js"), str(root)) is False

    def test_subdirectory_rules_do_not_leak_upwards(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                "frontend/.gitignore": "build/\n",
                "build/output.txt": "x\n",
            },
        )
        assert is_gitignored(str(root / "build"), str(root)) is False
        assert is_gitignored(str(root / "build/output.txt"), str(root)) is False

    def test_subdirectory_rules_do_not_leak_sideways(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                "frontend/.gitignore": "dist/\n",
                "backend/dist/server.py": "x = 1\n",
            },
        )
        assert is_gitignored(str(root / "backend/dist/server.py"), str(root)) is False

    def test_rules_are_relative_to_their_own_directory(self, tmp_path):
        """`/secret.txt` in a nested file anchors to that directory, not the root."""
        root = _repo(
            tmp_path,
            {
                "pkg/.gitignore": "/secret.txt\n",
                "pkg/secret.txt": "x\n",
                "secret.txt": "x\n",
            },
        )
        assert is_gitignored(str(root / "pkg/secret.txt"), str(root)) is True
        assert is_gitignored(str(root / "secret.txt"), str(root)) is False

    def test_three_levels_deep(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                "a/b/.gitignore": "*.tmp\n",
                "a/b/c/scratch.tmp": "x\n",
                "a/b/c/keep.py": "x = 1\n",
            },
        )
        assert is_gitignored(str(root / "a/b/c/scratch.tmp"), str(root)) is True
        assert is_gitignored(str(root / "a/b/c/keep.py"), str(root)) is False


# ---------------------------------------------------------------------------
# Behaviour that must not have changed
# ---------------------------------------------------------------------------


class TestExistingBehaviourPreserved:
    def test_root_gitignore(self, tmp_path):
        root = _repo(tmp_path, {".gitignore": "*.log\n"})
        assert is_gitignored(str(root / "debug.log"), str(root)) is True
        assert is_gitignored(str(root / "app.py"), str(root)) is False

    def test_git_info_exclude_is_read(self, tmp_path):
        root = _repo(tmp_path, {".git/info/exclude": "scratch/\n"})
        (root / "scratch").mkdir()
        assert is_gitignored(str(root / "scratch"), str(root)) is True

    def test_git_info_exclude_only_applies_at_the_root(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                ".git/info/exclude": "*.log\n",
                "pkg/.git/info/exclude": "*.py\n",
                "pkg/app.py": "x = 1\n",
            },
        )
        assert is_gitignored(str(root / "pkg/app.py"), str(root)) is False

    def test_directory_only_rule_needs_the_trailing_slash(self, tmp_path):
        root = _repo(tmp_path, {".gitignore": "build/\n"})
        (root / "build").mkdir()
        (root / "build.py").write_text("x = 1\n", encoding="utf-8")
        assert is_gitignored(str(root / "build"), str(root)) is True
        assert is_gitignored(str(root / "build.py"), str(root)) is False

    def test_negation(self, tmp_path):
        root = _repo(tmp_path, {".gitignore": "*.log\n!keep.log\n"})
        assert is_gitignored(str(root / "debug.log"), str(root)) is True
        assert is_gitignored(str(root / "keep.log"), str(root)) is False

    def test_comments_and_blank_lines(self, tmp_path):
        root = _repo(tmp_path, {".gitignore": "# a comment\n\n*.log\n"})
        assert is_gitignored(str(root / "debug.log"), str(root)) is True

    def test_missing_root_returns_false(self, tmp_path):
        assert is_gitignored(str(tmp_path / "a.py"), str(tmp_path / "nope")) is False

    def test_empty_root_returns_false(self, tmp_path):
        assert is_gitignored(str(tmp_path / "a.py"), "") is False

    def test_no_rules_files_returns_false(self, tmp_path):
        assert is_gitignored(str(tmp_path / "a.py"), str(tmp_path)) is False

    def test_path_outside_the_root(self, tmp_path):
        root = _repo(tmp_path / "repo", {".gitignore": "*.log\n"})
        outside = tmp_path / "elsewhere" / "debug.log"
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_text("x", encoding="utf-8")
        assert is_gitignored(str(outside), str(root)) is False

    def test_root_itself_is_never_ignored(self, tmp_path):
        root = _repo(tmp_path, {".gitignore": "*\n"})
        assert is_gitignored(str(root), str(root)) is False

    def test_unreadable_rules_file_is_skipped(self, tmp_path, monkeypatch):
        root = _repo(tmp_path, {".gitignore": "*.log\n"})

        def boom(*args, **kwargs):
            raise OSError("permission denied")

        monkeypatch.setattr("builtins.open", boom)
        assert is_gitignored(str(root / "debug.log"), str(root)) is False

    def test_pathspec_missing_disables_matching(self, tmp_path, monkeypatch):
        root = _repo(tmp_path, {".gitignore": "*.log\n"})
        monkeypatch.setattr(gitignore_module, "pathspec", None)
        clear_matcher_cache()
        assert is_gitignored(str(root / "debug.log"), str(root)) is False


class TestMatcherApi:
    def test_is_dir_hint_avoids_the_stat(self, tmp_path):
        """A directory rule must match even for a path that no longer exists."""
        root = _repo(tmp_path, {".gitignore": "build/\n"})
        matcher = GitignoreMatcher(str(root))
        assert matcher.is_ignored(str(root / "build"), is_dir=True) is True
        assert matcher.is_ignored(str(root / "build"), is_dir=False) is False

    def test_clear_forces_a_recompile(self, tmp_path, counted_compiles):
        root = _repo(tmp_path, {".gitignore": "*.log\n"})
        matcher = GitignoreMatcher(str(root))
        matcher.is_ignored(str(root / "a.log"))
        matcher.clear()
        matcher.is_ignored(str(root / "a.log"))
        assert counted_compiles["n"] == 2


# ---------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------


class TestTraversalHonoursNestedRules:
    def test_nested_build_directory_is_skipped(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                "frontend/.gitignore": "generated/\n",
                "frontend/generated/bundle.js": "console.log(1)\n",
                "frontend/src/app.js": "export default 1\n",
                "app.py": "x = 1\n",
            },
        )

        documents, ctx = TraversalPipeline(
            folder_path=str(root), respect_gitignore=True
        ).run()

        loaded = sorted(doc.metadata["relative_path"] for doc in documents)
        assert "frontend/src/app.js" in loaded
        assert "app.py" in loaded
        assert not any(path.startswith("frontend/generated") for path in loaded)
        assert any(
            "generated" in path and reason == "ignored by gitignore"
            for path, reason in ctx.skipped
        )

    def test_without_the_flag_nothing_is_gitignored(self, tmp_path):
        root = _repo(
            tmp_path,
            {
                "frontend/.gitignore": "generated/\n",
                "frontend/generated/bundle.js": "console.log(1)\n",
            },
        )

        documents, _ = TraversalPipeline(
            folder_path=str(root), respect_gitignore=False
        ).run()

        loaded = sorted(doc.metadata["relative_path"] for doc in documents)
        assert "frontend/generated/bundle.js" in loaded



def test_nested_negation_overrides_root_rule(tmp_path):
    (tmp_path / ".gitignore").write_text("*.log\n", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / ".gitignore").write_text("!keep.log\n", encoding="utf-8")
    (nested / "keep.log").write_text("keep", encoding="utf-8")

    assert not is_gitignored(str(nested / "keep.log"), str(tmp_path))


def test_root_gitignore_overrides_git_info_exclude(tmp_path):
    git_info = tmp_path / ".git" / "info"
    git_info.mkdir(parents=True)
    (git_info / "exclude").write_text("important.log\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("!important.log\n", encoding="utf-8")
    target = tmp_path / "important.log"
    target.write_text("keep", encoding="utf-8")

    assert not is_gitignored(str(target), str(tmp_path))
