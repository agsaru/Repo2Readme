from .loader import LocalRepoLoader, UrlRepoLoader


class RepoLoader:
    def __init__(
        self,
        source,
        include_patterns=None,
        exclude_patterns=None,
        max_file_size_kb=200,
        respect_gitignore=False,
    ):
        self.source = source
        self.include_patterns = include_patterns
        self.exclude_patterns = exclude_patterns
        self.max_file_size_kb = max_file_size_kb
        self.respect_gitignore = respect_gitignore

    def load(self, return_skip_info=False):
        if self.source.startswith("https://github.com/"):
            loader = UrlRepoLoader(
                self.source,
                include_patterns=self.include_patterns,
                exclude_patterns=self.exclude_patterns,
                max_file_size_kb=self.max_file_size_kb,
                respect_gitignore=self.respect_gitignore,
            )
            result = loader.load(return_skip_info=return_skip_info)
            if return_skip_info:
                docs, temp_dir, skipped = result
                return docs, temp_dir, loader, skipped
            docs, temp_dir = result
            return docs, temp_dir, loader
        else:
            loader = LocalRepoLoader(
                self.source,
                include_patterns=self.include_patterns,
                exclude_patterns=self.exclude_patterns,
                max_file_size_kb=self.max_file_size_kb,
                respect_gitignore=self.respect_gitignore,
            )
            result = loader.load(return_skip_info=return_skip_info)
            if return_skip_info:
                docs, root_path, skipped = result
                return docs, root_path, loader, skipped
            docs, root_path = result
            return docs, root_path, loader