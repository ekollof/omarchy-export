import argparse
import subprocess
import sys
from pathlib import Path

from . import VERSION
from . import export, importer, menu, rollback, util


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omarchy-export",
        description="Export or import transportable Omarchy settings (keybinds, themes, plugins, hooks, devlink, packages and more).",
    )
    parser.add_argument("--version", action="version", version=f"omarchy-export {VERSION}")
    sub = parser.add_subparsers(dest="command")

    p_export = sub.add_parser("export", help="create a portable settings bundle (.tar.gz)")
    p_export.add_argument("-o", "--output", help="output bundle path (default: ./omarchy-export-<host>-<date>.tar.gz)")
    p_export.add_argument("--only", help="comma-separated category ids to export")
    p_export.add_argument("--all", action="store_true", help="export every category with content, no interactive picker")
    p_export.add_argument("--with-media", action="store_true", help="include large media (theme videos/backgrounds)")
    p_export.set_defaults(func=export.run_export)

    p_import = sub.add_parser("import", help="import settings from a bundle")
    p_import.add_argument("bundle", help="path to an OmarchyExport .tar.gz bundle")
    p_import.add_argument("--only", help="comma-separated category ids to import")
    p_import.add_argument("--all", action="store_true", help="import every category in the bundle, no interactive picker")
    p_import.add_argument("--dry-run", action="store_true", help="show the plan without writing anything")
    p_import.add_argument("--yes", "-y", action="store_true", help="apply without confirmation (still backs up)")
    p_import.add_argument("--allow-machine-specific", action="store_true", help="also import monitor layout")
    p_import.set_defaults(func=importer.run_import)

    p_list = sub.add_parser("list", help="list the contents of a bundle")
    p_list.add_argument("bundle")
    p_list.set_defaults(func=run_list)

    p_menu = sub.add_parser("menu", help="install/remove the Omarchy menu entry")
    p_menu.add_argument("--remove", action="store_true", help="remove the menu entry")
    p_menu.set_defaults(func=run_menu)

    p_rollback = sub.add_parser("rollback", help="roll back the latest import using its backup")
    p_rollback.add_argument("timestamp", nargs="?", help="backup timestamp (default: latest); see --list")
    p_rollback.add_argument("--list", action="store_true", help="list available backups")
    p_rollback.add_argument("--yes", "-y", action="store_true", help="apply without confirmation")
    p_rollback.set_defaults(func=rollback.run_rollback)

    return parser


def run_list(args) -> int:
    manifest, _stage = importer.open_bundle(Path(args.bundle).expanduser())
    util.headline(f"Bundle: {Path(args.bundle).name}")
    print(f"  from:    {manifest.get('user')}@{manifest.get('hostname')}")
    print(f"  created: {manifest.get('created')}")
    print(f"  omarchy: {manifest.get('omarchy_version')}")
    print(f"  tool:    {manifest.get('tool_version')}")
    util.headline("Categories")
    for cid, meta in manifest.get("categories", {}).items():
        count = meta.get("files", "?")
        extra = " (special)" if meta.get("special") else f" ({count} files)"
        print(f"  {cid:<18} {meta.get('label', cid)}{extra}")
        for w in meta.get("warnings", []):
            print(f"                      {util._c(util.YELLOW, '⚠ ' + w)}")
    return 0


def run_menu(args) -> int:
    if args.remove:
        return menu.remove()
    return menu.install()


ACTIONS = [
    ("export", "Export settings to a bundle"),
    ("import", "Import settings from a bundle"),
    ("rollback", "Roll back the last import"),
    ("menu", "Install Omarchy menu entry"),
    ("quit", "Quit"),
]


def pick_action() -> str | None:
    if util.require_bin("fzf"):
        labels = "\n".join(a[1] for a in ACTIONS)
        proc = subprocess.run(
            ["fzf", "--height", str(len(ACTIONS) + 2), "--header", "OmarchyExport - what do you want to do?", "--prompt", "action> "],
            input=labels,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return None
        chosen = proc.stdout.strip()
        for key, label in ACTIONS:
            if label == chosen:
                return key
        return None
    for i, (_, label) in enumerate(ACTIONS, 1):
        print(f"  {i}. {label}")
    try:
        raw = input("Choose: ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if raw.isdigit() and 1 <= int(raw) <= len(ACTIONS):
        return ACTIONS[int(raw) - 1][0]
    return None


def interactive_picker() -> int:
    action = pick_action()
    if action in (None, "quit"):
        return 0
    parser = build_parser()
    if action == "export":
        return export.run_export(parser.parse_args(["export"]))
    if action == "import":
        try:
            raw = input("Bundle path: ").strip()
        except (EOFError, KeyboardInterrupt):
            return 0
        if not raw:
            return 1
        return importer.run_import(parser.parse_args(["import", raw]))
    if action == "rollback":
        return rollback.run_rollback(parser.parse_args(["rollback"]))
    return menu.install()


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        if sys.stdin.isatty() and sys.stdout.isatty():
            return interactive_picker()
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print()
        return 130
