import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RESET = "\033[0m"

USE_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    if not USE_COLOR:
        return text
    return f"{code}{text}{RESET}"


def info(msg: str) -> None:
    print(f"{_c(CYAN, '·')} {msg}")


def ok(msg: str) -> None:
    print(f"{_c(GREEN, '✓')} {msg}")


def warn(msg: str) -> None:
    print(f"{_c(YELLOW, '⚠')} {msg}")


def err(msg: str) -> None:
    print(f"{_c(RED, '✗')} {msg}", file=sys.stderr)


def headline(msg: str) -> None:
    print(f"\n{_c(BOLD, msg)}")


def human_size(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unit == "GiB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n} B"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd, check=True, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True, check=check, cwd=cwd
    )


def run_ok(cmd, cwd=None) -> bool:
    return subprocess.run(
        cmd, capture_output=True, text=True, cwd=cwd
    ).returncode == 0


def run_out(cmd, cwd=None) -> str:
    proc = subprocess.run(
        cmd, capture_output=True, text=True, cwd=cwd
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def require_bin(name: str) -> bool:
    return shutil.which(name) is not None


SECRET_PATTERNS = re.compile(
    r"(?i)^\s*(export\s+)?[A-Z0-9_]*(TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|APIKEY|PRIVKEY|PRIVATE)[A-Z0-9_]*=",
    re.MULTILINE,
)

PRIVATE_KEY_MARKER = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")


def scan_secrets(text: str) -> bool:
    return bool(SECRET_PATTERNS.search(text) or PRIVATE_KEY_MARKER.search(text))


def copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def backup_file(target: Path, backup_root: Path) -> Path | None:
    if not target.exists():
        return None
    try:
        rel = target.resolve().relative_to(Path.home())
        dest = backup_root / rel
    except ValueError:
        dest = backup_root / "absolute" / target.relative_to(target.anchor)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if target.is_dir():
        shutil.copytree(target, dest, dirs_exist_ok=True, symlinks=True)
    else:
        shutil.copy2(target, dest)
    return dest


def copy_tree(src: Path, dest: Path, skip_names=()) -> None:
    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns(*skip_names) if skip_names else None,
        dirs_exist_ok=True,
    )


def safe_relpath(name: str) -> bool:
    p = Path(name)
    return not p.is_absolute() and ".." not in p.parts
