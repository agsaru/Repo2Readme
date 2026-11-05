"""
Binary file detection utilities.

Provides content-based detection of binary files to allow the traversal
pipeline to skip unsupported content before attempting text decoding,
metadata extraction, or language detection.
"""

from __future__ import annotations

from repo2readme.utils.text_encoding import (
    decode_bytes,
    encoding_from_bom,
    looks_like_text,
)

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

    The prefix is classified in this order:

    1. A UTF-16 / UTF-32 byte order mark means text. The null bytes that make
       up half of a UTF-16 file would otherwise be read as binary evidence,
       which is how ordinary Windows-encoded source files ended up skipped.
    2. A known binary format signature (PNG, JPEG, PDF, ZIP, ELF, ...) means
       binary.
    3. A null byte outside a BOM-declared encoding means binary.
    4. Otherwise the sample is decoded through the shared fallback chain in
       :mod:`repo2readme.utils.text_encoding`. A multi-byte character cut in
       half by the sample boundary is tolerated, so a valid UTF-8 file is no
       longer called binary because of where byte 8192 lands. Because the last
       encoding in that chain cannot fail, the decoded text is then judged on
       its density of control characters: source files in a legacy single-byte
       encoding pass, binaries that happen to contain no null byte in their
       first 8 KB do not.

    Args:
        file_path: Absolute or relative path to the file to inspect.
        sample_size: Maximum number of bytes to read. Defaults to 8192.

    Returns:
        True if the file appears to be binary, False if it appears to be
        plain text (including UTF-8, UTF-16 and legacy single-byte encodings).

    Raises:
        OSError: If the file cannot be opened or read due to an I/O error.
        ValueError: If ``file_path`` is empty.
    """
    if not file_path:
        raise ValueError("file_path must not be empty")
    if sample_size < 0:
        raise ValueError("sample_size must be non-negative")

    with open(file_path, "rb") as f:
        sample = f.read(sample_size)

    if not sample:
        return False

    # A byte order mark is an explicit declaration of a text encoding, so it is
    # checked before anything else - including the null-byte rule, which every
    # UTF-16 file would otherwise trip on its second byte.
    bom_encoding = encoding_from_bom(sample)

    # Check for known binary signatures in the file prefix.
    prefix = sample[:12]
    for signatures in _BINARY_SIGNATURES:
        if any(prefix.startswith(sig) for sig in signatures):
            return True

    if bom_encoding is None and b"\x00" in sample:
        # Null bytes are a strong, extension-independent indicator of binary
        # data in any encoding that does not declare itself.
        return True

    decoded = decode_bytes(sample, allow_truncated=True)
    if decoded is None:
        return True

    return not looks_like_text(decoded.text)
