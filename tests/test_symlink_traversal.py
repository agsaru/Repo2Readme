import pytest
from repo2readme.loaders.loader import LocalRepoLoader


def _skip_if_no_symlink_support(tmp_path):
    """Verify symbolic link creation is supported; otherwise skip the test."""
    probe = tmp_path / "symlink_probe"
    target = tmp_path / "symlink_target"
    target.write_text("x", encoding="utf-8")
    try:
        probe.symlink_to(target)
    except (OSError, NotImplementedError, PermissionError):
        pytest.skip("Symbolic links are not supported or require elevated privileges on this platform.")


def test_local_traversal_normal(tmp_path):
    """Regression test: normal traversal without symlinks works as before."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "main.py").write_text("print('hello')", encoding="utf-8")
    (repo_dir / "sub").mkdir()
    (repo_dir / "sub" / "utils.py").write_text("x = 1", encoding="utf-8")

    loader = LocalRepoLoader(str(repo_dir))
    docs, root = loader.load()

    assert root == str(repo_dir)
    assert len(docs) == 2
    paths = {doc.metadata["relative_path"] for doc in docs}
    assert paths == {"main.py", "sub/utils.py"}


def test_local_traversal_skips_broken_symlink(tmp_path):
    """Broken symbolic links are skipped safely."""
    _skip_if_no_symlink_support(tmp_path)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "main.py").write_text("print('hello')", encoding="utf-8")
    
    broken_link = repo_dir / "broken_link"
    broken_link.symlink_to(repo_dir / "nonexistent")

    loader = LocalRepoLoader(str(repo_dir))
    docs, root = loader.load()

    assert len(docs) == 1
    assert docs[0].metadata["relative_path"] == "main.py"


def test_local_traversal_skips_broken_symlink_dir(tmp_path):
    """Broken directory symlinks are skipped safely."""
    _skip_if_no_symlink_support(tmp_path)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "main.py").write_text("print('hello')", encoding="utf-8")
    
    broken_dir_link = repo_dir / "bad_dir_link"
    broken_dir_link.symlink_to(repo_dir / "does_not_exist")

    loader = LocalRepoLoader(str(repo_dir))
    docs, root = loader.load()

    assert len(docs) == 1
    assert docs[0].metadata["relative_path"] == "main.py"


def test_local_traversal_directory_symlink(tmp_path):
    """Directory symbolic links are followed once."""
    _skip_if_no_symlink_support(tmp_path)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "main.py").write_text("print('hello')", encoding="utf-8")
    
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    (src_dir / "helper.py").write_text("y = 2", encoding="utf-8")
    
    link_dir = repo_dir / "link_to_src"
    link_dir.symlink_to(src_dir, target_is_directory=True)

    loader = LocalRepoLoader(str(repo_dir))
    docs, root = loader.load()

    paths = {doc.metadata["relative_path"] for doc in docs}
    # src/ is visited first; link_to_src/ resolves to the same canonical path and is skipped
    assert paths == {"main.py", "src/helper.py"}


def test_local_traversal_circular_symlink(tmp_path):
    """Circular symbolic links are detected and do not cause infinite recursion."""
    _skip_if_no_symlink_support(tmp_path)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "main.py").write_text("print('hello')", encoding="utf-8")
    
    loop_link = repo_dir / "A" / "loop"
    (repo_dir / "A").mkdir()
    loop_link.symlink_to(repo_dir / "A", target_is_directory=True)

    loader = LocalRepoLoader(str(repo_dir))
    docs, root = loader.load()

    assert len(docs) == 1
    assert docs[0].metadata["relative_path"] == "main.py"


def test_local_traversal_multiple_symlinks_same_target(tmp_path):
    """Multiple symlinks to the same directory are deduplicated."""
    _skip_if_no_symlink_support(tmp_path)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "main.py").write_text("print('hello')", encoding="utf-8")
    
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    (src_dir / "a.py").write_text("a = 1", encoding="utf-8")
    (src_dir / "b.py").write_text("b = 2", encoding="utf-8")
    
    link1 = repo_dir / "link1"
    link1.symlink_to(src_dir, target_is_directory=True)
    link2 = repo_dir / "link2"
    link2.symlink_to(src_dir, target_is_directory=True)

    loader = LocalRepoLoader(str(repo_dir))
    docs, root = loader.load()

    paths = sorted(doc.metadata["relative_path"] for doc in docs)
    # link1/ is followed; link2/ resolves to same canonical path and is skipped
    assert paths == sorted(["main.py", "link1/a.py", "link1/b.py"])


def test_local_traversal_nested_symlinks(tmp_path):
    """Nested symbolic links are handled correctly."""
    _skip_if_no_symlink_support(tmp_path)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "main.py").write_text("print('hello')", encoding="utf-8")
    
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    (src_dir / "inner.py").write_text("inner = 1", encoding="utf-8")
    
    link_to_src = repo_dir / "link_to_src"
    link_to_src.symlink_to(src_dir, target_is_directory=True)
    
    inner_link = link_to_src / "inner_link"
    inner_link.symlink_to(src_dir, target_is_directory=True)

    loader = LocalRepoLoader(str(repo_dir))
    docs, root = loader.load()

    paths = sorted(doc.metadata["relative_path"] for doc in docs)
    # link_to_src is followed; inner_link resolves to the same canonical src and is skipped
    assert "link_to_src/inner.py" in paths
    assert "link_to_src/inner_link/inner.py" not in paths


def test_local_traversal_file_symlink(tmp_path):
    """File symbolic links are processed normally."""
    _skip_if_no_symlink_support(tmp_path)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "main.py").write_text("print('hello')", encoding="utf-8")
    
    original = repo_dir / "data.txt"
    original.write_text("hello", encoding="utf-8")
    
    file_link = repo_dir / "data_link.txt"
    file_link.symlink_to(original)

    loader = LocalRepoLoader(str(repo_dir))
    docs, root = loader.load()

    paths = {doc.metadata["relative_path"] for doc in docs}
    assert paths == {"main.py", "data_link.txt"}


def test_local_traversal_symlink_duplicate_prevention(tmp_path):
    """A directory visited via symlink is not visited again via another path."""
    _skip_if_no_symlink_support(tmp_path)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "main.py").write_text("print('hello')", encoding="utf-8")
    
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    (src_dir / "a.py").write_text("a = 1", encoding="utf-8")
    
    link1 = repo_dir / "link1"
    link1.symlink_to(src_dir, target_is_directory=True)
    
    nested = link1 / "nested"
    nested.mkdir()
    (nested / "n.py").write_text("n = 1", encoding="utf-8")
    
    link2 = repo_dir / "link2"
    link2.symlink_to(src_dir, target_is_directory=True)

    loader = LocalRepoLoader(str(repo_dir))
    docs, root = loader.load()

    paths = sorted(doc.metadata["relative_path"] for doc in docs)
    # link1/ is followed; link2/ resolves to the same canonical path as src/ and is skipped
    assert paths == sorted([
        "main.py",
        "link1/a.py",
        "link1/nested/n.py",
    ])


def test_local_traversal_returns_skipped_info_for_symlinks(tmp_path):
    """Skipped symlinks are reported when return_skip_info=True."""
    _skip_if_no_symlink_support(tmp_path)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "main.py").write_text("print('hello')", encoding="utf-8")
    
    broken = repo_dir / "broken"
    broken.symlink_to(repo_dir / "nonexistent")
    
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    (src_dir / "a.py").write_text("a = 1", encoding="utf-8")
    
    link1 = repo_dir / "link1"
    link1.symlink_to(src_dir, target_is_directory=True)
    link2 = repo_dir / "link2"
    link2.symlink_to(src_dir, target_is_directory=True)

    loader = LocalRepoLoader(str(repo_dir))
    docs, root, skipped = loader.load(return_skip_info=True)

    rel_skipped = [(p if not p.endswith("/") else p, r) for p, r in skipped]
    assert ("broken/", "broken symbolic link") in rel_skipped
    assert any(p == "link2/" and r == "circular or duplicate symbolic link" for p, r in rel_skipped)
