from __future__ import annotations
import os
import tempfile
import shutil
import subprocess
from langchain_community.document_loaders import TextLoader

from repo2readme.utils.filter import github_file_filter
from repo2readme.utils.force_remove import force_remove


class LocalRepoLoader:
    def __init__(
        self,
        folder_path: str,
        include_patterns=None,
        exclude_patterns=None,
        max_file_size_kb: int | None = 200,
    ):
        self.folder_path = folder_path
        self.include_patterns = include_patterns
        self.exclude_patterns = exclude_patterns
        self.max_file_size_kb = max_file_size_kb

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

    def load(self, return_skip_info=False):
        if not os.path.exists(self.folder_path):
            raise FileNotFoundError(f"Folder not found: {self.folder_path}")

        docs = []
        skipped: list[tuple[str, str]] = [] if return_skip_info else []
        visited_dirs: set[str] = set()
        root_resolved = os.path.realpath(self.folder_path)
        visited_dirs.add(root_resolved)

        for current, dirs, files in os.walk(self.folder_path):
            new_dirs = []
            for directory in dirs:
                full_dir_path = os.path.join(current, directory)
                rel_dir_path = os.path.relpath(full_dir_path, self.folder_path).replace("\\", "/")

                allowed, reason = github_file_filter(
                    rel_dir_path,
                    include_patterns=self.include_patterns,
                    exclude_patterns=self.exclude_patterns,
                    root_path=self.folder_path,
                    max_file_size_kb=None,
                )

                if not allowed:
                    if return_skip_info:
                        skipped.append((rel_dir_path + "/", reason))
                    continue

                resolved_path = os.path.realpath(full_dir_path)

                if resolved_path in visited_dirs:
                    if return_skip_info:
                        skipped.append((rel_dir_path + "/", "circular or duplicate symbolic link"))
                    continue

                if os.path.islink(full_dir_path):
                    if not os.path.isdir(resolved_path):
                        if return_skip_info:
                            skipped.append((rel_dir_path + "/", "broken symbolic link"))
                        continue

                visited_dirs.add(resolved_path)
                new_dirs.append(directory)

            dirs[:] = new_dirs

            for file_name in files:
                full_path = os.path.join(current, file_name)
                rel_path = os.path.relpath(full_path, self.folder_path).replace("\\", "/")

                allowed, reason = github_file_filter(
                    rel_path,
                    include_patterns=self.include_patterns,
                    exclude_patterns=self.exclude_patterns,
                    root_path=self.folder_path,
                    max_file_size_kb=self.max_file_size_kb,
                )

                if not allowed:
                    if return_skip_info:
                        skipped.append((rel_path, reason))
                    continue

                try:
                    loader = TextLoader(full_path, encoding="utf-8")
                    loaded_docs = loader.load()

                    for doc in loaded_docs:
                        doc.metadata["file_path"] = full_path.replace("\\", "/")
                        doc.metadata["file_name"] = file_name
                        doc.metadata["file_type"] = os.path.splitext(file_name)[1].lower()
                        doc.metadata["relative_path"] = rel_path

                    docs.extend(loaded_docs)

                except Exception as error:
                    print(f"[ERROR] Cannot load {full_path}: {error}")

        if return_skip_info:
            return docs, self.folder_path, skipped
        return docs, self.folder_path


class UrlRepoLoader:
    def __init__(
        self,
        clone_url: str,
        branch: str = "main",
        include_patterns=None,
        exclude_patterns=None,
        max_file_size_kb: int | None = 200,
    ):
        self.clone_url = clone_url
        self.branch = branch
        self.include_patterns = include_patterns
        self.exclude_patterns = exclude_patterns
        self.max_file_size_kb = max_file_size_kb
        self.temp_dir = None

    def get_repo_name(self):
        name = self.clone_url.rstrip("/").split("/")[-1]
        return name.removesuffix(".git")

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

    def load(self, return_skip_info=False):
        repo_name = self.get_repo_name()
        base_temp = tempfile.gettempdir()
        default_temp_dir = os.path.join(base_temp, repo_name)
        
        # Only create a new temp directory if one wasn't already set (e.g., by tests)
        if self.temp_dir is None:
            self.temp_dir = default_temp_dir

        # ALWAYS clean before cloning
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, onerror=force_remove)

        os.makedirs(self.temp_dir, exist_ok=True)

        # Clone repository using git command directly
        try:
            subprocess.run(
                ["git", "clone", "--branch", self.branch, "--depth", "1", self.clone_url, self.temp_dir],
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to clone repository: {e.stderr}") from e

        docs = []
        skipped: list[tuple[str, str]] = [] if return_skip_info else []
        visited_dirs: set[str] = set()
        root_resolved = os.path.realpath(self.temp_dir)
        visited_dirs.add(root_resolved)

        for current, dirs, files in os.walk(self.temp_dir):
            new_dirs = []
            for directory in dirs:
                full_dir_path = os.path.join(current, directory)
                rel_dir_path = os.path.relpath(full_dir_path, self.temp_dir).replace("\\", "/")

                allowed, reason = github_file_filter(
                    rel_dir_path,
                    include_patterns=self.include_patterns,
                    exclude_patterns=self.exclude_patterns,
                    root_path=self.temp_dir,
                    max_file_size_kb=None,
                )

                if not allowed:
                    if return_skip_info:
                        skipped.append((rel_dir_path + "/", reason))
                    continue

                resolved_path = os.path.realpath(full_dir_path)

                if resolved_path in visited_dirs:
                    if return_skip_info:
                        skipped.append((rel_dir_path + "/", "circular or duplicate symbolic link"))
                    continue

                if os.path.islink(full_dir_path):
                    if not os.path.isdir(resolved_path):
                        if return_skip_info:
                            skipped.append((rel_dir_path + "/", "broken symbolic link"))
                        continue

                visited_dirs.add(resolved_path)
                new_dirs.append(directory)

            dirs[:] = new_dirs

            for file_name in files:
                full_path = os.path.join(current, file_name)
                rel_path = os.path.relpath(full_path, self.temp_dir).replace("\\", "/")

                allowed, reason = github_file_filter(
                    rel_path,
                    include_patterns=self.include_patterns,
                    exclude_patterns=self.exclude_patterns,
                    root_path=self.temp_dir,
                    max_file_size_kb=self.max_file_size_kb,
                )

                if not allowed:
                    if return_skip_info:
                        skipped.append((rel_path, reason))
                    continue

                try:
                    loader = TextLoader(full_path, encoding="utf-8")
                    loaded_docs = loader.load()

                    for doc in loaded_docs:
                        doc.metadata["file_path"] = full_path.replace("\\", "/")
                        doc.metadata["file_name"] = file_name
                        doc.metadata["file_type"] = os.path.splitext(file_name)[1].lower()
                        doc.metadata["relative_path"] = rel_path

                    docs.extend(loaded_docs)

                except Exception as error:
                    print(f"[ERROR] Cannot load {full_path}: {error}")

        if return_skip_info:
            return docs, self.temp_dir, skipped
        return docs, self.temp_dir

    def cleanup(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, onerror=force_remove)