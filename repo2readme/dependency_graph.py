"""
Lightweight dependency-aware context graph for README generation.

Builds an internal graph of file dependencies using lightweight regex parsing
for Python and JavaScript/TypeScript. Supports analysis of entry points,
core modules, isolated files, and leaf modules.

No external dependencies. Gracefully handles syntax errors, missing modules,
unsupported languages, and malformed files.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DependencyGraph:
    """
    Internal dependency graph representing relationships between files.

    Attributes:
        nodes: Set of file paths (absolute, normalized)
        outgoing: Mapping from file -> set of files it imports
        incoming: Mapping from file -> set of files that import it
        errors: List of parsing errors encountered (non-fatal)
    """

    nodes: set[str] = field(default_factory=set)
    outgoing: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    incoming: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    errors: list[str] = field(default_factory=list)

    def add_edge(self, source: str, target: str) -> None:
        """Add a dependency edge from source to target."""
        self.nodes.add(source)
        self.nodes.add(target)
        self.outgoing[source].add(target)
        self.incoming[target].add(source)

    def get_outgoing_count(self, file_path: str) -> int:
        """Return the number of files this file imports."""
        return len(self.outgoing.get(file_path, set()))

    def get_incoming_count(self, file_path: str) -> int:
        """Return the number of files that import this file."""
        return len(self.incoming.get(file_path, set()))

    def get_dependencies(self, file_path: str) -> set[str]:
        """Return files that this file depends on."""
        return self.outgoing.get(file_path, set()).copy()

    def get_dependents(self, file_path: str) -> set[str]:
        """Return files that depend on this file."""
        return self.incoming.get(file_path, set()).copy()

    def get_entry_points(self) -> list[str]:
        """
        Return files with no incoming dependencies (entry points).

        These are files that nothing else imports.
        """
        return sorted([f for f in self.nodes if self.get_incoming_count(f) == 0])

    def get_isolated_files(self) -> list[str]:
        """
        Return files with no dependencies at all (neither incoming nor outgoing).
        """
        return sorted([
            f for f in self.nodes
            if self.get_incoming_count(f) == 0 and self.get_outgoing_count(f) == 0
        ])

    def get_leaf_modules(self) -> list[str]:
        """
        Return files that are imported but don't import anything else.
        These are leaf nodes in the dependency graph.
        """
        return sorted([
            f for f in self.nodes
            if self.get_incoming_count(f) > 0 and self.get_outgoing_count(f) == 0
        ])

    def get_core_modules(self, top_n: int = 10) -> list[tuple[str, int]]:
        """
        Return top-N most-connected files by incoming dependency count.

        These are files that many other files depend on.
        Returns list of (file_path, incoming_count) sorted by count descending.
        """
        ranked = sorted(
            [(f, self.get_incoming_count(f)) for f in self.nodes],
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_n]

    def get_dependency_stats(self) -> dict:
        """Return summary statistics about the dependency graph."""
        total_nodes = len(self.nodes)
        total_edges = sum(len(v) for v in self.outgoing.values())

        if total_nodes == 0:
            return {
                "total_files": 0,
                "total_dependencies": 0,
                "entry_points": 0,
                "isolated_files": 0,
                "leaf_modules": 0,
                "avg_dependencies_per_file": 0.0,
                "max_incoming_count": 0,
            }

        incoming_counts = [self.get_incoming_count(f) for f in self.nodes]
        return {
            "total_files": total_nodes,
            "total_dependencies": total_edges,
            "entry_points": len(self.get_entry_points()),
            "isolated_files": len(self.get_isolated_files()),
            "leaf_modules": len(self.get_leaf_modules()),
            "avg_dependencies_per_file": total_edges / total_nodes if total_nodes > 0 else 0.0,
            "max_incoming_count": max(incoming_counts) if incoming_counts else 0,
        }

    def to_markdown_summary(self) -> str:
        """
        Generate a markdown summary of the dependency graph for README inclusion.

        Returns markdown string with sections for Core Modules, Entry Points,
        and Dependency Statistics.
        """
        stats = self.get_dependency_stats()

        if stats["total_files"] == 0:
            return ""

        lines = ["## Dependency Overview\n"]

        # Core modules
        core = self.get_core_modules(top_n=5)
        if core:
            lines.append("### Core Modules\n")
            lines.append("Files with the most dependencies:\n")
            for file_path, count in core:
                # Extract just the filename and relative path
                display = file_path.split("/")[-1] if "/" in file_path else file_path
                lines.append(f"- `{display}` ({count} incoming dependencies)\n")
            lines.append("\n")

        # Entry points
        entry_points = self.get_entry_points()
        if entry_points:
            lines.append("### Entry Points\n")
            lines.append("Files with no incoming dependencies:\n")
            for ep in entry_points[:10]:  # Limit to top 10
                display = ep.split("/")[-1] if "/" in ep else ep
                lines.append(f"- `{display}`\n")
            if len(entry_points) > 10:
                lines.append(f"- ... and {len(entry_points) - 10} more\n")
            lines.append("\n")

        # Statistics
        lines.append("### Dependency Statistics\n")
        lines.append(f"- **Total files analyzed**: {stats['total_files']}\n")
        lines.append(f"- **Total dependencies**: {stats['total_dependencies']}\n")
        lines.append(f"- **Entry points**: {stats['entry_points']}\n")
        lines.append(f"- **Isolated files**: {stats['isolated_files']}\n")
        lines.append(f"- **Leaf modules**: {stats['leaf_modules']}\n")
        lines.append(f"- **Avg dependencies per file**: {stats['avg_dependencies_per_file']:.1f}\n")

        return "".join(lines)


# ---------------------------------------------------------------------------
# Lightweight import parsers
# ---------------------------------------------------------------------------

def _resolve_python_import(
    source_file: str,
    import_path: str,
    files_map: dict[str, str],
) -> Optional[str]:
    """
    Attempt to resolve a Python import to an actual file path.

    Args:
        source_file: Absolute path of the file containing the import
        import_path: The module path being imported (e.g., "os", "utils.helpers")
        files_map: Mapping from normalized file paths to absolute paths

    Returns:
        Resolved absolute file path, or None if not found
    """
    # Standard library / third-party: skip
    if not import_path or import_path.startswith("_"):
        return None

    # Handle relative imports
    if import_path.startswith("."):
        source_dir = source_file.rsplit("/", 1)[0] if "/" in source_file else ""
        # Count leading dots
        dots = 0
        for char in import_path:
            if char == ".":
                dots += 1
            else:
                break
        module_path = import_path[dots:]

        # Navigate up directories by moving to parent (dots - 1) times
        base_dir = source_dir
        for _ in range(max(0, dots - 1)):
            base_dir = base_dir.rsplit("/", 1)[0] if "/" in base_dir else ""
    else:
        base_dir = source_file.rsplit("/", 1)[0] if "/" in source_file else ""
        module_path = import_path

    if not module_path:
        return None

    # Try as package __init__.py
    candidate = f"{base_dir}/{module_path.replace('.', '/')}/__init__.py"
    if candidate in files_map:
        return candidate

    # Try as module file, including sibling module names like helpers.py
    candidate = f"{base_dir}/{module_path.replace('.', '/')}.py"
    if candidate in files_map:
        return candidate

    return None


def _resolve_js_import(
    source_file: str,
    import_path: str,
    files_map: dict[str, str],
) -> Optional[str]:
    """
    Attempt to resolve a JavaScript/TypeScript import to an actual file path.

    Args:
        source_file: Absolute path of the file containing the import
        import_path: The module path being imported (e.g., "./utils", "lodash")
        files_map: Mapping from normalized file paths to absolute paths

    Returns:
        Resolved absolute file path, or None if not found
    """
    # Skip node_modules and absolute imports
    if not import_path or import_path.startswith("node_modules"):
        return None

    # Only resolve relative imports
    if not import_path.startswith("."):
        return None

    source_dir = source_file.rsplit("/", 1)[0] if "/" in source_file else ""
    base_dir = source_dir

    # Remove query strings, hashes, and leading ./ if present
    clean_path = import_path.split("?")[0].split("#")[0]
    if clean_path.startswith("./"):
        clean_path = clean_path[2:]

    # Try direct path
    candidate = f"{base_dir}/{clean_path}"
    if candidate in files_map:
        return candidate

    # Try with .js extension
    candidate = f"{base_dir}/{clean_path}.js"
    if candidate in files_map:
        return candidate

    # Try with .ts extension
    candidate = f"{base_dir}/{clean_path}.ts"
    if candidate in files_map:
        return candidate

    # Try as directory index
    candidate = f"{base_dir}/{clean_path}/index.js"
    if candidate in files_map:
        return candidate

    candidate = f"{base_dir}/{clean_path}/index.ts"
    if candidate in files_map:
        return candidate

    return None


def _parse_python_imports(content: str) -> list[str]:
    """
    Extract Python import paths from file content.

    Returns list of imported module paths.
    """
    imports = []

    # Match: import module [as alias] [, module ...]
    for match in re.finditer(r'^\s*import\s+([^\n#]+)', content, re.MULTILINE):
        line = match.group(1).strip()
        # Remove inline comments
        line = re.sub(r'#.*$', '', line).strip()
        # Split on commas, handle 'as' aliases
        parts = [p.strip().split()[0] for p in line.split(',') if p.strip()]
        imports.extend(parts)

    # Match: from module import name [as alias] [, name ...]
    for match in re.finditer(r'^\s*from\s+([^\s]+)\s+import\s+([^\n#]+)', content, re.MULTILINE):
        module_path = match.group(1).strip()
        imports.append(module_path)

    return imports


def _parse_js_imports(content: str) -> list[str]:
    """
    Extract JavaScript/TypeScript import paths from file content.

    Returns list of imported module paths.
    """
    imports = []

    # Match: import X from 'module'
    for match in re.finditer(r'import\s+.*?from\s+["\']([^"\']+)["\']', content):
        imports.append(match.group(1).strip())

    # Match: import('module') for dynamic imports
    for match in re.finditer(r'import\s*\(\s*["\']([^"\']+)["\']\s*\)', content):
        path = match.group(1).strip()
        if path not in imports:
            imports.append(path)

    # Match: require('module')
    for match in re.finditer(r'require\s*\(\s*["\']([^"\']+)["\']\s*\)', content):
        path = match.group(1).strip()
        if path not in imports:
            imports.append(path)

    return imports


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_dependency_graph(documents: list[dict]) -> DependencyGraph:
    """
    Build a dependency graph from a list of documents.

    Each document is a dict with 'content' and 'metadata' keys.
    Metadata must contain 'file_path' (absolute path).

    Args:
        documents: List of document dicts from the traversal pipeline

    Returns:
        DependencyGraph instance with all detected relationships
    """
    graph = DependencyGraph()

    # Build file path normalization map
    # Key: normalized path (forward slashes), Value: original file_path from metadata
    files_map: dict[str, str] = {}
    for doc in documents:
        file_path = doc.get("metadata", {}).get("file_path", "")
        if file_path:
            normalized = file_path.replace("\\", "/")
            files_map[normalized] = file_path

    # Process each file
    for doc in documents:
        metadata = doc.get("metadata", {})
        content = doc.get("content", "")
        source_file = metadata.get("file_path", "")

        if not source_file or not content:
            continue

        # Detect language from file type or content
        file_type = metadata.get("file_type", "")
        language = _detect_language_from_ext(file_type)

        if language == "python":
            imports = _parse_python_imports(content)
            resolver = _resolve_python_import
        elif language in ("javascript", "typescript"):
            imports = _parse_js_imports(content)
            resolver = _resolve_js_import
        else:
            # Unsupported language: skip
            continue

        # Resolve imports to actual files
        normalized_source = source_file.replace("\\", "/")
        for import_path in imports:
            try:
                resolved = resolver(normalized_source, import_path, files_map)
                if resolved and resolved != source_file:
                    graph.add_edge(source_file, resolved)
            except Exception:
                # Never fail on individual import resolution
                pass

    return graph


def _detect_language_from_ext(file_type: str) -> str:
    """Detect language from file extension."""
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".mjs": "javascript",
        ".cjs": "javascript",
    }
    return ext_map.get(file_type.lower(), "")


# ---------------------------------------------------------------------------
# README enrichment
# ---------------------------------------------------------------------------

def enrich_readme_with_graph(readme: str, graph: DependencyGraph) -> str:
    """
    Enhance an existing README with dependency graph information.

    Appends a "Dependency Overview" section if the graph has meaningful data.

    Args:
        readme: Original README markdown string
        graph: DependencyGraph instance

    Returns:
        Enhanced README markdown string
    """
    summary = graph.to_markdown_summary()

    if not summary:
        return readme

    # Append dependency overview at the end
    return readme.rstrip() + "\n\n" + summary