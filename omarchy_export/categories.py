from dataclasses import dataclass, field
from pathlib import Path

HOME = Path.home()
CONFIG = HOME / ".config"
OMARCHY = CONFIG / "omarchy"
STATE = HOME / ".local" / "state" / "omarchy"

MEDIA_SUFFIXES = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v", ".gif"}
MEDIA_SIZE_LIMIT = 1024 * 1024

MERGE_JSON = "json"
MERGE_TERMINAL = "terminal"


@dataclass
class FileSpec:
    target: Path
    archive: str
    merge: str | None = None


@dataclass
class Category:
    id: str
    label: str
    description: str
    warning: str | None = None
    specs: list[FileSpec] = field(default_factory=list)
    special: str | None = None
    available: bool = True
    media_gated: bool = False
    skipped_media: list[str] = field(default_factory=list)

    def has_content(self) -> bool:
        if self.special:
            return self.available
        return any(s.target.exists() for s in self.specs)


def is_media(path: Path) -> bool:
    if path.suffix.lower() in MEDIA_SUFFIXES:
        return True
    try:
        return path.stat().st_size > MEDIA_SIZE_LIMIT
    except OSError:
        return False


def _glob(base: Path, pattern: str) -> list[Path]:
    if not base.exists():
        return []
    return sorted(p for p in base.glob(pattern) if p.is_file())


def _dir_files(base: Path, archive_prefix: str, skip_suffix=()) -> list[FileSpec]:
    if not base.exists():
        return []
    specs = []
    for p in sorted(base.rglob("*")):
        if p.is_dir():
            continue
        if p.suffix in skip_suffix:
            continue
        rel = p.relative_to(base)
        specs.append(FileSpec(p, f"{archive_prefix}/{rel}"))
    return specs


def _themes_specs(cat: Category) -> list[FileSpec]:
    specs = []
    themes_dir = OMARCHY / "themes"
    if not themes_dir.exists():
        return specs
    for theme in sorted(p for p in themes_dir.iterdir() if p.is_dir()):
        for p in sorted(theme.rglob("*")):
            if p.is_dir():
                continue
            if ".git" in p.relative_to(themes_dir).parts:
                continue
            rel = p.relative_to(themes_dir)
            if is_media(p):
                cat.skipped_media.append(str(rel))
                continue
            specs.append(FileSpec(p, f"themes/{rel}"))
    return specs


def _terminals_specs() -> list[FileSpec]:
    merge = MERGE_TERMINAL
    return [
        FileSpec(CONFIG / "alacritty" / "alacritty.toml", "terminals/alacritty.toml", merge),
        FileSpec(CONFIG / "foot" / "foot.ini", "terminals/foot.ini", merge),
        FileSpec(CONFIG / "kitty" / "kitty.conf", "terminals/kitty.conf", merge),
        FileSpec(CONFIG / "ghostty" / "config", "terminals/ghostty.conf", merge),
    ]


def build_categories() -> list[Category]:
    cats: list[Category] = []

    cats.append(
        Category(
            id="hypr-bindings",
            label="Hyprland keybinds",
            description="~/.config/hypr/bindings.lua",
            specs=[FileSpec(CONFIG / "hypr" / "bindings.lua", "hypr-bindings/bindings.lua")],
        )
    )
    cats.append(
        Category(
            id="hypr-config",
            label="Hyprland tweaks",
            description="input, look'n'feel, autostart, hyprsunset, screenshot",
            specs=[
                FileSpec(CONFIG / "hypr" / name, f"hypr-config/{name}")
                for name in (
                    "input.lua",
                    "looknfeel.lua",
                    "autostart.lua",
                    "hyprsunset.conf",
                    "xdph.conf",
                )
            ],
        )
    )
    cats.append(
        Category(
            id="hypr-monitors",
            label="Monitor layout",
            description="monitors.lua / monitors.conf",
            warning="Machine-specific: hardware descriptors, positions and modes almost certainly differ on the target machine.",
            specs=[
                FileSpec(CONFIG / "hypr" / name, f"hypr-monitors/{name}")
                for name in ("monitors.lua", "monitors.conf")
            ],
        )
    )
    cats.append(
        Category(
            id="shell",
            label="Omarchy shell layout",
            description="shell.json (bar, idle, plugins) and shell.toml",
            specs=[
                FileSpec(OMARCHY / "shell.json", "shell/shell.json", MERGE_JSON),
                FileSpec(OMARCHY / "shell.toml", "shell/shell.toml"),
            ],
        )
    )
    themes = Category(
        id="themes",
        label="Custom themes",
        description="~/.config/omarchy/themes/* (colors, overlays, previews)",
        media_gated=True,
    )
    themes.specs = _themes_specs(themes)
    cats.append(themes)
    cats.append(
        Category(
            id="backgrounds",
            label="Theme backgrounds",
            description="~/.config/omarchy/backgrounds/*",
            specs=_dir_files(OMARCHY / "backgrounds", "backgrounds"),
        )
    )
    cats.append(
        Category(
            id="plugins",
            label="Shell plugins",
            description="~/.config/omarchy/plugins/* (git-aware)",
            special="plugins",
            warning="Plugins contain executable QML/script code.",
        )
    )
    cats.append(
        Category(
            id="hooks",
            label="Automation hooks",
            description="~/.config/omarchy/hooks/",
            warning="Hooks are arbitrary executable scripts. Only import them from sources you trust.",
            specs=_dir_files(OMARCHY / "hooks", "hooks", skip_suffix=(".sample",)),
        )
    )
    cats.append(
        Category(
            id="themed-overrides",
            label="Theme template overrides",
            description="~/.config/omarchy/themed/*.tpl",
            specs=[
                FileSpec(p, f"themed-overrides/{p.name}")
                for p in _glob(OMARCHY / "themed", "*.tpl")
            ],
        )
    )
    menu_spec = OMARCHY / "extensions" / "omarchy-menu.jsonc"
    if menu_spec.exists() and len(menu_spec.read_text().strip()) > 2:
        cats.append(
            Category(
                id="menu",
                label="Menu extensions",
                description="extensions/omarchy-menu.jsonc",
                specs=[FileSpec(menu_spec, "menu/omarchy-menu.jsonc")],
            )
        )
    cats.append(
        Category(
            id="branding",
            label="Branding",
            description="about.txt and screensaver.txt",
            specs=[
                FileSpec(OMARCHY / "branding" / name, f"branding/{name}")
                for name in ("about.txt", "screensaver.txt")
            ],
        )
    )
    cats.append(
        Category(
            id="defaults",
            label="Defaults and choices",
            description="default agent, theme, font, toggles, terminal/browser/editor choice",
            special="defaults",
        )
    )
    cats.append(
        Category(
            id="terminals",
            label="Terminal configs",
            description="alacritty, foot, kitty, ghostty",
            specs=_terminals_specs(),
        )
    )
    cats.append(
        Category(
            id="app-configs",
            label="App configs",
            description="btop (+ themes), starship, lazygit, fastfetch",
            specs=(
                _dir_files(CONFIG / "btop", "app-configs/btop")
                + _dir_files(CONFIG / "lazygit", "app-configs/lazygit")
                + _dir_files(CONFIG / "fastfetch", "app-configs/fastfetch")
                + [
                    FileSpec(p, f"app-configs/starship.toml")
                    for p in [CONFIG / "starship.toml"]
                    if p.exists()
                ]
            ),
        )
    )
    gitconfig = Category(
        id="gitconfig",
        label="git config",
        description="~/.config/git/config",
        warning="Contains your name and email address.",
        specs=[FileSpec(CONFIG / "git" / "config", "gitconfig/config")],
    )
    cats.append(gitconfig)
    cats.append(
        Category(
            id="environment",
            label="Environment variables",
            description="~/.config/environment.d/*.conf",
            warning="Reviewed for secret-like entries at export time.",
            specs=[
                FileSpec(p, f"environment/{p.name}")
                for p in _glob(CONFIG / "environment.d", "*.conf")
            ],
        )
    )
    cats.append(
        Category(
            id="packages",
            label="Foreign/AUR packages",
            description="pacman -Qm list with reinstall script",
            special="packages",
        )
    )
    cats.append(
        Category(
            id="devlink",
            label="Dev link",
            description="OMARCHY_PATH checkout info, remote, branch and local diff",
            special="devlink",
            warning="Includes a patch of uncommitted changes in your Omarchy checkout.",
        )
    )

    return cats


CATEGORIES = build_categories()


def by_id(cid: str) -> Category | None:
    for cat in CATEGORIES:
        if cat.id == cid:
            return cat
    return None
