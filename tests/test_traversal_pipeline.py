"""
Comprehensive tests for the modular traversal pipeline.

Covers:
- deterministic ordering
- concurrent traversal
- worker failures
- empty repositories
- repositories containing thousands of files (mock)
- nested directories
- gitignore handling
- performance regression checks where practical
"""

import os
from unittest.mock import patch

import pytest

import repo2readme.loaders.traversal.stages as stages
from repo2readme.loaders.traversal.pipeline import TraversalPipeline
from repo2readme.loaders.traversal.stages import (
    discover_files,
    filter_file,
    check_binary_file,
    extract_file_metadata,
    detect_file_language,
    create_document,
    load_file_content,
    FilteredFile,
    FileMetadata,
    ProgressEventType,
    TraversalProgressEvent,
)
from repo2readme.utils.filter import is_file_size_allowed as _real_is_file_size_allowed


@pytest.fixture
def sample_repo(tmp_path):
    repo = tmp_path / "sample_repo"
    repo.mkdir()
    src = repo / "src"
    src.mkdir()
    docs_dir = repo / "docs"
    docs_dir.mkdir()
    (repo / "README.md").write_text("# Sample", encoding="utf-8")
    (src / "main.py").write_text("print('hello')", encoding="utf-8")
    (src / "utils.py").write_text("def util(): pass", encoding="utf-8")
    (docs_dir / "guide.md").write_text("# Guide", encoding="utf-8")
    (repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
    return str(repo)


@pytest.fixture
def nested_repo(tmp_path):
    repo = tmp_path / "nested_repo"
    repo.mkdir()
    current = repo
    for i in range(10):
        current = current / f"level{i}"
        current.mkdir()
    (current / "leaf.py").write_text("# deep file", encoding="utf-8")
    return str(repo)


class TestDiscoverFiles:
    def test_discover_basic(self, sample_repo):
        files, ctx = discover_files(sample_repo)
        assert len(files) == 5  # README.md, main.py, utils.py, guide.md, .gitignore
        basenames = [os.path.basename(f) for f in files]
        assert basenames == sorted(basenames)

    def test_discover_empty_repo(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        files, ctx = discover_files(str(empty))
        assert files == []

    def test_discover_deterministic_ordering(self, tmp_path):
        repo = tmp_path / "order_test"
        repo.mkdir()
        for name in ["z.py", "y.py", "x.py"]:
            (repo / name).write_text("x", encoding="utf-8")
        files, ctx = discover_files(str(repo))
        basenames = [os.path.basename(f) for f in files]
        assert basenames == ["x.py", "y.py", "z.py"]

    def test_discover_subdirectories_excluded(self, tmp_path):
        repo = tmp_path / "sub_exclude"
        repo.mkdir()
        (repo / "node_modules").mkdir()
        (repo / "node_modules" / "pkg.js").write_text("x", encoding="utf-8")
        (repo / "src").mkdir()
        (repo / "src" / "app.py").write_text("x", encoding="utf-8")
        files, ctx = discover_files(str(repo))
        basenames = [os.path.basename(f) for f in files]
        assert "app.py" in basenames


class TestFilterFile:
    def test_filter_accepts_valid_file(self, tmp_path):
        fp = tmp_path / "test.py"
        fp.write_text("x", encoding="utf-8")
        result, reason = filter_file(str(fp), str(tmp_path))
        assert result is not None
        assert result.relative_path == "test.py"
        assert reason is None

    def test_filter_rejects_excluded(self, tmp_path):
        fp = tmp_path / "secret.py"
        fp.write_text("x", encoding="utf-8")
        result, reason = filter_file(str(fp), str(tmp_path), exclude_patterns=["secret.py"])
        assert result is None
        assert reason == "excluded by pattern"


class TestLoadFileContent:
    def test_load_text_file(self, tmp_path):
        fp = tmp_path / "test.py"
        fp.write_text("print('hello')", encoding="utf-8")
        content, error = load_file_content(str(fp))
        assert content == "print('hello')"
        assert error is None

    def test_load_empty_file(self, tmp_path):
        fp = tmp_path / "empty.txt"
        fp.write_text("", encoding="utf-8")
        content, error = load_file_content(str(fp))
        assert content is not None
        assert error is None


class TestExtractFileMetadata:
    def test_basic_metadata(self, tmp_path):
        fp = tmp_path / "test.py"
        fp.write_text("content", encoding="utf-8")
        ff = FilteredFile(absolute_path=str(fp), relative_path="test.py", file_name="test.py")
        metadata = extract_file_metadata(ff, "content")
        assert metadata.file_name == "test.py"
        assert metadata.file_type == ".py"
        assert metadata.relative_path == "test.py"
        assert metadata.language == "unknown"


class TestDetectFileLanguage:
    def test_detect_python(self, tmp_path):
        fp = tmp_path / "test.py"
        fp.write_text("import os", encoding="utf-8")
        ff = FilteredFile(absolute_path=str(fp), relative_path="test.py", file_name="test.py")
        metadata = extract_file_metadata(ff, "import os")
        lang = detect_file_language(metadata, "import os")
        assert lang == "python"


class TestCreateDocument:
    def test_document_creation(self):
        metadata = FileMetadata(
            absolute_path="/tmp/test.py", relative_path="test.py",
            file_name="test.py", file_type=".py", file_size=10, language="python",
        )
        doc = create_document(metadata, "print('hello')")
        assert doc.page_content == "print('hello')"
        assert doc.metadata["file_path"] == "/tmp/test.py"
        assert doc.metadata["file_name"] == "test.py"


class TestTraversalPipeline:
    def test_pipeline_basic(self, sample_repo):
        pipeline = TraversalPipeline(sample_repo)
        documents, ctx = pipeline.run()
        assert len(documents) == 4
        assert ctx.root_path == sample_repo

    def test_pipeline_empty_repo(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        pipeline = TraversalPipeline(str(empty))
        documents, ctx = pipeline.run()
        assert documents == []

    def test_pipeline_deterministic_ordering(self, tmp_path):
        repo = tmp_path / "det_order"
        repo.mkdir()
        for name in ["a.py", "b.py", "c.py", "d.py"]:
            (repo / name).write_text(f"# {name}", encoding="utf-8")
        pipeline = TraversalPipeline(str(repo), max_workers=4)
        docs1, _ = pipeline.run()
        docs2, _ = pipeline.run()
        paths1 = [d.metadata["relative_path"] for d in docs1]
        paths2 = [d.metadata["relative_path"] for d in docs2]
        assert paths1 == paths2
        assert paths1 == ["a.py", "b.py", "c.py", "d.py"]

    def test_pipeline_with_exclude(self, sample_repo):
        pipeline = TraversalPipeline(sample_repo, exclude_patterns=["*.md"])
        documents, ctx = pipeline.run()
        # main.py, utils.py (README.md and guide.md excluded; .gitignore filtered by default)
        assert len(documents) == 2

    def test_pipeline_gitignore(self, tmp_path):
        repo = tmp_path / "gitignore_pipeline"
        repo.mkdir()
        (repo / "main.py").write_text("print('hello')", encoding="utf-8")
        (repo / "debug.log").write_text("log data", encoding="utf-8")
        (repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
        pipeline = TraversalPipeline(str(repo), respect_gitignore=True)
        documents, ctx = pipeline.run()
        paths = [d.metadata["relative_path"] for d in documents]
        assert "main.py" in paths
        assert "debug.log" not in paths

    def test_pipeline_nested_directories(self, nested_repo):
        pipeline = TraversalPipeline(nested_repo)
        documents, ctx = pipeline.run()
        assert len(documents) == 1
        assert documents[0].metadata["relative_path"].endswith("leaf.py")

    def test_pipeline_concurrent_processing(self, tmp_path):
        repo = tmp_path / "concurrent"
        repo.mkdir()
        for i in range(50):
            (repo / f"file_{i:03d}.py").write_text(f"# file {i}", encoding="utf-8")
        pipeline = TraversalPipeline(str(repo), max_workers=8)
        documents, ctx = pipeline.run()
        assert len(documents) == 50
        paths = [d.metadata["relative_path"] for d in documents]
        assert paths == sorted(paths)

    @patch("repo2readme.loaders.traversal.pipeline.load_file_content")
    def test_pipeline_worker_failure(self, mock_load, tmp_path):
        repo = tmp_path / "worker_fail"
        repo.mkdir()
        (repo / "good.py").write_text("ok", encoding="utf-8")
        (repo / "bad.py").write_text("fail", encoding="utf-8")
        def side_effect(path):
            if "bad" in path:
                return None, "simulated_error"
            return "content", None
        mock_load.side_effect = side_effect
        pipeline = TraversalPipeline(str(repo), max_workers=2)
        documents, ctx = pipeline.run()
        assert len(documents) == 1

    def test_pipeline_thousands_of_files(self, tmp_path):
        repo = tmp_path / "thousands"
        repo.mkdir()
        for i in range(1000):
            (repo / f"file_{i:04d}.py").write_text(f"# file {i}", encoding="utf-8")
        pipeline = TraversalPipeline(str(repo), max_workers=8)
        documents, ctx = pipeline.run()
        assert len(documents) == 1000
        paths = [d.metadata["relative_path"] for d in documents]
        assert paths == sorted(paths)

    def test_pipeline_max_workers_respected(self, tmp_path):
        repo = tmp_path / "workers"
        repo.mkdir()
        for i in range(10):
            (repo / f"f{i}.py").write_text("x", encoding="utf-8")
        pipeline = TraversalPipeline(str(repo), max_workers=2)
        assert pipeline.max_workers == 2
        documents, ctx = pipeline.run()
        assert len(documents) == 10

    def test_pipeline_default_workers_unchanged(self, tmp_path):
        repo = tmp_path / "default_workers"
        repo.mkdir()
        (repo / "test.py").write_text("x", encoding="utf-8")
        pipeline = TraversalPipeline(str(repo))
        assert pipeline.max_workers is None
        documents, ctx = pipeline.run()
        assert len(documents) == 1

    def test_pipeline_include_pattern(self, tmp_path):
        repo = tmp_path / "include_test"
        repo.mkdir()
        (repo / "main.py").write_text("x", encoding="utf-8")
        (repo / "data.json").write_text("{}", encoding="utf-8")
        pipeline = TraversalPipeline(str(repo), include_patterns=["*.py"])
        documents, ctx = pipeline.run()
        paths = [d.metadata["relative_path"] for d in documents]
        assert "main.py" in paths
        assert "data.json" not in paths

    def test_no_size_limit_preserves_existing_behavior(self, tmp_path):
        repo = tmp_path / "unlimited_repo"
        repo.mkdir()
        (repo / "small.py").write_text("x" * 100, encoding="utf-8")
        (repo / "large.py").write_text("x" * 500_000, encoding="utf-8")
        pipeline = TraversalPipeline(str(repo), max_file_size_kb=None)
        documents, ctx = pipeline.run()
        assert len(documents) == 2
        paths = [d.metadata["relative_path"] for d in documents]
        assert "small.py" in paths
        assert "large.py" in paths
        assert len(ctx.skipped) == 0

    def test_file_below_limit_is_processed(self, tmp_path):
        repo = tmp_path / "below_repo"
        repo.mkdir()
        (repo / "small.py").write_text("x" * 100, encoding="utf-8")
        pipeline = TraversalPipeline(str(repo), max_file_size_kb=200)
        documents, ctx = pipeline.run()
        assert len(documents) == 1
        assert documents[0].metadata["relative_path"] == "small.py"

    def test_file_at_limit_is_processed(self, tmp_path):
        repo = tmp_path / "at_limit_repo"
        repo.mkdir()
        # Exactly 200 KB = 204800 bytes
        (repo / "exact.py").write_text("x" * 204800, encoding="utf-8")
        pipeline = TraversalPipeline(str(repo), max_file_size_kb=200)
        documents, ctx = pipeline.run()
        assert len(documents) == 1
        assert documents[0].metadata["relative_path"] == "exact.py"

    def test_file_above_limit_is_skipped(self, tmp_path):
        repo = tmp_path / "above_repo"
        repo.mkdir()
        (repo / "small.py").write_text("x" * 100, encoding="utf-8")
        (repo / "large.py").write_text("x" * 204801, encoding="utf-8")
        pipeline = TraversalPipeline(str(repo), max_file_size_kb=200)
        documents, ctx = pipeline.run()
        assert len(documents) == 1
        assert documents[0].metadata["relative_path"] == "small.py"
        skipped_paths = [s[0] for s in ctx.skipped]
        assert "large.py" in skipped_paths

    def test_skip_reason_includes_size_info(self, tmp_path):
        repo = tmp_path / "reason_repo"
        repo.mkdir()
        (repo / "large.py").write_text("x" * 300 * 1024, encoding="utf-8")
        pipeline = TraversalPipeline(str(repo), max_file_size_kb=200)
        documents, ctx = pipeline.run()
        assert len(documents) == 0
        skipped_reasons = [s[1] for s in ctx.skipped]
        assert any("exceeds maximum file size" in r for r in skipped_reasons)
        assert any("307200 B" in r for r in skipped_reasons)
        assert any("204800 B" in r for r in skipped_reasons)

    @patch("repo2readme.loaders.traversal.pipeline.load_file_content")
    def test_oversized_file_skipped_before_content_load(self, mock_load, tmp_path):
        repo = tmp_path / "no_load_repo"
        repo.mkdir()
        (repo / "small.py").write_text("x" * 100, encoding="utf-8")
        (repo / "large.py").write_text("x" * 250_000, encoding="utf-8")
        mock_load.return_value = ("content", None)
        pipeline = TraversalPipeline(str(repo), max_file_size_kb=200)
        documents, ctx = pipeline.run()
        assert len(documents) == 1
        assert documents[0].metadata["relative_path"] == "small.py"
        loaded_paths = [call.args[0] for call in mock_load.call_args_list]
        assert not any("large.py" in p for p in loaded_paths)

    @patch("repo2readme.loaders.traversal.pipeline.detect_file_language")
    def test_oversized_file_skipped_before_language_detection(
        self, mock_detect, tmp_path
    ):
        repo = tmp_path / "no_lang_repo"
        repo.mkdir()
        (repo / "small.py").write_text("x" * 100, encoding="utf-8")
        (repo / "large.py").write_text("x" * 250_000, encoding="utf-8")
        mock_detect.return_value = "python"
        pipeline = TraversalPipeline(str(repo), max_file_size_kb=200)
        documents, ctx = pipeline.run()
        assert len(documents) == 1
        detected_paths = [
            call.args[0].absolute_path for call in mock_detect.call_args_list
        ]
        assert not any("large.py" in p for p in detected_paths)

    def test_mixed_repo_processes_small_and_skips_large(self, tmp_path):
        repo = tmp_path / "mixed_repo"
        repo.mkdir()
        (repo / "a.py").write_text("x" * 100, encoding="utf-8")
        (repo / "b.py").write_text("x" * 500_000, encoding="utf-8")
        (repo / "c.py").write_text("x" * 100, encoding="utf-8")
        (repo / "d.py").write_text("x" * 750_000, encoding="utf-8")
        pipeline = TraversalPipeline(str(repo), max_file_size_kb=200)
        documents, ctx = pipeline.run()
        assert len(documents) == 2
        paths = [d.metadata["relative_path"] for d in documents]
        assert paths == ["a.py", "c.py"]
        skipped_paths = [s[0] for s in ctx.skipped]
        assert "b.py" in skipped_paths
        assert "d.py" in skipped_paths

    def test_multiple_oversized_files_handled(self, tmp_path):
        repo = tmp_path / "multi_large"
        repo.mkdir()
        for name in ["a.py", "b.py", "c.py"]:
            (repo / name).write_text("x" * 500_000, encoding="utf-8")
        pipeline = TraversalPipeline(str(repo), max_file_size_kb=200)
        documents, ctx = pipeline.run()
        assert len(documents) == 0
        assert len(ctx.skipped) == 3

    def test_document_ordering_remains_deterministic(self, tmp_path):
        repo = tmp_path / "order_repo"
        repo.mkdir()
        for name in ["z.py", "y.py", "x.py"]:
            (repo / name).write_text("x" * 100, encoding="utf-8")
        pipeline = TraversalPipeline(str(repo), max_file_size_kb=200)
        documents, ctx = pipeline.run()
        paths = [d.metadata["relative_path"] for d in documents]
        assert paths == ["x.py", "y.py", "z.py"]

    def test_existing_filtering_unchanged_with_size_limit(self, tmp_path):
        repo = tmp_path / "filter_repo"
        repo.mkdir()
        (repo / "main.py").write_text("x" * 100, encoding="utf-8")
        (repo / "debug.log").write_text("log data", encoding="utf-8")
        (repo / "large.py").write_text("x" * 500_000, encoding="utf-8")
        (repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
        pipeline = TraversalPipeline(
            str(repo), max_file_size_kb=200, respect_gitignore=True
        )
        documents, ctx = pipeline.run()
        paths = [d.metadata["relative_path"] for d in documents]
        assert "main.py" in paths
        assert "debug.log" not in paths
        assert "large.py" not in paths

    def test_negative_limit_raises_error(self, tmp_path):
        repo = tmp_path / "neg_repo"
        repo.mkdir()
        (repo / "a.py").write_text("x", encoding="utf-8")
        with pytest.raises(ValueError, match="non-negative"):
            TraversalPipeline(str(repo), max_file_size_kb=-1)

    def test_zero_limit_only_allows_empty_files(self, tmp_path):
        repo = tmp_path / "zero_repo"
        repo.mkdir()
        (repo / "empty.py").write_text("", encoding="utf-8")
        (repo / "small.py").write_text("x", encoding="utf-8")
        pipeline = TraversalPipeline(str(repo), max_file_size_kb=0)
        documents, ctx = pipeline.run()
        assert len(documents) == 1
        assert documents[0].metadata["relative_path"] == "empty.py"
        skipped_paths = [s[0] for s in ctx.skipped]
        assert "small.py" in skipped_paths

    @patch("repo2readme.utils.filter.is_file_size_allowed")
    def test_stat_failure_does_not_crash_traversal(
        self, mock_size_check, tmp_path
    ):
        repo = tmp_path / "stat_fail_repo"
        repo.mkdir()
        (repo / "good.py").write_text("x" * 100, encoding="utf-8")
        (repo / "bad.py").write_text("x" * 100, encoding="utf-8")

        def side_effect(path, **kwargs):
            if "bad.py" in path:
                return False, "cannot determine file size: simulated stat failure"
            return _real_is_file_size_allowed(path, **kwargs)

        mock_size_check.side_effect = side_effect

        pipeline = TraversalPipeline(str(repo), max_file_size_kb=200)
        documents, ctx = pipeline.run()
        assert len(documents) == 1
        assert documents[0].metadata["relative_path"] == "good.py"
        skipped_reasons = [s[1] for s in ctx.skipped]
        assert any("cannot determine file size" in r for r in skipped_reasons)


class TestEdgeCases:
    def test_repo_with_only_ignored_files(self, tmp_path):
        repo = tmp_path / "all_ignored"
        repo.mkdir()
        (repo / "file.exe").write_text("x", encoding="utf-8")
        pipeline = TraversalPipeline(str(repo))
        documents, ctx = pipeline.run()
        assert documents == []

    def test_pipeline_skip_failed_file(self, tmp_path):
        repo = tmp_path / "partial_fail"
        repo.mkdir()
        (repo / "good.py").write_text("print('ok')", encoding="utf-8")
        (repo / "bad.bin").write_bytes(b"\x00\x01\x02\x03")
        pipeline = TraversalPipeline(str(repo))
        documents, ctx = pipeline.run()
        assert len(documents) >= 1
        paths = [d.metadata["relative_path"] for d in documents]
        assert "good.py" in paths


class TestProgressCallbacks:
    """Tests for the optional progress-callback mechanism (issue #77)."""

    def _collect_events(self, tmp_path, file_specs, callback, **kwargs):
        repo = tmp_path / "cb_repo"
        repo.mkdir()
        for name, content in file_specs:
            target = repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        events = []
        callback.side_effect = lambda e: events.append(e)
        pipeline = TraversalPipeline(str(repo), progress_callback=callback, **kwargs)
        documents, ctx = pipeline.run()
        return documents, ctx, events

    def test_pipeline_works_without_callback(self, tmp_path):
        repo = tmp_path / "no_cb"
        repo.mkdir()
        (repo / "a.py").write_text("x", encoding="utf-8")
        pipeline = TraversalPipeline(str(repo))
        documents, ctx = pipeline.run()
        assert len(documents) == 1

    def test_callback_receives_total_count(self, tmp_path):
        from unittest.mock import MagicMock

        cb = MagicMock()
        self._collect_events(
            tmp_path,
            [("a.py", "x"), ("b.py", "y"), ("c.py", "z")],
            cb,
        )
        discovered_events = [
            c.args[0]
            for c in cb.call_args_list
            if c.args[0].event_type == ProgressEventType.FILES_DISCOVERED
        ]
        assert len(discovered_events) == 1
        assert discovered_events[0].total == 3
        assert discovered_events[0].completed == 0

    def test_callback_invoked_per_file(self, tmp_path):
        from unittest.mock import MagicMock

        cb = MagicMock()
        self._collect_events(
            tmp_path,
            [("a.py", "x"), ("b.py", "y")],
            cb,
        )
        terminal_events = [
            c.args[0]
            for c in cb.call_args_list
            if c.args[0].event_type != ProgressEventType.FILES_DISCOVERED
        ]
        assert len(terminal_events) == 2

    def test_callback_completed_and_total_counts(self, tmp_path):
        from unittest.mock import MagicMock

        cb = MagicMock()
        self._collect_events(
            tmp_path,
            [("a.py", "x"), ("b.py", "y"), ("c.py", "z")],
            cb,
        )
        terminal_events = [
            c.args[0]
            for c in cb.call_args_list
            if c.args[0].event_type != ProgressEventType.FILES_DISCOVERED
        ]
        completed_values = [e.completed for e in terminal_events]
        assert completed_values == [1, 2, 3]
        for e in terminal_events:
            assert e.total == 3

    def test_callback_receives_relative_path(self, tmp_path):
        from unittest.mock import MagicMock

        cb = MagicMock()
        self._collect_events(
            tmp_path,
            [("src/main.py", "x")],
            cb,
        )
        completed_events = [
            c.args[0]
            for c in cb.call_args_list
            if c.args[0].event_type == ProgressEventType.FILE_COMPLETED
        ]
        assert len(completed_events) == 1
        assert completed_events[0].relative_path == "src/main.py"

    def test_callback_with_multiple_workers(self, tmp_path):
        from unittest.mock import MagicMock

        cb = MagicMock()
        files = [(f"f{i:03d}.py", "#") for i in range(20)]
        self._collect_events(
            tmp_path,
            files,
            cb,
            max_workers=4,
        )
        terminal_events = [
            c.args[0]
            for c in cb.call_args_list
            if c.args[0].event_type != ProgressEventType.FILES_DISCOVERED
        ]
        assert len(terminal_events) == 20
        completed_values = [e.completed for e in terminal_events]
        assert set(completed_values) == set(range(1, 21))
        for e in terminal_events:
            assert e.total == 20

    def test_skipped_files_not_double_counted(self, tmp_path):
        from unittest.mock import MagicMock

        cb = MagicMock()
        self._collect_events(
            tmp_path,
            [("a.py", "x"), ("b.txt", "y"), ("c.py", "z")],
            cb,
        )
        terminal_events = [
            c.args[0]
            for c in cb.call_args_list
            if c.args[0].event_type != ProgressEventType.FILES_DISCOVERED
        ]
        assert len(terminal_events) == 3
        assert terminal_events[-1].completed == 3
        assert terminal_events[-1].total == 3
        completed_paths = [
            e.relative_path
            for e in terminal_events
            if e.event_type == ProgressEventType.FILE_COMPLETED
        ]
        skipped_paths = [
            e.relative_path
            for e in terminal_events
            if e.event_type == ProgressEventType.FILE_SKIPPED
        ]
        assert set(completed_paths) == {"a.py", "c.py"}
        assert skipped_paths == ["b.txt"]

    @patch("repo2readme.loaders.traversal.pipeline.load_file_content")
    def test_failed_files_not_double_counted(self, mock_load, tmp_path):
        from unittest.mock import MagicMock

        def side_effect(path):
            if "bad" in path:
                return None, "simulated_error"
            return "content", None

        mock_load.side_effect = side_effect

        cb = MagicMock()
        repo = tmp_path / "fail_repo"
        repo.mkdir()
        (repo / "good.py").write_text("ok", encoding="utf-8")
        (repo / "bad.py").write_text("fail", encoding="utf-8")

        pipeline = TraversalPipeline(str(repo), progress_callback=cb)
        documents, ctx = pipeline.run()

        terminal_events = [
            c.args[0]
            for c in cb.call_args_list
            if c.args[0].event_type != ProgressEventType.FILES_DISCOVERED
        ]
        assert len(terminal_events) == 2
        assert terminal_events[-1].completed == 2
        assert terminal_events[-1].total == 2
        types = [e.event_type for e in terminal_events]
        assert ProgressEventType.FILE_COMPLETED in types
        # Load errors are recorded as skips (added to ctx.skipped), so the
        # progress event is FILE_SKIPPED rather than FILE_FAILED.
        assert ProgressEventType.FILE_SKIPPED in types

    def test_callback_does_not_change_document_ordering(self, tmp_path):
        from unittest.mock import MagicMock

        cb = MagicMock()
        repo = tmp_path / "order_repo"
        repo.mkdir()
        for name in ["z.py", "y.py", "x.py"]:
            (repo / name).write_text("x", encoding="utf-8")

        pipeline = TraversalPipeline(str(repo), progress_callback=cb, max_workers=4)
        documents, ctx = pipeline.run()
        paths = [d.metadata["relative_path"] for d in documents]
        assert paths == ["x.py", "y.py", "z.py"]

    def test_callback_exception_does_not_corrupt_pipeline(self, tmp_path):
        repo = tmp_path / "cb_error_repo"
        repo.mkdir()
        (repo / "a.py").write_text("x", encoding="utf-8")
        (repo / "b.py").write_text("y", encoding="utf-8")

        call_count = 0

        def bad_callback(event):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("observer boom")

        pipeline = TraversalPipeline(str(repo), progress_callback=bad_callback)
        documents, ctx = pipeline.run()

        assert len(documents) == 2
        paths = [d.metadata["relative_path"] for d in documents]
        assert paths == ["a.py", "b.py"]
        assert call_count == 3  # 1 FILES_DISCOVERED + 2 FILE_COMPLETED
        assert any("Progress callback error" in e for e in ctx.errors)
        assert any("observer boom" in e for e in ctx.errors)

    def test_callback_exception_does_not_prevent_completion(self, tmp_path):
        repo = tmp_path / "cb_error2"
        repo.mkdir()
        files = [(f"f{i:02d}.py", "#") for i in range(5)]
        for name, content in files:
            (repo / name).write_text(content, encoding="utf-8")

        events = []
        fail_once = True

        def fail_once_callback(event):
            events.append(event)
            if fail_once and event.event_type == ProgressEventType.FILES_DISCOVERED:
                raise RuntimeError("first event boom")

        pipeline = TraversalPipeline(str(repo), progress_callback=fail_once_callback)
        documents, ctx = pipeline.run()

        assert len(documents) == 5
        assert len(events) == 6  # 1 discovered + 5 completed
        assert any("Progress callback error" in e for e in ctx.errors)


class TestBinaryDetection:
    """Integration tests for binary file detection in the traversal pipeline."""

    def test_png_skipped_in_pipeline(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "text.py").write_text("print('hello')", encoding="utf-8")
        # Use .dat so the file passes default filtering; binary detection
        # should still catch the PNG content signature.
        (repo / "image.dat").write_bytes(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        )
        pipeline = TraversalPipeline(str(repo))
        documents, ctx = pipeline.run()
        assert len(documents) == 1
        assert documents[0].metadata["relative_path"] == "text.py"
        skipped_reasons = {s[0]: s[1] for s in ctx.skipped}
        assert skipped_reasons["image.dat"] == "binary_file"

    def test_jpeg_skipped_in_pipeline(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "text.py").write_text("print('hello')", encoding="utf-8")
        (repo / "photo.dat").write_bytes(
            b"\xff\xd8\xff\xe0" + b"\x00" * 100
        )
        pipeline = TraversalPipeline(str(repo))
        documents, ctx = pipeline.run()
        assert len(documents) == 1
        skipped_reasons = {s[0]: s[1] for s in ctx.skipped}
        assert skipped_reasons["photo.dat"] == "binary_file"

    def test_null_byte_file_skipped(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "text.py").write_text("print('hello')", encoding="utf-8")
        (repo / "random.dat").write_bytes(b"\x00\x01\x02\x03")
        pipeline = TraversalPipeline(str(repo))
        documents, ctx = pipeline.run()
        assert len(documents) == 1
        skipped_reasons = {s[0]: s[1] for s in ctx.skipped}
        assert skipped_reasons["random.dat"] == "binary_file"

    def test_arbitrary_binary_skipped(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "text.py").write_text("print('hello')", encoding="utf-8")
        (repo / "datafile").write_bytes(
            b"\xde\xad\xbe\xef\xca\xfe\xba\xbe\x13\x37"
        )
        pipeline = TraversalPipeline(str(repo))
        documents, ctx = pipeline.run()
        assert len(documents) == 1
        skipped_reasons = {s[0]: s[1] for s in ctx.skipped}
        assert skipped_reasons["datafile"] == "binary_file"

    def test_mixed_repo_processes_successfully(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "a.py").write_text("print('a')", encoding="utf-8")
        (repo / "b.dat").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        (repo / "c.py").write_text("print('c')", encoding="utf-8")
        (repo / "d.py").write_text("print('d')", encoding="utf-8")
        pipeline = TraversalPipeline(str(repo))
        documents, ctx = pipeline.run()
        assert len(documents) == 3
        paths = [d.metadata["relative_path"] for d in documents]
        assert paths == ["a.py", "c.py", "d.py"]

    @patch("repo2readme.loaders.traversal.pipeline.load_file_content")
    def test_binary_does_not_reach_text_decoding(self, mock_load, tmp_path):
        mock_load.return_value = ("content", None)
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "text.py").write_text("print('hello')", encoding="utf-8")
        (repo / "image.dat").write_bytes(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        )
        pipeline = TraversalPipeline(str(repo))
        documents, ctx = pipeline.run()
        assert len(documents) == 1
        # load_file_content should only be called for text.py
        assert mock_load.call_count == 1
        assert "text.py" in mock_load.call_args[0][0]

    @patch("repo2readme.loaders.traversal.pipeline.detect_file_language")
    def test_binary_does_not_reach_language_detection(self, mock_detect, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "text.py").write_text("print('hello')", encoding="utf-8")
        (repo / "image.dat").write_bytes(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        )
        pipeline = TraversalPipeline(str(repo))
        documents, ctx = pipeline.run()
        assert len(documents) == 1
        # detect_file_language should only be called for text.py
        assert mock_detect.call_count == 1
        # First positional arg is FileMetadata; check its relative_path
        assert mock_detect.call_args[0][0].relative_path == "text.py"

    def test_binary_in_skipped_reporting(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "text.py").write_text("print('hello')", encoding="utf-8")
        (repo / "image.dat").write_bytes(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        )
        pipeline = TraversalPipeline(str(repo))
        documents, ctx = pipeline.run()
        skipped_reasons = {s[0]: s[1] for s in ctx.skipped}
        assert skipped_reasons["image.dat"] == "binary_file"

    def test_existing_filtering_unchanged(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text("print('hello')", encoding="utf-8")
        (repo / "node_modules").mkdir()
        (repo / "node_modules" / "pkg.js").write_text("x", encoding="utf-8")
        (repo / "large.dat").write_bytes(b"\x00" * 1024)
        pipeline = TraversalPipeline(str(repo))
        documents, ctx = pipeline.run()
        # main.py should be processed, node_modules excluded, large.dat is binary
        assert len(documents) == 1
        assert documents[0].metadata["relative_path"] == "main.py"

    def test_traversal_ordering_unchanged(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "z.py").write_text("z", encoding="utf-8")
        (repo / "a.py").write_text("a", encoding="utf-8")
        (repo / "m.dat").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        pipeline = TraversalPipeline(str(repo))
        documents, ctx = pipeline.run()
        paths = [d.metadata["relative_path"] for d in documents]
        assert paths == ["a.py", "z.py"]

    def test_binary_io_error_does_not_crash_pipeline(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "good.py").write_text("print('hello')", encoding="utf-8")
        (repo / "bad.dat").write_bytes(b"\x00" * 10)
        # Mock check_binary_file to simulate an I/O error only for bad.dat
        def check_binary_side_effect(path):
            if "bad.dat" in path:
                return False, "permission_error: permission denied"
            return False, None

        with patch(
            "repo2readme.loaders.traversal.pipeline.check_binary_file",
            side_effect=check_binary_side_effect,
        ):
            pipeline = TraversalPipeline(str(repo))
            documents, ctx = pipeline.run()
        # good.py should still be processed; bad.dat should be skipped with error
        assert len(documents) == 1
        assert documents[0].metadata["relative_path"] == "good.py"
        assert any("permission_error" in e for e in ctx.errors)
        skipped_reasons = {s[0]: s[1] for s in ctx.skipped}
        assert skipped_reasons["bad.dat"] == "permission_error: permission denied"

    def test_binary_check_stage_callable(self):
        """The check_binary_file stage is importable and callable."""
        assert callable(check_binary_file)


class TestRepositoryMetadata:
    """Cached repository metadata computed during traversal (issue #78)."""

    @staticmethod
    def _expected_stats(root):
        """Mirror the discovery-stage semantics used to build the cache."""
        file_count = 0
        directory_count = 0
        total_size = 0
        for current, dirs, files in os.walk(root):
            directory_count += 1
            for name in files:
                full = os.path.join(current, name)
                if os.path.isfile(full):
                    file_count += 1
                    total_size += os.path.getsize(full)
        return file_count, directory_count, total_size

    def test_metadata_created_during_discovery(self, sample_repo):
        files, ctx = discover_files(sample_repo)
        assert ctx.repository_metadata is not None
        assert ctx.repository_metadata.file_count == len(files)

    def test_pipeline_context_carries_metadata(self, sample_repo):
        pipeline = TraversalPipeline(sample_repo)
        documents, ctx = pipeline.run()
        assert len(documents) == 4
        assert ctx.repository_metadata is not None

    def test_metadata_values_match_repository(self, sample_repo):
        _, ctx = discover_files(sample_repo)
        exp_files, exp_dirs, exp_size = self._expected_stats(sample_repo)
        assert ctx.repository_metadata.file_count == exp_files
        assert ctx.repository_metadata.file_count == 5
        assert ctx.repository_metadata.directory_count == exp_dirs
        assert ctx.repository_metadata.directory_count == 3
        assert ctx.repository_metadata.total_size == exp_size
        assert ctx.repository_metadata.total_size > 0

    def test_metadata_stats_computed_once_not_per_consumer(self, sample_repo, monkeypatch):
        calls = {"count": 0}
        real = stages._get_file_size

        def counting(path):
            calls["count"] += 1
            return real(path)

        monkeypatch.setattr(stages, "_get_file_size", counting)
        _, ctx = discover_files(sample_repo)
        # Size aggregation runs exactly once per discovered file, even though
        # downstream consumers read the cached aggregate statistics.
        assert calls["count"] == ctx.repository_metadata.file_count
        # Reading the cached metadata triggers no further stat operations.
        before = calls["count"]
        assert ctx.repository_metadata.total_size > 0
        assert calls["count"] == before

    def test_full_pipeline_stats_computed_once(self, sample_repo, monkeypatch):
        calls = {"count": 0}
        real = stages._get_file_size

        def counting(path):
            calls["count"] += 1
            return real(path)

        monkeypatch.setattr(stages, "_get_file_size", counting)
        pipeline = TraversalPipeline(sample_repo)
        documents, ctx = pipeline.run()
        # One size stat per discovered file during discovery; downstream file
        # processing (documents) does not repeat the repository-size pass.
        assert ctx.repository_metadata.file_count == 5
        assert calls["count"] == ctx.repository_metadata.file_count

    def test_fresh_traversal_gets_fresh_metadata(self, tmp_path):
        repo = tmp_path / "fresh_meta"
        repo.mkdir()
        (repo / "a.py").write_text("x", encoding="utf-8")

        pipeline1 = TraversalPipeline(str(repo))
        _, ctx1 = pipeline1.run()
        meta1 = ctx1.repository_metadata

        (repo / "b.py").write_text("y", encoding="utf-8")
        pipeline2 = TraversalPipeline(str(repo))
        _, ctx2 = pipeline2.run()
        meta2 = ctx2.repository_metadata

        # A new scan must not reuse the previous scan's metadata object and
        # must reflect the current repository contents.
        assert meta1 is not meta2
        assert meta1.file_count == 1
        assert meta2.file_count == meta1.file_count + 1

    def test_empty_repository_metadata(self, tmp_path):
        empty = tmp_path / "empty_meta"
        empty.mkdir()
        pipeline = TraversalPipeline(str(empty))
        documents, ctx = pipeline.run()
        assert documents == []
        assert ctx.repository_metadata is not None
        assert ctx.repository_metadata.file_count == 0
        assert ctx.repository_metadata.directory_count == 1
        assert ctx.repository_metadata.total_size == 0

    def test_nested_directories_metadata(self, nested_repo):
        pipeline = TraversalPipeline(nested_repo)
        documents, ctx = pipeline.run()
        assert len(documents) == 1
        assert ctx.repository_metadata.file_count == 1
        assert ctx.repository_metadata.directory_count == 11
        leaf_path = os.path.join(
            nested_repo, *[f"level{i}" for i in range(10)], "leaf.py"
        )
        assert ctx.repository_metadata.total_size == os.path.getsize(leaf_path)

    def test_document_ordering_unchanged_with_metadata(self, tmp_path):
        repo = tmp_path / "order_meta"
        repo.mkdir()
        for name in ["z.py", "y.py", "x.py"]:
            (repo / name).write_text("x" * 100, encoding="utf-8")
        pipeline = TraversalPipeline(str(repo))
        documents, ctx = pipeline.run()
        paths = [d.metadata["relative_path"] for d in documents]
        assert paths == ["x.py", "y.py", "z.py"]
        assert ctx.repository_metadata.file_count == 3
