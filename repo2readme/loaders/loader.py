from __future__ import annotations
import os
import tempfile
import shutil
import subprocess
from typing import Iterable  # noqa: F401

from repo2readme.utils.filter import github_file_filter
from repo2readme.utils.force_remove import force_remove
from repo2readme.utils.gitignore import is_gitignored  # noqa: F401
from repo2readme.loaders.source import classify_source, repo_name_from_url
from repo2readme.loaders.traversal import TraversalPipeline
from collections import OrderedDict  # noqa: F401
from langchain_core.documents import Document

# Backward-compatible placeholder: tests patch this symbol.
# The actual import is kept lazy inside the local loader to avoid importing
# langchain during normal simple-file reads.
TextLoader = None  # type: ignore[assignment,misc]


def _run_traversal(
    folder_path: str,
    include_patterns=None,
    exclude_patterns=None,
    max_file_size_kb: int | None = 200,
    respect_gitignore: bool = False,
    max_workers: int | None = None,
):
    """
    Walk ``folder_path`` with the shared traversal pipeline.

    Both loaders funnel through here, so symlink handling, gitignore support,
    binary detection, skip reasons and the parallel worker pool behave
    identically whether the repository was cloned or was already on disk.
    """
    pipeline = TraversalPipeline(
        folder_path=folder_path,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        max_file_size_kb=max_file_size_kb,
        respect_gitignore=respect_gitignore,
        max_workers=max_workers,
    )

    documents, ctx = pipeline.run()

    # Convert DocumentResult back to langchain Document objects for
    # backward compatibility
    docs = [
        Document(
            page_content=doc_result.page_content,
            metadata=dict(doc_result.metadata),
        )
        for doc_result in documents
    ]

    return docs, ctx


class LocalRepoLoader:
    def __init__(
        self,
        folder_path: str,
        include_patterns=None,
        exclude_patterns=None,
        max_file_size_kb: int | None = 200,
        respect_gitignore: bool = False,
        max_workers: int | None = None,
    ):
        if max_file_size_kb is not None and max_file_size_kb < 0:
            raise ValueError(
                f"max_file_size_kb must be non-negative, got {max_file_size_kb}"
            )
        self.folder_path = folder_path
        self.include_patterns = include_patterns
        self.exclude_patterns = exclude_patterns
        self.max_file_size_kb = max_file_size_kb
        self.respect_gitignore = respect_gitignore
        self.max_workers = max_workers

    def _should_include(self, path: str) -> bool:
        relative_path = os.path.relpath(path, self.folder_path).replace("\\", "/")

        size_limit = None if os.path.isdir(path) else self.max_file_size_kb

        allowed, _ = github_file_filter(
            relative_path,
            include_patterns=self.include_patterns,
            exclude_patterns=self.exclude_patterns,
            root_path=self.folder_path,
            max_file_size_kb=size_limit,
        )
        return allowed

    def _is_within_root(self, path: str, root: str) -> bool:
        try:
            common = os.path.commonpath([path, root])
            return common == root
        except ValueError:
            return False

    def load(self, return_skip_info=False):
        if not os.path.exists(self.folder_path):
            raise FileNotFoundError(f"Folder not found: {self.folder_path}")
        if not os.path.isdir(self.folder_path):
            raise NotADirectoryError(f"Repository path is not a directory: {self.folder_path}")

        docs, ctx = _run_traversal(
            self.folder_path,
            include_patterns=self.include_patterns,
            exclude_patterns=self.exclude_patterns,
            max_file_size_kb=self.max_file_size_kb,
            respect_gitignore=self.respect_gitignore,
            max_workers=self.max_workers,
        )

        if return_skip_info:
            return docs, self.folder_path, ctx.skipped
        return docs, self.folder_path


class UrlRepoLoader:
    def __init__(
        self,
        clone_url: str,
        branch: str = "main",
        include_patterns=None,
        exclude_patterns=None,
        max_file_size_kb: int | None = 200,
        respect_gitignore: bool = False,
        max_workers: int | None = None,
    ):
        if max_file_size_kb is not None and max_file_size_kb < 0:
            raise ValueError(
                f"max_file_size_kb must be non-negative, got {max_file_size_kb}"
            )
        resolved_source = classify_source(clone_url)
        if not resolved_source.is_remote:
            raise ValueError("UrlRepoLoader requires a remote repository URL")
        self.clone_url = resolved_source.value
        self.branch = branch
        self.include_patterns = include_patterns
        self.exclude_patterns = exclude_patterns
        self.max_file_size_kb = max_file_size_kb
        self.respect_gitignore = respect_gitignore
        self.max_workers = max_workers
        self.temp_dir = None

    def get_repo_name(self):
        return repo_name_from_url(self.clone_url)

    def _should_include(self, path: str) -> bool:
        if self.temp_dir:
            relative_path = os.path.relpath(path, self.temp_dir).replace("\\", "/")
        else:
            relative_path = path.replace("\\", "/")

        size_limit = None if os.path.isdir(path) else self.max_file_size_kb

        allowed, _ = github_file_filter(
            relative_path,
            include_patterns=self.include_patterns,
            exclude_patterns=self.exclude_patterns,
            root_path=self.temp_dir,
            max_file_size_kb=size_limit,
        )
        return allowed

    def _is_within_root(self, path: str, root: str) -> bool:
        try:
            common = os.path.commonpath([path, root])
            return common == root
        except ValueError:
            return False

    def _prepare_clone_dir(self) -> None:
        """
        Choose the directory to clone into.

        The destination used to be ``<tempdir>/<repo-name>``, which is
        predictable: another process (or a second run of this tool against the
        same repository) can create it first, and it was unconditionally
        removed with ``rmtree`` before cloning. ``mkdtemp`` gives a private,
        unpredictable directory instead, so two concurrent runs no longer
        clobber each other.

        A destination set explicitly on the instance is still honoured, and
        still cleaned before the clone.
        """
        if self.temp_dir is None:
            self.temp_dir = tempfile.mkdtemp(prefix="repo2readme-")
            return

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, onerror=force_remove)
        os.makedirs(self.temp_dir, exist_ok=True)

    def load(self, return_skip_info=False):
        self._prepare_clone_dir()

        try:
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--branch",
                    self.branch,
                    "--depth",
                    "1",
                    self.clone_url,
                    self.temp_dir,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to clone repository: {e.stderr}") from e

        # The clone is now an ordinary directory, so it goes through the same
        # traversal pipeline as a local repository. This is what makes
        # --max-workers, binary detection and the repository metadata apply to
        # remote repositories too; they were previously local-only because this
        # class hand-rolled its own os.walk.
        docs, ctx = _run_traversal(
            self.temp_dir,
            include_patterns=self.include_patterns,
            exclude_patterns=self.exclude_patterns,
            max_file_size_kb=self.max_file_size_kb,
            respect_gitignore=self.respect_gitignore,
            max_workers=self.max_workers,
        )

        if return_skip_info:
            return docs, self.temp_dir, ctx.skipped
        return docs, self.temp_dir

    def cleanup(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, onerror=force_remove)
