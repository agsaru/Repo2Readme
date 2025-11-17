import os
from langchain_community.document_loaders import TextLoader
from utils.filter import github_file_filter

class LocalRepoLoader:
    def __init__(self, folder_path: str):
        self.folder_path = folder_path

    def load(self):
        if not os.path.exists(self.folder_path):
            raise FileNotFoundError(f"Folder does not exist: {self.folder_path}")

        docs = []

        for current_dir_path, dirs, files in os.walk(self.folder_path):
            dirs[:] = [d for d in dirs if not github_file_filter(d)]
            for file in files:
                if github_file_filter(file):
                    continue

                file_path = os.path.join(current_dir_path, file)
                try:
                    loader = TextLoader(file_path, encoding="utf-8")
                    docs.extend(loader.load())
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")

        return docs
