# qGitSync

**Sync folders between computers using GitHub.**

[![Latest release](https://img.shields.io/github/v/release/kostq/qGitSync)](https://github.com/kostq/qGitSync/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[Русская версия](README.ru.md)

qGitSync watches your folders and keeps them in sync with GitHub repositories.
Change a file — it gets committed and pushed automatically; open the app on
another computer — the changes arrive.

## Download

**[⬇ qGitSync.exe — latest release](https://github.com/kostq/qGitSync/releases/latest/download/qGitSync.exe)**
(Windows, single file, no installation required)

## Features

- **Multiple folders**, each linked to its own GitHub repository, with
  per-folder settings and log.
- **Three sync modes** (can be combined): automatically N seconds after the
  last file change, on a schedule every N minutes, or manually.
- **Fast remote pickup**: a lightweight check asks GitHub every N minutes
  (1 by default) and pulls only when there is actually something new — changes
  made on another computer arrive within a minute or two.
- **Safe conflict handling**: if the same file was edited on two computers,
  sync never stops — the server version keeps the original name and your local
  version is saved next to it as `file (conflict PCNAME date).ext`, then both
  are synced everywhere. Nothing is ever lost silently.
- **Repository management built in**: list, create and delete your GitHub
  repositories from the app (personal access token, stored in the Windows
  Credential Manager — never in files).
- **Status at a glance**: 🟢 synced / 🔄 syncing / 🔴 error / ⚠️ conflict,
  pending-changes counters, tray notifications on problems.
- **Zero-dependency install**: a single `qGitSync.exe`. If Git is missing,
  the app offers to download a portable copy (~60 MB) just for itself.
- **System tray**: closing the window keeps sync running in the background;
  optional autostart with Windows. A second launch simply brings up the
  running instance — no duplicate processes.
- **Languages**: English (default), Russian, Spanish.

## Quick start

1. Run `qGitSync.exe` (or `py app.py` from source).
2. **GitHub token** (once): toolbar → *GitHub token* → *Open the tokens page*
   → generate a classic token with `repo` + `delete_repo` scopes → paste →
   *Check and save*.
3. **Add folder**: pick a folder and choose how to bind it — create a new
   repository right from the app, pick one of yours from the list, paste a
   URL, or keep it local for now.
4. Done. The first sync starts automatically.

**Second computer:** run qGitSync, save the same token, *Add folder* → point
at an **empty** folder → *Pick one of my repositories* → same repo. Files are
cloned and stay in sync both ways.

## How it works

Each sync is `git add -A` → `commit` → `pull --rebase --autostash` → `push`.
If the same file was edited on two computers at once, qGitSync keeps both
versions: the incoming one under the original file name, the local one as a
conflict copy next to it — and both spread to every computer. The full history
of every sync also stays on GitHub, so any past state can be restored.

Settings live in `%LOCALAPPDATA%\qGitSync\config.json`; portable Git (if
downloaded) in `%LOCALAPPDATA%\qGitSync\MinGit`.

## GitHub limits worth knowing

- Files over 100 MB are rejected by GitHub (use Git LFS for those).
- Keep a repository under ~1–2 GB.
- Great for documents, code and notes; not for movies or disk backups.

## Building from source

```
py -m pip install -r requirements.txt
py app.py                # run

py -m pip install pyinstaller
py -m PyInstaller --noconfirm --onefile --windowed --name qGitSync --icon icon.ico --add-data "icon.ico;." app.py
# → dist\qGitSync.exe
```

## Project layout

| File | Purpose |
|------|---------|
| `app.py` | Qt (PySide6) user interface |
| `core.py` | git operations, GitHub API, configuration |
| `i18n.py` | translations (EN/RU/ES) |

## License

[MIT](LICENSE)
