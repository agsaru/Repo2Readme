"""
Unit tests for binary file detection (issue #75).

Covers:
- PNG and other recognizable binary formats
- JPEG and other common binary formats
- Null byte detection
- Arbitrary binary files without special extensions
- Arbitrary binary without null bytes or known signatures
- ASCII text files NOT detected as binary
- UTF-8 source files with non-ASCII characters NOT detected as binary
"""

from __future__ import annotations

import pytest

from repo2readme.utils.binary import is_binary_content


class TestIsBinaryContent:
    """Unit tests for the is_binary_content helper."""

    def test_png_detected_as_binary(self, tmp_path):
        png_file = tmp_path / "image.png"
        png_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        assert is_binary_content(str(png_file)) is True

    def test_jpeg_detected_as_binary(self, tmp_path):
        jpeg_file = tmp_path / "photo.jpg"
        jpeg_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        assert is_binary_content(str(jpeg_file)) is True

    def test_gif_detected_as_binary(self, tmp_path):
        gif_file = tmp_path / "anim.gif"
        gif_file.write_bytes(b"GIF89a" + b"\x00" * 100)
        assert is_binary_content(str(gif_file)) is True

    def test_pdf_detected_as_binary(self, tmp_path):
        pdf_file = tmp_path / "doc.pdf"
        pdf_file.write_bytes(b"%PDF-1.4" + b"\x00" * 100)
        assert is_binary_content(str(pdf_file)) is True

    def test_zip_detected_as_binary(self, tmp_path):
        zip_file = tmp_path / "archive.zip"
        zip_file.write_bytes(b"PK\x03\x04" + b"\x00" * 100)
        assert is_binary_content(str(zip_file)) is True

    def test_null_bytes_detected_as_binary(self, tmp_path):
        binary_file = tmp_path / "random.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03\x04\x05")
        assert is_binary_content(str(binary_file)) is True

    def test_arbitrary_binary_without_extension_detected(self, tmp_path):
        binary_file = tmp_path / "unknown_file"
        binary_file.write_bytes(b"\x00\xde\xad\xbe\xef")
        assert is_binary_content(str(binary_file)) is True

    def test_arbitrary_binary_without_null_or_signature(self, tmp_path):
        """Arbitrary binary bytes with no null, no known signature are binary."""
        binary_file = tmp_path / "raw_data"
        binary_file.write_bytes(b"\xde\xad\xbe\xef\xca\xfe\xba\xbe\x13\x37")
        assert is_binary_content(str(binary_file)) is True

    def test_ascii_text_not_detected_as_binary(self, tmp_path):
        text_file = tmp_path / "hello.txt"
        text_file.write_text("print('hello world')\n", encoding="utf-8")
        assert is_binary_content(str(text_file)) is False

    def test_utf8_text_with_non_ascii_not_detected_as_binary(self, tmp_path):
        text_file = tmp_path / "unicode.txt"
        text_file.write_text("你好世界\nПривет мир\n", encoding="utf-8")
        assert is_binary_content(str(text_file)) is False

    def test_empty_file_not_detected_as_binary(self, tmp_path):
        empty_file = tmp_path / "empty.txt"
        empty_file.write_bytes(b"")
        assert is_binary_content(str(empty_file)) is False

    def test_io_error_raised(self, tmp_path):
        nonexistent = tmp_path / "does_not_exist"
        with pytest.raises(OSError):
            is_binary_content(str(nonexistent))

    def test_empty_path_raises_value_error(self):
        with pytest.raises(ValueError):
            is_binary_content("")
