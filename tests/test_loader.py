import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from repo2readme.loaders.loader import LocalRepoLoader, UrlRepoLoader


# ----------------------------------------------------------------------
# LocalRepoLoader Tests
# ----------------------------------------------------------------------


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


@patch("repo2readme.loaders.loader.github_file_filter")
def test_local_should_include(mock_filter):
    mock_filter.return_value = True

    loader = LocalRepoLoader("repo")

    result = loader._should_include("repo/main.py")

    assert result is True
    mock_filter.assert_called_once()


def test_local_load_missing_directory():
    loader = LocalRepoLoader("does_not_exist")

    with pytest.raises(FileNotFoundError):
        loader.load()


@patch("repo2readme.loaders.loader.TextLoader")
@patch.object(LocalRepoLoader, "_should_include")
@patch("repo2readme.loaders.loader.os.walk")
@patch("repo2readme.loaders.loader.os.path.exists")
def test_local_load_success(
    mock_exists,
    mock_walk,
    mock_include,
    mock_textloader,
):
    mock_exists.return_value = True

    mock_walk.return_value = [
        ("repo", [], ["main.py"])
    ]

    mock_include.return_value = True

    document = Document(
        page_content="print('hello')",
        metadata={},
    )

    loader_instance = MagicMock()
    loader_instance.load.return_value = [document]
    mock_textloader.return_value = loader_instance

    loader = LocalRepoLoader("repo")

    docs, root = loader.load()

    assert root == "repo"
    assert len(docs) == 1

    metadata = docs[0].metadata

    assert metadata["file_name"] == "main.py"
    assert metadata["file_type"] == ".py"
    assert metadata["relative_path"] == "main.py"
    assert metadata["file_path"].endswith("repo/main.py")


@patch("repo2readme.loaders.loader.TextLoader")
@patch.object(LocalRepoLoader, "_should_include")
@patch("repo2readme.loaders.loader.os.walk")
@patch("repo2readme.loaders.loader.os.path.exists")
def test_local_load_skips_failed_file(
    mock_exists,
    mock_walk,
    mock_include,
    mock_textloader,
):
    mock_exists.return_value = True

    mock_walk.return_value = [
        ("repo", [], ["broken.py"])
    ]

    mock_include.return_value = True

    loader_instance = MagicMock()
    loader_instance.load.side_effect = Exception("Load Failed")
    mock_textloader.return_value = loader_instance

    loader = LocalRepoLoader("repo")

    docs, _ = loader.load()

    assert docs == []


# ----------------------------------------------------------------------
# UrlRepoLoader Tests
# ----------------------------------------------------------------------


def test_url_repo_loader_init():
    loader = UrlRepoLoader(
        clone_url="https://github.com/user/repo.git",
        branch="dev",
        include_patterns=["*.py"],
        exclude_patterns=["docs/*"],
        max_file_size_kb=50,
    )

    assert loader.clone_url == "https://github.com/user/repo.git"
    assert loader.branch == "dev"
    assert loader.include_patterns == ["*.py"]
    assert loader.exclude_patterns == ["docs/*"]
    assert loader.max_file_size_kb == 50
    assert loader.temp_dir is None


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/user/repo", "repo"),
        ("https://github.com/user/repo.git", "repo"),
        ("https://github.com/org/project.git/", "project"),
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

    result = loader._should_include("/tmp/repo/src/main.py")

    assert result is True
    mock_filter.assert_called_once()


@patch("repo2readme.loaders.loader.GitLoader")
@patch("repo2readme.loaders.loader.os.makedirs")
@patch("repo2readme.loaders.loader.os.path.exists")
@patch("repo2readme.loaders.loader.shutil.rmtree")
def test_url_load_success(
    mock_rmtree,
    mock_exists,
    mock_makedirs,
    mock_gitloader,
):
    mock_exists.return_value = False

    document = Document(
        page_content="code",
        metadata={
            "source": "src/main.py",
        },
    )

    git_loader = MagicMock()
    git_loader.load.return_value = [document]

    mock_gitloader.return_value = git_loader

    loader = UrlRepoLoader(
        "https://github.com/user/repo.git"
    )

    docs, root = loader.load()

    assert root.endswith("repo")
    assert len(docs) == 1

    metadata = docs[0].metadata

    assert metadata["file_name"] == "main.py"
    assert metadata["file_type"] == ".py"
    assert metadata["relative_path"] == "src/main.py"
    assert metadata["file_path"].endswith("src/main.py")


@patch("repo2readme.loaders.loader.shutil.rmtree")
@patch("repo2readme.loaders.loader.os.path.exists")
def test_cleanup(mock_exists, mock_rmtree):
    mock_exists.return_value = True

    loader = UrlRepoLoader("https://github.com/user/repo.git")
    loader.temp_dir = tempfile.gettempdir()

    loader.cleanup()

    mock_rmtree.assert_called_once()


@patch("repo2readme.loaders.loader.os.path.exists")
@patch("repo2readme.loaders.loader.shutil.rmtree")
def test_cleanup_when_directory_missing(
    mock_rmtree,
    mock_exists,
):
    mock_exists.return_value = False

    loader = UrlRepoLoader("https://github.com/user/repo.git")
    loader.temp_dir = tempfile.gettempdir()

    loader.cleanup()

    mock_rmtree.assert_not_called()