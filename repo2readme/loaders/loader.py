from __future__ import annotations
import os
import tempfile
import shutil
from langchain_community.document_loaders import TextLoader, GitLoader

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

        allowed, _ = github_file_filter(
            relative_path,
            include_patterns=self.include_patterns,
            exclude_patterns=self.exclude_patterns,
            root_path=self.folder_path,
            max_file_size_kb=self.max_file_size_kb,
        )
        return allowed

    def load(self, return_skip_info=False):
        if not os.path.exists(self.folder_path):
            raise FileNotFoundError(f"Folder not found: {self.folder_path}")

        docs = []
        skipped: list[tuple[str, str]] = [] if return_skip_info else []

        for current, dirs, files in os.walk(self.folder_path):
            dirs[:] = [
                directory
                for directory in dirs
                if self._should_include(os.path.join(current, directory))
            ]

            for file_name in files:
                full_path = os.path.join(current, file_name)
                rel_path = os.path.relpath(full_path, self.folder_path).replace("\\", "/")

                if not self._should_include(full_path):
                    if return_skip_info:
                        _, reason = github_file_filter(
                            rel_path,
                            include_patterns=self.include_patterns,
                            exclude_patterns=self.exclude_patterns,
                            root_path=self.folder_path,
                            max_file_size_kb=self.max_file_size_kb,
                        )
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

        allowed, _ = github_file_filter(
            relative_path,
            include_patterns=self.include_patterns,
            exclude_patterns=self.exclude_patterns,
            root_path=self.temp_dir,
            max_file_size_kb=self.max_file_size_kb,
        )
        return allowed

    def load(self):
        repo_name = self.get_repo_name()
        base_temp = tempfile.gettempdir()
        self.temp_dir = os.path.join(base_temp, repo_name)

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, onerror=force_remove)

        os.makedirs(self.temp_dir, exist_ok=True)

        loader = GitLoader(
            repo_path=self.temp_dir,
            clone_url=self.clone_url,
            branch=self.branch,
            file_filter=self._should_include,
        )

        docs = loader.load()

        for doc in docs:
            source = doc.metadata.get("source")

            if source:
                full_path = os.path.join(self.temp_dir, source)
                normalized_full_path = full_path.replace("\\", "/")

                doc.metadata["file_path"] = normalized_full_path
                doc.metadata["file_name"] = os.path.basename(source)
                doc.metadata["file_type"] = os.path.splitext(source)[1].lower()
                doc.metadata["relative_path"] = source.replace("\\", "/")

        return docs, self.temp_dir

    def cleanup(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, onerror=force_remove)