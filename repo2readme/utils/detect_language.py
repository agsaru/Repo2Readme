"""
Language detection module for repo2readme.

Detection order:
1. Extension-based detection (primary, highest priority)
2. Filename-based detection (for extensionless files)
3. Unix shebang detection (first line of file)
4. Lightweight content-based detection (rule-based heuristics)
5. Unknown (fallback)
"""

import os
import re
from typing import Optional

# ---------------------------------------------------------------------------
# 1. EXTENSION → LANGUAGE MAP (existing, unchanged)
# ---------------------------------------------------------------------------
EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    # Programming Languages
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".pl": "perl",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".fish": "bash",
    ".ps1": "powershell",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".r": "r",
    # Markdown / documentation
    ".md": "markdown",
    ".markdown": "markdown",
    ".rst": "rst",
    # Data / config
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "ini",
    ".xml": "xml",
    ".csv": "csv",
    # Web
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".less": "less",
    # Shell / build
    ".bat": "batch",
    ".cmd": "batch",
    ".gradle": "groovy",
    ".groovy": "groovy",
    ".sql": "sql",
    ".dockerignore": "dockerfile",
}

# ---------------------------------------------------------------------------
# 2. FILENAME → LANGUAGE MAP (for common extensionless files)
# ---------------------------------------------------------------------------
FILENAME_LANGUAGE_MAP: dict[str, str] = {
    "dockerfile": "dockerfile",
    "makefile": "makefile",
    "jenkinsfile": "groovy",
    "procfile": "procfile",
    "cmakelists.txt": "cmake",
    "gemfile": "ruby",
    "rakefile": "ruby",
    "brewfile": "ruby",
    "vagrantfile": "ruby",
    "docker-compose.yml": "yaml",
    "docker-compose.yaml": "yaml",
    # Additional common filenames
    "justfile": "just",
    "snakefile": "python",
    "cargo.toml": "rust",
    "gemfile.lock": "ruby",
    "guardfile": "ruby",
    "capfile": "ruby",
    "podfile": "ruby",
    "fastfile": "ruby",
    "appfile": "ruby",
    "matchfile": "ruby",
    "pluginfile": "ruby",
}

# ---------------------------------------------------------------------------
# 3. SHEBANG PATTERNS
# ---------------------------------------------------------------------------
# Ordered from most-specific to least-specific to avoid false positives.
SHEBANG_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Python (direct path: /usr/bin/python* or env path: env python*)
    (
        re.compile(
            r"^\s*#!\s*(?:(?:/usr/bin/env\s+)|(?:/usr/bin/))python(\d+(?:\.\d+)?)?(?:\s|$)"
        ),
        "python",
    ),
    (re.compile(r"^\s*#!\s*/bin/python(\d+(?:\.\d+)?)?(?:\s|$)"), "python"),
    # Bash
    (
        re.compile(
            r"^\s*#!\s*(?:(?:/usr/bin/env\s+)|(?:/usr/bin/)|(?:/bin/))bash(?:\s|$)"
        ),
        "bash",
    ),
    # Sh
    (
        re.compile(
            r"^\s*#!\s*(?:(?:/usr/bin/env\s+)|(?:/usr/bin/)|(?:/bin/))sh(?:\s|$)"
        ),
        "sh",
    ),
    # Node
    (
        re.compile(
            r"^\s*#!\s*(?:(?:/usr/bin/env\s+)|(?:/usr/bin/)|(?:/bin/))node(?:\s|$)"
        ),
        "javascript",
    ),
    # Deno / Bun
    (
        re.compile(
            r"^\s*#!\s*(?:(?:/usr/bin/env\s+)|(?:/usr/bin/))(?:deno|bun)(?:\s|$)"
        ),
        "javascript",
    ),
    # Ruby
    (
        re.compile(
            r"^\s*#!\s*(?:(?:/usr/bin/env\s+)|(?:/usr/bin/)|(?:/bin/))ruby(?:\s|$)"
        ),
        "ruby",
    ),
    # Perl
    (
        re.compile(
            r"^\s*#!\s*(?:(?:/usr/bin/env\s+)|(?:/usr/bin/)|(?:/bin/))perl(?:\s|$)"
        ),
        "perl",
    ),
    # PHP
    (
        re.compile(
            r"^\s*#!\s*(?:(?:/usr/bin/env\s+)|(?:/usr/bin/)|(?:/bin/))php(?:\s|$)"
        ),
        "php",
    ),
    # Racket
    (re.compile(r"^\s*#!\s*/usr/bin/env\s+racket(?:\s|$)"), "racket"),
    # Lua
    (re.compile(r"^\s*#!\s*/usr/bin/env\s+lua(?:\s|$)"), "lua"),
    # Awk
    (re.compile(r"^\s*#!\s*/usr/bin/env\s+awk(?:\s|$)"), "awk"),
    # Guile (Scheme)
    (re.compile(r"^\s*#!\s*/usr/bin/env\s+guile(?:\s|$)"), "scheme"),
    # Tcl
    (re.compile(r"^\s*#!\s*/usr/bin/env\s+tclsh(?:\s|$)"), "tcl"),
]

# ---------------------------------------------------------------------------
# 4. CONTENT-BASED DETECTION RULES
# ---------------------------------------------------------------------------
# Each entry is a (language, list-of-markers) pair.
# Markers are checked against the first 8 KB of content.
# More specific markers should come first for each language.
CONTENT_RULES: list[tuple[str, list[str]]] = [
    # Dockerfile
    ("dockerfile", ["FROM ", "RUN ", "COPY ", "CMD ", "ENTRYPOINT "]),
    # Python
    ("python", ['if __name__ == "__main__"', "def ", "import ", "from ", "class "]),
    # TypeScript
    ("typescript", ["interface ", "implements ", "readonly ", "type "]),
    # JavaScript (less specific than TypeScript, so listed after)
    ("javascript", ["module.exports", "require(", "=>", "const ", "let ", "function "]),
    # Shell
    ("bash", ["#!/", "echo ", "export ", "fi", "then ", "done ", "else "]),
    # YAML
    ("yaml", ["---\n", ":\n  ", "  - ", ": "]),
    # JSON
    ("json", ["{", "[", '"', ": ", "}"]),
    # Markdown
    ("markdown", ["# ", "## ", "```", "---"]),
    # Groovy / Jenkinsfile
    ("groovy", ["pipeline {", "stages {", "stage(", "agent "]),
    # Makefile
    ("makefile", ["CC=", "CFLAGS=", "LDFLAGS=", "$@", "$<", ":=", "PHONY"]),
    # Ruby
    ("ruby", ["require ", "gem ", "def ", "end", "module ", "class "]),
    # Perl
    ("perl", ["use strict", "use warnings", "my $", 'print "']),
    # PHP
    ("php", ["<?php", "function ", "echo ", "$this->"]),
]

# Maximum bytes to read for content-based detection
_MAX_CONTENT_BYTES = 8192


# ===================================================================
# Helper functions
# ===================================================================


def _detect_by_extension(path: str) -> Optional[str]:
    """
    Detect language based on file extension.
    Returns language string or None if no match.
    """
    _, extension = os.path.splitext(path)

    # Handle dotfiles (e.g., ".gitignore", ".env")
    if not extension and path.startswith("."):
        extension = path

    return EXTENSION_LANGUAGE_MAP.get(extension.lower(), None)


def _detect_by_filename(path: str) -> Optional[str]:
    """
    Detect language based on filename for common extensionless files.
    Extracts just the basename for matching.
    Returns language string or None if no match.
    """
    filename = os.path.basename(path)
    return FILENAME_LANGUAGE_MAP.get(filename.lower(), None)


def _detect_by_shebang(content: str) -> Optional[str]:
    """
    Detect language by parsing the first line of content for a Unix shebang.
    Ignores leading whitespace before the shebang marker.
    Returns language string or None if no match.
    """
    if not content:
        return None

    # Extract the first line (up to first newline)
    first_line = content.split("\n")[0].strip()

    # Only check lines that look like shebangs (start with #!)
    if not first_line.startswith("#!"):
        return None

    # Try each shebang pattern
    for pattern, language in SHEBANG_PATTERNS:
        if pattern.match(first_line):
            return language

    return None


def _detect_by_content(content: str) -> Optional[str]:
    """
    Lightweight rule-based content detection.
    Inspects only the first 8 KB of content.
    Uses simple string matching (no heavy parsing libraries).
    Returns language string or None if no match.
    """
    if not content:
        return None

    # Limit content to avoid scanning large files
    sample = content[:_MAX_CONTENT_BYTES]

    for language, markers in CONTENT_RULES:
        score = 0
        for marker in markers:
            if marker in sample:
                score += 1

        # Require at least 2 markers to match
        if score >= 2:
            return language

    return None


def _read_file_content(file_path: str) -> Optional[str]:
    """
    Safely read the first portion of a file for detection purposes.
    Handles binary files, permission errors, and other I/O issues.
    Returns content string or None if the file cannot be read.
    """
    try:
        with open(file_path, "rb") as f:
            raw = f.read(_MAX_CONTENT_BYTES)

        # Check for null bytes indicating binary content
        if b"\0" in raw:
            return None

        # Decode with UTF-8 (fallback to latin-1)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1")

    except (IOError, OSError, PermissionError):
        return None


# ===================================================================
# Main API
# ===================================================================


def detect_lang(path: str, content: Optional[str] = None) -> str:
    """
    Detect the programming or markup language of a file.

    Detection order:
    1. Extension-based detection (highest priority, backward compatible)
    2. Filename-based detection (for extensionless files)
    3. Unix shebang detection (first line)
    4. Lightweight content-based detection
    5. Unknown (fallback)

    Args:
        path: File path or filename (can be just an extension like ".py").
        content: Optional file content as string. If not provided and the path
                 points to an existing file, it will be read automatically.

    Returns:
        A string identifying the language (e.g., "python", "javascript", "unknown").
    """
    # Step 1: Extension-based detection (highest priority)
    result = _detect_by_extension(path)
    if result:
        return result

    # Step 2: Filename-based detection
    result = _detect_by_filename(path)
    if result:
        return result

    # Obtain content for shebang and content-based detection
    file_content: Optional[str] = content

    # If content was not passed, try to read the file
    if file_content is None:
        # If path looks like a valid file path, try to read it
        if os.path.isfile(path):
            file_content = _read_file_content(path)

    if file_content is None:
        return "unknown"

    # Step 3: Shebang detection
    result = _detect_by_shebang(file_content)
    if result:
        return result

    # Step 4: Content-based detection (final fallback)
    result = _detect_by_content(file_content)
    if result:
        return result

    # Step 5: Unknown
    return "unknown"
