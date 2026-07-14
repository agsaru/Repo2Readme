from repo2readme.utils.filter import is_file_size_allowed, github_file_filter
from repo2readme.utils.tree import extract_tree
import os


def test_is_file_size_allowed_small_and_large(tmp_path):
    small = tmp_path / "small.txt"
    small.write_text("hello", encoding="utf-8")

    large = tmp_path / "large.bin"
    large.write_text("x" * 2048, encoding="utf-8")

    # small file allowed under 1 KB
    assert is_file_size_allowed("small.txt", root_path=str(tmp_path), max_file_size_kb=1)

    # large file not allowed under 1 KB
    assert not is_file_size_allowed("large.bin", root_path=str(tmp_path), max_file_size_kb=1)

    # non-existent files should be treated as allowed (stat raises OSError)
    assert is_file_size_allowed("no-such-file.txt", root_path=str(tmp_path), max_file_size_kb=1)


def test_extract_tree_and_file_list_respects_default_ignores(tmp_path):
    base = tmp_path / "project"
    src = base / "src"
    node = base / "node_modules" / "pkg"
    src.mkdir(parents=True)
    node.mkdir(parents=True)

    readme = base / "README.md"
    main = src / "main.py"
    nm = node / "index.js"

    readme.write_text("# hi", encoding="utf-8")
    main.write_text("print('ok')", encoding="utf-8")
    nm.write_text("module.exports = {}", encoding="utf-8")

    tree, files = extract_tree(str(base))

    assert os.path.basename(str(base)) + "/" in tree
    assert "README.md" in tree
    assert "main.py" in tree
    # node_modules should be filtered out by default and not appear
    assert "node_modules" not in tree

    # file paths should include the visible files and exclude node_modules
    file_basenames = {os.path.basename(p) for p in files}
    assert "README.md" in file_basenames
    assert "main.py" in file_basenames
    assert "index.js" not in file_basenames


def test_nested_include_exclude_and_protected_large_file(tmp_path):
    base = tmp_path / "repo"
    src = base / "src"
    private = src / "private"
    configs = base / "configs"
    private.mkdir(parents=True)
    configs.mkdir(parents=True)

    public_file = src / "app.py"
    secret_file = private / "secret.py"
    lock_file = configs / "package-lock.json"

    public_file.write_text("print('public')", encoding="utf-8")
    secret_file.write_text("print('secret')", encoding="utf-8")
    lock_file.write_text("{}", encoding="utf-8")

    # include parent but exclude nested path => nested file excluded
    include = ["src/*"]
    exclude = ["src/private/*"]
    ok, reason = github_file_filter(str(public_file), include_patterns=include, exclude_patterns=exclude, root_path=str(base))
    assert ok is True

    ok2, reason2 = github_file_filter(str(secret_file), include_patterns=include, exclude_patterns=exclude, root_path=str(base))
    assert ok2 is False and reason2 == "excluded by pattern"

    # protected large file must be explicitly included by exact name or path
    ok3, reason3 = github_file_filter(str(lock_file), include_patterns=["*.json"], root_path=str(base))
    assert ok3 is False and reason3 == "protected large file"

    # explicit include of the exact path allows the protected file
    ok4, reason4 = github_file_filter(str(lock_file), include_patterns=["configs/package-lock.json"], root_path=str(base))
    assert ok4 is True
