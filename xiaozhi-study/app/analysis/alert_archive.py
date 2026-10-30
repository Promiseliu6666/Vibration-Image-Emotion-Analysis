"""Retain event evidence independently of ordinary frame expiration."""
from pathlib import Path
import shutil

def protect(path, root):
    if not path:
        return ""
    source=Path(path)
    base=Path(root).resolve()
    resolved=source.resolve()
    if not resolved.is_relative_to(base):
        raise ValueError("Frame path outside capture directory")
    archive=base/'alerts'
    if resolved.is_relative_to(archive):
        return str(source)
    if not source.is_file():
        return ""
    target=Path(root)/'alerts'/source.parent.name/source.name
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():
        shutil.copy2(source,target)
    return str(target)
