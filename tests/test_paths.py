"""Tests for repository-relative path handling.

Absolute paths used to reach the summarization prompt, the cache key and the
directory roll-up, which put machine-specific paths into the generated README,
built a directory node per filesystem component, and made the cache miss
whenever the checkout moved.
"""

import os
from unittest.mock import patch

import pytest

from repo2readme.services.summarization import (
    build_directory_tree,
    generate_all_summaries,
)
from repo2readme.summarize.summary import summarize_file
from repo2readme.utils.paths import display_path, to_posix, to_repo_relative

# ---------------------------------------------------------------------------
# to_posix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("src/main.py", "src/main.py"),
        ("src\\main.py", "src/main.py"),
        ("./src/main.py", "src/main.py"),
        ("././src/main.py", "src/main.py"),
        ("  src/main.py  ", "src/main.py"),
        ("src/pkg/", "src/pkg"),
        ("", ""),
    ],
)
def test_to_posix(raw, expected):
    assert to_posix(raw) == expected


# ---------------------------------------------------------------------------
# to_repo_relative
# ---------------------------------------------------------------------------


def test_absolute_path_under_root_becomes_relative():
    assert to_repo_relative("/home/me/app/src/api/routes.py", "/home/me/app") == (
        "src/api/routes.py"
    )


def test_absolute_path_at_the_root_becomes_a_bare_name():
    assert to_repo_relative("/home/me/app/README.md", "/home/me/app") == "README.md"


def test_a_relative_path_is_left_alone():
    assert to_repo_relative("src/main.py", "/home/me/app") == "src/main.py"
    assert to_repo_relative("./src/main.py", "/home/me/app") == "src/main.py"


def test_root_with_a_trailing_separator_is_tolerated():
    assert to_repo_relative("/home/me/app/src/a.py", "/home/me/app/") == "src/a.py"


def test_path_outside_the_root_falls_back_to_the_basename():
    """A repository-relative path that escapes the repository should not end up
    in the prompt or the cache key."""
    assert to_repo_relative("/etc/passwd", "/home/me/app") == "passwd"


def test_missing_root_returns_the_normalized_path():
    assert to_repo_relative("src\\main.py", "") == "src/main.py"


def test_empty_path_returns_empty():
    assert to_repo_relative("", "/home/me/app") == ""


def test_a_path_under_the_root_is_stripped_on_any_platform():
    """A Windows-shaped path is not "absolute" to POSIX os.path, but the prefix
    strip still has to work - CI runs on Linux, users do not."""
    assert to_repo_relative("C:/work/app/src/main.py", "C:/work/app") == "src/main.py"
    assert to_repo_relative("C:\\work\\app\\src\\main.py", "C:\\work\\app") == (
        "src/main.py"
    )


# ---------------------------------------------------------------------------
# display_path
# ---------------------------------------------------------------------------


def test_display_path_prefers_relative_path():
    metadata = {
        "file_path": "/private/var/folders/xy/T/app/src/main.py",
        "relative_path": "src/main.py",
    }
    assert display_path(metadata) == "src/main.py"


def test_display_path_normalizes_the_relative_path():
    assert display_path({"relative_path": "src\\main.py"}) == "src/main.py"


def test_display_path_derives_one_when_relative_path_is_missing():
    metadata = {"file_path": "/home/me/app/src/main.py"}
    assert display_path(metadata, root="/home/me/app") == "src/main.py"


def test_display_path_without_a_root_still_normalizes():
    assert display_path({"file_path": "src\\main.py"}) == "src/main.py"


def test_display_path_of_empty_metadata():
    assert display_path({}) == ""
    assert display_path(None) == ""


# ---------------------------------------------------------------------------
# summarize_file pins the path
# ---------------------------------------------------------------------------


def test_summarize_file_uses_the_given_path_in_the_prompt():
    seen = {}

    class FakeChain:
        def invoke(self, payload):
            seen.update(payload)
            return {"file_path": payload["file_path"], "description": "x"}

    with patch(
        "repo2readme.summarize.summary.create_summarizer", return_value=FakeChain()
    ):
        summarize_file("src/api/routes.py", "python", "code")

    assert seen["file_path"] == "src/api/routes.py"


def test_summarize_file_overwrites_a_path_the_model_got_wrong():
    """The prompt asks the model to echo the path back; the roll-up must not
    depend on it doing so."""

    class FakeChain:
        def invoke(self, payload):
            return {"file_path": "totally/made/up.py", "description": "x"}

    with patch(
        "repo2readme.summarize.summary.create_summarizer", return_value=FakeChain()
    ):
        result = summarize_file("src/api/routes.py", "python", "code")

    assert result["file_path"] == "src/api/routes.py"


def test_summarize_file_normalizes_windows_separators():
    class FakeChain:
        def invoke(self, payload):
            return {"file_path": payload["file_path"], "description": "x"}

    with patch(
        "repo2readme.summarize.summary.create_summarizer", return_value=FakeChain()
    ):
        result = summarize_file("src\\api\\routes.py", "python", "code")

    assert result["file_path"] == "src/api/routes.py"


def test_summarize_file_error_placeholder_carries_the_normalized_path():
    with patch(
        "repo2readme.summarize.summary.create_summarizer",
        side_effect=RuntimeError("boom"),
    ):
        result = summarize_file("src\\api\\routes.py", "python", "code")

    assert result["file_path"] == "src/api/routes.py"
    assert result["error"] == "boom"


def test_summarize_file_tolerates_a_non_dict_response():
    class FakeChain:
        def invoke(self, payload):
            return ["not", "a", "dict"]

    with patch(
        "repo2readme.summarize.summary.create_summarizer", return_value=FakeChain()
    ):
        assert summarize_file("a.py", "python", "code") == ["not", "a", "dict"]


# ---------------------------------------------------------------------------
# build_directory_tree
# ---------------------------------------------------------------------------


def test_directory_tree_from_relative_paths():
    tree = build_directory_tree(
        [
            {"file_path": "src/api/routes.py"},
            {"file_path": "src/main.py"},
            {"file_path": "README.md"},
        ]
    )

    assert set(tree["children"]) == {"src"}
    assert [s["file_path"] for s in tree["files"]] == ["README.md"]

    src = tree["children"]["src"]
    assert src["path"] == "src"
    assert set(src["children"]) == {"api"}
    assert src["children"]["api"]["path"] == "src/api"


def test_directory_tree_normalizes_absolute_paths():
    """An absolute path used to create a node per filesystem component, so a
    --url run started the tree at "/", "private", "var", "folders", ..."""
    tree = build_directory_tree([{"file_path": "/private/var/T/app/src/main.py"}])

    assert "" not in tree["children"]
    assert "/" not in tree["children"]
    assert "private" in tree["children"]  # still one node per component...
    # ...but no empty root node from the leading slash.
    assert all(name for name in tree["children"])


def test_directory_tree_normalizes_separators_and_dot_segments():
    tree = build_directory_tree(
        [{"file_path": "./src\\api/routes.py"}, {"file_path": "src/./main.py"}]
    )

    assert set(tree["children"]) == {"src"}
    assert set(tree["children"]["src"]["children"]) == {"api"}


def test_directory_tree_skips_unusable_entries():
    tree = build_directory_tree(
        [
            "a bare string",
            {"file_path": ""},
            {"file_path": "."},
            {"file_path": "src/main.py"},
        ]
    )
    assert set(tree["children"]) == {"src"}
    assert tree["files"] == []


# ---------------------------------------------------------------------------
# End to end through generate_all_summaries
# ---------------------------------------------------------------------------


class _RecordingCache:
    def __init__(self):
        self.gets = []
        self.puts = []

    def get(self, file_path, content, language):
        self.gets.append(file_path)
        # Always a miss: these tests are about which key is used, not hits.

    def put(self, file_path, content, language, summary, mtime):
        self.puts.append(file_path)


def _document(root, relative):
    return {
        "content": "print('hi')",
        "metadata": {
            "file_path": f"{root}/{relative}",
            "file_name": os.path.basename(relative),
            "file_type": ".py",
            "relative_path": relative,
        },
    }


def test_prompt_and_cache_key_use_the_relative_path():
    root = "/private/var/folders/xy/T/checkout"
    documents = [_document(root, "src/api/routes.py"), _document(root, "main.py")]
    cache = _RecordingCache()
    seen_paths = []

    def fake_summarize(file_path, language, content, **kwargs):
        seen_paths.append(file_path)
        return {"file_path": file_path, "description": "x"}

    with patch(
        "repo2readme.services.summarization.summarize_file", side_effect=fake_summarize
    ):
        summaries, errors = generate_all_summaries(documents, cache)

    assert errors == []
    assert sorted(seen_paths) == ["main.py", "src/api/routes.py"]
    assert sorted(cache.gets) == ["main.py", "src/api/routes.py"]
    assert sorted(cache.puts) == ["main.py", "src/api/routes.py"]
    assert not any(root in s["file_path"] for s in summaries)


def test_no_absolute_path_survives_into_the_summaries():
    root = "/Users/someone/work/app"
    documents = [_document(root, "src/main.py")]

    def fake_summarize(file_path, language, content, **kwargs):
        return {"file_path": file_path, "description": f"summary of {file_path}"}

    with patch(
        "repo2readme.services.summarization.summarize_file", side_effect=fake_summarize
    ):
        summaries, _ = generate_all_summaries(documents, _RecordingCache())

    rendered = str(summaries)
    assert "/Users/someone" not in rendered
    assert "src/main.py" in rendered


def test_failures_are_reported_with_the_relative_path():
    root = "/Users/someone/work/app"
    documents = [_document(root, "src/main.py")]

    with patch(
        "repo2readme.services.summarization.summarize_file",
        side_effect=RuntimeError("boom"),
    ):
        summaries, errors = generate_all_summaries(documents, _RecordingCache())

    assert summaries == []
    assert [e.file_path for e in errors] == ["src/main.py"]


def test_metadata_without_relative_path_still_works():
    documents = [
        {
            "content": "x",
            "metadata": {"file_path": "/abs/root/src/main.py", "file_type": ".py"},
        }
    ]
    cache = _RecordingCache()

    with patch(
        "repo2readme.services.summarization.summarize_file",
        side_effect=lambda file_path, **kw: {"file_path": file_path},
    ):
        generate_all_summaries(documents, cache)

    # No root is available here, so the absolute path is normalized but kept;
    # the run must not crash or drop the file.
    assert cache.gets == ["/abs/root/src/main.py"]
