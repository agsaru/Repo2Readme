"""Repository statistics and project health analysis.

Static analysis of a repository's structure, language distribution, file
sizes, complexity, and documentation coverage — no API keys required.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from dataclasses import dataclass, field

from repo2readme.utils.detect_language import detect_lang


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FileStats:
    path: str
    relative_path: str
    language: str
    size_bytes: int
    line_count: int
    blank_lines: int
    comment_lines: int
    code_lines: int
    has_docstring: bool
    complexity_score: int

    @property
    def comment_ratio(self) -> float:
        non_blank = self.line_count - self.blank_lines
        return self.comment_lines / non_blank if non_blank else 0.0


@dataclass
class LanguageStats:
    name: str
    file_count: int = 0
    total_lines: int = 0
    code_lines: int = 0
    blank_lines: int = 0
    comment_lines: int = 0
    total_bytes: int = 0
    avg_complexity: float = 0.0
    avg_file_size_lines: float = 0.0

    @property
    def comment_ratio(self) -> float:
        non_blank = self.total_lines - self.blank_lines
        return self.comment_lines / non_blank if non_blank else 0.0


@dataclass
class DirectoryStats:
    name: str
    file_count: int = 0
    total_size_bytes: int = 0
    languages: dict[str, int] = field(default_factory=dict)


@dataclass
class RepoStats:
    total_files: int = 0
    total_size_bytes: int = 0
    total_lines: int = 0
    total_code_lines: int = 0
    total_blank_lines: int = 0
    total_comment_lines: int = 0
    languages: dict[str, LanguageStats] = field(default_factory=dict)
    top_level_dirs: dict[str, DirectoryStats] = field(default_factory=dict)
    file_stats: list[FileStats] = field(default_factory=list)
    largest_files: list[FileStats] = field(default_factory=list)
    most_complex_files: list[FileStats] = field(default_factory=list)
    documentation_files: int = 0
    config_files: int = 0
    test_files: int = 0
    documentation_score: float = 0.0
    code_quality_score: float = 0.0
    project_maturity_score: float = 0.0


# ---------------------------------------------------------------------------
# Comment / complexity helpers
# ---------------------------------------------------------------------------

_LANG_ALIAS = {
    "jsx": "javascript", "tsx": "typescript", "mjs": "javascript",
    "cjs": "javascript", "rs": "rust", "py": "python", "js": "javascript",
    "ts": "typescript", "rb": "ruby",
}

# Family-based comment patterns
_SINGLE_LINE_COMMENT = re.compile(r'^\s*#')
_BLOCK_COMMENT_START = re.compile(r'^\s*/\*')
_BLOCK_COMMENT_CONT = re.compile(r'^\s*\*')
_SINGLE_SLASH_SLASH = re.compile(r'^\s*//')

_LANG_COMMENT_PATTERNS: dict[str, list[re.Pattern]] = {
    "python": [_SINGLE_LINE_COMMENT],
    "ruby": [_SINGLE_LINE_COMMENT],
    "bash": [_SINGLE_LINE_COMMENT],
    "sh": [_SINGLE_LINE_COMMENT],
    "yaml": [_SINGLE_LINE_COMMENT],
    "toml": [_SINGLE_LINE_COMMENT],
    "javascript": [_SINGLE_SLASH_SLASH, _BLOCK_COMMENT_START, _BLOCK_COMMENT_CONT],
    "typescript": [_SINGLE_SLASH_SLASH, _BLOCK_COMMENT_START, _BLOCK_COMMENT_CONT],
    "java": [_SINGLE_SLASH_SLASH, _BLOCK_COMMENT_START, _BLOCK_COMMENT_CONT],
    "go": [_SINGLE_SLASH_SLASH, _BLOCK_COMMENT_START, _BLOCK_COMMENT_CONT],
    "rust": [_SINGLE_SLASH_SLASH, _BLOCK_COMMENT_START, _BLOCK_COMMENT_CONT],
    "c": [_SINGLE_SLASH_SLASH, _BLOCK_COMMENT_START, _BLOCK_COMMENT_CONT],
    "cpp": [_SINGLE_SLASH_SLASH, _BLOCK_COMMENT_START, _BLOCK_COMMENT_CONT],
    "csharp": [_SINGLE_SLASH_SLASH, _BLOCK_COMMENT_START, _BLOCK_COMMENT_CONT],
    "css": [_BLOCK_COMMENT_START, _BLOCK_COMMENT_CONT],
    "scss": [_BLOCK_COMMENT_START, _BLOCK_COMMENT_CONT, _SINGLE_SLASH_SLASH],
    "php": [_SINGLE_SLASH_SLASH, _BLOCK_COMMENT_START, _BLOCK_COMMENT_CONT],
}

# Complexity markers per family
_COMPLEXITY_C_FAMILY = ["if (", "if(", "for (", "for(", "while (", "while(", "case ", "catch ("]
_COMPLEXITY_PYTHON = ["if ", "elif ", "for ", "while ", "except ", "and ", "or "]
_COMPLEXITY_GO = ["if ", "for ", "switch ", "select ", "case "]
_COMPLEXITY_RUST = ["if ", "if let", "for ", "while ", "match ", "loop "]
_COMPLEXITY_RUBY = ["if ", "unless ", "while ", "case ", "rescue "]
_COMPLEXITY_BASH = ["if ", "then", "elif ", "for ", "while ", "case "]

_LANG_COMPLEXITY: dict[str, list[str]] = {
    "python": _COMPLEXITY_PYTHON, "ruby": _COMPLEXITY_RUBY,
    "bash": _COMPLEXITY_BASH, "sh": _COMPLEXITY_BASH,
    "go": _COMPLEXITY_GO, "rust": _COMPLEXITY_RUST,
    "javascript": _COMPLEXITY_C_FAMILY, "typescript": _COMPLEXITY_C_FAMILY,
    "java": _COMPLEXITY_C_FAMILY, "c": _COMPLEXITY_C_FAMILY,
    "cpp": _COMPLEXITY_C_FAMILY, "csharp": _COMPLEXITY_C_FAMILY,
    "php": _COMPLEXITY_C_FAMILY, "kotlin": _COMPLEXITY_C_FAMILY,
    "swift": _COMPLEXITY_C_FAMILY, "scala": _COMPLEXITY_C_FAMILY,
}

_DOC_EXTENSIONS = {".md", ".markdown", ".rst", ".txt"}
_DOC_BASENAMES = {"readme", "changelog", "contributing", "license", "authors", "history", "news"}
_TEST_MARKERS = {"test", "tests", "spec", "specs", "__tests__", "__test__"}
_TEST_STEM_SUFFIXES = (".test", ".spec")
_CONFIG_FILENAMES = {
    "package.json", "pyproject.toml", "setup.py", "setup.cfg", "Cargo.toml",
    "go.mod", "go.sum", "pom.xml", "build.gradle", "Makefile", "CMakeLists.txt",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml", ".gitignore",
    ".dockerignore", "tsconfig.json", ".eslintrc.json", ".eslintrc.js",
    "eslint.config.js", "prettier.config.js", ".prettierrc", "jest.config.js",
    "jest.config.ts", "vitest.config.ts", "webpack.config.js", "vite.config.ts",
    "vite.config.js", "babel.config.json", "tox.ini", "noxfile.py",
    ".mypy.ini", ".pylintrc", ".editorconfig", ".pre-commit-config.yaml",
    "renovate.json", "dependabot.yml", "codecov.yml", ".coveragerc",
}


def _get_patterns(lang: str) -> list[re.Pattern]:
    return _LANG_COMMENT_PATTERNS.get(_LANG_ALIAS.get(lang, lang), [])


def _count_comment_lines(content: str, language: str) -> int:
    patterns = _get_patterns(language)
    if not patterns:
        return 0
    count = 0
    for line in content.splitlines():
        stripped = line.strip()
        if stripped and any(p.match(stripped) for p in patterns):
            count += 1
    return count


def _estimate_complexity(content: str, language: str) -> int:
    key = _LANG_ALIAS.get(language, language)
    markers = _LANG_COMPLEXITY.get(key, [])
    score = 1
    for line in content.splitlines():
        stripped = line.strip()
        if stripped and any(m in stripped for m in markers):
            score += 1
    return score


def _has_docstring(content: str, language: str) -> bool:
    key = _LANG_ALIAS.get(language, language)
    text = content.lstrip()
    if key == "python":
        return text.startswith('"""') or text.startswith("'''")
    if key in ("javascript", "typescript", "java"):
        return text.startswith("/**")
    return False


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

def _is_doc_file(relative_path: str) -> bool:
    basename = os.path.basename(relative_path).lower()
    stem, ext = os.path.splitext(basename)
    return ext in _DOC_EXTENSIONS or stem in _DOC_BASENAMES or basename.startswith("readme")


def _is_test_file(relative_path: str) -> bool:
    parts = relative_path.replace("\\", "/").split("/")
    basename = os.path.basename(relative_path).lower()
    stem, ext = os.path.splitext(basename)
    if ext in {".test.js", ".test.ts", ".test.py", ".spec.js", ".spec.ts", ".spec.py"}:
        return True
    if any(stem.endswith(s) for s in _TEST_STEM_SUFFIXES):
        return True
    return any(p.lower() in _TEST_MARKERS for p in parts)


def _is_config_file(relative_path: str) -> bool:
    basename = os.path.basename(relative_path)
    return basename in _CONFIG_FILENAMES


def _top_level_dir(relative_path: str) -> str:
    parts = relative_path.replace("\\", "/").split("/")
    return parts[0] if len(parts) > 1 else "."


# ---------------------------------------------------------------------------
# Health scoring
# ---------------------------------------------------------------------------

def _compute_documentation_score(stats: RepoStats) -> float:
    score = 0.0
    has_readme = any("readme" in f.relative_path.lower() for f in stats.file_stats
                     if _is_doc_file(f.relative_path))
    if has_readme:
        score += 30
    if stats.total_files > 0:
        score += min(20, (stats.documentation_files / stats.total_files) * 200)
    code_files = [f for f in stats.file_stats if f.code_lines > 0]
    if code_files:
        score += min(30, (sum(1 for f in code_files if f.has_docstring) / len(code_files)) * 30)
    non_blank = stats.total_lines - stats.total_blank_lines
    if non_blank > 0:
        cr = stats.total_comment_lines / non_blank
        if cr > 0.1:
            score += 10
        if cr > 0.2:
            score += 10
    return min(100.0, score)


def _compute_code_quality_score(stats: RepoStats) -> float:
    score = 0.0
    if stats.file_stats:
        avg = sum(f.complexity_score for f in stats.file_stats) / len(stats.file_stats)
        score += 30 if avg < 5 else 20 if avg < 10 else 10 if avg < 20 else 0
    if stats.test_files > 0:
        score += min(25, (stats.test_files / max(1, stats.total_files)) * 250)
    if stats.file_stats:
        large = sum(1 for f in stats.file_stats if f.size_bytes > 100 * 1024) / len(stats.file_stats)
        score += 20 if large < 0.05 else 10 if large < 0.15 else 0
    if stats.config_files:
        score += 15
    lang_count = sum(1 for ls in stats.languages.values() if ls.code_lines > 0)
    if lang_count >= 2:
        score += 10
    return min(100.0, score)


def _compute_maturity_score(stats: RepoStats) -> float:
    score = 0.0
    score += 25 if stats.total_files >= 50 else 15 if stats.total_files >= 20 else 5 if stats.total_files >= 5 else 0
    score += 25 if stats.total_code_lines >= 5000 else 15 if stats.total_code_lines >= 1000 else 5 if stats.total_code_lines >= 200 else 0
    score += 20 if len(stats.top_level_dirs) >= 5 else 10 if len(stats.top_level_dirs) >= 3 else 0
    all_rel = {f.relative_path.split("/")[0] for f in stats.file_stats}
    if {"github", ".github", ".circleci", ".travis.yml", "Jenkinsfile"} & all_rel:
        score += 15
    if stats.config_files:
        score += 15
    return min(100.0, score)


# ---------------------------------------------------------------------------
# Main analysis API
# ---------------------------------------------------------------------------

def analyze_repository(documents: list[dict], root_path: str) -> RepoStats:
    """Analyze loaded documents and return comprehensive repository stats."""
    stats = RepoStats()
    lang_accum: dict[str, LanguageStats] = {}
    dir_accum: dict[str, DirectoryStats] = {}

    for doc in documents:
        meta = doc.get("metadata", {})
        content = doc.get("content", "")
        file_path = meta.get("file_path", "")
        relative_path = meta.get("relative_path", "")
        if not file_path:
            continue

        language = detect_lang(file_path, content)
        size_bytes = len(content.encode("utf-8")) if isinstance(content, str) else 0
        lines = content.splitlines() if isinstance(content, str) else []
        line_count = len(lines)
        blank_lines = sum(1 for l in lines if not l.strip())
        comment_lines = _count_comment_lines(content, language)
        code_lines = max(0, line_count - blank_lines - comment_lines)
        complexity = _estimate_complexity(content, language)
        docstring = _has_docstring(content, language)

        fs = FileStats(file_path, relative_path, language, size_bytes, line_count,
                        blank_lines, comment_lines, code_lines, docstring, complexity)
        stats.file_stats.append(fs)

        # Accumulate language stats
        if language not in lang_accum:
            lang_accum[language] = LanguageStats(name=language)
        ls = lang_accum[language]
        ls.file_count += 1
        ls.total_lines += line_count
        ls.code_lines += code_lines
        ls.blank_lines += blank_lines
        ls.comment_lines += comment_lines
        ls.total_bytes += size_bytes

        # Accumulate directory stats
        top_dir = _top_level_dir(relative_path)
        if top_dir not in dir_accum:
            dir_accum[top_dir] = DirectoryStats(name=top_dir)
        ds = dir_accum[top_dir]
        ds.file_count += 1
        ds.total_size_bytes += size_bytes
        ds.languages[language] = ds.languages.get(language, 0) + 1

        # Aggregate counters
        stats.total_files += 1
        stats.total_size_bytes += size_bytes
        stats.total_lines += line_count
        stats.total_code_lines += code_lines
        stats.total_blank_lines += blank_lines
        stats.total_comment_lines += comment_lines
        if _is_doc_file(relative_path):
            stats.documentation_files += 1
        if _is_config_file(relative_path):
            stats.config_files += 1
        if _is_test_file(relative_path):
            stats.test_files += 1

    # Finalize language averages
    for lang, ls in lang_accum.items():
        lang_files = [f for f in stats.file_stats if f.language == lang]
        if lang_files:
            ls.avg_complexity = sum(f.complexity_score for f in lang_files) / len(lang_files)
            ls.avg_file_size_lines = ls.total_lines / len(lang_files)

    stats.languages = dict(sorted(lang_accum.items(), key=lambda kv: kv[1].code_lines, reverse=True))
    stats.top_level_dirs = dict(sorted(dir_accum.items(), key=lambda kv: kv[1].file_count, reverse=True))
    stats.largest_files = sorted(stats.file_stats, key=lambda f: f.size_bytes, reverse=True)[:10]
    stats.most_complex_files = sorted(stats.file_stats, key=lambda f: f.complexity_score, reverse=True)[:10]
    stats.documentation_score = _compute_documentation_score(stats)
    stats.code_quality_score = _compute_code_quality_score(stats)
    stats.project_maturity_score = _compute_maturity_score(stats)
    return stats


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_bytes(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def health_bar(score: float, width: int = 20) -> str:
    filled = int(score / 100 * width)
    empty = width - filled
    color = "green" if score >= 80 else "yellow" if score >= 50 else "red"
    return f"[{color}]{'█' * filled}{'░' * empty}[/{color}] {score:.0f}/100"


def format_stats_summary(stats: RepoStats) -> str:
    lang_count = sum(1 for ls in stats.languages.values() if ls.code_lines > 0)
    return f"{stats.total_files} files, {stats.total_code_lines:,} code lines, {lang_count} language{'s' if lang_count != 1 else ''}"
