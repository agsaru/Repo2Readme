"""Comprehensive unit tests for the enhanced language detection module."""
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


class TestExtensionDetection:
    def test_python_extension(self):
        assert _detect_by_extension(".py") == "python"
        assert _detect_by_extension("main.py") == "python"

    def test_javascript_extension(self):
        assert _detect_by_extension(".js") == "javascript"
        assert _detect_by_extension(".jsx") == "javascript"

    def test_typescript_extension(self):
        assert _detect_by_extension(".ts") == "typescript"
        assert _detect_by_extension(".tsx") == "typescript"

    def test_markdown_extension(self):
        assert _detect_by_extension(".md") == "markdown"

    def test_data_extensions(self):
        assert _detect_by_extension(".json") == "json"
        assert _detect_by_extension(".yaml") == "yaml"

    def test_case_insensitivity(self):
        assert _detect_by_extension(".PY") == "python"
        assert _detect_by_extension(".MD") == "markdown"

    def test_dotfile_as_extension(self):
        assert _detect_by_extension(".gitignore") is None
        assert _detect_by_extension(".dockerignore") == "dockerfile"

    def test_unknown_extension(self):
        assert _detect_by_extension(".xyz") is None
        assert _detect_by_extension("README") is None


class TestFilenameDetection:
    def test_dockerfile(self):
        assert _detect_by_filename("Dockerfile") == "dockerfile"
        assert _detect_by_filename("DOCKERFILE") == "dockerfile"

    def test_makefile(self):
        assert _detect_by_filename("Makefile") == "makefile"

    def test_jenkinsfile(self):
        assert _detect_by_filename("Jenkinsfile") == "groovy"

    def test_procfile(self):
        assert _detect_by_filename("Procfile") == "procfile"

    def test_cmakelists(self):
        assert _detect_by_filename("CMakeLists.txt") == "cmake"

    def test_ruby_files(self):
        assert _detect_by_filename("Gemfile") == "ruby"
        assert _detect_by_filename("Rakefile") == "ruby"
        assert _detect_by_filename("Brewfile") == "ruby"
        assert _detect_by_filename("Vagrantfile") == "ruby"
        assert _detect_by_filename("Gemfile.lock") == "ruby"

    def test_unknown_filename(self):
        assert _detect_by_filename("random_file") is None


class TestShebangDetection:
    def test_shebang_python(self):
        assert _detect_by_shebang("#!/usr/bin/env python") == "python"
        assert _detect_by_shebang("#!/usr/bin/python") == "python"
        assert _detect_by_shebang("#!/usr/bin/python3") == "python"

    def test_shebang_bash(self):
        assert _detect_by_shebang("#!/bin/bash") == "bash"
        assert _detect_by_shebang("#!/usr/bin/env bash") == "bash"
        assert _detect_by_shebang("#!/bin/sh") == "sh"

    def test_shebang_node(self):
        assert _detect_by_shebang("#!/usr/bin/env node") == "javascript"
        assert _detect_by_shebang("#!/usr/bin/node") == "javascript"

    def test_shebang_ruby_perl_php(self):
        assert _detect_by_shebang("#!/usr/bin/env ruby") == "ruby"
        assert _detect_by_shebang("#!/usr/bin/perl") == "perl"
        assert _detect_by_shebang("#!/usr/bin/env php") == "php"

    def test_shebang_with_leading_whitespace(self):
        assert _detect_by_shebang("  #!/usr/bin/env python") == "python"
        assert _detect_by_shebang("\t#!/bin/bash") == "bash"

    def test_shebang_second_line_not_checked(self):
        assert _detect_by_shebang("print('hello')\n#!/usr/bin/env python") is None

    def test_no_shebang(self):
        assert _detect_by_shebang("print('hello')") is None
        assert _detect_by_shebang("") is None

    def test_shebang_with_arguments(self):
        assert _detect_by_shebang("#!/usr/bin/env python -u") == "python"
        assert _detect_by_shebang("#!/usr/bin/python -i") == "python"


class TestContentDetection:
    def test_python_content(self):
        content = """
import os
import sys
class Test:
    pass
"""
        assert _detect_by_content(content) == "python"

    def test_python_if_main(self):
        content = """
if __name__ == "__main__":
    main()
import os
"""
        assert _detect_by_content(content) == "python"

    def test_python_self(self):
        content = """
class Foo:
    def __init__(self):
        self.value = 0
"""
        assert _detect_by_content(content) == "python"

    def test_javascript_content(self):
        content = """
function greet(name) { return `Hello, ${name}`; }
module.exports = greet;
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

    def test_shell_content(self):
        content = """#!/bin/bash
echo "Hello"
export PATH=$PATH:/usr/local/bin
"""
        assert _detect_by_content(content) == "bash"

    def test_json_content(self):
        assert _detect_by_content('{"name": "test"}') == "json"

    def test_empty_content(self):
        assert _detect_by_content("") is None
        assert _detect_by_content(None) is None  # type: ignore

    def test_ruby_content(self):
        content = """require 'json'
puts 'hello'
class Foo
end
"""
        assert _detect_by_content(content) == "ruby"


class TestDetectLang:
    def test_extension_precedence(self):
        content = "#!/usr/bin/env node\nconst x = 1"
        assert detect_lang("script.py", content=content) == "python"

    def test_filename_detection(self):
        assert detect_lang("Dockerfile") == "dockerfile"
        assert detect_lang("Makefile") == "makefile"
        assert detect_lang("Jenkinsfile") == "groovy"

    def test_shebang_detection(self):
        content = "#!/usr/bin/env python\nprint('hello')"
        assert detect_lang("script", content=content) == "python"

    def test_content_detection_fallback(self):
        content = """
import os
import sys
class Test:
    pass
"""
        assert detect_lang("unknown_file", content=content) == "python"

    def test_unknown_when_nothing_matches(self):
        assert detect_lang("unknown_file", content="hello world") == "unknown"

    def test_backward_compatible(self):
        assert detect_lang(".py") == "python"
        assert detect_lang("main.py") == "python"
        assert detect_lang(".js") == "javascript"
        assert detect_lang(".json") == "json"
        assert detect_lang(".md") == "markdown"

    def test_shebang_precedence_over_content(self):
        content = "#! /usr/bin/env node\nimport os\nclass A: pass"
        assert detect_lang("script", content=content) == "javascript"

    def test_filename_precedence_over_shebang(self):
        content = "#!/usr/bin/env python\nprint('hello')"
        assert detect_lang("Dockerfile", content=content) == "dockerfile"


class TestEdgeCases:
    def test_empty_file(self):
        assert detect_lang("empty.txt", content="") == "unknown"

    def test_binary_content(self):
        assert detect_lang("script", content="hello\x00world") == "unknown"

    def test_binary_file_read(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            f.write(b"\x00\x01\x02\x03")
            bin_path = f.name
        try:
            assert _read_file_content(bin_path) is None
        finally:
            os.unlink(bin_path)

    def test_nonexistent_file(self):
        assert _read_file_content("/nonexistent/path/file.py") is None

    def test_case_insensitive_filename(self):
        assert _detect_by_filename("DOCKERFILE") == "dockerfile"
        assert _detect_by_filename("MAKEFILE") == "makefile"

    def test_unicode_content(self):
        content = "#!/usr/bin/env python\nprint('héllo')"
        assert detect_lang("script", content=content) == "python"

    def test_large_file_reading(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w") as f:
            f.write("#!/usr/bin/env python\n")
            f.write("# " + "x" * 20000)
            f_path = f.name
        try:
            content = _read_file_content(f_path)
            assert content is not None
            assert len(content) <= 8192
        finally:
            os.unlink(f_path)


class TestDetectionOrder:
    def test_extension_wins(self):
        content = "#! /usr/bin/env node\nconst x = 1"
        assert detect_lang("script.py", content=content) == "python"

    def test_filename_second(self):
        content = "#! /usr/bin/env python\nconst x = 1"
        assert detect_lang("Dockerfile", content=content) == "dockerfile"

    def test_shebang_third(self):
        content = "#!/usr/bin/env python\nconst x = 1"
        assert detect_lang("unknown_script", content=content) == "python"

    def test_content_fourth(self):
        content = "const x = 1\nmodule.exports = x"
        assert detect_lang("unknown_script", content=content) == "javascript"

    def test_unknown_last(self):
        assert detect_lang("FILE", content="nothing matches here") == "unknown"


class TestFileReadingIntegration:
    def test_detect_from_real_file(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w") as f:
            f.write("#!/usr/bin/env python\nimport os\nprint('hello')\n")
            f_path = f.name
        try:
            assert detect_lang(f_path) == "python"
        finally:
            os.unlink(f_path)

    def test_detect_from_real_file_no_extension(self):
        with tempfile.NamedTemporaryFile(delete=False, mode="w") as f:
            f.write("#!/usr/bin/env python\nimport os\nprint('hello')\n")
            f_path = f.name
        try:
            assert detect_lang(f_path) == "python"
        finally:
            os.unlink(f_path)

    def test_detect_shebang_from_real_file(self):
        tmpdir = tempfile.mkdtemp()
        try:
            f_path = os.path.join(tmpdir, "run_server")
            with open(f_path, "w") as f:
                f.write("#!/usr/bin/env node\nconsole.log('hello')\n")
            assert detect_lang(f_path) == "javascript"
        finally:
            import shutil
            shutil.rmtree(tmpdir)