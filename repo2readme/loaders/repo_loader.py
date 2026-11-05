from repo2readme.loaders.source import classify_source

from .loader import LocalRepoLoader, UrlRepoLoader


class RepoLoader:
    """
    Dispatches a source string to the loader that can handle it.

    The choice used to be ``source.startswith("https://github.com/")``, which
    routed every other git URL - SSH, scp-style, GitLab, self-hosted, plain
    http, or the same URL in capitals - to the local loader, where it failed
    with "Folder not found". ``classify_source`` makes the decision instead and
    accepts everything ``git clone`` does.
    """

    def __init__(
        self,
        source,
        include_patterns=None,
        exclude_patterns=None,
        max_file_size_kb=200,
        respect_gitignore=False,
        max_workers=None,
        branch="main",
    ):
        self.source = source
        self.include_patterns = include_patterns
        self.exclude_patterns = exclude_patterns
        self.max_file_size_kb = max_file_size_kb
        self.respect_gitignore = respect_gitignore
        self.max_workers = max_workers
        self.branch = branch

    def _build_loader(self):
        resolved = classify_source(self.source)

        if resolved.is_remote:
            return UrlRepoLoader(
                resolved.value,
                branch=self.branch,
                include_patterns=self.include_patterns,
                exclude_patterns=self.exclude_patterns,
                max_file_size_kb=self.max_file_size_kb,
                respect_gitignore=self.respect_gitignore,
                max_workers=self.max_workers,
            )

        return LocalRepoLoader(
            resolved.value,
            include_patterns=self.include_patterns,
            exclude_patterns=self.exclude_patterns,
            max_file_size_kb=self.max_file_size_kb,
            respect_gitignore=self.respect_gitignore,
            max_workers=self.max_workers,
        )

    def load(self, return_skip_info=False):
        loader = self._build_loader()
        try:
            result = loader.load(return_skip_info=return_skip_info)
        except BaseException:
            cleanup = getattr(loader, "cleanup", None)
            if cleanup:
                cleanup()
            raise

        if return_skip_info:
            docs, root_path, skipped = result
            return docs, root_path, loader, skipped

        docs, root_path = result
        return docs, root_path, loader
