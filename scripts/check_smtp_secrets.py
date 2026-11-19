"""Check tracked configuration and Python files without printing secret values."""

import ast
import re
import subprocess
import warnings
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENT = re.compile(
    r"^[ \t]*(?:export[ \t]+)?MAIL_PASSWORD[ \t]*=[ \t]*([^\r\n]*)$",
    re.MULTILINE,
)


def main():
    paths = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=ROOT
    ).decode("utf-8").split("\0")
    errors = set()
    for name in filter(None, paths):
        path = ROOT / name
        if not path.is_file():
            continue
        is_template = path.name.endswith(".example")
        if name.startswith("ruoyi-fastapi-backend/.env") and not is_template:
            errors.add(f"{name}: private backend environment file is tracked")
        if not (path.name.startswith(".env") or path.suffix in {".py", ".yml", ".yaml", ".toml", ".ini", ".cfg"}):
            continue
        content = path.read_text(encoding="utf-8-sig", errors="replace")
        for match in ASSIGNMENT.finditer(content) if path.suffix != ".py" else ():
            value = match.group(1).strip().strip("\"'")
            if value and not value.startswith("#"):
                errors.add(f"{name}: nonempty literal MAIL_PASSWORD assignment")
        if path.suffix == ".py":
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", SyntaxWarning)
                    tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.keyword) and node.arg == "MAIL_PASSWORD":
                    if isinstance(node.value, ast.Constant) and node.value.value:
                        errors.add(f"{name}:{node.lineno}: hardcoded SMTP password")
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    if any(isinstance(target, ast.Name) and target.id == "MAIL_PASSWORD" for target in targets):
                        if isinstance(node.value, ast.Constant) and node.value.value:
                            errors.add(f"{name}:{node.lineno}: hardcoded SMTP password")
    if errors:
        print("SMTP secret check failed (values omitted):")
        print("\n".join(sorted(errors)))
        return 1
    print("SMTP secret check passed: no tracked backend private env files or literal SMTP passwords.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
