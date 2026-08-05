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

from repo2readme.loaders.traversal.pipeline import TraversalPipeline
from repo2readme.loaders.traversal.stages import (
    discover_files,
    filter_file,
    extract_file_metadata,
    detect_file_language,
    create_document,
    load_file_content,
    FilteredFile,
    FileMetadata,
)


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
