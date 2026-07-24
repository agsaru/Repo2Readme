import tempfile
from pathlib import Path

from repo2readme.utils.gitignore import is_gitignored


def test_no_gitignore_does_not_filter():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "main.py").write_text("print('hello')", encoding="utf-8")
        Path(tmp, "keep.log").write_text("log", encoding="utf-8")

        assert is_gitignored(str(Path(tmp, "main.py")), tmp) is False
        assert is_gitignored(str(Path(tmp, "keep.log")), tmp) is False


def test_ignored_directories_are_filtered():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "src").mkdir()
        Path(tmp, "src", "app.py").write_text("print('app')", encoding="utf-8")
        Path(tmp, "node_modules").mkdir()
        Path(tmp, "node_modules", "pkg").mkdir()
        Path(tmp, "node_modules", "pkg", "index.js").write_text("x", encoding="utf-8")
        Path(tmp, "build").mkdir()
        Path(tmp, "build", "out.bin").write_text("x", encoding="utf-8")

        Path(tmp, ".gitignore").write_text("node_modules/\nbuild/\n", encoding="utf-8")

        assert is_gitignored(str(Path(tmp, "src", "app.py")), tmp) is False
        assert is_gitignored(str(Path(tmp, "node_modules", "pkg", "index.js")), tmp) is True
        assert is_gitignored(str(Path(tmp, "build", "out.bin")), tmp) is True


def test_ignored_file_patterns_are_filtered():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "main.py").write_text("print('hello')", encoding="utf-8")
        Path(tmp, "debug.log").write_text("log", encoding="utf-8")
        Path(tmp, "temp.tmp").write_text("tmp", encoding="utf-8")

        Path(tmp, ".gitignore").write_text("*.log\n*.tmp\n", encoding="utf-8")

        assert is_gitignored(str(Path(tmp, "main.py")), tmp) is False
        assert is_gitignored(str(Path(tmp, "debug.log")), tmp) is True
        assert is_gitignored(str(Path(tmp, "temp.tmp")), tmp) is True


def test_nested_ignore_patterns():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "src").mkdir()
        Path(tmp, "src", "utils.py").write_text("x", encoding="utf-8")
        Path(tmp, "src", "generated").mkdir()
        Path(tmp, "src", "generated", "prisma").mkdir()
        Path(tmp, "src", "generated", "prisma", "schema.ts").write_text("x", encoding="utf-8")

        Path(tmp, ".gitignore").write_text("src/generated/prisma/\n", encoding="utf-8")

        assert is_gitignored(str(Path(tmp, "src", "utils.py")), tmp) is False
        assert is_gitignored(str(Path(tmp, "src", "generated", "prisma", "schema.ts")), tmp) is True


def test_git_info_exclude_is_respected():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "main.py").write_text("print('hello')", encoding="utf-8")
        Path(tmp, "secret.log").write_text("secret", encoding="utf-8")

        git_dir = Path(tmp, ".git", "info")
        git_dir.mkdir(parents=True, exist_ok=True)
        Path(git_dir, "exclude").write_text("secret.log\n", encoding="utf-8")

        assert is_gitignored(str(Path(tmp, "main.py")), tmp) is False
        assert is_gitignored(str(Path(tmp, "secret.log")), tmp) is True


def test_default_behavior_unchanged_when_flag_disabled():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "main.py").write_text("print('hello')", encoding="utf-8")
        Path(tmp, ".gitignore").write_text("main.py\n", encoding="utf-8")

        assert is_gitignored(str(Path(tmp, "main.py")), tmp) is True




def test_skip_info_reports_gitignore():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "main.py").write_text("print('hello')", encoding="utf-8")
        Path(tmp, "debug.log").write_text("log", encoding="utf-8")
        Path(tmp, ".gitignore").write_text("*.log\n", encoding="utf-8")

        assert is_gitignored(str(Path(tmp, "main.py")), tmp) is False
        assert is_gitignored(str(Path(tmp, "debug.log")), tmp) is True


def test_gitignore_loader_no_git_dir_does_not_raise():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "main.py").write_text("print('hello')", encoding="utf-8")
        assert is_gitignored(str(Path(tmp, "main.py")), tmp) is False


def test_is_gitignored_no_gitignore_file():
    with tempfile.TemporaryDirectory() as tmp:
        assert is_gitignored(str(Path(tmp, "main.py")), tmp) is False


def test_is_gitignored_empty_file():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, ".gitignore").write_text("", encoding="utf-8")
        assert is_gitignored(str(Path(tmp, "main.py")), tmp) is False


def test_is_gitignored_invalid_path():
    assert is_gitignored("", "") is False
    assert is_gitignored("/nonexistent/file.py", "/nonexistent/root") is False
    assert is_gitignored("main.py", "/nonexistent/root") is False


def test_directory_with_ignored_file_is_not_ignored():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "src").mkdir()
        Path(tmp, "src", "app.py").write_text("print('hello')", encoding="utf-8")
        Path(tmp, "src", "debug.log").write_text("log", encoding="utf-8")

        Path(tmp, ".gitignore").write_text("*.log\n", encoding="utf-8")

        assert is_gitignored(str(Path(tmp, "src")), tmp) is False
        assert is_gitignored(str(Path(tmp, "src", "app.py")), tmp) is False
        assert is_gitignored(str(Path(tmp, "src", "debug.log")), tmp) is True


def test_ignored_directory_patterns_match_directory_explicitly():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "src").mkdir()
        Path(tmp, "src", "app.py").write_text("print('hello')", encoding="utf-8")
        Path(tmp, "build").mkdir()
        Path(tmp, "build", "out.bin").write_text("x", encoding="utf-8")

        Path(tmp, ".gitignore").write_text("build/\n", encoding="utf-8")

        assert is_gitignored(str(Path(tmp, "src", "app.py")), tmp) is False
        assert is_gitignored(str(Path(tmp, "build")), tmp) is True
        assert is_gitignored(str(Path(tmp, "build", "out.bin")), tmp) is True
