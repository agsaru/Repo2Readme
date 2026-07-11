import os
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from repo2readme.loaders.loader import LocalRepoLoader, UrlRepoLoader


def test_local_repo_loader_init():
    loader = LocalRepoLoader(
        folder_path="repo",
        include_patterns=["*.py"],
        exclude_patterns=["tests/*"],
        max_file_size_kb=100,
    )

    assert loader.folder_path == "repo"
    assert loader.include_patterns == ["*.py"]
    assert loader.exclude_patterns == ["tests/*"]
    assert loader.max_file_size_kb == 100


def test_local_loader_missing_folder():
    loader = LocalRepoLoader("does_not_exist")

    with pytest.raises(FileNotFoundError):
        loader.load()


@patch("repo2readme.loaders.loader.github_file_filter")
def test_should_include(mock_filter, tmp_path):
    mock_filter.return_value = True

    loader = LocalRepoLoader(str(tmp_path))

    file = tmp_path / "a.py"
    file.write_text("print('hi')")

    assert loader._should_include(str(file))

    mock_filter.assert_called_once()


@patch("repo2readme.loaders.loader.TextLoader")
def test_load_adds_metadata(mock_loader, tmp_path):
    file = tmp_path / "main.py"
    file.write_text("print('hello')")

    mock_loader.return_value.load.return_value = [
        Document(page_content="hello", metadata={})
    ]

    loader = LocalRepoLoader(str(tmp_path))

    docs, root = loader.load()

    assert root == str(tmp_path)
    assert len(docs) == 1

    metadata = docs[0].metadata

    assert metadata["file_name"] == "main.py"
    assert metadata["file_type"] == ".py"
    assert metadata["relative_path"] == "main.py"
    assert metadata["file_path"].endswith("main.py")


@patch("repo2readme.loaders.loader.TextLoader")
def test_load_handles_loader_exception(mock_loader, tmp_path, capsys):
    file = tmp_path / "bad.py"
    file.write_text("print('bad')")

    mock_loader.return_value.load.side_effect = Exception("boom")

    loader = LocalRepoLoader(str(tmp_path))

    docs, _ = loader.load()

    assert docs == []

    captured = capsys.readouterr()
    assert "[ERROR]" in captured.out


def test_url_loader_init():
    loader = UrlRepoLoader(
        clone_url="https://github.com/user/repo.git",
        branch="dev",
        include_patterns=["*.py"],
        exclude_patterns=["tests/*"],
        max_file_size_kb=50,
    )

    assert loader.clone_url.endswith("repo.git")
    assert loader.branch == "dev"
    assert loader.include_patterns == ["*.py"]
    assert loader.exclude_patterns == ["tests/*"]
    assert loader.max_file_size_kb == 50
    assert loader.temp_dir is None


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/user/repo.git", "repo"),
        ("https://github.com/user/repo", "repo"),
        ("git@github.com:user/repo.git", "repo"),
    ],
)
def test_get_repo_name(url, expected):
    loader = UrlRepoLoader(url)

    assert loader.get_repo_name() == expected


@patch("repo2readme.loaders.loader.github_file_filter")
def test_url_should_include(mock_filter):
    mock_filter.return_value = True

    loader = UrlRepoLoader("https://github.com/user/repo.git")
    loader.temp_dir = "/tmp/repo"

    assert loader._should_include("/tmp/repo/src/main.py")

    mock_filter.assert_called_once()

@patch("repo2readme.loaders.loader.GitLoader")
def test_url_load_metadata(mock_gitloader):
    document = Document(
        page_content="hello",
        metadata={"source": "src/main.py"},
    )

    mock_gitloader.return_value.load.return_value = [document]

    loader = UrlRepoLoader(
        "https://github.com/user/repo.git",
        branch="main",
    )

    docs, _ = loader.load()

    try:
        assert len(docs) == 1

        metadata = docs[0].metadata

        assert metadata["file_name"] == "main.py"
        assert metadata["file_type"] == ".py"
        assert metadata["relative_path"] == "src/main.py"
        assert metadata["file_path"].endswith("src/main.py")

        mock_gitloader.assert_called_once()
    finally:
        loader.cleanup()

def test_cleanup(tmp_path):
    loader = UrlRepoLoader("https://github.com/user/repo.git")

    loader.temp_dir = str(tmp_path)

    assert os.path.exists(loader.temp_dir)

    loader.cleanup()

    assert not os.path.exists(loader.temp_dir)