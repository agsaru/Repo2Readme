from repo2readme.utils.filter import github_file_filter
from repo2readme.utils.filter import github_file_filter

def test_github_file_filter_allows_valid_files():
    assert github_file_filter("repo2readme/cli/main.py") == True
    assert github_file_filter("src/app.tsx") == True

def test_github_file_filter_blocks_ignored_dirs():
    assert github_file_filter("node_modules/package/index.js") == False
    assert github_file_filter(".git/config") == False
    assert github_file_filter("venv/bin/activate") == False

def test_github_file_filter_blocks_ignored_extensions():
    assert github_file_filter("dist/app.exe") == False
    assert github_file_filter("data.csv") == False

def test_include_pattern_allows_default_ignored_json_file():
    assert github_file_filter(
        "package.json",
        include_patterns=["package.json"],
    ) is True


def test_exclude_pattern_blocks_otherwise_allowed_file():
    assert github_file_filter(
        "src/app.py",
        exclude_patterns=["src/*"],
    ) is False


def test_include_pattern_does_not_override_explicit_exclude():
    assert github_file_filter(
        "package.json",
        include_patterns=["package.json"],
        exclude_patterns=["package.json"],
    ) is False


def test_broad_json_include_does_not_include_protected_lock_file_by_default():
    assert github_file_filter(
        "package-lock.json",
        include_patterns=["*.json"],
    ) is False


def test_file_size_limit_blocks_large_included_file(tmp_path):
    large_file = tmp_path / "large-config.json"
    large_file.write_text("x" * 300 * 1024, encoding="utf-8")

    assert github_file_filter(
        "large-config.json",
        include_patterns=["*.json"],
        root_path=str(tmp_path),
        max_file_size_kb=200,
    ) is False


def test_file_size_limit_allows_small_included_file(tmp_path):
    small_file = tmp_path / "package.json"
    small_file.write_text('{"name": "demo"}', encoding="utf-8")

    assert github_file_filter(
        "package.json",
        include_patterns=["package.json"],
        root_path=str(tmp_path),
        max_file_size_kb=200,
    ) is True