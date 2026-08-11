import tempfile
import subprocess
from unittest.mock import MagicMock, patch
import pytest
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
    mock_filter.return_value = (True, "")

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
    mock_filter.return_value = (True, "")

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
    mock_filter.return_value = (True, "")

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


@patch("repo2readme.loaders.loader.github_file_filter")
def test_local_load_returns_skipped_info(mock_filter, tmp_path):
    def filter_side_effect(path, *args, **kwargs):
        if path == "node_modules":
            return (False, "ignored by default rules")
        elif path == "node_modules/package.json":
            return (False, "ignored by default rules")
        elif path == "large.py":
            return (False, "exceeds maximum file size (2000 B > 1024 B limit)")
        elif path == "README.md":
            return (False, "excluded by pattern")
        return (True, "")

    mock_filter.side_effect = filter_side_effect

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    (repo_dir / "main.py").write_text("print('hello')", encoding="utf-8")
    (repo_dir / "README.md").write_text("# README", encoding="utf-8")
    
    large_file = repo_dir / "large.py"
    large_file.write_text("x" * 2000, encoding="utf-8")
    
    node_modules = repo_dir / "node_modules"
    node_modules.mkdir()
    (node_modules / "package.json").write_text("{}", encoding="utf-8")

    loader = LocalRepoLoader(str(repo_dir), max_file_size_kb=1, exclude_patterns=["*.md"])
    docs, root, skipped = loader.load(return_skip_info=True)

    assert len(docs) == 1
    assert docs[0].metadata["relative_path"] == "main.py"
    
    # node_modules/ is pruned, so package.json inside is never encountered
    assert len(skipped) == 3
    assert ("node_modules/", "ignored by default rules") in skipped
    assert ("large.py", "exceeds maximum file size (2000 B > 1024 B limit)") in skipped
    assert ("README.md", "excluded by pattern") in skipped


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
    mock_filter.return_value = (True, "")
    url_loader.temp_dir = "/tmp/repo"

    result = url_loader._should_include("/tmp/repo/src/main.py")

    assert result is True
    mock_filter.assert_called_once()


@patch("repo2readme.loaders.loader.shutil.rmtree")
@patch("repo2readme.loaders.loader.subprocess.run")
@patch("repo2readme.loaders.loader.github_file_filter")
def test_url_load_success(mock_filter, mock_subprocess, mock_rmtree, url_loader, tmp_path):
    mock_filter.return_value = (True, "")
    mock_subprocess.return_value = MagicMock(returncode=0)

    # Create fake repo structure
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    main_file = src_dir / "main.py"
    main_file.write_text("print('hello')", encoding="utf-8")

    url_loader.temp_dir = str(repo_dir)
    
    docs, root, skipped = url_loader.load(return_skip_info=True)

    assert root == str(repo_dir)
    assert len(docs) == 1
    assert docs[0].page_content == "print('hello')"

    metadata = docs[0].metadata
    assert metadata["file_name"] == "main.py"
    assert metadata["file_type"] == ".py"
    assert metadata["relative_path"] == "src/main.py"
    assert metadata["file_path"] == str(main_file).replace("\\", "/")
    
    assert skipped == []


@patch("repo2readme.loaders.loader.shutil.rmtree")
@patch("repo2readme.loaders.loader.subprocess.run")
@patch("repo2readme.loaders.loader.github_file_filter")
def test_url_load_returns_skipped_info(mock_filter, mock_subprocess, mock_rmtree, url_loader, tmp_path):
    mock_subprocess.return_value = MagicMock(returncode=0)
    
    def filter_side_effect(path, *args, **kwargs):
        if path == "node_modules":
            return (False, "ignored by default rules")
        elif path == "node_modules/package.json":
            return (False, "ignored by default rules")
        elif path == "large.py":
            return (False, "exceeds maximum file size (2000 B > 1024 B limit)")
        elif path == "README.md":
            return (False, "excluded by pattern")
        return (True, "")

    mock_filter.side_effect = filter_side_effect

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    (repo_dir / "main.py").write_text("print('hello')", encoding="utf-8")
    (repo_dir / "README.md").write_text("# README", encoding="utf-8")
    
    large_file = repo_dir / "large.py"
    large_file.write_text("x" * 2000, encoding="utf-8")
    
    node_modules = repo_dir / "node_modules"
    node_modules.mkdir()
    (node_modules / "package.json").write_text("{}", encoding="utf-8")

    url_loader.temp_dir = str(repo_dir)
    url_loader.max_file_size_kb = 1
    url_loader.exclude_patterns = ["*.md"]
    
    docs, root, skipped = url_loader.load(return_skip_info=True)

    assert len(docs) == 1
    assert docs[0].metadata["relative_path"] == "main.py"
    
    # node_modules/ is pruned, so package.json is never encountered
    assert len(skipped) == 3
    assert ("node_modules/", "ignored by default rules") in skipped
    assert ("large.py", "exceeds maximum file size (2000 B > 1024 B limit)") in skipped
    assert ("README.md", "excluded by pattern") in skipped


@patch("repo2readme.loaders.loader.shutil.rmtree")
@patch("repo2readme.loaders.loader.subprocess.run")
def test_url_load_missing_source_metadata(mock_subprocess, mock_rmtree, url_loader, tmp_path):
    mock_subprocess.return_value = MagicMock(returncode=0)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    main_file = repo_dir / "main.py"
    main_file.write_text("code", encoding="utf-8")

    url_loader.temp_dir = str(repo_dir)
    
    docs, _ = url_loader.load()

    assert len(docs) == 1
    assert docs[0].metadata["file_name"] == "main.py"
    assert docs[0].metadata["file_path"] == str(main_file).replace("\\", "/")


@patch("repo2readme.loaders.loader.shutil.rmtree")
@patch("repo2readme.loaders.loader.subprocess.run") 
@patch("repo2readme.loaders.loader.os.path.exists")
def test_url_load_removes_existing_temp_dir(mock_exists, mock_subprocess, mock_rmtree, url_loader, tmp_path):
    """Ensures that if the temp directory already exists, it is removed before loading."""
    mock_exists.return_value = True
    mock_subprocess.return_value = MagicMock(returncode=0)
    
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "test.py").write_text("test", encoding="utf-8")
    url_loader.temp_dir = str(repo_dir)
    
    url_loader.load()

    # Verify rmtree was called to remove the existing directory
    mock_rmtree.assert_called()


@patch("repo2readme.loaders.loader.subprocess.run")
def test_url_load_clone_failure(mock_subprocess, url_loader):
    # Mock subprocess.run to raise CalledProcessError when check=True is used
    mock_subprocess.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd=["git", "clone", "--branch", "main", "--depth", "1", "https://github.com/user/repo.git", "/tmp/repo"],
        stderr="fatal: repository not found"
    )

    with pytest.raises(RuntimeError) as exc_info:
        url_loader.load()

    assert "Failed to clone repository" in str(exc_info.value)


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