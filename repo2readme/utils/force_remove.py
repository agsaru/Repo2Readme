import os, stat

def force_remove(func, path, excinfo):
    """
    Works with GitLoader because GitLoader still calls the old 3-argument onerror callback.
    """
    try:
        os.chmod(path, stat.S_IWRITE)   # remove read-only flag
    except Exception:
        pass
    
    try:
        func(path)   # retry the delete (func = os.remove or os.rmdir)
    except Exception:
        pass

