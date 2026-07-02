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

    def load(self):
        if self.source.startswith("https://github.com/"):
            loader = UrlRepoLoader(
                self.source,
                include_patterns=self.include_patterns,
                exclude_patterns=self.exclude_patterns,
                max_file_size_kb=self.max_file_size_kb,
            )
        else:
            loader = LocalRepoLoader(
                self.source,
                include_patterns=self.include_patterns,
                exclude_patterns=self.exclude_patterns,
                max_file_size_kb=self.max_file_size_kb,
            )

        docs, root_path = loader.load()
        return docs, root_path, loader