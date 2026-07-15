"""
Comprehensive unit tests for the enhanced language detection module.

Covers:
- Extension-based detection (backward compatibility)
- Filename-based detection
- Shebang detection (various patterns)
- Content-based detection (rule-based heuristics)
- Precedence: extension > filename > shebang > content
- Edge cases: empty files, binary files, unreadable files, etc.
"""

import os
import tempfile


from repo2readme.utils.detect_language import (
    _detect_by_extension,
    _detect_by_filename,
    _detect_by_shebang,
    _detect_by_content,
    _read_file_content,
    detect_lang,
)


# ===================================================================
# EXTENSION DETECTION
# ===================================================================


class TestExtensionDetection:
    """Tests for extension-based language detection (backward compatible)."""

    def test_python_extension(self):
        assert _detect_by_extension(".py") == "python"
        assert _detect_by_extension("main.py") == "python"
        assert _detect_by_extension("/path/to/main.py") == "python"

    def test_javascript_extension(self):
        assert _detect_by_extension(".js") == "javascript"
        assert _detect_by_extension(".jsx") == "javascript"

    def test_typescript_extension(self):
        assert _detect_by_extension(".ts") == "typescript"
        assert _detect_by_extension(".tsx") == "typescript"

    def test_cpp_extension(self):
        assert _detect_by_extension(".cpp") == "cpp"
        assert _detect_by_extension(".c") == "c"
        assert _detect_by_extension(".cs") == "csharp"

    def test_markdown_extension(self):
        assert _detect_by_extension(".md") == "markdown"
        assert _detect_by_extension(".markdown") == "markdown"

    def test_data_extensions(self):
        assert _detect_by_extension(".json") == "json"
        assert _detect_by_extension(".yaml") == "yaml"
        assert _detect_by_extension(".yml") == "yaml"

    def test_web_extensions(self):
        assert _detect_by_extension(".html") == "html"
        assert _detect_by_extension(".css") == "css"

    def test_case_insensitivity(self):
        assert _detect_by_extension(".PY") == "python"
        assert _detect_by_extension(".Js") == "javascript"
        assert _detect_by_extension(".MD") == "markdown"

    def test_dotfile_as_extension(self):
        # _detect_by_extension returns None for unknown, not "unknown"
        assert _detect_by_extension(".gitignore") is None
        assert _detect_by_extension(".env") is None
        assert _detect_by_extension(".dockerignore") == "dockerfile"

    def test_unknown_extension(self):
        assert _detect_by_extension(".xyz") is None
        assert _detect_by_extension(".unknown") is None
        assert _detect_by_extension(".txt") is None

    def test_no_extension(self):
        assert _detect_by_extension("README") is None
        assert _detect_by_extension("Makefile") is None
        assert _detect_by_extension("Dockerfile") is None


# ===================================================================
# FILENAME DETECTION
# ===================================================================


class TestFilenameDetection:
    """Tests for filename-based language detection."""

    def test_dockerfile(self):
        assert _detect_by_filename("Dockerfile") == "dockerfile"
        assert _detect_by_filename("dockerfile") == "dockerfile"
        assert _detect_by_filename("DOCKERFILE") == "dockerfile"
        assert _detect_by_filename("/path/to/Dockerfile") == "dockerfile"

    def test_makefile(self):
        assert _detect_by_filename("Makefile") == "makefile"
        assert _detect_by_filename("makefile") == "makefile"
        assert _detect_by_filename("MAKEFILE") == "makefile"

    def test_jenkinsfile(self):
        assert _detect_by_filename("Jenkinsfile") == "groovy"
        assert _detect_by_filename("jenkinsfile") == "groovy"

    def test_procfile(self):
        assert _detect_by_filename("Procfile") == "procfile"
        assert _detect_by_filename("procfile") == "procfile"

    def test_cmakelists(self):
        assert _detect_by_filename("CMakeLists.txt") == "cmake"
        assert _detect_by_filename("cmakelists.txt") == "cmake"

    def test_ruby_files(self):
        assert _detect_by_filename("Gemfile") == "ruby"
        assert _detect_by_filename("Rakefile") == "ruby"
        assert _detect_by_filename("Brewfile") == "ruby"
        assert _detect_by_filename("Vagrantfile") == "ruby"
        assert _detect_by_filename("Gemfile.lock") == "ruby"

    def test_unknown_filename(self):
        assert _detect_by_filename("random_file") is None
        assert _detect_by_filename("notes.txt") is None
        assert _detect_by_filename(".hidden") is None

    def test_filename_not_confused_with_path(self):
        # Even if the path contains a known filename, only the basename matches
        assert _detect_by_filename("/project/Dockerfile/project.cfg") is None


# ===================================================================
# SHEBANG DETECTION
# ===================================================================


class TestShebangDetection:
    """Tests for shebang-based language detection."""

    def test_shebang_python(self):
        assert _detect_by_shebang("#!/usr/bin/env python") == "python"
        assert _detect_by_shebang("#!/usr/bin/python") == "python"
        assert _detect_by_shebang("#!/usr/bin/python3") == "python"
        assert _detect_by_shebang("#!/usr/bin/env python3.10") == "python"

    def test_shebang_bash(self):
        assert _detect_by_shebang("#!/bin/bash") == "bash"
        assert _detect_by_shebang("#!/usr/bin/env bash") == "bash"
        assert _detect_by_shebang("#!/bin/sh") == "sh"

    def test_shebang_sh(self):
        assert _detect_by_shebang("#!/bin/sh") == "sh"
        assert _detect_by_shebang("#!/usr/bin/env sh") == "sh"

    def test_shebang_node(self):
        assert _detect_by_shebang("#!/usr/bin/env node") == "javascript"
        assert _detect_by_shebang("#!/usr/bin/node") == "javascript"

    def test_shebang_ruby(self):
        assert _detect_by_shebang("#!/usr/bin/env ruby") == "ruby"
        assert _detect_by_shebang("#!/usr/bin/ruby") == "ruby"

    def test_shebang_perl(self):
        assert _detect_by_shebang("#!/usr/bin/env perl") == "perl"
        assert _detect_by_shebang("#!/usr/bin/perl") == "perl"

    def test_shebang_php(self):
        assert _detect_by_shebang("#!/usr/bin/env php") == "php"
        assert _detect_by_shebang("#!/usr/bin/php") == "php"

    def test_shebang_with_leading_whitespace(self):
        assert _detect_by_shebang("  #!/usr/bin/env python") == "python"
        assert _detect_by_shebang("\t#!/bin/bash") == "bash"
        assert _detect_by_shebang("  \t  #!/usr/bin/env node") == "javascript"

    def test_shebang_second_line_not_checked(self):
        content = "print('hello')\n#!/usr/bin/env python"
        assert _detect_by_shebang(content) is None

    def test_no_shebang(self):
        assert _detect_by_shebang("print('hello')") is None
        assert _detect_by_shebang("") is None

    def test_shebang_invalid(self):
        assert _detect_by_shebang("#!/usr/bin/env invalid_program") is None
        assert _detect_by_shebang("#!just a comment") is None

    def test_shebang_with_arguments(self):
        # Shebangs with arguments should still match the interpreter
        assert _detect_by_shebang("#!/usr/bin/env python -u") == "python"
        assert _detect_by_shebang("#!/usr/bin/python -i") == "python"

    def test_malformed_shebang_missing_interpreter(self):
        assert _detect_by_shebang("#!") is None
        assert _detect_by_shebang("") is None
        assert _detect_by_shebang(None) is None  # type: ignore


# ===================================================================
# CONTENT-BASED DETECTION
# ===================================================================


class TestContentDetection:
    """Tests for content-based language detection."""

    def test_python_content(self):
        content = """
import os
import sys

def main():
    print("Hello")
"""
        assert _detect_by_content(content) == "python"

    def test_python_content_class(self):
        content = """
class MyClass:
    def __init__(self):
        pass
"""
        assert _detect_by_content(content) == "python"

    def test_python_content_if_main(self):
        content = """
if __name__ == "__main__":
    main()
import sys
"""
        assert _detect_by_content(content) == "python"

    def test_javascript_content(self):
        content = """
function greet(name) {
    return `Hello, ${name}`;
}
module.exports = greet;
"""
        assert _detect_by_content(content) == "javascript"

    def test_javascript_content_arrow_const(self):
        content = """
const greet = (name) => {
    return `Hello, ${name}`;
};
"""
        assert _detect_by_content(content) == "javascript"

    def test_javascript_content_require(self):
        content = """
const fs = require('fs');
const path = require('path');
"""
        assert _detect_by_content(content) == "javascript"

    def test_typescript_content(self):
        content = """
interface User {
    name: string;
    readonly id: number;
}
"""
        assert _detect_by_content(content) == "typescript"

    def test_yaml_content(self):
        content = """
name: test
nested:
  key: value
"""
        assert _detect_by_content(content) == "yaml"

    def test_yaml_dashes(self):
        content = """---
name: test
nested:
  key: value
"""
        assert _detect_by_content(content) == "yaml"

    def test_markdown_content(self):
        content = """
# My Project
## Installation
```bash
pip install mypackage
```
"""
        assert _detect_by_content(content) == "markdown"

    def test_dockerfile_content(self):
        content = """FROM python:3.12
RUN pip install -r requirements.txt
COPY . /app
CMD ["python", "app.py"]
"""
        assert _detect_by_content(content) == "dockerfile"

    def test_empty_content(self):
        assert _detect_by_content("") is None
        assert _detect_by_content(None) is None  # type: ignore

    def test_content_too_short_for_detection(self):
        assert _detect_by_content("hello world") is None

    def test_shell_content(self):
        content = """
#!/bin/bash
echo "Hello"
export PATH=$PATH:/usr/local/bin
"""
        assert _detect_by_content(content) == "bash"

    def test_json_content(self):
        content = '{"name": "test", "value": 1}'
        assert _detect_by_content(content) == "json"


# ===================================================================
# MAIN detect_lang() — PRECEDENCE & INTEGRATION
# ===================================================================


class TestDetectLang:
    """Tests for the main detect_lang function focusing on precedence."""

    def test_extension_takes_precedence_over_filename(self):
        """A file with .py extension should be python even if named Dockerfile.py"""
        result = detect_lang("Dockerfile.py")
        assert result == "python"

    def test_extension_takes_precedence_over_shebang(self):
        """A .js file with a python shebang should still be javascript"""
        content = "#!/usr/bin/env python\nprint('hello')"
        result = detect_lang("script.js", content=content)
        assert result == "javascript"

    def test_extension_takes_precedence_over_content(self):
        """A .py file with dockerfile content should still be python"""
        content = """FROM python:3.12
RUN pip install
COPY . /app
"""
        result = detect_lang("test.py", content=content)
        assert result == "python"

    def test_filename_detected_when_no_extension(self):
        """Dockerfile without extension should be detected as dockerfile"""
        result = detect_lang("Dockerfile")
        assert result == "dockerfile"

    def test_shebang_detected_when_no_extension_or_filename(self):
        content = "#!/usr/bin/env python\nprint('hello')"
        result = detect_lang("script", content=content)
        assert result == "python"

    def test_content_detected_when_all_else_fails(self):
        content = """
import os
import sys
class Test:
    pass
"""
        result = detect_lang("unknown_file", content=content)
        assert result == "python"

    def test_unknown_when_nothing_matches(self):
        result = detect_lang("unknown_file", content="hello world")
        assert result == "unknown"

    def test_unknown_empty_path(self):
        result = detect_lang("")
        assert result == "unknown"

    def test_backward_compatible_extension_only(self):
        """Existing call pattern: detect_lang('.py') should still work."""
        assert detect_lang(".py") == "python"
        assert detect_lang(".js") == "javascript"
        assert detect_lang(".md") == "markdown"
        assert detect_lang(".json") == "json"

    def test_backward_compatible_path_only(self):
        """Existing call pattern: detect_lang('main.py') should still work."""
        assert detect_lang("main.py") == "python"
        assert detect_lang("src/index.js") == "javascript"

    def test_filename_precedence_over_shebang(self):
        """A file named 'Dockerfile' should be dockerfile regardless of shebang"""
        content = "#!/usr/bin/env python\nprint('hello')"
        result = detect_lang("Dockerfile", content=content)
        assert result == "dockerfile"

    def test_filename_precedence_over_content(self):
        """A file named 'Makefile' should be makefile regardless of content"""
        content = "#!/usr/bin/env python\nimport os\nclass A: pass"
        result = detect_lang("Makefile", content=content)
        assert result == "makefile"

    def test_shebang_precedence_over_content(self):
        """Shebang should win over content-based detection"""
        content = "#! /usr/bin/env node\nimport os\nclass A: pass"
        result = detect_lang("script", content=content)
        assert result == "javascript"


# ===================================================================
# EDGE CASES
# ===================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_file_content(self):
        result = detect_lang("empty_file.txt", content="")
        assert result == "unknown"

    def test_empty_file_no_content(self):
        result = detect_lang("empty_file.txt")
        assert result == "unknown"

    def test_binary_content(self):
        """Binary content with null bytes should not be detected."""
        binary_content = "hello\x00world\x00\x00"
        result = detect_lang("script", content=binary_content)
        # Binary content passed directly won't have null byte check (only file reads do)
        # No shebang, no content match -> unknown
        assert result == "unknown"

    def test_binary_file_read(self):
        """Reading a binary file should return None (content unavailable)."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            f.write(b"\x00\x01\x02\x03")
            bin_path = f.name
        try:
            result = _read_file_content(bin_path)
            assert result is None  # Binary file detection
        finally:
            os.unlink(bin_path)

    def test_nonexistent_file(self):
        result = _read_file_content("/nonexistent/path/file.py")
        assert result is None

    def test_unreadable_file_permission(self):
        """Simulate permission error by reading a directory as file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _read_file_content(tmpdir)
            assert result is None  # Can't read directory as file

    def test_case_insensitive_filename(self):
        """Uppercase filenames should be matched case-insensitively."""
        assert _detect_by_filename("DOCKERFILE") == "dockerfile"
        assert _detect_by_filename("MAKEFILE") == "makefile"

    def test_filename_with_spaces(self):
        """Filenames with spaces should not cause errors."""
        result = detect_lang("my unknown file.txt")
        assert result == "unknown"

    def test_path_with_spaces(self):
        result = detect_lang("/path/to/a file.py")
        assert result == "python"

    def test_malformed_shebang_comment(self):
        """Normal comments starting with # should not trigger shebang detection."""
        content = "# this is just a comment\nprint('hello')"
        result = detect_lang("script.py", content=content)
        assert result == "python"  # extension wins

    def test_shebang_without_newline(self):
        """Shebang as the only content (no newline) should still work."""
        assert _detect_by_shebang("#!/usr/bin/env python") == "python"

    def test_unicode_content(self):
        """Unicode content should not break detection."""
        content = "#!/usr/bin/env python\n# -*- coding: utf-8 -*-\nprint('héllo')"
        result = detect_lang("unicode_script", content=content)
        assert result == "python"

    def test_large_file_reading(self):
        """_read_file_content should not read more than _MAX_CONTENT_BYTES."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w") as f:
            f.write("#!/usr/bin/env python\n")
            f.write("# " + "x" * 20000)  # Very long file
            f_path = f.name
        try:
            content = _read_file_content(f_path)
            assert content is not None
            assert len(content) <= 8192  # Should be limited
        finally:
            os.unlink(f_path)


# ===================================================================
# DETECTION ORDER / PRECEDENCE (explicit full integration tests)
# ===================================================================


class TestDetectionOrder:
    """Explicit tests verifying the full precedence chain."""

    def test_order_extension_wins(self):
        """1. Extension must have highest priority."""
        content = "#! /usr/bin/env node\nconst x = 1"
        assert detect_lang("script.py", content=content) == "python"

    def test_order_filename_second(self):
        """2. Filename detection when no extension."""
        content = "#! /usr/bin/env python\nconst x = 1"
        assert detect_lang("Dockerfile", content=content) == "dockerfile"

    def test_order_shebang_third(self):
        """3. Shebang detection when no extension or filename match."""
        content = "#! /usr/bin/env python\nconst x = 1"
        assert detect_lang("unknown_script", content=content) == "python"

    def test_order_content_fourth(self):
        """4. Content detection when nothing else matches."""
        content = "const x = 1\nmodule.exports = x"
        assert detect_lang("unknown_script", content=content) == "javascript"

    def test_order_unknown_last(self):
        """5. Unknown when all strategies fail."""
        assert detect_lang("FILE", content="nothing matches here") == "unknown"


# ===================================================================
# FILE READING INTEGRATION
# ===================================================================


class TestFileReadingIntegration:
    """Integration tests that create actual files and read them."""

    def test_detect_from_real_file(self):
        """Detect language by reading a real file."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w") as f:
            f.write("#!/usr/bin/env python\nimport os\nprint('hello')\n")
            f_path = f.name
        try:
            result = detect_lang(f_path)
            # Extension-based: .py → python
            assert result == "python"
        finally:
            os.unlink(f_path)

    def test_detect_from_real_file_no_extension(self):
        """Detect language from a real file without extension."""
        with tempfile.NamedTemporaryFile(delete=False, mode="w") as f:
            f.write("#!/usr/bin/env python\nimport os\nprint('hello')\n")
            f_path = f.name
        try:
            result = detect_lang(f_path)
            # No extension → shebang: #!/usr/bin/env python
            assert result == "python"
        finally:
            os.unlink(f_path)

    def test_detect_filename_from_real_file(self):
        """Detect language from a real file by filename."""
        tmpdir = tempfile.mkdtemp()
        try:
            f_path = os.path.join(tmpdir, "Dockerfile")
            with open(f_path, "w") as f:
                f.write("FROM python:3.12\nRUN pip install -r requirements.txt\n")
            result = detect_lang(f_path)
            assert result == "dockerfile"
        finally:
            import shutil

            shutil.rmtree(tmpdir)

    def test_detect_shebang_from_real_file(self):
        """Shebang detection from a real file without extension."""
        tmpdir = tempfile.mkdtemp()
        try:
            f_path = os.path.join(tmpdir, "run_server")
            with open(f_path, "w") as f:
                f.write("#!/usr/bin/env node\nconsole.log('hello')\n")
            result = detect_lang(f_path)
            assert result == "javascript"
        finally:
            import shutil

            shutil.rmtree(tmpdir)
