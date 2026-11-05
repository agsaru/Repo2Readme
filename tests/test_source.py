"""Tests for source classification and the loader routing built on it.

The old check was ``source.startswith("https://github.com/")``, so every other
git URL form was treated as a directory and failed with "Folder not found".
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from repo2readme.loaders.loader import UrlRepoLoader
from repo2readme.loaders.repo_loader import RepoLoader
from repo2readme.loaders.source import (
    InvalidSourceError,
    SourceKind,
    classify_source,
    is_remote_source,
    repo_name_from_url,
)

# ---------------------------------------------------------------------------
# classify_source
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "https://github.com/acme/app",
        "https://github.com/acme/app.git",
        "http://github.com/acme/app",
        "HTTPS://github.com/acme/app",
        "https://gitlab.com/acme/app",
        "https://bitbucket.org/acme/app",
        "https://git.company.internal/acme/app.git",
        "https://github.enterprise.example.com/team/service",
        "ssh://git@github.com/acme/app.git",
        "ssh://git@git.company.internal:2222/acme/app.git",
        "git://github.com/acme/app.git",
        "git@github.com:acme/app.git",
        "git@gitlab.com:group/subgroup/app.git",
        "user@host.example.com:repos/app",
    ],
)
def test_remote_sources_are_recognised(source):
    resolved = classify_source(source)
    assert resolved.kind is SourceKind.REMOTE
    assert resolved.is_remote is True
    assert resolved.is_local is False
    assert is_remote_source(source) is True


@pytest.mark.parametrize(
    "source",
    [
        ".",
        "..",
        "/absolute/path/to/repo",
        "relative/path",
        "./relative/path",
        "C:\\Users\\me\\repo",
        "my-repo",
    ],
)
def test_local_sources_are_recognised(source):
    resolved = classify_source(source)
    assert resolved.kind is SourceKind.LOCAL
    assert resolved.is_local is True
    assert is_remote_source(source) is False


def test_tilde_paths_are_expanded():
    resolved = classify_source("~/projects/app")
    assert resolved.is_local
    assert resolved.value == os.path.expanduser("~/projects/app")
    assert resolved.original == "~/projects/app"


def test_file_urls_become_plain_paths():
    resolved = classify_source("file:///tmp/my%20repo")
    assert resolved.is_local
    assert resolved.value == "/tmp/my repo"


def test_git_plus_scheme_is_stripped():
    resolved = classify_source("git+ssh://git@github.com/acme/app.git")
    assert resolved.is_remote
    assert resolved.value == "ssh://git@github.com/acme/app.git"
    assert resolved.original == "git+ssh://git@github.com/acme/app.git"



@pytest.mark.parametrize(
    "source",
    [
        "https://user:password@github.com/acme/app.git",
        "https://token@github.com/acme/app.git",
        "https://github.com/acme/app.git?access_token=secret",
        "https://github.com/acme/app.git?api_key=secret",
    ],
)
def test_embedded_credentials_are_rejected(source):
    with pytest.raises(InvalidSourceError, match="credentials"):
        classify_source(source)


def test_ssh_username_is_allowed():
    assert classify_source("ssh://git@github.com/acme/app.git").is_remote


def test_url_loader_rejects_embedded_credentials():
    with pytest.raises(InvalidSourceError, match="credentials"):
        UrlRepoLoader("https://user:password@github.com/acme/app.git")

def test_surrounding_whitespace_is_ignored():
    assert classify_source("  https://github.com/acme/app  ").value == (
        "https://github.com/acme/app"
    )


@pytest.mark.parametrize("source", ["", "   ", None])
def test_empty_sources_are_rejected(source):
    with pytest.raises(InvalidSourceError, match="empty"):
        classify_source(source)


def test_unclonable_scheme_is_rejected_with_a_useful_message():
    with pytest.raises(InvalidSourceError) as excinfo:
        classify_source("s3://bucket/key")

    message = str(excinfo.value)
    assert "s3" in message
    assert "https" in message
    assert "scp-style" in message


def test_windows_drive_letter_is_not_mistaken_for_scp_syntax():
    assert classify_source("C:\\repo\\app").is_local


def test_host_port_without_user_is_not_scp_syntax():
    assert classify_source("localhost:8080").is_local


# ---------------------------------------------------------------------------
# repo_name_from_url
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/user/repo", "repo"),
        ("https://github.com/user/repo.git", "repo"),
        ("https://github.com/org/project.git/", "project"),
        ("https://github.com/user/repo///", "repo"),
        ("git@github.com:acme/app.git", "app"),
        ("git@gitlab.com:group/subgroup/app", "app"),
        ("ssh://git@github.com/acme/app.git", "app"),
        ("https://github.com/user/repo?tab=readme-ov-file", "repo"),
        ("https://github.com/user/repo#readme", "repo"),
    ],
)
def test_repo_name_from_url(url, expected):
    assert repo_name_from_url(url) == expected
    assert UrlRepoLoader(url).get_repo_name() == expected


# ---------------------------------------------------------------------------
# RepoLoader routing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "git@github.com:acme/app.git",
        "ssh://git@github.com/acme/app.git",
        "https://gitlab.com/acme/app",
        "http://github.com/acme/app",
        "https://git.company.internal/acme/app.git",
    ],
)
def test_repo_loader_routes_every_remote_form_to_the_url_loader(source):
    loader = RepoLoader(source)._build_loader()
    assert isinstance(loader, UrlRepoLoader)
    assert loader.clone_url == source


def test_repo_loader_still_routes_github_https_to_the_url_loader():
    loader = RepoLoader("https://github.com/acme/app")._build_loader()
    assert isinstance(loader, UrlRepoLoader)


def test_repo_loader_routes_a_path_to_the_local_loader(tmp_path):
    from repo2readme.loaders.loader import LocalRepoLoader

    loader = RepoLoader(str(tmp_path))._build_loader()
    assert isinstance(loader, LocalRepoLoader)
    assert loader.folder_path == str(tmp_path)


def test_max_workers_reaches_the_url_loader():
    """--max-workers was accepted and silently dropped for remote repos."""
    loader = RepoLoader(
        "https://github.com/acme/app", max_workers=9
    )._build_loader()
    assert loader.max_workers == 9


def test_all_options_reach_the_url_loader():
    loader = RepoLoader(
        "git@github.com:acme/app.git",
        include_patterns=["*.py"],
        exclude_patterns=["docs/*"],
        max_file_size_kb=42,
        respect_gitignore=True,
        max_workers=3,
        branch="develop",
    )._build_loader()

    assert loader.include_patterns == ["*.py"]
    assert loader.exclude_patterns == ["docs/*"]
    assert loader.max_file_size_kb == 42
    assert loader.respect_gitignore is True
    assert loader.max_workers == 3
    assert loader.branch == "develop"


# ---------------------------------------------------------------------------
# Clone destination
# ---------------------------------------------------------------------------


@patch("repo2readme.loaders.loader.subprocess.run")
def test_clone_uses_a_private_temp_dir(mock_run, tmp_path):
    """The destination used to be <tempdir>/<repo-name>, which is guessable
    and was removed with rmtree before every clone."""
    mock_run.return_value = MagicMock(returncode=0)

    loader = UrlRepoLoader("https://github.com/acme/app.git")
    loader.load()

    assert loader.temp_dir is not None
    assert loader.temp_dir != os.path.join(tempfile.gettempdir(), "app")
    assert os.path.basename(loader.temp_dir).startswith("repo2readme-")
    assert os.path.isdir(loader.temp_dir)

    loader.cleanup()
    assert not os.path.exists(loader.temp_dir)


@patch("repo2readme.loaders.loader.subprocess.run")
def test_two_loaders_for_the_same_repo_get_different_directories(mock_run):
    mock_run.return_value = MagicMock(returncode=0)

    first = UrlRepoLoader("https://github.com/acme/app.git")
    second = UrlRepoLoader("https://github.com/acme/app.git")
    first.load()
    second.load()

    try:
        assert first.temp_dir != second.temp_dir
    finally:
        first.cleanup()
        second.cleanup()


@patch("repo2readme.loaders.loader.subprocess.run")
def test_clone_target_is_passed_to_git(mock_run):
    mock_run.return_value = MagicMock(returncode=0)

    loader = UrlRepoLoader("git@github.com:acme/app.git", branch="develop")
    try:
        loader.load()
        command = mock_run.call_args[0][0]
        assert command[:2] == ["git", "clone"]
        assert "--branch" in command
        assert command[command.index("--branch") + 1] == "develop"
        assert command[-2:] == ["git@github.com:acme/app.git", loader.temp_dir]
    finally:
        loader.cleanup()


# ---------------------------------------------------------------------------
# The cloned tree goes through the shared traversal pipeline
# ---------------------------------------------------------------------------


@patch("repo2readme.loaders.loader.subprocess.run")
def test_remote_repositories_use_the_same_traversal_as_local_ones(
    mock_run, tmp_path
):
    from repo2readme.loaders.loader import LocalRepoLoader

    mock_run.return_value = MagicMock(returncode=0)

    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "main.py").write_text("print('hi')", encoding="utf-8")
    (repo / "README.md").write_text("# hi", encoding="utf-8")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "dep.js").write_text("x", encoding="utf-8")

    url_loader = UrlRepoLoader("https://github.com/acme/app.git")
    url_loader.temp_dir = str(repo)
    with patch("repo2readme.loaders.loader.shutil.rmtree"):
        url_docs, _, url_skipped = url_loader.load(return_skip_info=True)

    local_docs, _, local_skipped = LocalRepoLoader(str(repo)).load(
        return_skip_info=True
    )

    assert sorted(d.metadata["relative_path"] for d in url_docs) == sorted(
        d.metadata["relative_path"] for d in local_docs
    )
    assert sorted(url_skipped) == sorted(local_skipped)
    assert ("node_modules/", "ignored by default rules") in url_skipped


@patch("repo2readme.loaders.loader.subprocess.run")
def test_url_loader_accepts_max_workers(mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=0)

    repo = tmp_path / "repo"
    repo.mkdir()
    for i in range(5):
        (repo / f"mod_{i}.py").write_text(f"x = {i}", encoding="utf-8")

    loader = UrlRepoLoader("https://github.com/acme/app.git", max_workers=4)
    loader.temp_dir = str(repo)
    with patch("repo2readme.loaders.loader.shutil.rmtree"):
        docs, _ = loader.load()

    assert loader.max_workers == 4
    assert len(docs) == 5


@patch("repo2readme.loaders.loader.subprocess.run")
def test_clone_failure_is_reported_as_a_runtime_error(mock_run):
    import subprocess

    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=128, cmd=["git", "clone"], stderr="fatal: repository not found"
    )

    loader = UrlRepoLoader("https://github.com/acme/nope.git")
    with pytest.raises(RuntimeError, match="repository not found"):
        loader.load()

    loader.cleanup()
