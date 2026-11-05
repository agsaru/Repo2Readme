"""Classification of the ``--url`` / ``--local`` argument.

``RepoLoader`` used to decide whether a source was remote with a single literal
prefix check::

    if self.source.startswith("https://github.com/"):

Every other form of git URL - SSH, scp-style, GitLab, a self-hosted host, plain
``http``, or the same GitHub URL typed in capitals - fell through to the local
loader and failed with ``FileNotFoundError: Folder not found: git@github.com:...``,
which points the user at a directory rather than at the real problem.

This module owns that decision. ``git`` itself accepts all of these forms, so
there is no reason for the CLI to accept fewer.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from urllib.parse import parse_qsl, unquote, urlparse
from urllib.request import url2pathname

# A URL scheme as defined by RFC 3986: letter, then letters/digits/+/-/.
_SCHEME_RE = re.compile(r"^(?P<scheme>[a-zA-Z][a-zA-Z0-9+.\-]*)://")

# scp-style syntax, e.g. ``git@github.com:acme/app.git``. Deliberately strict:
# there must be a user, a host with no slash before the colon, and a path after
# it, so a Windows drive letter (``C:\repo``) or a bare ``host:port`` is not
# mistaken for a repository.
_SCP_RE = re.compile(r"^[^/\s:@]+@[^/\s:@]+:(?!//)[^\s].*$")

# Schemes git can clone from.
REMOTE_SCHEMES = frozenset({"http", "https", "ssh", "git", "ftp", "ftps"})

# Schemes that name something on the local filesystem.
LOCAL_SCHEMES = frozenset({"file"})


class SourceKind(str, Enum):
    """Whether a source has to be cloned first or can be read in place."""

    REMOTE = "remote"
    LOCAL = "local"


class InvalidSourceError(ValueError):
    """Raised when a source is empty or uses a scheme git cannot clone."""


@dataclass(frozen=True)
class RepoSource:
    """The classified source.

    Attributes
    ----------
    kind:
        ``REMOTE`` if it needs cloning, ``LOCAL`` if it is a path.
    value:
        What to hand to the loader: the clone URL for a remote source, the
        filesystem path for a local one. ``file://`` URLs are decoded here, so
        the loader only ever sees a plain path.
    original:
        The string the user typed, for error messages.
    """

    kind: SourceKind
    value: str
    original: str

    @property
    def is_remote(self) -> bool:
        return self.kind is SourceKind.REMOTE

    @property
    def is_local(self) -> bool:
        return self.kind is SourceKind.LOCAL


def _file_url_to_path(source: str) -> str:
    """Convert a ``file://`` URL to a local path."""
    parsed = urlparse(source)
    # A host of "localhost" (or empty) is the only one that makes sense; keep
    # anything else in the path so the failure is visible rather than silent.
    path = url2pathname(unquote(parsed.path))
    if parsed.netloc and parsed.netloc.lower() not in ("", "localhost"):
        return f"//{parsed.netloc}{path}"
    return path



def _validate_remote_credentials(source: str, scheme: str) -> None:
    """Reject secrets embedded in a remote URL before Git can echo them."""
    parsed = urlparse(source)
    if parsed.password is not None or (
        scheme != "ssh" and parsed.username is not None
    ):
        raise InvalidSourceError(
            "Repository URLs must not contain embedded credentials. "
            "Use a Git credential helper or SSH keys instead."
        )

    credential_keys = {
        "token",
        "access_token",
        "password",
        "secret",
        "credential",
        "api_key",
        "auth",
    }
    if any(
        key.lower() in credential_keys
        for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
    ):
        raise InvalidSourceError(
            "Repository URLs must not contain credentials in query parameters. "
            "Use a Git credential helper or SSH keys instead."
        )

def classify_source(source: str) -> RepoSource:
    """
    Decide whether ``source`` is a remote repository or a local path.

    Recognised as remote: any ``scheme://`` URL whose scheme git can clone
    (``http``, ``https``, ``ssh``, ``git``, ``ftp``, ``ftps``) and scp-style
    ``user@host:path``. Scheme matching is case-insensitive.

    Recognised as local: ``file://`` URLs (decoded to a path) and everything
    else, including relative paths, ``~`` paths and Windows drive letters.

    Raises
    ------
    InvalidSourceError
        If ``source`` is empty, or uses a ``scheme://`` git cannot clone.
    """
    if source is None or not str(source).strip():
        raise InvalidSourceError("Repository source is empty.")

    original = str(source).strip()

    scheme_match = _SCHEME_RE.match(original)
    if scheme_match:
        scheme = scheme_match.group("scheme").lower()

        if scheme in LOCAL_SCHEMES:
            return RepoSource(SourceKind.LOCAL, _file_url_to_path(original), original)

        if scheme in REMOTE_SCHEMES:
            _validate_remote_credentials(original, scheme)
            return RepoSource(SourceKind.REMOTE, original, original)

        # git+ssh://, git+https://, ... are how some tools spell these.
        if scheme.startswith("git+"):
            remainder = scheme[len("git+"):]
            if remainder in REMOTE_SCHEMES:
                stripped = original[len("git+"):]
                _validate_remote_credentials(original, remainder)
                return RepoSource(SourceKind.REMOTE, stripped, original)

        raise InvalidSourceError(
            f"Unsupported URL scheme {scheme!r}. "
            f"Supported schemes: {', '.join(sorted(REMOTE_SCHEMES | LOCAL_SCHEMES))}, "
            "or scp-style user@host:path."
        )

    if _SCP_RE.match(original):
        return RepoSource(SourceKind.REMOTE, original, original)

    return RepoSource(SourceKind.LOCAL, os.path.expanduser(original), original)


def is_remote_source(source: str) -> bool:
    """Whether ``source`` names something that has to be cloned."""
    try:
        return classify_source(source).is_remote
    except InvalidSourceError:
        return False


def repo_name_from_url(clone_url: str) -> str:
    """
    Last path component of a clone URL, without a ``.git`` suffix.

    Handles trailing slashes, a ``.git/`` suffix, scp-style URLs and query
    strings or fragments left on a copied browser URL.
    """
    candidate = str(clone_url).strip()

    # Drop anything after ? or #, which a copied browser URL often carries.
    for separator in ("?", "#"):
        candidate = candidate.split(separator, 1)[0]

    # scp-style URLs put the path after the colon.
    if _SCP_RE.match(candidate):
        candidate = candidate.split(":", 1)[1]
    elif _SCHEME_RE.match(candidate):
        candidate = urlparse(candidate).path or candidate

    candidate = candidate.rstrip("/")
    if candidate.endswith(".git"):
        candidate = candidate[: -len(".git")]
        candidate = candidate.rstrip("/")

    name = candidate.rsplit("/", 1)[-1]
    return name.removesuffix(".git")
