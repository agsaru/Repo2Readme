import os, stat

def force_remove(func, path, excinfo):
    """Forces read-only files to write and then removes the file"""
 
    try:
        os.chmod(path, stat.S_IWRITE)  
    except Exception:
        pass
    
    try:
        func(path)   
    except Exception:
        pass

