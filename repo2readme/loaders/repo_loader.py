
from .loader import UrlRepoLoader,LocalRepoLoader

class RepoLoader:
    def __init__(self, source):
        self.source = source

    def load(self):
        if self.source.startswith("https://github.com/"):
            loader = UrlRepoLoader(self.source)
        else:
            loader = LocalRepoLoader(self.source)

        docs, root_path = loader.load()
        return docs, root_path, loader

