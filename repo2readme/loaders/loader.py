import os
import tempfile
import shutil
from langchain_community.document_loaders import TextLoader, GitLoader
from repo2readme.utils.filter import github_file_filter
from repo2readme.utils.force_remove import force_remove
class LocalRepoLoader:
    def __init__(self, folder_path: str):
        self.folder_path = folder_path

    def load(self):
        if not os.path.exists(self.folder_path):
            raise FileNotFoundError(f"Folder not found: {self.folder_path}")

        docs = []

        for current, dirs, files in os.walk(self.folder_path):

            # Only allow dirs that pass filter
            dirs[:] = [
                d for d in dirs
                if github_file_filter(os.path.join(current, d))
            ]

            for f in files:
                full = os.path.join(current, f)

                # Skip ignored files
                if not github_file_filter(full):
                    continue

                try:
                    loader = TextLoader(full, encoding="utf-8")
                    loaded_docs=loader.load()
                    for doc in loaded_docs:
                        doc.metadata["file_path"] = full.replace("\\", "/")
                        doc.metadata["file_name"] = f
                        doc.metadata["file_type"] = os.path.splitext(f)[1].lower()
                        doc.metadata["relative_path"] = os.path.relpath(full, self.folder_path).replace("\\", "/")

                    docs.extend(loaded_docs)
                except Exception as e:
                    print(f"[ERROR] Cannot load {full}: {e}")

        return docs, self.folder_path

class UrlRepoLoader:
    def __init__(self, clone_url: str, branch: str = "main"):
        self.clone_url = clone_url
        self.branch = branch
        self.temp_dir = None

    def get_repo_name(self):
        name = self.clone_url.split("/")[-1]
        return name.replace(".git", "")

    def load(self):
        repo_name = self.get_repo_name()
        base_temp = tempfile.gettempdir()
        self.temp_dir = os.path.join(base_temp, repo_name)

        # Fresh clone
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, onerror=force_remove)

        os.makedirs(self.temp_dir, exist_ok=True)

        loader = GitLoader(
            repo_path=self.temp_dir,
            clone_url=self.clone_url,
            branch=self.branch,
            file_filter=github_file_filter     # Uses NEW logic
        )

        docs = loader.load()
        return docs, self.temp_dir

    def cleanup(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, onerror=force_remove)
