IGNORE_DIRS = {
    # JS/TS
    "node_modules", ".next", ".npm", ".yarn", ".pnpm", "bower_components",

    # Python
    "__pycache__", ".venv", "venv", "env", ".mypy_cache", ".pytest_cache",

    # Java / Kotlin / JVM
    "build", "target", ".gradle", ".mvn",

    # C# / .NET
    "bin", "obj", "packages", ".nuget",

    # Ruby
    ".bundle", "vendor/bundle",

    # Go / Rust
    "pkg", "target", ".cargo",

    # PHP
    "vendor",

    # General
    ".git", ".idea", ".vscode", ".cache", "coverage", "logs", "dist", "out","public"
}

IGNORE_FILES = [
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
]
IGNORE_EXTENSIONS = {
    # binaries
    ".exe", ".dll", ".bin", ".class", ".o", ".so", ".dylib",
    # archives
    ".zip", ".tar", ".gz", ".jar", ".war", ".ear",
    # images
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    # misc
    ".log", ".lock", ".db", ".sqlite", ".pdf", ".csv",".env",".gitignore"
}

def github_file_filter(path:str)->bool:
    """ This function returns false if the files folder or
      files extension matches the IGNORE_EXTENSIONS or IGNORE_DIRS.Or returns true
    """
    uni_path = path.replace("\\", "/")

    filename = uni_path.split("/")[-1]
    if filename in IGNORE_FILES:
        return False

    for ex in IGNORE_EXTENSIONS:
        if uni_path.endswith(ex):
            return False
    for d in IGNORE_DIRS:
        if f"/{d}/" in uni_path or uni_path.startswith(d + "/"):
            return False
    return True