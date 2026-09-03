import subprocess
import sys

from . import util


def fzf_available() -> bool:
    return util.require_bin("fzf") and sys.stdin.isatty() and sys.stdout.isatty()


def fzf_multi(options: list[str], header: str) -> list[int]:
    text = "\n".join(f"{i}|{option}" for i, option in enumerate(options))
    proc = subprocess.run(
        [
            "fzf",
            "--multi",
            "--ansi",
            "-d",
            r"\|",
            "--with-nth",
            "2..",
            "--header",
            header,
            "--prompt",
            "select> ",
            "--no-clear",
        ],
        input=text,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    picked = []
    for line in proc.stdout.strip().splitlines():
        try:
            picked.append(int(line.split("|", 1)[0]))
        except ValueError:
            continue
    return sorted(set(picked))


def _parse_ranges(spec: str, limit: int) -> list[int]:
    picked = set()
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            start, _, end = part.partition("-")
            if start.isdigit() and end.isdigit():
                for n in range(int(start), int(end) + 1):
                    if 1 <= n <= limit:
                        picked.add(n - 1)
        elif part.isdigit() and 1 <= int(part) <= limit:
            picked.add(int(part) - 1)
    return sorted(picked)


def prompt_multi(options: list[str], header: str) -> list[int]:
    print(header)
    for i, option in enumerate(options, 1):
        print(f"  {i:>3}. {option}")
    while True:
        try:
            raw = input("Numbers or ranges to include (e.g. 1,3-5; empty = all): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return []
        if not raw:
            return list(range(len(options)))
        picked = _parse_ranges(raw, len(options))
        if picked:
            return picked
        util.warn("nothing understood; try again")


def confirm(question: str, default: bool = False) -> bool:
    suffix = " [Y/n]" if default else " [y/N]"
    try:
        answer = input(question + suffix + ": ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def select_categories(
    cats_by_id,
    only: str | None,
    all_flag: bool,
    allow_empty: bool,
    action: str,
    check_content: bool = False,
) -> list[str]:
    if only:
        wanted = [x.strip() for x in only.split(",") if x.strip()]
        for cid in wanted:
            if cid not in cats_by_id:
                util.err(f"unknown category: {cid}")
                util.info(f"available: {', '.join(c for c in cats_by_id)}")
                return []
        return wanted

    available = []
    for cid, cat in cats_by_id.items():
        if check_content and hasattr(cat, "has_content") and not cat.has_content():
            continue
        available.append(cid)
    if not available:
        return []

    if all_flag or not (sys.stdin.isatty() and sys.stdout.isatty()):
        return available

    labels = []
    for cid in available:
        cat = cats_by_id[cid]
        label = getattr(cat, "label", cid)
        description = getattr(cat, "description", "")
        warning = getattr(cat, "warning", None)
        suffix = f"  {util._c(util.YELLOW, '⚠ ' + warning)}" if warning else ""
        labels.append(f"{cid:<18} {label} — {description}{suffix}")

    header = f"OmarchyExport: pick categories to {action} (tab to toggle, enter to confirm)"
    if fzf_available():
        picked = fzf_multi(labels, header)
    else:
        picked = prompt_multi(labels, header)
    if not picked and not allow_empty:
        return []
    return [available[i] for i in picked]
