# OmarchyExport

Export and import transportable Omarchy settings between machines as a single
`.tar.gz` bundle. Selective both ways, with checksum verification, timestamped
backups, and merge handling for files Omarchy owns.

## Install

```bash
make install            # user-local: ~/.local/bin/omarchy-export
# or
makepkg -f && pacman -U omarchy-export-*.pkg.tar.zst
```

## Usage

```bash
omarchy-export                  # interactive picker (also in the Omarchy menu after `omarchy-export menu`)
omarchy-export export           # pick categories, write ./omarchy-export-<host>-<date>.tar.gz
omarchy-export export --all --with-media -o /tmp/settings.tar.gz
omarchy-export list settings.tar.gz
omarchy-export import settings.tar.gz             # pick categories, preview plan, confirm
omarchy-export import settings.tar.gz --dry-run  # plan only
omarchy-export import settings.tar.gz --only hypr-bindings,shell,themes --yes
omarchy-export rollback           # undo the latest import from its backup
omarchy-export rollback --list    # show available backups
omarchy-export rollback <timestamp>
omarchy-export menu             # install the "Export / Import settings" menu row
omarchy-export menu --remove
```

## What can be transported

| Category | id | Notes |
|---|---|---|
| Hyprland keybinds | `hypr-bindings` | `bindings.lua` |
| Hyprland tweaks | `hypr-config` | input, look'n'feel, autostart, hyprsunset, xdph |
| Monitor layout | `hypr-monitors` | machine-specific; import needs `--allow-machine-specific` |
| Shell layout | `shell` | `shell.json` merged (bar layout, idle, plugin enablement), `shell.toml` |
| Custom themes | `themes` | user theme dirs; large media only with `--with-media` |
| Theme backgrounds | `backgrounds` | |
| Shell plugins | `plugins` | git plugins recorded as remote+HEAD+local patch; bundled copy as fallback |
| Hooks | `hooks` | executable code — trust the source |
| Theme template overrides | `themed-overrides` | `themed/*.tpl` |
| Menu extensions | `menu` | `extensions/omarchy-menu.jsonc` |
| Branding | `branding` | about.txt, screensaver.txt |
| Defaults & choices | `defaults` | default agent, theme name, font, toggles, terminal/browser/editor choice |
| Terminal configs | `terminals` | alacritty/foot/kitty/ghostty; theme include lines preserved |
| App configs | `app-configs` | btop (+themes), starship, lazygit, fastfetch |
| git config | `gitconfig` | contains your name/email |
| Environment | `environment` | scanned for secret-like entries at export |
| Foreign/AUR packages | `packages` | `pacman -Qm` list + reviewable reinstall script |
| Dev link | `devlink` | checkout remote/branch/HEAD + patch of local modifications; import prints manual steps |

Export and import are independent selections: export only what you want to
share, import only what the target machine needs.

- Hooks and plugins contain code; warnings are surfaced at both export and
  import.

## Rollback

Every import that changes files records an `import-log.json` next to its
backup. `omarchy-export rollback` restores the most recent backup, removes
files the import had added, and prunes directories left empty. Before touching
anything it snapshots the current state, so a rollback is itself reversible
with `omarchy-export rollback <snapshot-name>` (the command prints it).
Backups without an import log (from older versions) are restored as-is and
added files are kept. Hyprland is reloaded and the shell restarted after the
same categories that triggered it on import.

- Bundles carry a manifest with SHA256 checksums; import aborts on mismatch.
- Overwritten files are backed up to
  `~/.local/state/omarchy-export/backups/<timestamp>/` preserving `$HOME`
  relative paths, together with an `import-log.json` recording exactly what
  the import changed.
- `shell.json` is merged (imported keys win, target-only keys survive).
- Terminal configs keep their Omarchy theme include/import lines.
- Monitors are excluded from import unless explicitly forced.
- Packages and dev link are never applied automatically: you get a script to
  review and printed steps to run.
- Hooks and plugins contain code; warnings are surfaced at both export and
  import.

## Plugin / menu integration

Omarchy shell plugins are QML UI components, which is the wrong vehicle for
system tooling, so the core lives in this CLI. The shell integration is the
menu row installed by `omarchy-export menu`, which launches the interactive
picker in a terminal. The tool is also a natural candidate to be upstreamed as
`omarchy export` / `omarchy import` built-ins.
