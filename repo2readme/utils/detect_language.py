import os
EXTENSION_LANGUAGE_MAP = {
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

    # Markup / Docs
    ".md": "markdown",
    ".markdown": "markdown",

    # Data files
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",

    # Web
    ".html": "html",
    ".css": "css",
}

def detect_lang(path:str):
    _,extension=os.path.splitext(path)
    return EXTENSION_LANGUAGE_MAP.get(extension,"unknown")