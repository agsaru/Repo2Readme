"""
Lazy-loading module for repo2readme loaders.

Imports are deferred to avoid triggering heavy library imports (e.g.
langchain, spacy, numpy) at module-import time.
"""

from .repo_loader import RepoLoader

__all__ = ["LocalRepoLoader", "UrlRepoLoader", "RepoLoader"]

# Lazy-loading wrappers preserve lightweight import while keeping class
# identity for isinstance(), issubclass(), subclassing, and unittest.mock.patch().
_LocalRepoLoader = None
_UrlRepoLoader = None


def LocalRepoLoader(*args, **kwargs):
    """Lazy wrapper for LocalRepoLoader."""
    global _LocalRepoLoader
    if _LocalRepoLoader is None:
        from .loader import LocalRepoLoader as _cls
        _LocalRepoLoader = _cls
    return _LocalRepoLoader(*args, **kwargs)


def UrlRepoLoader(*args, **kwargs):
    """Lazy wrapper for UrlRepoLoader."""
    global _UrlRepoLoader
    if _UrlRepoLoader is None:
        from .loader import UrlRepoLoader as _cls
        _UrlRepoLoader = _cls
    return _UrlRepoLoader(*args, **kwargs)
