from __future__ import annotations

import threading

from repo2readme.services import summarization
from repo2readme.summarize import directory_summary


class FakeCache:
    def __init__(self, cached=None):
        self.cached = cached
        self.saved = []
        self.lookups = []

    def get(self, *args):
        self.lookups.append(args)
        return self.cached

    def put(self, *args):
        self.saved.append(args)


def _document(path, relative_path):
    return {
        "content": "print('hello')",
        "metadata": {
            "file_path": path,
            "relative_path": relative_path,
            "language": "python",
            "mtime": 1,
        },
    }


def test_summaries_keep_document_order_when_workers_finish_out_of_order(monkeypatch):
    second_finished = threading.Event()

    def fake_summarize_file(file_path, **_kwargs):
        if file_path.endswith("first.py"):
            assert second_finished.wait(timeout=2)
        else:
            second_finished.set()
        return {"file_path": file_path, "description": file_path}

    monkeypatch.setattr(summarization, "summarize_file", fake_summarize_file)
    cache = FakeCache()

    summaries, errors = summarization.generate_all_summaries(
        [
            _document("/repo/first.py", "first.py"),
            _document("/repo/second.py", "second.py"),
        ],
        cache,
        max_workers=2,
    )

    assert errors == []
    assert [item["file_path"] for item in summaries] == [
        "/repo/first.py",
        "/repo/second.py",
    ]
    assert [item["relative_path"] for item in summaries] == [
        "first.py",
        "second.py",
    ]


def test_cached_summary_gets_the_current_relative_path():
    cache = FakeCache(
        cached={"file_path": "/old/checkout/src/main.py", "description": "entry"}
    )

    summaries, errors = summarization.generate_all_summaries(
        [_document("/new/checkout/src/main.py", "src/main.py")],
        cache,
        cache_namespace="remote-abc",
    )

    assert errors == []
    assert summaries[0]["file_path"] == "/new/checkout/src/main.py"
    assert summaries[0]["relative_path"] == "src/main.py"
    assert cache.lookups[0][0] == "remote-abc/src/main.py"
    assert cache.saved == []


def test_directory_tree_uses_relative_paths_when_available():
    tree = summarization.build_directory_tree(
        [
            {
                "file_path": "/tmp/clone-123/src/main.py",
                "relative_path": "src/main.py",
                "description": "entry",
            }
        ]
    )

    assert "" not in tree["children"]
    assert "src" in tree["children"]
    assert tree["children"]["src"]["files"][0]["file_path"] == "/tmp/clone-123/src/main.py"


def test_failed_directory_rollup_falls_back_to_file_summaries(monkeypatch):
    file_summaries = [
        {
            "file_path": f"/tmp/clone/src/file_{index}.py",
            "relative_path": f"src/file_{index}.py",
            "description": "file summary",
        }
        for index in range(16)
    ]

    monkeypatch.setattr(
        directory_summary,
        "summarize_directory",
        lambda **_kwargs: {"file_path": "src", "error": "provider unavailable"},
    )

    result = summarization.generate_hierarchical_summaries(file_summaries)

    assert result == file_summaries



def test_remote_cache_key_does_not_depend_on_temporary_clone_path():
    first = summarization.summary_cache_key(
        {
            "file_path": "/tmp/clone-one/src/main.py",
            "relative_path": "src/main.py",
        },
        "remote-abc",
    )
    second = summarization.summary_cache_key(
        {
            "file_path": "/tmp/clone-two/src/main.py",
            "relative_path": "src/main.py",
        },
        "remote-abc",
    )

    assert first == second == "remote-abc/src/main.py"
