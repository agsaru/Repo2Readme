from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _installed_version

# Kept in sync with pyproject.toml. Used as the fallback when the package is
# not installed, e.g. when running from a source checkout.
version = "1.1.0"

try:
    __version__ = _installed_version("repo2readme")
except PackageNotFoundError:  
    __version__ = version
