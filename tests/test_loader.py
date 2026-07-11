from repo2readme.loaders import UrlRepoLoader


def test_repo_name_plain():
    assert UrlRepoLoader(
        "https://github.com/user/repo"
    ).get_repo_name() == "repo"


def test_repo_name_with_git_extension():
    assert UrlRepoLoader(
        "https://github.com/user/repo.git"
    ).get_repo_name() == "repo"


def test_repo_name_with_trailing_slash():
    assert UrlRepoLoader(
        "https://github.com/user/repo/"
    ).get_repo_name() == "repo"


def test_repo_name_with_git_and_trailing_slash():
    assert UrlRepoLoader(
        "https://github.com/user/repo.git/"
    ).get_repo_name() == "repo"


def test_repo_name_multiple_trailing_slashes():
    assert UrlRepoLoader(
        "https://github.com/user/repo///"
    ).get_repo_name() == "repo"