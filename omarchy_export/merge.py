import json
from pathlib import Path

from .categories import MERGE_JSON, MERGE_TERMINAL

THEME_STATE_MARKER = "omarchy/current/theme"

PRESERVE_LINE_PREFIXES = (
    "general.import",
    "include",
    "config-file",
)


def deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _preserve_lines(text: str) -> list[str]:
    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if THEME_STATE_MARKER in line and any(
            line.startswith(prefix) for prefix in PRESERVE_LINE_PREFIXES
        ):
            kept.append(line)
    return kept


def merge_target_text(merge_kind: str, target: Path, incoming: str) -> str:
    if merge_kind == MERGE_JSON:
        try:
            current = json.loads(target.read_text()) if target.exists() else {}
        except json.JSONDecodeError:
            current = {}
        try:
            new = json.loads(incoming)
        except json.JSONDecodeError:
            return incoming
        return json.dumps(deep_merge(current, new), indent=2) + "\n"
    if merge_kind == MERGE_TERMINAL:
        if target.exists():
            kept = _preserve_lines(target.read_text())
            if kept:
                existing = set(_preserve_lines(incoming))
                missing = [l for l in kept if l not in existing]
                if missing:
                    return incoming.rstrip("\n") + "\n\n" + "\n".join(missing) + "\n"
        return incoming
    return incoming
