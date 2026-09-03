import json
import shutil
import sys
import tarfile
import tempfile
import time
from pathlib import Path

from . import SCHEMA, special, util
from .categories import HOME
from .merge import merge_target_text
from .ui import confirm, select_categories

EXPORT_STATE = HOME / ".local" / "state" / "omarchy-export"

MACHINE_SPECIFIC = {"hypr-monitors"}


def open_bundle(bundle: Path) -> tuple[dict, Path]:
    if not bundle.exists():
        raise SystemExit(util.err(f"bundle not found: {bundle}"))
    stage = Path(tempfile.mkdtemp(prefix="omarchy-import-"))
    with tarfile.open(bundle, "r:gz") as tar:
        for member in tar.getmembers():
            if not util.safe_relpath(member.name):
                raise SystemExit(util.err(f"unsafe path in bundle: {member.name}"))
        tar.extractall(stage, filter="data")
    manifest_path = stage / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(util.err("bundle has no manifest.json; not an OmarchyExport bundle"))
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") != SCHEMA:
        raise SystemExit(
            util.err(f"bundle schema {manifest.get('schema')} not supported (this tool understands {SCHEMA})")
        )
    problems = []
    for rel, digest in manifest.get("files", {}).items():
        p = stage / rel
        if not p.exists():
            problems.append(f"missing: {rel}")
        elif util.sha256(p) != digest:
            problems.append(f"checksum mismatch: {rel}")
    if problems:
        for p in problems:
            util.err(p)
        raise SystemExit(util.err("bundle integrity check failed; aborting"))
    util.ok("bundle integrity verified")
    return manifest, stage


def bundle_categories(stage: Path) -> dict[str, dict]:
    files = json.loads((stage / "files.json").read_text())
    by_cat: dict[str, dict] = {}
    for entry in files:
        by_cat.setdefault(entry["cat"], {"files": [], "special": False})["files"].append(entry)
    for cat_id in ("plugins", "packages", "devlink", "defaults"):
        if (stage / f"{cat_id}.json").exists():
            by_cat.setdefault(cat_id, {"files": [], "special": True})["special"] = True
    return by_cat


def bundle_has_content(cat_id: str, stage: Path) -> bool:
    meta = stage / f"{cat_id}.json"
    if meta.exists():
        return True
    payload = stage / "payload" / cat_id
    return payload.exists() and any(payload.rglob("*"))


def plan_actions(entries: list[dict], stage: Path, allow_machine: bool) -> list[tuple[str, dict]]:
    actions = []
    for entry in entries:
        cat = entry["cat"]
        if cat in MACHINE_SPECIFIC and not allow_machine:
            actions.append(("skip-machine", entry))
            continue
        target = HOME / entry["target"]
        src = stage / entry["archive"]
        if not src.exists():
            actions.append(("skip-missing", entry))
            continue
        if entry.get("merge"):
            actions.append(("merge" if target.exists() else "add", entry))
        else:
            actions.append(("overwrite" if target.exists() else "add", entry))
    return actions


def print_plan(actions, notes: list[str]) -> None:
    util.headline("Import plan")
    for kind, entry in actions:
        target = HOME / entry["target"]
        if kind == "add":
            marker = util._c(util.GREEN, "add      ")
        elif kind == "overwrite":
            marker = util._c(util.YELLOW, "overwrite")
        elif kind == "merge":
            marker = util._c(util.CYAN, "merge    ")
        else:
            marker = util._c(util.YELLOW, "skip     ")
        print(f"  {marker}  {target}" + ("  (machine-specific)" if kind == "skip-machine" else ""))
    for note in notes:
        print(f"  {util._c(util.CYAN, 'note     ')}  {note}")


def _log_entry(kind: str, entry: dict, log: dict) -> None:
    log["actions"].append({"action": kind, "target": entry["target"], "cat": entry["cat"]})
    if kind == "add":
        log["added"].append(entry["target"])


def apply_actions(actions, stage: Path, backup_root: Path, log: dict) -> int:
    applied = 0
    for kind, entry in actions:
        if kind in ("skip-machine", "skip-missing"):
            if kind == "skip-machine":
                util.warn(f"skipped machine-specific file: {entry['target']} (use --allow-machine-specific to force)")
            continue
        target = HOME / entry["target"]
        src = stage / entry["archive"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            util.backup_file(target, backup_root)
        if entry.get("merge"):
            merged = merge_target_text(entry["merge"], target, src.read_text())
            target.write_text(merged)
        else:
            shutil.copy2(src, target)
        _log_entry(kind, entry, log)
        applied += 1
    return applied


def run_import(args) -> int:
    bundle = Path(args.bundle).expanduser()
    manifest, stage = open_bundle(bundle)
    meta = manifest
    util.info(
        f"bundle: {bundle.name} | from {meta.get('user')}@{meta.get('hostname')} | omarchy {meta.get('omarchy_version')} | created {meta.get('created')}"
    )
    local_version = util.run_out(["omarchy", "version"]) or "unknown"
    if local_version != meta.get("omarchy_version") and meta.get("omarchy_version") not in ("unknown", None):
        util.warn(f"omarchy version differs: bundle {meta.get('omarchy_version')} vs local {local_version}")

    by_cat = bundle_categories(stage)
    present = {cid: info for cid, info in by_cat.items() if bundle_has_content(cid, stage)}
    if not present:
        util.err("bundle contains no categories")
        return 1

    selected_ids = select_categories(
        present,
        args.only,
        args.all,
        allow_empty=False,
        action="import",
    )
    if not selected_ids:
        util.err("nothing selected")
        return 1

    entries = [e for cid in selected_ids for e in by_cat.get(cid, {}).get("files", [])]
    actions = plan_actions(entries, stage, args.allow_machine_specific)

    special_notes = []
    if "packages" in selected_ids:
        special_notes.append("packages: reinstall script will be saved for manual review")
    if "devlink" in selected_ids:
        special_notes.append("devlink: instructions will be printed (never applied automatically)")
    if "plugins" in selected_ids:
        special_notes.append("plugins: cloned from recorded git remote (fallback: bundled copy) and patched")
    if "defaults" in selected_ids:
        special_notes.append("defaults: files copied; theme/font application will be offered afterwards")

    print_plan(actions, special_notes)
    for cid in selected_ids:
        cat_meta = meta.get("categories", {}).get(cid, {})
        for w in cat_meta.get("warnings", []):
            util.warn(f"[{cid}] {w}")

    if args.dry_run:
        util.ok("dry run - nothing written")
        return 0

    if not args.yes:
        if not confirm("Apply this import plan?", default=False):
            util.info("aborted")
            return 1

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_root = EXPORT_STATE / "backups" / timestamp
    log = {"bundle": bundle.name, "applied": timestamp, "added": [], "actions": []}
    applied = apply_actions(actions, stage, backup_root, log)
    util.ok(f"{applied} files written (backups: {backup_root})" if applied else "no file changes")

    notes: list[str] = []
    if "plugins" in selected_ids:
        notes.extend(special.import_plugins(stage, backup_root, log))
    if "packages" in selected_ids:
        notes.extend(special.import_packages(stage))
    if "devlink" in selected_ids:
        notes.extend(special.import_devlink(stage))
    if "defaults" in selected_ids:
        notes.extend(special.import_defaults(stage, backup_root, log))
    for note in notes:
        util.info(note)

    if log["actions"]:
        (backup_root / "import-log.json").write_text(json.dumps(log, indent=2) + "\n")

    post_import_actions(actions, args)
    shutil.rmtree(stage, ignore_errors=True)
    util.ok("import complete")
    return 0


def post_import_actions(actions, args) -> None:
    cats_applied = {entry["cat"] for kind, entry in actions if kind in ("add", "overwrite", "merge")}
    if not cats_applied:
        return
    hypr_touched = any(c.startswith("hypr-") for c in cats_applied)
    shell_touched = "shell" in cats_applied
    if not hypr_touched and not shell_touched:
        return

    interactive = sys.stdin.isatty()
    if hypr_touched and util.require_bin("hyprctl"):
        do_reload = args.yes or (interactive and confirm("Reload Hyprland now?", default=True))
        if do_reload:
            errors = util.run_out(["hyprctl", "configerrors"])
            if errors and "valid" not in errors.lower():
                util.warn(f"hyprctl configerrors: {errors}")
            util.run(["hyprctl", "reload"], check=False)
            util.ok("hyprctl reload sent")
    if shell_touched and (util.require_bin("omarchy-restart-shell") or util.require_bin("omarchy")):
        do_restart = args.yes or (interactive and confirm("Restart omarchy shell now?", default=True))
        if do_restart:
            util.run(["omarchy", "restart", "shell"], check=False)
            util.ok("omarchy shell restarted")

    if "defaults" in cats_applied and interactive and not args.yes:
        theme_file = HOME / ".local" / "state" / "omarchy" / "current" / "theme.name"
        if theme_file.exists():
            theme = theme_file.read_text().strip()
            if theme and confirm(f"Apply theme '{theme}' now?", default=False):
                util.run(["omarchy", "theme", "set", theme], check=False)
                util.ok(f"theme set to {theme}")
