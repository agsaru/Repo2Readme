"""
Lazy-loading module for repo2readme loaders.

Imports are deferred to avoid triggering heavy library imports (e.g.
langchain, spacy, numpy) at module-import time.
"""

from .repo_loader import RepoLoader

__all__ = ["LocalRepoLoader", "UrlRepoLoader", "RepoLoader"]


def LocalRepoLoader(*args, **kwargs):
    """Lazy wrapper for LocalRepoLoader."""
    from .loader import LocalRepoLoader as _cls
    return _cls(*args, **kwargs)


def UrlRepoLoader(*args, **kwargs):
    """Lazy wrapper for UrlRepoLoader."""
    from .loader import UrlRepoLoader as _cls
    return _cls(*args, **kwargs)
