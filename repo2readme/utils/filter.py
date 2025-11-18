import os

IGNORE_DIRS = {
    "node_modules", ".next", ".npm", ".yarn", ".pnpm", "bower_components",
    "__pycache__", ".venv", "venv", "env", ".mypy_cache", ".pytest_cache",
    "build", "target", ".gradle", ".mvn",
    "bin", "obj", "packages", ".nuget",
    ".bundle", "vendor", "vendor/bundle",
    "pkg", ".cargo",
    ".git", ".idea", ".vscode", ".cache", "coverage", "logs", "dist", "out", "public"
}

IGNORE_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    ".env",
    ".env.example",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.test",
}

IGNORE_EXTENSIONS = {
    ".exe", ".dll", ".bin", ".class", ".o", ".so", ".dylib",
    ".zip", ".tar", ".gz", ".jar", ".war", ".ear",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".log", ".lock", ".db", ".sqlite", ".pdf",
    ".csv" ,".json"# if you want to ignore JSON too
}


def github_file_filter(path: str) -> bool:
    uni = path.replace("\\", "/")
    lower = uni.lower().strip()
    base = os.path.basename(lower).strip()

    # Ignore specific file names
    if base in IGNORE_FILES:
        return False
    # Ignore directories
    for d in IGNORE_DIRS:
      if f"/{d}/" in lower or lower.endswith(f"/{d}"):
        return False


    # Ignore extensions
    _, ext = os.path.splitext(base)
    if ext in IGNORE_EXTENSIONS:
        return False

    return True  # load everything else
