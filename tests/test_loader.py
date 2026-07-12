import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from repo2readme.loaders.loader import LocalRepoLoader, UrlRepoLoader

@pytest.fixture
def url_loader():
    """Provides a pre-configured UrlRepoLoader instance for testing."""
    return UrlRepoLoader(
        clone_url="https://github.com/user/repo.git",
        branch="dev",
        include_patterns=["*.py"],
        exclude_patterns=["docs/*"],
        max_file_size_kb=50,
    )


# LocalRepoLoader Tests

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
    mock_filter.return_value = (True, None)

    loader = LocalRepoLoader("repo")
    result = loader._should_include("repo/main.py")

    assert result is True
    mock_filter.assert_called_once()


def test_local_load_missing_directory():
    loader = LocalRepoLoader("does_not_exist")

    with pytest.raises(FileNotFoundError):
        loader.load()


@patch("repo2readme.loaders.loader.github_file_filter")
def test_local_load_success(mock_filter, tmp_path):
    mock_filter.return_value = (True, None)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    main_file = repo_dir / "main.py"
    main_file.write_text("print('hello world')", encoding="utf-8")

    loader = LocalRepoLoader(str(repo_dir))
    docs, root = loader.load()

    assert root == str(repo_dir)
    assert len(docs) == 1
    assert docs[0].page_content == "print('hello world')"

    metadata = docs[0].metadata
    assert metadata["file_name"] == "main.py"
    assert metadata["file_type"] == ".py"
    assert metadata["relative_path"] == "main.py"
    
    expected_path = str(main_file).replace("\\", "/")
    assert metadata["file_path"] == expected_path


@patch("repo2readme.loaders.loader.TextLoader")
@patch("repo2readme.loaders.loader.github_file_filter")
def test_local_load_skips_failed_file(mock_filter, mock_textloader, tmp_path):
    mock_filter.return_value = (True, None)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    broken_file = repo_dir / "broken.py"
    broken_file.write_text("bad data")

    loader_instance = MagicMock()
    loader_instance.load.side_effect = Exception("Load Failed")
    mock_textloader.return_value = loader_instance

    loader = LocalRepoLoader(str(repo_dir))
    docs, _ = loader.load()

    assert docs == []


# UrlRepoLoader Tests

def test_url_repo_loader_init(url_loader):
    assert url_loader.clone_url == "https://github.com/user/repo.git"
    assert url_loader.branch == "dev"
    assert url_loader.include_patterns == ["*.py"]
    assert url_loader.exclude_patterns == ["docs/*"]
    assert url_loader.max_file_size_kb == 50
    assert url_loader.temp_dir is None


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/user/repo", "repo"),
        ("https://github.com/user/repo.git", "repo"),
        ("https://github.com/org/project.git/", "project"),
        ("https://github.com/user/repo.git/", "repo"),
        ("https://github.com/user/repo///", "repo"),
    ],
)

def test_get_repo_name(url, expected):
    loader = UrlRepoLoader(url)
    assert loader.get_repo_name() == expected


@patch("repo2readme.loaders.loader.github_file_filter")
def test_url_should_include(mock_filter, url_loader):
    mock_filter.return_value = (True, None)
    url_loader.temp_dir = "/tmp/repo"

    result = url_loader._should_include("/tmp/repo/src/main.py")

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
    url_loader,
):
    mock_exists.return_value = False

    document = Document(
        page_content="code",
        metadata={"source": "src/main.py"},
    )

    git_loader = MagicMock()
    git_loader.load.return_value = [document]
    mock_gitloader.return_value = git_loader

    docs, root = url_loader.load()

    assert root.endswith("repo")
    assert len(docs) == 1

    metadata = docs[0].metadata
    assert metadata["file_name"] == "main.py"
    assert metadata["file_type"] == ".py"
    
    # Check normalized paths
    assert metadata["relative_path"] == "src/main.py"
    assert metadata["file_path"].endswith("src/main.py")


@patch("repo2readme.loaders.loader.GitLoader")
@patch("repo2readme.loaders.loader.os.makedirs")
@patch("repo2readme.loaders.loader.os.path.exists")
def test_url_load_missing_source_metadata(
    mock_exists,
    mock_makedirs,
    mock_gitloader,
    url_loader,
):
    """Tests that documents missing a 'source' key in metadata do not cause a crash."""
    mock_exists.return_value = False

    document = Document(
        page_content="code",
        metadata={},
    )

    git_loader = MagicMock()
    git_loader.load.return_value = [document]
    mock_gitloader.return_value = git_loader

    docs, _ = url_loader.load()

    assert len(docs) == 1
    assert "file_name" not in docs[0].metadata
    assert "file_path" not in docs[0].metadata


@patch("repo2readme.loaders.loader.GitLoader")
@patch("repo2readme.loaders.loader.shutil.rmtree")
@patch("repo2readme.loaders.loader.os.makedirs")
@patch("repo2readme.loaders.loader.os.path.exists")
def test_url_load_removes_existing_temp_dir(
    mock_exists,
    mock_makedirs,
    mock_rmtree,
    mock_gitloader,
    url_loader,
):
    """Ensures that if the temp directory already exists, it is removed before cloning."""
    mock_exists.return_value = True
    
    git_loader = MagicMock()
    git_loader.load.return_value = []
    mock_gitloader.return_value = git_loader

    url_loader.load()

    mock_rmtree.assert_called_once()
    mock_makedirs.assert_called_once()


@patch("repo2readme.loaders.loader.shutil.rmtree")
@patch("repo2readme.loaders.loader.os.path.exists")
def test_cleanup(mock_exists, mock_rmtree, url_loader):
    mock_exists.return_value = True
    url_loader.temp_dir = tempfile.gettempdir()

    url_loader.cleanup()

    mock_rmtree.assert_called_once()


@patch("repo2readme.loaders.loader.os.path.exists")
@patch("repo2readme.loaders.loader.shutil.rmtree")
def test_cleanup_when_directory_missing(mock_rmtree, mock_exists, url_loader):
    mock_exists.return_value = False
    url_loader.temp_dir = tempfile.gettempdir()

    url_loader.cleanup()

    mock_rmtree.assert_not_called()
