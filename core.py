# -*- coding: utf-8 -*-
"""
qGitSync core — headless logic:
  * git discovery/installation (incl. portable MinGit)
  * repository operations (init/clone/sync)
  * GitHub API (token): list/create/delete repositories
  * configuration with multiple folder profiles
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
import zipfile
from datetime import datetime

try:
    import keyring
except ImportError:
    keyring = None

from i18n import tr

APP_NAME = "qGitSync"
_LOCAL = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
APP_DATA = os.path.join(_LOCAL, APP_NAME)
OLD_APP_DATA = os.path.join(_LOCAL, "GitSync")  # data dir of the pre-rename version
CONFIG_PATH = os.path.join(APP_DATA, "config.json")
MINGIT_DIR = os.path.join(APP_DATA, "MinGit")
ASKPASS_BAT = os.path.join(APP_DATA, "askpass.bat")
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

KEYRING_SERVICE = "qGitSync"
OLD_KEYRING_SERVICE = "GitSync"
KEYRING_TOKEN_KEY = "github-token"

# fallback if the GitHub API can't be asked for the latest release
MINGIT_FALLBACK_URL = ("https://github.com/git-for-windows/git/releases/download/"
                       "v2.47.1.windows.1/MinGit-2.47.1-64-bit.zip")


def ensure_app_data():
    # one-time migration from the old "GitSync" data dir
    if not os.path.isdir(APP_DATA) and os.path.isdir(OLD_APP_DATA):
        try:
            os.rename(OLD_APP_DATA, APP_DATA)
        except OSError:
            pass
    os.makedirs(APP_DATA, exist_ok=True)


ensure_app_data()


# ---------------------------------------------------------------- git.exe

_git_exe_cache = None


def find_git():
    """Путь к git.exe: системный из PATH или наш портативный MinGit."""
    global _git_exe_cache
    if _git_exe_cache and os.path.exists(_git_exe_cache):
        return _git_exe_cache
    exe = shutil.which("git")
    if exe:
        _git_exe_cache = exe
        return exe
    mingit = os.path.join(MINGIT_DIR, "cmd", "git.exe")
    if os.path.exists(mingit):
        _git_exe_cache = mingit
        return mingit
    return None


def mingit_download_url():
    """Ссылка на свежий MinGit 64-bit с GitHub, с запасным вариантом."""
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/git-for-windows/git/releases/latest",
            headers={"User-Agent": APP_NAME})
        with urllib.request.urlopen(req, timeout=15) as resp:
            release = json.load(resp)
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if name.startswith("MinGit-") and name.endswith("-64-bit.zip") \
                    and "busybox" not in name:
                return asset["browser_download_url"]
    except Exception:
        pass
    return MINGIT_FALLBACK_URL


def install_mingit(progress=None):
    """Скачать и распаковать портативный MinGit. progress(done, total) — колбэк."""
    ensure_app_data()
    url = mingit_download_url()
    zip_path = os.path.join(APP_DATA, "mingit.zip")
    req = urllib.request.Request(url, headers={"User-Agent": APP_NAME})
    with urllib.request.urlopen(req, timeout=60) as resp, open(zip_path, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if os.path.isdir(MINGIT_DIR):
        shutil.rmtree(MINGIT_DIR, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(MINGIT_DIR)
    os.remove(zip_path)
    global _git_exe_cache
    _git_exe_cache = None
    exe = find_git()
    if not exe:
        raise RuntimeError(tr("MinGit downloaded, but git.exe was not found after unpacking"))
    return exe


# ---------------------------------------------------------------- токен GitHub

def save_token(token):
    if keyring is None:
        raise RuntimeError(tr("keyring library is not installed"))
    keyring.set_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY, token)


def load_token():
    if keyring is None:
        return None
    try:
        token = keyring.get_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY)
        if token:
            return token
        # migrate a token saved by the pre-rename version
        old = keyring.get_password(OLD_KEYRING_SERVICE, KEYRING_TOKEN_KEY)
        if old:
            keyring.set_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY, old)
        return old
    except Exception:
        return None


def delete_token():
    if keyring is None:
        return
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY)
    except Exception:
        pass


def _write_askpass():
    """Скрипт, который отдаёт git'у логин/токен из переменной окружения (сам токен
    на диск не пишется)."""
    ensure_app_data()
    content = ('@echo off\r\n'
               'echo.%~1 | findstr /i "username" >nul\r\n'
               'if not errorlevel 1 (echo x-access-token) else (echo %GITSYNC_TOKEN%)\r\n')
    with open(ASKPASS_BAT, "w", encoding="ascii") as f:
        f.write(content)


# ---------------------------------------------------------------- запуск git

class GitError(Exception):
    pass


class GitNotFound(Exception):
    pass


def is_dead_remote_error(err):
    """True — стойкая проблема (репозиторий удалён/нет доступа), нужно сообщить.
    False — скорее всего временный сбой сети, молчим."""
    low = (err or "").lower()
    return any(s in low for s in (
        "repository not found",
        "does not appear to be a git repository",
        "authentication failed",
        "access denied",
        "invalid username or password",
        "could not read username",
        "permission denied",
    ))


def run_git(args, cwd, check=True, use_token=True):
    exe = find_git()
    if not exe:
        raise GitNotFound(tr("git not found"))
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    # quotepath=off: русские/юникодные имена файлов выводятся как есть, а не "\320..."
    pre = ["-c", "core.quotepath=off"]
    token = load_token() if use_token else None
    if token:
        _write_askpass()
        env["GIT_ASKPASS"] = ASKPASS_BAT
        env["GITSYNC_TOKEN"] = token
        pre += ["-c", "credential.helper="]  # токен главнее сохранённых паролей
    proc = subprocess.run(
        [exe] + pre + args,
        cwd=cwd or None,
        capture_output=True,
        creationflags=CREATE_NO_WINDOW,
        env=env,
    )
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    err = proc.stderr.decode("utf-8", errors="replace").strip()
    if check and proc.returncode != 0:
        raise GitError(err or out or f"git {' '.join(args)} -> exit code {proc.returncode}")
    return out, err, proc.returncode


def run_git_raw(args, cwd):
    """git с бинарным stdout (для git show блобов — нельзя декодировать)."""
    exe = find_git()
    if not exe:
        raise GitNotFound(tr("git not found"))
    proc = subprocess.run([exe, "-c", "core.quotepath=off"] + args,
                          cwd=cwd or None, capture_output=True,
                          creationflags=CREATE_NO_WINDOW)
    return proc.stdout, proc.returncode


# ---------------------------------------------------------------- репозиторий

class Repo:
    def __init__(self, folder):
        self.folder = folder
        self.last_conflicts = []  # [(file, copy_name)] последнего sync/setup

    def is_repo(self):
        try:
            out, _, code = run_git(["rev-parse", "--is-inside-work-tree"], self.folder,
                                   check=False, use_token=False)
            return code == 0 and out == "true"
        except GitNotFound:
            return False

    def branch(self):
        out, _, code = run_git(["rev-parse", "--abbrev-ref", "HEAD"], self.folder,
                               check=False, use_token=False)
        if code != 0 or out == "HEAD":
            return "main"
        return out

    def has_remote(self):
        out, _, code = run_git(["remote"], self.folder, check=False, use_token=False)
        return code == 0 and "origin" in out.split()

    def remote_url(self):
        out, _, code = run_git(["remote", "get-url", "origin"], self.folder,
                               check=False, use_token=False)
        return out if code == 0 else ""

    def changes_count(self):
        out, _, code = run_git(["status", "--porcelain"], self.folder,
                               check=False, use_token=False)
        if code != 0:
            return 0
        return len([l for l in out.splitlines() if l.strip()])

    def ahead_count(self):
        branch = self.branch()
        out, _, code = run_git(["rev-list", "--count", f"origin/{branch}..HEAD"],
                               self.folder, check=False, use_token=False)
        return int(out) if code == 0 and out.isdigit() else 0

    def behind_count(self):
        branch = self.branch()
        out, _, code = run_git(["rev-list", "--count", f"HEAD..origin/{branch}"],
                               self.folder, check=False, use_token=False)
        return int(out) if code == 0 and out.isdigit() else 0

    def fetch(self):
        _, err, code = run_git(["fetch", "origin"], self.folder, check=False)
        return code == 0, err

    def ensure_identity(self):
        out, _, _ = run_git(["config", "user.name"], self.folder, check=False, use_token=False)
        if not out:
            run_git(["config", "user.name", os.environ.get("USERNAME", "GitSync")],
                    self.folder, use_token=False)
        out, _, _ = run_git(["config", "user.email"], self.folder, check=False, use_token=False)
        if not out:
            run_git(["config", "user.email",
                     f"{os.environ.get('USERNAME', 'user')}@{socket.gethostname()}"],
                    self.folder, use_token=False)

    def _conflict_copy_name(self, path):
        """Имя для копии локальной версии: 'file (conflict HOST 2026-07-16 15-04).txt'."""
        base, ext = os.path.splitext(path)
        stamp = datetime.now().strftime("%Y-%m-%d %H-%M")
        host = socket.gethostname()
        cand = f"{base} (conflict {host} {stamp}){ext}"
        n = 2
        while os.path.exists(os.path.join(self.folder, cand)):
            cand = f"{base} (conflict {host} {stamp} {n}){ext}"
            n += 1
        return cand

    def _merge_keep_both(self, branch, log):
        """Слить origin/branch, разрешая конфликты без потери данных:
        версия с сервера остаётся под своим именем, локальная сохраняется копией."""
        self.last_conflicts = []
        _, err, code = run_git(
            ["merge", "--no-edit", "--allow-unrelated-histories", f"origin/{branch}"],
            self.folder, check=False, use_token=False)
        if code == 0:
            return
        out, _, _ = run_git(["diff", "--name-only", "--diff-filter=U"], self.folder,
                            check=False, use_token=False)
        files = [f for f in out.splitlines() if f.strip()]
        if not files:
            run_git(["merge", "--abort"], self.folder, check=False, use_token=False)
            raise GitError(tr("Pull failed:\n{err}", err=err))

        for f in files:
            ours, oc = run_git_raw(["show", f":2:{f}"], self.folder)    # локальная
            _theirs, tc = run_git_raw(["show", f":3:{f}"], self.folder)  # с сервера
            fs_path = os.path.join(self.folder, f.replace("/", os.sep))
            if oc == 0 and tc == 0:
                # изменён с обеих сторон: локальную — в копию, серверную — под имя
                copy_rel = self._conflict_copy_name(f)
                copy_path = os.path.join(self.folder, copy_rel.replace("/", os.sep))
                os.makedirs(os.path.dirname(copy_path) or self.folder, exist_ok=True)
                with open(copy_path, "wb") as fh:
                    fh.write(ours)
                run_git(["checkout", "--theirs", "--", f], self.folder, use_token=False)
                run_git(["add", "--", f, copy_rel], self.folder, use_token=False)
                self.last_conflicts.append((f, copy_rel))
                log(tr("Conflict in {file}: both versions kept (copy: {copy})",
                       file=f, copy=copy_rel))
            elif oc == 0:
                # на сервере удалён, у нас изменён — оставляем наш
                with open(fs_path, "wb") as fh:
                    fh.write(ours)
                run_git(["add", "--", f], self.folder, use_token=False)
                self.last_conflicts.append((f, f))
                log(tr("Conflict in {file}: both versions kept (copy: {copy})",
                       file=f, copy=f))
            else:
                # у нас удалён, на сервере изменён — берём серверный
                run_git(["checkout", "--theirs", "--", f], self.folder, use_token=False)
                run_git(["add", "--", f], self.folder, use_token=False)
        _, err, code = run_git(["commit", "--no-edit"], self.folder,
                               check=False, use_token=False)
        if code != 0:
            run_git(["merge", "--abort"], self.folder, check=False, use_token=False)
            raise GitError(tr("Merge failed:\n{err}", err=err))

    def _integrate(self, branch, log):
        """Забрать origin/branch: сперва чистый rebase, при конфликте — keep-both merge."""
        self.last_conflicts = []
        _, err, code = run_git(["pull", "--rebase", "--autostash", "origin", branch],
                               self.folder, check=False)
        if code == 0:
            return
        low = (err or "").lower()
        if "couldn't find remote ref" in low or "no such ref" in low:
            log(tr("Remote branch doesn't exist yet — it will be created on push."))
            return
        conflictish = any(s in low for s in (
            "conflict", "could not apply", "unrelated histories",
            "would be overwritten"))
        if not conflictish:
            raise GitError(tr("Pull failed:\n{err}", err=err))
        run_git(["rebase", "--abort"], self.folder, check=False, use_token=False)
        log(tr("Conflict — keeping both versions..."))
        self._merge_keep_both(branch, log)

    def set_remote(self, remote_url, log):
        """Change or remove the origin URL."""
        if remote_url:
            if self.has_remote():
                run_git(["remote", "set-url", "origin", remote_url], self.folder,
                        use_token=False)
            else:
                run_git(["remote", "add", "origin", remote_url], self.folder,
                        use_token=False)
            log(tr("Remote repository: {url}", url=remote_url))
        elif self.has_remote():
            run_git(["remote", "remove", "origin"], self.folder, use_token=False)
            log(tr("Remote link removed."))

    def setup(self, remote_url, log):
        """Connect a folder: init/clone, bind origin, pull the remote state."""
        folder = self.folder
        if not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)

        if self.is_repo():
            log(tr("Folder is already a git repository."))
        elif remote_url and not os.listdir(folder):
            log(tr("Folder is empty — cloning repository..."))
            run_git(["clone", remote_url, folder], None)
            log(tr("Clone finished."))
            self.ensure_identity()
            return
        else:
            log(tr("Initializing git repository in the folder..."))
            run_git(["init", "-b", "main"], folder, use_token=False)

        self.ensure_identity()

        if remote_url:
            self.set_remote(remote_url, log)
            log(tr("Checking remote repository..."))
            _, _, code = run_git(["fetch", "origin"], folder, check=False)
            if code != 0:
                log(tr("Could not fetch remote data (the repository may be empty — that's fine)."))
            else:
                branch = self.branch()
                _, _, code = run_git(["rev-parse", f"origin/{branch}"], folder,
                                     check=False, use_token=False)
                if code == 0:
                    log(tr("Remote repository already has files — merging with local ones..."))
                    # сначала фиксируем локальное состояние, чтобы совпадающие
                    # имена файлов стали обычными конфликтами (и решились keep-both)
                    run_git(["add", "-A"], folder, use_token=False)
                    if self.changes_count() > 0:
                        log(tr("Saving local files before merging..."))
                        run_git(["commit", "-m",
                                 f"Initial state from {socket.gethostname()}"],
                                folder, check=False, use_token=False)
                    self._integrate(branch, log)
        log(tr("Setup finished."))

    def sync(self, log):
        """add -> commit -> pull --rebase -> push. True if something was pushed."""
        folder = self.folder
        branch = self.branch()

        run_git(["add", "-A"], folder, use_token=False)
        if self.changes_count() > 0:
            msg = f"Sync from {socket.gethostname()} {datetime.now():%Y-%m-%d %H:%M:%S}"
            _, err, code = run_git(["commit", "-m", msg], folder, check=False, use_token=False)
            if code == 0:
                log(tr("Commit created: {msg}", msg=msg))
            elif "nothing to commit" not in (err or ""):
                raise GitError(err)

        if not self.has_remote():
            log(tr("No remote configured — changes saved locally only."))
            return False

        # ни одного коммита ещё нет (пустая папка + пустой репозиторий)
        _, _, head_code = run_git(["rev-parse", "HEAD"], folder,
                                  check=False, use_token=False)
        if head_code != 0:
            log(tr("Nothing to push — everything is in sync."))
            return False

        log(tr("Pulling changes..."))
        self._integrate(branch, log)

        if self.ahead_count() > 0 or run_git(
                ["rev-parse", f"origin/{branch}"], folder, check=False, use_token=False)[2] != 0:
            log(tr("Pushing changes..."))
            _, err, code = run_git(["push", "-u", "origin", branch], folder, check=False)
            if code != 0:
                raise GitError(tr("Push failed:\n{err}", err=err))
            log(tr("Changes pushed."))
            return True
        log(tr("Nothing to push — everything is in sync."))
        return False


# ---------------------------------------------------------------- GitHub API

class GitHubError(Exception):
    pass


class GitHub:
    API = "https://api.github.com"

    def __init__(self, token):
        if not token:
            raise GitHubError(tr("GitHub token is not set"))
        self.token = token

    def _request(self, method, path, data=None):
        req = urllib.request.Request(
            self.API + path,
            method=method,
            data=json.dumps(data).encode() if data is not None else None,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": APP_NAME,
                "Content-Type": "application/json",
            })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read()).get("message", "")
            except Exception:
                detail = ""
            if e.code == 401:
                raise GitHubError(tr("GitHub rejected the token (401). Check the token."))
            if e.code == 403:
                raise GitHubError(tr(
                    "Permission denied (403): {detail}. The token needs the repo scope "
                    "(and delete_repo for deletion).", detail=detail))
            if e.code == 404:
                raise GitHubError(tr("Not found (404): {detail}", detail=detail))
            raise GitHubError(tr("GitHub replied {code}: {detail}",
                                 code=e.code, detail=detail))
        except urllib.error.URLError as e:
            raise GitHubError(tr("No connection to GitHub: {reason}", reason=e.reason))

    def user(self):
        return self._request("GET", "/user")

    def repos(self):
        """Все свои репозитории (с постраничной загрузкой)."""
        result, page = [], 1
        while True:
            chunk = self._request(
                "GET", f"/user/repos?per_page=100&page={page}&affiliation=owner&sort=updated")
            if not chunk:
                break
            result.extend(chunk)
            if len(chunk) < 100:
                break
            page += 1
        return result

    def create_repo(self, name, private=True, description=""):
        return self._request("POST", "/user/repos", {
            "name": name, "private": private, "description": description,
            "auto_init": False})

    def delete_repo(self, full_name):
        self._request("DELETE", f"/repos/{full_name}")


# ---------------------------------------------------------------- конфигурация

DEFAULT_PROFILE = {
    "id": "",
    "name": "",
    "folder": "",
    "remote_url": "",
    "auto_sync": False,
    "debounce_seconds": 10,
    "timer_enabled": False,
    "timer_minutes": 30,
    "remote_check": True,       # лёгкий fetch: быстро замечать чужие изменения
    "remote_check_minutes": 1,
}


def new_profile(name, folder, remote_url=""):
    p = dict(DEFAULT_PROFILE)
    p["id"] = uuid.uuid4().hex[:12]
    p["name"] = name or os.path.basename(folder) or folder
    p["folder"] = folder
    p["remote_url"] = remote_url
    return p


class Config:
    def __init__(self):
        self.profiles = []
        self.start_minimized = False
        self.language = "en"
        self.load()

    def load(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.profiles = data.get("profiles", [])
            self.start_minimized = data.get("start_minimized", False)
            self.language = data.get("language", "en")
        except Exception:
            self.profiles = []
        # дополняем недостающие поля у старых профилей
        for p in self.profiles:
            for k, v in DEFAULT_PROFILE.items():
                p.setdefault(k, v)
        self._migrate_v1()

    def _migrate_v1(self):
        """Подхватить настройки первой версии (config.json рядом со скриптом)."""
        if self.profiles:
            return
        old_path = os.path.join(os.path.dirname(os.path.abspath(
            sys.argv[0] if getattr(sys, "frozen", False) else __file__)), "config.json")
        try:
            with open(old_path, "r", encoding="utf-8") as f:
                old = json.load(f)
            if old.get("folder"):
                p = new_profile("", old["folder"], old.get("remote_url", ""))
                p["auto_sync"] = old.get("auto_sync", False)
                p["debounce_seconds"] = old.get("debounce_seconds", 10)
                p["timer_enabled"] = old.get("timer_enabled", False)
                p["timer_minutes"] = old.get("timer_minutes", 30)
                self.profiles.append(p)
                self.save()
        except Exception:
            pass

    def save(self):
        ensure_app_data()
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"profiles": self.profiles,
                       "start_minimized": self.start_minimized,
                       "language": self.language},
                      f, ensure_ascii=False, indent=2)

    def get(self, profile_id):
        for p in self.profiles:
            if p["id"] == profile_id:
                return p
        return None

    def remove(self, profile_id):
        self.profiles = [p for p in self.profiles if p["id"] != profile_id]
        self.save()
