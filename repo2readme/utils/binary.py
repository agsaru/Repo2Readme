"""
Binary file detection utilities.

Provides content-based detection of binary files to allow the traversal
pipeline to skip unsupported content before attempting text decoding,
metadata extraction, or language detection.
"""

from __future__ import annotations

# Bounded sample size for binary detection (8 KB).
# This matches the sample size used in repo2readme.utils.detect_language.
_MAX_SAMPLE_SIZE = 8192

# Known binary file signatures checked against the file prefix.
# Each entry is a tuple of byte sequences; if any matches the start of the
# sample, the file is considered binary.
_BINARY_SIGNATURES: tuple[tuple[bytes, ...], ...] = (
    # Images
    (b"\x89PNG\r\n\x1a\n",),  # PNG
    (b"\xff\xd8\xff",),  # JPEG/JFIF
    (b"GIF87a", b"GIF89a"),  # GIF
    (b"BM",),  # BMP
    (b"\x00\x00\x01\x00",),  # ICO
    # Documents
    (b"%PDF",),  # PDF
    # Archives / compressed
    (b"PK\x03\x04",),  # ZIP, JAR, DOCX, XLSX, PPTX, APK, etc.
    (b"Rar!\x1a\x07\x00", b"Rar!\x1a\x07\x01\x00",),  # RAR
    (b"\x1f\x8b",),  # GZIP
    (b"BZh",),  # BZIP2
    (b"\xfd\x37\x7a\x58\x5a\x00",),  # XZ
    (b"ustar",),  # TAR
    # Executables / object files
    (b"\x7fELF",),  # ELF
    (b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf",),  # Mach-O 32/64
    (b"\xcf\xfa\xed\xfe",),  # Mach-O reverse
    (b"MZ",),  # Windows PE/COFF
    # Databases
    (b"SQLite format 3",),  # SQLite
    # Media
    (b"ID3", b"\xff\xfb",),  # MP3
    (b"fLaC",),  # FLAC
)


def is_binary_content(file_path: str, sample_size: int = _MAX_SAMPLE_SIZE) -> bool:
    """
    Determine whether a file appears to contain binary content.

    Reads only a bounded prefix of the file (default 8 KB) to avoid loading
    large files entirely into memory. Detection is content-based and does not
    rely on file extensions.

    A file is considered binary if the inspected prefix contains:

    1. Any null byte (``\\x00``), OR
    2. A known binary format signature (e.g., PNG, JPEG, PDF, ZIP, ELF), OR
    3. Bytes that cannot be decoded as UTF-8 (the encoding used by
       ``load_file_content``).

    UTF-8 text files containing non-ASCII characters are *not* classified as
    binary, because null bytes, known signatures, and invalid UTF-8 byte
    sequences are absent from valid UTF-8 encoded text.

    Args:
        file_path: Absolute or relative path to the file to inspect.
        sample_size: Maximum number of bytes to read. Defaults to 8192.

    Returns:
        True if the file appears to be binary, False if it appears to be
        plain text (including UTF-8 with non-ASCII characters).

    Raises:
        OSError: If the file cannot be opened or read due to an I/O error.
        ValueError: If ``file_path`` is empty.
    """
    if not file_path:
        raise ValueError("file_path must not be empty")

    try:
        with open(file_path, "rb") as f:
            sample = f.read(sample_size)
    except OSError:
        raise

    if not sample:
        return False

    # Null bytes are a strong, extension-independent indicator of binary data.
    if b"\x00" in sample:
        return True

    # Check for known binary signatures in the file prefix.
    prefix = sample[:12]
    for signatures in _BINARY_SIGNATURES:
        if any(prefix.startswith(sig) for sig in signatures):
            return True

    # Fallback: try to decode the sample as UTF-8 (the encoding used by
    # load_file_content). If the sample cannot be decoded as valid UTF-8,
    # the file is binary even without null bytes or a known signature.
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return True

    return False
