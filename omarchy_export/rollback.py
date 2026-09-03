import json
import os
import shutil
import time
from pathlib import Path

from . import util
from .categories import HOME
from .ui import confirm

EXPORT_STATE = HOME / ".local" / "state" / "omarchy-export"
BACKUPS = EXPORT_STATE / "backups"
LOG_NAME = "import-log.json"


def list_backup_dirs() -> list[Path]:
    if not BACKUPS.exists():
        return []
    return sorted(
        p
        for p in BACKUPS.iterdir()
        if p.is_dir() and "-pre-rollback" not in p.name
    )


def load_log(target: Path) -> dict | None:
    log_file = target / LOG_NAME
    if not log_file.exists():
        return None
    try:
        return json.loads(log_file.read_text())
    except json.JSONDecodeError:
        return None


def backup_files(target: Path) -> list[Path]:
    return [p for p in sorted(target.rglob("*")) if p.is_file() and p.name != LOG_NAME]


def _restore(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest, symlinks=True)
    else:
        shutil.copy2(src, dest)


def _snapshot(dest: Path, snapshot_dir: Path) -> None:
    rel = dest.relative_to(HOME)
    snap = snapshot_dir / rel
    snap.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_dir():
        shutil.copytree(dest, snap, symlinks=True, dirs_exist_ok=True)
    else:
        shutil.copy2(dest, snap)


def _prune_empty_dirs(paths: list[Path]) -> list[str]:
    candidates = set()
    for p in paths:
        parent = p.parent
        while parent != HOME and HOME in parent.parents:
            candidates.add(parent)
            parent = parent.parent
    pruned = []
    for d in sorted(candidates, key=lambda x: len(x.parts), reverse=True):
        try:
            d.rmdir()
            pruned.append(str(d))
        except OSError:
            pass
    return pruned


def _write_snapshot_marker(snapshot_dir: Path, source: str) -> None:
    (snapshot_dir / LOG_NAME).write_text(
        json.dumps({"kind": "pre-rollback", "source": source, "created": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=2) + "\n"
    )


def run_rollback(args) -> int:
    if args.list:
        dirs = list_backup_dirs()
        if not dirs:
            util.info("no backups found")
            return 0
        util.headline("Available backups (newest last)")
        for d in dirs:
            log = load_log(d)
            count = len(backup_files(d))
            bundle = f" <- {log['bundle']}" if log and log.get("bundle") else ""
            print(f"  {d.name}  ({count} files){bundle}")
        return 0

    if args.timestamp:
        target = BACKUPS / args.timestamp
        if not target.is_dir():
            util.err(f"no such backup: {target}")
            return 1
    else:
        dirs = list_backup_dirs()
        if not dirs:
            util.err("no backups found; nothing to roll back")
            return 1
        target = dirs[-1]

    log = load_log(target)
    files = backup_files(target)
    added = []
    snapshot_mode = log is not None
    if snapshot_mode:
        added = log.get("added", [])

    util.headline(f"Rollback plan: {target.name}")
    if log and log.get("bundle"):
        util.info(f"import was from: {log['bundle']} at {log.get('applied', '?')}")
    print(f"  {util._c(util.CYAN, 'restore  ')}  {len(files)} files from backup")
    for f in files[:12]:
        print(f"             {f.relative_to(target)}")
    if len(files) > 12:
        print(f"             ... and {len(files) - 12} more")
    if added:
        print(f"  {util._c(util.YELLOW, 'remove   ')}  {len(added)} files added by the import")
        for rel in added[:12]:
            print(f"             {rel}")
        if len(added) > 12:
            print(f"             ... and {len(added) - 12} more")
    if not snapshot_mode:
        util.warn("this backup has no import log; files added by the import are kept")

    if not args.yes:
        if not confirm("Apply this rollback?", default=False):
            util.info("aborted")
            return 1

    stamp = time.strftime("%Y%m%d-%H%M%S")
    snapshot_dir = BACKUPS / f"{target.name}-pre-rollback-{stamp}"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    restored = 0
    touched = []
    for f in files:
        rel = f.relative_to(target)
        dest = HOME / rel
        if dest.exists():
            _snapshot(dest, snapshot_dir)
        _restore(f, dest)
        restored += 1
        touched.append(dest)

    removed = 0
    removed_paths = []
    if snapshot_mode:
        for rel in added:
            dest = HOME / rel
            if not dest.exists():
                continue
            _snapshot(dest, snapshot_dir)
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
            removed += 1
            removed_paths.append(dest)

    pruned = _prune_empty_dirs(removed_paths)
    _write_snapshot_marker(snapshot_dir, target.name)

    util.ok(f"{restored} files restored, {removed} imported files removed")
    if pruned:
        util.info(f"removed {len(pruned)} now-empty directories")
    util.ok(f"previous state saved to {snapshot_dir}")
    util.info(f"undo this rollback with: omarchy-export rollback {snapshot_dir.name}")

    _post_rollback(touched, args)
    return 0


def _post_rollback(touched: list[Path], args) -> None:
    import sys

    interactive = sys.stdin.isatty()
    hypr = any(".config/hypr/" in p.parts for p in touched)
    shell = any(p.name == "shell.json" and ".config/omarchy" in p.parts for p in touched)
    if hypr and util.require_bin("hyprctl"):
        if args.yes or (interactive and confirm("Reload Hyprland now?", default=True)):
            errors = util.run_out(["hyprctl", "configerrors"])
            if errors and "valid" not in errors.lower():
                util.warn(f"hyprctl configerrors: {errors}")
            util.run(["hyprctl", "reload"], check=False)
            util.ok("hyprctl reload sent")
    if shell and util.require_bin("omarchy"):
        if args.yes or (interactive and confirm("Restart omarchy shell now?", default=True)):
            util.run(["omarchy", "restart", "shell"], check=False)
            util.ok("omarchy shell restarted")
