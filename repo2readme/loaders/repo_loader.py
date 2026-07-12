from .loader import LocalRepoLoader, UrlRepoLoader


class RepoLoader:
    def __init__(
        self,
        source,
        include_patterns=None,
        exclude_patterns=None,
        max_file_size_kb=200,
    ):
        self.source = source
        self.include_patterns = include_patterns
        self.exclude_patterns = exclude_patterns
        self.max_file_size_kb = max_file_size_kb

    def load(self, return_skip_info=False):
        if self.source.startswith("https://github.com/"):
            loader = UrlRepoLoader(
                self.source,
                include_patterns=self.include_patterns,
                exclude_patterns=self.exclude_patterns,
                max_file_size_kb=self.max_file_size_kb,
            )
            docs, temp_dir = loader.load()
            if return_skip_info:
                # GitLoader performs filtering internally and does not expose skipped files,
                # so skipped-file reporting is currently only available for LocalRepoLoader.
                return docs, temp_dir, loader, []
            return docs, temp_dir, loader
        else:
            loader = LocalRepoLoader(
                self.source,
                include_patterns=self.include_patterns,
                exclude_patterns=self.exclude_patterns,
                max_file_size_kb=self.max_file_size_kb,
            )
            result = loader.load(return_skip_info=return_skip_info)
            if return_skip_info:
                docs, root_path, skipped = result
                return docs, root_path, loader, skipped
            docs, root_path = result
            return docs, root_path, loader
