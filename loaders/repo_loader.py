from .local_loader import LocalRepoLoader
from .url_loader import UrlRepoLoader

class RepoLoader():
    def __init__(self, source: str):
        self.source = source
    def load(self):
        if self.source.startswith("https://github.com/"):
          return UrlRepoLoader(self.source).load()
        else:
          return LocalRepoLoader(self.source).load()
   
