import os
import tempfile
import shutil
from langchain_community.document_loaders import GitLoader
from utils.filter import github_file_filter

class UrlRepoLoader:
    def __init__(self, clone_url: str, branch: str = "main"):
        self.clone_url = clone_url
        self.branch = branch
        self.temp_dir = None


    def load(self):
        self.temp_dir = tempfile.mkdtemp(prefix="repo2readme_")
        loader = GitLoader(
            repo_path=self.temp_dir,
            clone_url=self.clone_url,
            branch=self.branch,
            file_filter=github_file_filter
        )

        docs = loader.load()
        
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        return docs

