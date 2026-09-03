from pathlib import Path

from . import util
from .categories import OMARCHY

MENU_FILE = OMARCHY / "extensions" / "omarchy-menu.jsonc"
MARKER = "// omarchy-export:v1"
ENTRY_ID = "tools.omarchy-export"
ENTRY = (
    f'  {MARKER}\n'
    f'  "{ENTRY_ID}": {{ "icon": "", "label": "Export / Import settings", '
    f'"description": "OmarchyExport", "action": "omarchy-launch-terminal omarchy-export" }},\n'
)


def install() -> int:
    MENU_FILE.parent.mkdir(parents=True, exist_ok=True)
    if MENU_FILE.exists():
        text = MENU_FILE.read_text()
        if MARKER in text:
            lines = [l for l in text.splitlines() if MARKER not in l and ENTRY_ID not in l]
            text = "\n".join(lines).rstrip("\n") + "\n"
        stripped = text.rstrip()
        if not stripped.endswith("}"):
            util.err(f"unexpected structure in {MENU_FILE}; not modifying")
            return 1
        head = stripped[:-1].rstrip()
        new_text = head + "\n" + ENTRY + "}\n"
    else:
        new_text = "{\n" + ENTRY + "}\n"
    MENU_FILE.write_text(new_text)
    util.ok(f"menu entry '{ENTRY_ID}' installed in {MENU_FILE}")
    util.info("the Omarchy menu picks it up automatically (hot-reload)")
    return 0


def remove() -> int:
    if not MENU_FILE.exists() or MARKER not in MENU_FILE.read_text():
        util.info("no OmarchyExport menu entry found")
        return 0
    lines = [
        l
        for l in MENU_FILE.read_text().splitlines()
        if MARKER not in l and ENTRY_ID not in l
    ]
    text = "\n".join(lines).rstrip("\n")
    if not text.endswith("}"):
        text += "\n}"
    MENU_FILE.write_text(text + "\n")
    util.ok("menu entry removed")
    return 0
