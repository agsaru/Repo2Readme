"""
Comprehensive tests for the dependency-aware context graph.

Covers:
- Python imports (absolute, relative, circular)
- JavaScript/TypeScript imports
- Entry point detection
- Leaf module detection
- Core module ranking
- Isolated file detection
- Dependency statistics
- Mixed-language repositories
- Malformed source code
- Graceful degradation
- README enrichment
- Repositories without dependencies
"""


import pytest

from repo2readme.dependency_graph import (
    DependencyGraph,
    build_dependency_graph,
    _parse_python_imports,
    _parse_js_imports,
    _resolve_python_import,
    _resolve_js_import,
    enrich_readme_with_graph,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def python_repo(tmp_path):
    """A Python repository with various import patterns."""
    repo = tmp_path / "py_repo"
    repo.mkdir()
    src = repo / "src"
    src.mkdir()
    utils = src / "utils"
    utils.mkdir()
    models = src / "models"
    models.mkdir()
    
    # Entry point
    (src / "main.py").write_text("""
import os
from src.utils import helper
from .models import user
import utils.config

def main():
    helper.run()
    user.create()
""", encoding="utf-8")
    
    # Helper module
    (utils / "__init__.py").write_text("""
from .helpers import do_work
from src.models import base

def run():
    do_work()
""", encoding="utf-8")
    
    (utils / "helpers.py").write_text("""
import json
from src.utils.config import settings

def do_work():
    pass
""", encoding="utf-8")
    
    # Config module
    (utils / "config.py").write_text("""
import os
settings = {"debug": True}
""", encoding="utf-8")
    
    # Models
    (models / "__init__.py").write_text("""
from .user import User
from src.utils.helpers import do_work
""", encoding="utf-8")
    
    (models / "user.py").write_text("""
from .base import BaseModel

class User(BaseModel):
    pass
""", encoding="utf-8")
    
    (models / "base.py").write_text("""
class BaseModel:
    pass
""", encoding="utf-8")
    
    # Isolated file
    (src / "standalone.py").write_text("""
# No imports
def isolated():
    pass
""", encoding="utf-8")
    
    return str(repo)


@pytest.fixture
def js_repo(tmp_path):
    """A JavaScript repository with import patterns."""
    repo = tmp_path / "js_repo"
    repo.mkdir()
    src = repo / "src"
    src.mkdir()
    utils = src / "utils"
    utils.mkdir()
    models = src / "models"
    models.mkdir()
    
    (src / "index.js").write_text("""
import { helper } from './utils/helper.js';
import config from './config.js';
const user = require('./models/user.js');

function main() {
    helper();
}
""", encoding="utf-8")
    
    (utils / "helper.js").write_text("""
import { settings } from '../config.js';
export function helper() {}
""", encoding="utf-8")
    
    (src / "config.js").write_text("""
export const settings = {};
""", encoding="utf-8")
    
    (src / "models" / "user.js").write_text("""
const User = require('./base');
module.exports = User;
""", encoding="utf-8")
    
    (src / "models" / "base.js").write_text("""
class Base {}
module.exports = Base;
""", encoding="utf-8")
    
    return str(repo)


@pytest.fixture
def mixed_repo(tmp_path):
    """A repository with both Python and JavaScript files."""
    repo = tmp_path / "mixed_repo"
    repo.mkdir()
    
    (repo / "main.py").write_text("import os", encoding="utf-8")
    (repo / "index.js").write_text("import _ from 'lodash';", encoding="utf-8")
    (repo / "README.md").write_text("# Test", encoding="utf-8")
    (repo / "config.json").write_text("{}", encoding="utf-8")
    
    return str(repo)


# ---------------------------------------------------------------------------
# Python import parser tests
# ---------------------------------------------------------------------------

class TestParsePythonImports:
    def test_simple_import(self):
        content = "import os\nimport sys"
        imports = _parse_python_imports(content)
        assert "os" in imports
        assert "sys" in imports

    def test_import_with_alias(self):
        content = "import numpy as np"
        imports = _parse_python_imports(content)
        assert "numpy" in imports

    def test_multiple_imports(self):
        content = "import os, sys, json"
        imports = _parse_python_imports(content)
        assert "os" in imports
        assert "sys" in imports
        assert "json" in imports

    def test_from_import(self):
        content = "from src.utils import helper"
        imports = _parse_python_imports(content)
        assert "src.utils" in imports

    def test_from_import_multiple(self):
        content = "from src.utils import helper, config"
        imports = _parse_python_imports(content)
        assert "src.utils" in imports

    def test_relative_import(self):
        content = "from . import helper"
        imports = _parse_python_imports(content)
        assert "." in imports

    def test_relative_import_from(self):
        content = "from .models import User"
        imports = _parse_python_imports(content)
        assert ".models" in imports

    def test_import_with_comment(self):
        content = "import os  # this is a comment"
        imports = _parse_python_imports(content)
        assert "os" in imports

    def test_no_imports(self):
        content = "x = 1\ny = 2"
        imports = _parse_python_imports(content)
        assert imports == []

    def test_multiline_import(self):
        content = """from src.utils import (
    helper,
    config,
    settings
)"""
        imports = _parse_python_imports(content)
        assert "src.utils" in imports


# ---------------------------------------------------------------------------
# JavaScript import parser tests
# ---------------------------------------------------------------------------

class TestParseJsImports:
    def test_import_from(self):
        content = "import { helper } from './utils.js';"
        imports = _parse_js_imports(content)
        assert "./utils.js" in imports

    def test_import_default(self):
        content = "import config from './config.js';"
        imports = _parse_js_imports(content)
        assert "./config.js" in imports

    def test_require(self):
        content = "const user = require('./user.js');"
        imports = _parse_js_imports(content)
        assert "./user.js" in imports

    def test_import_no_extension(self):
        content = "import { helper } from './utils';"
        imports = _parse_js_imports(content)
        assert "./utils" in imports

    def test_node_modules_skipped(self):
        content = "import _ from 'lodash';"
        imports = _parse_js_imports(content)
        assert "lodash" in imports  # Parser captures it, resolver skips it

    def test_dynamic_import(self):
        content = "import('./module.js')"
        imports = _parse_js_imports(content)
        assert "./module.js" in imports

    def test_no_imports(self):
        content = "const x = 1;"
        imports = _parse_js_imports(content)
        assert imports == []


# ---------------------------------------------------------------------------
# Python import resolver tests
# ---------------------------------------------------------------------------

class TestResolvePythonImport:
    def test_resolve_simple_module(self):
        files_map = {
            "/repo/src/utils.py": "/repo/src/utils.py",
        }
        result = _resolve_python_import("/repo/src/main.py", "utils", files_map)
        assert result == "/repo/src/utils.py"

    def test_resolve_package_init(self):
        files_map = {
            "/repo/src/utils/__init__.py": "/repo/src/utils/__init__.py",
        }
        result = _resolve_python_import("/repo/src/main.py", "utils", files_map)
        assert result == "/repo/src/utils/__init__.py"

    def test_resolve_submodule(self):
        files_map = {
            "/repo/src/utils/helpers.py": "/repo/src/utils/helpers.py",
        }
        result = _resolve_python_import("/repo/src/main.py", "utils.helpers", files_map)
        assert result == "/repo/src/utils/helpers.py"

    def test_relative_import_same_dir(self):
        files_map = {
            "/repo/src/helpers.py": "/repo/src/helpers.py",
        }
        result = _resolve_python_import("/repo/src/main.py", ".helpers", files_map)
        assert result == "/repo/src/helpers.py"

    def test_relative_import_parent(self):
        files_map = {
            "/repo/helpers.py": "/repo/helpers.py",
        }
        result = _resolve_python_import("/repo/src/main.py", "..helpers", files_map)
        assert result == "/repo/helpers.py"

    def test_standard_library_skipped(self):
        files_map = {}
        result = _resolve_python_import("/repo/main.py", "os", files_map)
        assert result is None

    def test_missing_module_returns_none(self):
        files_map = {}
        result = _resolve_python_import("/repo/main.py", "nonexistent", files_map)
        assert result is None


# ---------------------------------------------------------------------------
# JS import resolver tests
# ---------------------------------------------------------------------------

class TestResolveJsImport:
    def test_resolve_relative(self):
        files_map = {
            "/repo/src/utils.js": "/repo/src/utils.js",
        }
        result = _resolve_js_import("/repo/src/index.js", "./utils", files_map)
        assert result == "/repo/src/utils.js"

    def test_resolve_with_extension(self):
        files_map = {
            "/repo/src/utils.js": "/repo/src/utils.js",
        }
        result = _resolve_js_import("/repo/src/index.js", "./utils.js", files_map)
        assert result == "/repo/src/utils.js"

    def test_resolve_index_js(self):
        files_map = {
            "/repo/src/utils/index.js": "/repo/src/utils/index.js",
        }
        result = _resolve_js_import("/repo/src/index.js", "./utils", files_map)
        assert result == "/repo/src/utils/index.js"

    def test_absolute_import_skipped(self):
        files_map = {}
        result = _resolve_js_import("/repo/src/index.js", "lodash", files_map)
        assert result is None

    def test_node_modules_skipped(self):
        files_map = {}
        result = _resolve_js_import("/repo/src/index.js", "node_modules/lodash", files_map)
        assert result is None


# ---------------------------------------------------------------------------
# DependencyGraph tests
# ---------------------------------------------------------------------------

class TestDependencyGraph:
    def test_empty_graph(self):
        graph = DependencyGraph()
        assert graph.get_entry_points() == []
        assert graph.get_isolated_files() == []
        assert graph.get_leaf_modules() == []
        assert graph.get_core_modules() == []

    def test_add_edge(self):
        graph = DependencyGraph()
        graph.add_edge("/a.py", "/b.py")
        assert "/a.py" in graph.nodes
        assert "/b.py" in graph.nodes
        assert "/b.py" in graph.outgoing["/a.py"]
        assert "/a.py" in graph.incoming["/b.py"]

    def test_entry_points(self):
        graph = DependencyGraph()
        graph.add_edge("/a.py", "/b.py")
        graph.add_edge("/c.py", "/b.py")
        entry_points = graph.get_entry_points()
        assert "/a.py" in entry_points
        assert "/c.py" in entry_points
        assert "/b.py" not in entry_points

    def test_leaf_modules(self):
        graph = DependencyGraph()
        graph.add_edge("/a.py", "/b.py")
        graph.add_edge("/c.py", "/b.py")
        leaves = graph.get_leaf_modules()
        assert "/b.py" in leaves
        assert "/a.py" not in leaves
        assert "/c.py" not in leaves

    def test_isolated_files(self):
        graph = DependencyGraph()
        graph.add_edge("/a.py", "/b.py")
        isolated = graph.get_isolated_files()
        assert "/a.py" not in isolated
        assert "/b.py" not in isolated
        # Add an isolated file
        graph.nodes.add("/c.py")
        isolated = graph.get_isolated_files()
        assert "/c.py" in isolated

    def test_core_modules(self):
        graph = DependencyGraph()
        graph.add_edge("/a.py", "/c.py")
        graph.add_edge("/b.py", "/c.py")
        graph.add_edge("/d.py", "/c.py")
        core = graph.get_core_modules(top_n=2)
        # Only /c.py has incoming dependencies; entry points are excluded
        assert len(core) == 1
        assert core[0] == ("/c.py", 3)

    def test_dependency_stats(self):
        graph = DependencyGraph()
        graph.add_edge("/a.py", "/b.py")
        stats = graph.get_dependency_stats()
        assert stats["total_files"] == 2
        assert stats["total_dependencies"] == 1
        assert stats["entry_points"] == 1
        assert stats["leaf_modules"] == 1

    def test_dependency_lookup(self):
        graph = DependencyGraph()
        graph.add_edge("/a.py", "/b.py")
        graph.add_edge("/a.py", "/c.py")
        deps = graph.get_dependencies("/a.py")
        assert "/b.py" in deps
        assert "/c.py" in deps
        dependents = graph.get_dependents("/b.py")
        assert "/a.py" in dependents

    def test_outgoing_count(self):
        graph = DependencyGraph()
        graph.add_edge("/a.py", "/b.py")
        graph.add_edge("/a.py", "/c.py")
        assert graph.get_outgoing_count("/a.py") == 2
        assert graph.get_outgoing_count("/b.py") == 0

    def test_incoming_count(self):
        graph = DependencyGraph()
        graph.add_edge("/a.py", "/c.py")
        graph.add_edge("/b.py", "/c.py")
        assert graph.get_incoming_count("/c.py") == 2
        assert graph.get_incoming_count("/a.py") == 0


# ---------------------------------------------------------------------------
# build_dependency_graph integration tests
# ---------------------------------------------------------------------------

class TestBuildDependencyGraph:
    def test_python_repo(self, python_repo):
        from repo2readme.loaders.traversal.stages import discover_files, filter_file, load_file_content, extract_file_metadata, detect_file_language, create_document
        from repo2readme.loaders.traversal.stages import FileMetadata
        
        discovered, _ = discover_files(python_repo)
        filtered = []
        for path in discovered:
            ff, _ = filter_file(path, python_repo)
            if ff:
                filtered.append(ff)
        
        documents = []
        for ff in filtered:
            content, err = load_file_content(ff.absolute_path)
            if content:
                meta = extract_file_metadata(ff, content)
                lang = detect_file_language(meta, content)
                meta = FileMetadata(
                    absolute_path=meta.absolute_path,
                    relative_path=meta.relative_path,
                    file_name=meta.file_name,
                    file_type=meta.file_type,
                    file_size=meta.file_size,
                    language=lang,
                )
                doc = create_document(meta, content)
                documents.append({"content": doc.page_content, "metadata": doc.metadata})
        
        graph = build_dependency_graph(documents)
        
        assert len(graph.nodes) > 0
        # main.py imports from utils and models
        main_path = [f for f in graph.nodes if f.endswith("main.py")][0]
        assert graph.get_outgoing_count(main_path) > 0

    def test_js_repo(self, js_repo):
        from repo2readme.loaders.traversal.stages import discover_files, filter_file, load_file_content, extract_file_metadata, detect_file_language, create_document
        from repo2readme.loaders.traversal.stages import FileMetadata
        
        discovered, _ = discover_files(js_repo)
        filtered = []
        for path in discovered:
            ff, _ = filter_file(path, js_repo)
            if ff:
                filtered.append(ff)
        
        documents = []
        for ff in filtered:
            content, err = load_file_content(ff.absolute_path)
            if content:
                meta = extract_file_metadata(ff, content)
                lang = detect_file_language(meta, content)
                meta = FileMetadata(
                    absolute_path=meta.absolute_path,
                    relative_path=meta.relative_path,
                    file_name=meta.file_name,
                    file_type=meta.file_type,
                    file_size=meta.file_size,
                    language=lang,
                )
                doc = create_document(meta, content)
                documents.append({"content": doc.page_content, "metadata": doc.metadata})
        
        graph = build_dependency_graph(documents)
        assert len(graph.nodes) > 0

    def test_mixed_repo(self, mixed_repo):
        from repo2readme.loaders.traversal.stages import discover_files, filter_file, load_file_content, extract_file_metadata, detect_file_language, create_document
        from repo2readme.loaders.traversal.stages import FileMetadata
        
        discovered, _ = discover_files(mixed_repo)
        filtered = []
        for path in discovered:
            ff, _ = filter_file(path, mixed_repo)
            if ff:
                filtered.append(ff)
        
        documents = []
        for ff in filtered:
            content, err = load_file_content(ff.absolute_path)
            if content:
                meta = extract_file_metadata(ff, content)
                lang = detect_file_language(meta, content)
                meta = FileMetadata(
                    absolute_path=meta.absolute_path,
                    relative_path=meta.relative_path,
                    file_name=meta.file_name,
                    file_type=meta.file_type,
                    file_size=meta.file_size,
                    language=lang,
                )
                doc = create_document(meta, content)
                documents.append({"content": doc.page_content, "metadata": doc.metadata})
        
        graph = build_dependency_graph(documents)
        # Should not crash, may have 0 nodes for unsupported files
        assert isinstance(graph, DependencyGraph)

    def test_empty_documents(self):
        graph = build_dependency_graph([])
        assert len(graph.nodes) == 0

    def test_no_dependencies(self, tmp_path):
        """Repository with files that have no imports."""
        repo = tmp_path / "no_deps"
        repo.mkdir()
        (repo / "main.py").write_text("x = 1\n", encoding="utf-8")
        (repo / "utils.py").write_text("y = 2\n", encoding="utf-8")
        
        from repo2readme.loaders.traversal.stages import discover_files, filter_file, load_file_content, extract_file_metadata, detect_file_language, create_document
        from repo2readme.loaders.traversal.stages import FileMetadata
        
        discovered, _ = discover_files(str(repo))
        filtered = []
        for path in discovered:
            ff, _ = filter_file(path, str(repo))
            if ff:
                filtered.append(ff)
        
        documents = []
        for ff in filtered:
            content, _ = load_file_content(ff.absolute_path)
            if content:
                meta = extract_file_metadata(ff, content)
                lang = detect_file_language(meta, content)
                meta = FileMetadata(
                    absolute_path=meta.absolute_path,
                    relative_path=meta.relative_path,
                    file_name=meta.file_name,
                    file_type=meta.file_type,
                    file_size=meta.file_size,
                    language=lang,
                )
                doc = create_document(meta, content)
                documents.append({"content": doc.page_content, "metadata": doc.metadata})
        
        graph = build_dependency_graph(documents)
        # All files should be entry points (no dependencies)
        assert len(graph.get_entry_points()) == len(graph.nodes)

    def test_malformed_python(self, tmp_path):
        """Graph construction should not fail on malformed files."""
        repo = tmp_path / "malformed"
        repo.mkdir()
        (repo / "good.py").write_text("import os\n", encoding="utf-8")
        (repo / "bad.py").write_text("import!!!invalid!!!\n", encoding="utf-8")
        
        from repo2readme.loaders.traversal.stages import discover_files, filter_file, load_file_content, extract_file_metadata, detect_file_language, create_document
        from repo2readme.loaders.traversal.stages import FileMetadata
        
        discovered, _ = discover_files(str(repo))
        filtered = []
        for path in discovered:
            ff, _ = filter_file(path, str(repo))
            if ff:
                filtered.append(ff)
        
        documents = []
        for ff in filtered:
            content, _ = load_file_content(ff.absolute_path)
            if content:
                meta = extract_file_metadata(ff, content)
                lang = detect_file_language(meta, content)
                meta = FileMetadata(
                    absolute_path=meta.absolute_path,
                    relative_path=meta.relative_path,
                    file_name=meta.file_name,
                    file_type=meta.file_type,
                    file_size=meta.file_size,
                    language=lang,
                )
                doc = create_document(meta, content)
                documents.append({"content": doc.page_content, "metadata": doc.metadata})
        
        # Should not raise
        graph = build_dependency_graph(documents)
        assert isinstance(graph, DependencyGraph)

    def test_unsupported_language_skipped(self, tmp_path):
        """Files in unsupported languages should be skipped gracefully."""
        repo = tmp_path / "unsupported"
        repo.mkdir()
        (repo / "main.rs").write_text("use std::io;\n", encoding="utf-8")
        
        from repo2readme.loaders.traversal.stages import discover_files, filter_file, load_file_content, extract_file_metadata, detect_file_language, create_document
        from repo2readme.loaders.traversal.stages import FileMetadata
        
        discovered, _ = discover_files(str(repo))
        filtered = []
        for path in discovered:
            ff, _ = filter_file(path, str(repo))
            if ff:
                filtered.append(ff)
        
        documents = []
        for ff in filtered:
            content, _ = load_file_content(ff.absolute_path)
            if content:
                meta = extract_file_metadata(ff, content)
                lang = detect_file_language(meta, content)
                meta = FileMetadata(
                    absolute_path=meta.absolute_path,
                    relative_path=meta.relative_path,
                    file_name=meta.file_name,
                    file_type=meta.file_type,
                    file_size=meta.file_size,
                    language=lang,
                )
                doc = create_document(meta, content)
                documents.append({"content": doc.page_content, "metadata": doc.metadata})
        
        graph = build_dependency_graph(documents)
        # Rust files should be skipped, so graph should have no edges
        assert len(graph.nodes) == 0


# ---------------------------------------------------------------------------
# Markdown summary tests
# ---------------------------------------------------------------------------

class TestMarkdownSummary:
    def test_empty_graph(self):
        graph = DependencyGraph()
        summary = graph.to_markdown_summary()
        assert summary == ""

    def test_non_empty_graph(self):
        graph = DependencyGraph()
        graph.add_edge("/a.py", "/b.py")
        graph.add_edge("/c.py", "/b.py")
        summary = graph.to_markdown_summary()
        assert "Dependency Overview" in summary
        assert "Core Modules" in summary
        assert "Entry Points" in summary
        assert "Dependency Statistics" in summary

    def test_statistics_correctness(self):
        graph = DependencyGraph()
        graph.add_edge("/a.py", "/b.py")
        graph.add_edge("/c.py", "/b.py")
        stats = graph.get_dependency_stats()
        assert stats["total_files"] == 3
        assert stats["total_dependencies"] == 2
        assert stats["entry_points"] == 2  # a.py and c.py
        assert stats["leaf_modules"] == 1  # b.py


# ---------------------------------------------------------------------------
# README enrichment tests
# ---------------------------------------------------------------------------

class TestEnrichReadme:
    def test_no_overview_returns_original(self):
        graph = DependencyGraph()
        readme = "# My Project\n\nSome content."
        result = enrich_readme_with_graph(readme, graph)
        assert result == readme

    def test_enriches_with_overview(self):
        graph = DependencyGraph()
        graph.add_edge("/a.py", "/b.py")
        readme = "# My Project\n\nSome content."
        result = enrich_readme_with_graph(readme, graph)
        assert "Dependency Overview" in result
        assert result.startswith("# My Project")

    def test_preserves_existing_formatting(self):
        graph = DependencyGraph()
        graph.add_edge("/a.py", "/b.py")
        readme = "# Title\n\n## Section\n\nContent."
        result = enrich_readme_with_graph(readme, graph)
        assert "# Title" in result
        assert "## Section" in result

    def test_enrichment_idempotent(self):
        """Enriching twice should not duplicate the dependency overview."""
        graph = DependencyGraph()
        graph.add_edge("/a.py", "/b.py")
        readme = "# My Project\n\nSome content."
        result1 = enrich_readme_with_graph(readme, graph)
        result2 = enrich_readme_with_graph(result1, graph)
        assert result2.count("## Dependency Overview") == 1
        assert result2.count("### Core Modules") == 1
