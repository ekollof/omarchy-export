import json
import os
import socket
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from . import SCHEMA, VERSION, special, util
from .categories import CATEGORIES, HOME
from .ui import select_categories


def omarchy_version() -> str:
    return util.run_out(["omarchy", "version"]) or "unknown"


def stage_category(cat, stage: Path) -> list[dict]:
    entries = []
    for spec in cat.specs:
        if not spec.target.exists():
            continue
        dest = stage / "payload" / spec.archive
        dest.parent.mkdir(parents=True, exist_ok=True)
        util.copy_file(spec.target, dest)
        entries.append(
            {
                "archive": f"payload/{spec.archive}",
                "target": spec.target.resolve().relative_to(HOME).as_posix(),
                "cat": cat.id,
                "merge": spec.merge,
            }
        )
    return entries


def gather_warnings(cat) -> list[str]:
    warnings = []
    if cat.warning:
        warnings.append(cat.warning)
    if cat.id == "environment":
        for spec in cat.specs:
            if spec.target.exists() and util.scan_secrets(spec.target.read_text(errors="replace")):
                warnings.append(f"{spec.target.name} contains secret-like assignments; review before sharing this bundle.")
    if cat.skipped_media:
        warnings.append(
            "media files skipped (re-run export with --with-media to include): "
            + ", ".join(cat.skipped_media)
        )
    return warnings


def run_export(args) -> int:
    cats = {c.id: c for c in CATEGORIES}
    ids = select_categories(
        cats,
        args.only,
        args.all,
        allow_empty=False,
        action=f"export{' (with media)' if args.with_media else ''}",
        check_content=True,
    )
    selected = [cats[cid] for cid in ids]
    if not selected:
        util.err("nothing selected")
        return 1

    manifest_categories = {}
    files_index: list[dict] = []
    checksums: dict[str, str] = {}

    with tempfile.TemporaryDirectory(prefix="omarchy-export-") as tmp:
        stage = Path(tmp)
        for cat in selected:
            if cat.special:
                if not cat.available:
                    continue
                meta = special.collect_special(cat.id, stage)
                meta_file = stage / f"{cat.id}.json"
                meta_file.write_text(json.dumps(meta, indent=2))
                manifest_categories[cat.id] = {
                    "label": cat.label,
                    "warnings": gather_warnings(cat),
                    "special": True,
                }
                continue
            entries = stage_category(cat, stage)
            if not entries and not cat.has_content():
                continue
            files_index.extend(entries)
            manifest_categories[cat.id] = {
                "label": cat.label,
                "warnings": gather_warnings(cat),
                "files": len(entries),
            }

        files_file = stage / "files.json"
        files_file.write_text(json.dumps(files_index, indent=2))

        for p in sorted(stage.rglob("*")):
            if p.is_file():
                rel = p.relative_to(stage).as_posix()
                checksums[rel] = util.sha256(p)

        manifest = {
            "schema": SCHEMA,
            "tool": "omarchy-export",
            "tool_version": VERSION,
            "created": datetime.now().astimezone().isoformat(timespec="seconds"),
            "hostname": socket.gethostname(),
            "user": os.environ.get("USER", ""),
            "omarchy_version": omarchy_version(),
            "categories": manifest_categories,
            "files": checksums,
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

        output = Path(args.output) if args.output else Path(
            f"omarchy-export-{socket.gethostname()}-{datetime.now():%Y%m%d-%H%M}.tar.gz"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(output, "w:gz") as tar:
            for p in sorted(stage.rglob("*")):
                if p.is_file():
                    tar.add(p, arcname=p.relative_to(stage).as_posix())

    total = len(checksums)
    util.ok(f"wrote {output}")
    util.info(f"{total} files, {util.human_size(output.stat().st_size)}, categories: {', '.join(manifest_categories)}")
    for cid, meta in manifest_categories.items():
        for w in meta.get("warnings", []):
            util.warn(f"[{cid}] {w}")
    return 0
