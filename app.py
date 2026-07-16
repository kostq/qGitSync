# -*- coding: utf-8 -*-
"""
qGitSync — sync folders with GitHub. PySide6 UI.

Run:  py app.py   (or the built qGitSync.exe)
"""

import os
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox,
    QPlainTextEdit, QProgressDialog, QPushButton, QRadioButton, QSpinBox,
    QSplitter, QStatusBar, QSystemTrayIcon, QTableWidget, QTableWidgetItem,
    QToolBar, QVBoxLayout, QWidget,
)

import core
import i18n
from core import Config, GitHub, Repo, new_profile
from i18n import tr

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

APP_TITLE = "qGitSync"
INSTANCE_KEY = "qGitSync-single-instance"

STATE_ICON = {
    "idle": "⚪", "watching": "🟢", "syncing": "🔄",
    "ok": "🟢", "error": "🔴", "conflict": "⚠️",
}


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


# ================================================================ background

class Signals(QObject):
    log = Signal(str, str)          # profile_id, log line
    state = Signal(str, str)        # profile_id, state
    stats = Signal(str, str)        # profile_id, short status for the list
    global_msg = Signal(str)        # status bar message
    git_progress = Signal(int)      # MinGit download progress, %
    git_done = Signal(bool, str)    # MinGit install result
    notice = Signal(str, str)       # profile_id, tray notification text


if HAS_WATCHDOG:
    class _FsHandler(FileSystemEventHandler):
        def __init__(self, callback):
            self.callback = callback

        def on_any_event(self, event):
            p = (event.src_path or "") + (getattr(event, "dest_path", "") or "")
            sep = os.sep
            if f"{sep}.git{sep}" in p or p.endswith(f"{sep}.git"):
                return
            self.callback()


class ProfileRunner:
    """One folder: watchdog + debounce + schedule + sync worker."""

    def __init__(self, profile, signals: Signals):
        self.p = dict(profile)
        self.signals = signals
        self.repo = Repo(self.p["folder"])
        self.syncing = False
        self.pending = False
        self.error_state = None
        self.ignore_until = 0.0
        self.last_sync = None
        self.last_remote_check = None
        self.checking_remote = False
        self.remote_dead_notified = False
        self.debounce = None
        self.observer = None
        self.apply_settings(profile)

    def log(self, msg):
        self.signals.log.emit(self.p["id"], f"[{datetime.now():%H:%M:%S}] {msg}")

    def set_state(self, state):
        self.signals.state.emit(self.p["id"], state)

    def apply_settings(self, profile):
        if profile.get("remote_url") != self.p.get("remote_url"):
            self.remote_dead_notified = False  # ссылку сменили — проверяем заново
            self.error_state = None
        self.p = dict(profile)
        self.repo = Repo(self.p["folder"])
        self._restart_watcher()

    def _restart_watcher(self):
        if self.observer:
            self.observer.stop()
            self.observer = None
        if self.p["auto_sync"] and HAS_WATCHDOG and os.path.isdir(self.p["folder"]):
            self.observer = Observer()
            self.observer.daemon = True
            self.observer.schedule(_FsHandler(self._on_change), self.p["folder"],
                                   recursive=True)
            self.observer.start()
            self.log(tr("Watching enabled (sync {sec} sec. after changes)",
                        sec=self.p["debounce_seconds"]))
        if not self.syncing:
            self.set_state("watching" if self.p["auto_sync"] else "idle")

    def stop(self):
        if self.observer:
            self.observer.stop()
            self.observer = None
        if self.debounce:
            self.debounce.cancel()

    def _on_change(self):
        if self.syncing or time.time() < self.ignore_until:
            return
        if self.debounce:
            self.debounce.cancel()
        self.debounce = threading.Timer(
            max(3, self.p["debounce_seconds"]),
            lambda: self.request_sync(tr("changes in folder")))
        self.debounce.daemon = True
        self.debounce.start()

    def timer_due(self):
        if not self.p["timer_enabled"] or self.syncing:
            return False
        interval = max(1, self.p["timer_minutes"]) * 60
        return self.last_sync is None or time.time() - self.last_sync >= interval

    def remote_due(self):
        if not self.p.get("remote_check") or self.syncing or self.checking_remote:
            return False
        interval = max(1, self.p.get("remote_check_minutes", 1)) * 60
        return (self.last_remote_check is None
                or time.time() - self.last_remote_check >= interval)

    def check_remote(self):
        """Лёгкая проверка: fetch + сравнение. Полный синк — только если на
        сервере есть новые коммиты. Мёртвая ссылка (реп удалён/нет доступа) —
        помечаем папку и сообщаем один раз; сетевые сбои игнорируем молча."""
        self.checking_remote = True

        def worker():
            try:
                self.last_remote_check = time.time()
                if not self.repo.has_remote():
                    return
                ok, err = self.repo.fetch()
                if ok:
                    if self.remote_dead_notified or self.error_state == "error":
                        self.remote_dead_notified = False
                        self.error_state = None
                        self.set_state("watching" if self.p["auto_sync"] else "idle")
                    if self.repo.behind_count() > 0:
                        self.request_sync(tr("remote changes"))
                elif core.is_dead_remote_error(err) and not self.remote_dead_notified:
                    self.remote_dead_notified = True
                    self.error_state = "error"
                    self.log(tr(
                        "GitHub repository not found or access denied — check the link "
                        "({url})", url=self.p.get("remote_url", "")))
                    self.set_state("error")
                    self.signals.notice.emit(
                        self.p["id"],
                        tr("{name}: GitHub repository not found", name=self.p["name"]))
            except Exception:
                pass
            finally:
                self.checking_remote = False
        threading.Thread(target=worker, daemon=True).start()

    def request_sync(self, reason):
        if self.syncing:
            self.pending = True
            return
        threading.Thread(target=self._worker, args=(reason,), daemon=True).start()

    def _worker(self, reason):
        self.syncing = True
        self.error_state = None
        self.set_state("syncing")
        try:
            self.log(tr("— Sync ({reason}) —", reason=reason))
            self.repo.sync(self.log)
            self.last_sync = time.time()
            self.set_state("ok")
            if self.repo.last_conflicts:
                self.signals.notice.emit(
                    self.p["id"],
                    tr("{name}: conflict — both versions kept", name=self.p["name"]))
        except Exception as e:
            self.error_state = "conflict" if "CONFLICT" in str(e) or "КОНФЛИКТ" in str(e) \
                else "error"
            self.log(tr("ERROR: {err}", err=e))
            self.set_state(self.error_state)
        finally:
            self.syncing = False
            self.ignore_until = time.time() + 3
        if self.pending:
            self.pending = False
            self.request_sync(tr("queued changes"))

    def refresh_stats(self):
        """Short summary for the folder list (called from a background thread)."""
        try:
            if not self.repo.is_repo():
                self.signals.stats.emit(self.p["id"], tr("not set up"))
                return
            n = self.repo.changes_count()
            ahead = self.repo.ahead_count()
            parts = []
            if n:
                parts.append(tr("changes: {n}", n=n))
            if ahead:
                parts.append(tr("not pushed: {n}", n=ahead))
            self.signals.stats.emit(self.p["id"], ", ".join(parts) or tr("in sync"))
        except Exception:
            pass


# ================================================================ dialogs

class TokenDialog(QDialog):
    check_done = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("GitHub token"))
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel(tr(
            "A token lets the app create and list your repositories\n"
            "and push changes without asking for a password.\n\n"
            "1. Click “Open the tokens page” (github.com)\n"
            "2. Generate new token (classic), check scopes: repo, delete_repo\n"
            "3. Copy the token and paste it here")))

        btn_open = QPushButton(tr("Open the tokens page in a browser"))
        btn_open.clicked.connect(lambda: webbrowser.open(
            "https://github.com/settings/tokens/new?scopes=repo,delete_repo&description=qGitSync"))
        lay.addWidget(btn_open)

        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.Password)
        self.edit.setPlaceholderText("ghp_...")
        tok = core.load_token()
        if tok:
            self.edit.setText(tok)
        lay.addWidget(self.edit)

        self.status = QLabel("")
        lay.addWidget(self.status)

        row = QHBoxLayout()
        self.btn_check = QPushButton(tr("Check and save"))
        self.btn_check.clicked.connect(self.check_and_save)
        btn_del = QPushButton(tr("Delete token"))
        btn_del.clicked.connect(self.remove_token)
        btn_close = QPushButton(tr("Close"))
        btn_close.clicked.connect(self.reject)
        row.addWidget(self.btn_check)
        row.addWidget(btn_del)
        row.addStretch()
        row.addWidget(btn_close)
        lay.addLayout(row)
        self.check_done.connect(self._done)

    def check_and_save(self):
        token = self.edit.text().strip()
        if not token:
            self.status.setText(tr("Enter the token."))
            return
        self.btn_check.setEnabled(False)
        self.status.setText(tr("Checking the token..."))

        def worker():
            try:
                user = GitHub(token).user()
                core.save_token(token)
                ok, msg = True, tr("Token accepted. Signed in as {login}.",
                                   login=user.get("login"))
            except Exception as e:
                ok, msg = False, str(e)
            self.check_done.emit(ok, msg)
        threading.Thread(target=worker, daemon=True).start()

    def _done(self, ok, msg):
        self.btn_check.setEnabled(True)
        self.status.setText(msg)
        if ok:
            QTimer.singleShot(1200, self.accept)

    def remove_token(self):
        core.delete_token()
        self.edit.clear()
        self.status.setText(tr("Token removed from Windows credential storage."))


class RepoManagerDialog(QDialog):
    """GitHub repositories: list, create, delete, copy link."""

    repos_loaded = Signal(list)
    op_done = Signal(bool, str)

    def __init__(self, parent, config: Config):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle(tr("My GitHub repositories"))
        self.resize(680, 420)
        lay = QVBoxLayout(self)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            [tr("Name"), tr("Access"), tr("Updated"), tr("Link")])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(self.table)

        self.status = QLabel("")
        lay.addWidget(self.status)

        row = QHBoxLayout()
        b_refresh = QPushButton(tr("Refresh"))
        b_refresh.clicked.connect(self.load_repos)
        b_create = QPushButton(tr("Create repository..."))
        b_create.clicked.connect(self.create_repo)
        b_copy = QPushButton(tr("Copy link"))
        b_copy.clicked.connect(self.copy_url)
        b_delete = QPushButton(tr("Delete..."))
        b_delete.clicked.connect(self.delete_repo)
        b_close = QPushButton(tr("Close"))
        b_close.clicked.connect(self.accept)
        for b in (b_refresh, b_create, b_copy, b_delete):
            row.addWidget(b)
        row.addStretch()
        row.addWidget(b_close)
        lay.addLayout(row)

        self.repos_loaded.connect(self.fill_table)
        self.op_done.connect(self.on_op_done)
        self.load_repos()

    def gh(self):
        return GitHub(core.load_token())

    def load_repos(self):
        self.status.setText(tr("Loading repository list..."))

        def worker():
            try:
                self.repos_loaded.emit(self.gh().repos())
            except Exception as e:
                self.op_done.emit(False, str(e))
        threading.Thread(target=worker, daemon=True).start()

    def fill_table(self, repos):
        self.table.setRowCount(0)
        for r in repos:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(r["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(
                tr("private") if r["private"] else tr("public")))
            self.table.setItem(row, 2, QTableWidgetItem((r.get("pushed_at") or "")[:10]))
            self.table.setItem(row, 3, QTableWidgetItem(r["clone_url"]))
        self.table.resizeColumnsToContents()
        self.status.setText(tr("Repositories: {n}", n=len(repos)))

    def on_op_done(self, ok, msg):
        self.status.setText(msg)
        if ok:
            self.load_repos()

    def selected_repo(self):
        row = self.table.currentRow()
        if row < 0:
            return None, None
        return self.table.item(row, 0).text(), self.table.item(row, 3).text()

    def copy_url(self):
        _, url = self.selected_repo()
        if url:
            QApplication.clipboard().setText(url)
            self.status.setText(tr("Copied: {url}", url=url))

    def create_repo(self):
        name, ok = QInputDialog.getText(self, tr("New repository"),
                                        tr("Name (Latin letters, no spaces):"))
        if not ok or not name.strip():
            return
        name = name.strip().replace(" ", "-")
        private = QMessageBox.question(
            self, tr("Visibility"),
            tr("Make the repository private (visible only to you)?"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes

        def worker():
            try:
                r = self.gh().create_repo(name, private=private)
                self.op_done.emit(True, tr("Created: {url}", url=r["clone_url"]))
            except Exception as e:
                self.op_done.emit(False, str(e))
        threading.Thread(target=worker, daemon=True).start()

    def delete_repo(self):
        name, url = self.selected_repo()
        if not name:
            return
        typed, ok = QInputDialog.getText(
            self, tr("Delete repository"),
            tr("WARNING: the repository “{name}” will be deleted on GitHub PERMANENTLY\n"
               "together with its history. Local files are not affected.\n\n"
               "Type its name to confirm:", name=name))
        if not ok or typed.strip() != name:
            self.status.setText(tr("Deletion cancelled."))
            return

        def worker():
            try:
                gh = self.gh()
                login = gh.user()["login"]
                gh.delete_repo(f"{login}/{name}")
                notes = [tr("Repository {name} deleted.", name=name)]
                # unlink folders that pointed at the deleted repository
                base = url[:-4] if url.endswith(".git") else url
                for p in self.config.profiles:
                    pu = (p["remote_url"] or "").rstrip("/")
                    if pu and pu in (url, base):
                        p["remote_url"] = ""
                        try:
                            Repo(p["folder"]).set_remote("", lambda m: None)
                        except Exception:
                            pass
                        notes.append(tr(
                            "Unlinked folder “{name}” from the deleted repository.",
                            name=p["name"]))
                self.config.save()
                self.op_done.emit(True, " ".join(notes))
            except Exception as e:
                self.op_done.emit(False, str(e))
        threading.Thread(target=worker, daemon=True).start()


class AddFolderDialog(QDialog):
    """Add-folder wizard: local folder + how to bind it to GitHub."""

    repos_loaded = Signal(list)
    status_msg = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Add a folder"))
        self.setMinimumWidth(560)
        self.result_profile = None
        self.create_repo_name = None
        self.create_repo_private = True

        lay = QVBoxLayout(self)
        form = QFormLayout()

        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit()
        btn_browse = QPushButton(tr("Browse..."))
        btn_browse.clicked.connect(self.browse)
        folder_row.addWidget(self.folder_edit)
        folder_row.addWidget(btn_browse)
        form.addRow(tr("Folder") + ":", folder_row)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(tr("(default — folder name)"))
        form.addRow(tr("Name:"), self.name_edit)
        lay.addLayout(form)

        grp = QGroupBox(tr("GitHub repository"))
        g = QVBoxLayout(grp)

        self.rb_new = QRadioButton(tr("Create a new repository (token required)"))
        self.rb_existing = QRadioButton(tr("Pick one of my repositories (token required)"))
        self.rb_url = QRadioButton(tr("Enter a link manually"))
        self.rb_none = QRadioButton(tr("No GitHub for now (local only)"))
        self.rb_new.setChecked(True)

        g.addWidget(self.rb_new)
        new_row = QHBoxLayout()
        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText(tr("new repository name"))
        self.new_private = QCheckBox(tr("private"))
        self.new_private.setChecked(True)
        new_row.addSpacing(24)
        new_row.addWidget(self.new_name)
        new_row.addWidget(self.new_private)
        g.addLayout(new_row)

        g.addWidget(self.rb_existing)
        ex_row = QHBoxLayout()
        self.repo_combo = QComboBox()
        btn_load = QPushButton(tr("Load list"))
        btn_load.clicked.connect(self.load_repos)
        ex_row.addSpacing(24)
        ex_row.addWidget(self.repo_combo, 1)
        ex_row.addWidget(btn_load)
        g.addLayout(ex_row)

        g.addWidget(self.rb_url)
        url_row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://github.com/user/repository.git")
        url_row.addSpacing(24)
        url_row.addWidget(self.url_edit)
        g.addLayout(url_row)

        g.addWidget(self.rb_none)
        lay.addWidget(grp)

        self.status = QLabel("")
        lay.addWidget(self.status)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(tr("Add"))
        bb.button(QDialogButtonBox.Cancel).setText(tr("Cancel"))
        bb.accepted.connect(self.on_accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        self.repos_loaded.connect(self.fill_repos)
        self.status_msg.connect(self.status.setText)
        self.folder_edit.textChanged.connect(self.suggest_names)

    def browse(self):
        folder = QFileDialog.getExistingDirectory(self, tr("Select a folder"))
        if folder:
            self.folder_edit.setText(os.path.normpath(folder))

    def suggest_names(self, text):
        base = os.path.basename(text.strip().rstrip("\\/"))
        if base and not self.new_name.text():
            self.new_name.setPlaceholderText(base.lower().replace(" ", "-"))

    def load_repos(self):
        token = core.load_token()
        if not token:
            self.status.setText(tr("Save a GitHub token first (toolbar button)."))
            return
        self.status.setText(tr("Loading list..."))

        def worker():
            try:
                self.repos_loaded.emit(GitHub(token).repos())
            except Exception as e:
                self.status_msg.emit(str(e))
        threading.Thread(target=worker, daemon=True).start()

    def fill_repos(self, repos):
        self.repo_combo.clear()
        for r in repos:
            self.repo_combo.addItem(r["full_name"], r["clone_url"])
        self.status.setText(tr("Repositories loaded: {n}", n=len(repos)))
        self.rb_existing.setChecked(True)

    def on_accept(self):
        folder = self.folder_edit.text().strip()
        if not folder:
            self.status.setText(tr("Choose a folder."))
            return
        name = self.name_edit.text().strip() or os.path.basename(folder)

        remote = ""
        if self.rb_new.isChecked():
            if not core.load_token():
                self.status.setText(tr("A token is required to create a repository."))
                return
            repo_name = (self.new_name.text().strip()
                         or self.new_name.placeholderText().strip())
            if not repo_name:
                self.status.setText(tr("Enter a name for the new repository."))
                return
            self.create_repo_name = repo_name.replace(" ", "-")
            self.create_repo_private = self.new_private.isChecked()
        elif self.rb_existing.isChecked():
            remote = self.repo_combo.currentData() or ""
            if not remote:
                self.status.setText(tr("Load the list and pick a repository."))
                return
        elif self.rb_url.isChecked():
            remote = self.url_edit.text().strip()
            if not remote:
                self.status.setText(tr("Paste the repository link."))
                return

        self.result_profile = new_profile(name, folder, remote)
        self.accept()


# ================================================================ main window

class MainWindow(QMainWindow):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.setWindowTitle(tr("qGitSync — sync folders with GitHub"))
        self.resize(920, 620)

        self.signals = Signals()
        self.runners = {}
        self.logs = {}
        self.quitting = False
        self.tray_hint_shown = False

        icon_file = resource_path("icon.ico")
        self.app_icon = QIcon(icon_file) if os.path.exists(icon_file) else \
            self.style().standardIcon(self.style().StandardPixmap.SP_DriveNetIcon)
        self.setWindowIcon(self.app_icon)

        self.build_ui()
        self.build_tray()

        self.signals.log.connect(self.on_log)
        self.signals.state.connect(self.on_state)
        self.signals.stats.connect(self.on_stats)
        self.signals.global_msg.connect(self.statusBar().showMessage)
        self.signals.notice.connect(
            lambda pid, text: self.tray.showMessage(
                APP_TITLE, text, QSystemTrayIcon.Information, 5000))

        for p in self.config.profiles:
            self.add_profile_item(p)
            self.runners[p["id"]] = ProfileRunner(p, self.signals)
        if self.list.count():
            self.list.setCurrentRow(0)

        self.tick_timer = QTimer(self, interval=2000, timeout=self.on_tick)
        self.tick_timer.start()
        self.stats_timer = QTimer(self, interval=6000, timeout=self.refresh_stats)
        self.stats_timer.start()

        QTimer.singleShot(300, self.check_git)

    # ---------------- UI

    def build_ui(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(tb)

        a_add = QAction("➕ " + tr("Add folder"), self, triggered=self.add_folder)
        a_sync_all = QAction("🔄 " + tr("Sync all"), self, triggered=self.sync_all)
        a_repos = QAction("📚 " + tr("GitHub repositories"), self,
                          triggered=self.open_repo_manager)
        a_token = QAction("🔑 " + tr("GitHub token"), self, triggered=self.open_token_dialog)
        for a in (a_add, a_sync_all, a_repos, a_token):
            tb.addAction(a)

        menu = self.menuBar().addMenu(tr("Settings"))

        lang_menu = QMenu(tr("Language"), self)
        lang_group = QActionGroup(self)
        for code, label in i18n.LANGUAGES.items():
            act = QAction(label, self, checkable=True)
            act.setChecked(code == self.config.language)
            act.triggered.connect(lambda _=False, c=code: self.set_language(c))
            lang_group.addAction(act)
            lang_menu.addAction(act)
        menu.addMenu(lang_menu)

        self.act_autostart = QAction(tr("Run at Windows startup"), self,
                                     checkable=True, triggered=self.toggle_autostart)
        self.act_autostart.setChecked(self.is_autostart_enabled())
        menu.addAction(self.act_autostart)
        self.act_start_min = QAction(tr("Start minimized to tray"), self, checkable=True,
                                     triggered=self.toggle_start_minimized)
        self.act_start_min.setChecked(self.config.start_minimized)
        menu.addAction(self.act_start_min)
        menu.addSeparator()
        menu.addAction(QAction(tr("Exit"), self, triggered=self.quit_app))

        splitter = QSplitter()
        self.setCentralWidget(splitter)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(6, 6, 0, 6)
        ll.addWidget(QLabel(tr("Folders:")))
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self.on_select)
        ll.addWidget(self.list)
        splitter.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)

        self.grp = QGroupBox(tr("Folder"))
        form = QFormLayout(self.grp)
        self.lbl_folder = QLabel("—")
        self.lbl_folder.setTextInteractionFlags(Qt.TextSelectableByMouse)
        btn_open = QPushButton(tr("Open in Explorer"))
        btn_open.clicked.connect(self.open_in_explorer)
        frow = QHBoxLayout()
        frow.addWidget(self.lbl_folder, 1)
        frow.addWidget(btn_open)
        form.addRow(tr("Path:"), frow)
        self.lbl_remote = QLabel("—")
        self.lbl_remote.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow(tr("GitHub:"), self.lbl_remote)
        self.lbl_state = QLabel("—")
        form.addRow(tr("State:"), self.lbl_state)

        self.cb_auto = QCheckBox(tr("Automatically on changes, after"))
        self.sp_debounce = QSpinBox(minimum=3, maximum=600, suffix=tr(" sec."))
        arow = QHBoxLayout()
        arow.addWidget(self.cb_auto)
        arow.addWidget(self.sp_debounce)
        arow.addStretch()
        form.addRow(arow)

        self.cb_timer = QCheckBox(tr("On a schedule, every"))
        self.sp_timer = QSpinBox(minimum=1, maximum=1440, suffix=tr(" min."))
        trow = QHBoxLayout()
        trow.addWidget(self.cb_timer)
        trow.addWidget(self.sp_timer)
        trow.addStretch()
        form.addRow(trow)

        self.cb_remote = QCheckBox(tr("Check GitHub for changes, every"))
        self.sp_remote = QSpinBox(minimum=1, maximum=120, suffix=tr(" min."))
        rrow = QHBoxLayout()
        rrow.addWidget(self.cb_remote)
        rrow.addWidget(self.sp_remote)
        rrow.addStretch()
        form.addRow(rrow)

        for w in (self.cb_auto, self.cb_timer, self.cb_remote):
            w.toggled.connect(self.settings_changed)
        for w in (self.sp_debounce, self.sp_timer, self.sp_remote):
            w.valueChanged.connect(self.settings_changed)

        brow = QHBoxLayout()
        self.btn_sync = QPushButton(tr("Sync now"))
        self.btn_sync.clicked.connect(self.sync_selected)
        btn_link = QPushButton(tr("Change repository link..."))
        btn_link.clicked.connect(self.change_remote)
        btn_remove = QPushButton(tr("Remove from list..."))
        btn_remove.clicked.connect(self.remove_selected)
        brow.addWidget(self.btn_sync)
        brow.addWidget(btn_link)
        brow.addWidget(btn_remove)
        brow.addStretch()
        form.addRow(brow)
        rl.addWidget(self.grp)

        rl.addWidget(QLabel(tr("Log:")))
        self.log_view = QPlainTextEdit(readOnly=True)
        rl.addWidget(self.log_view, 1)
        splitter.addWidget(right)
        splitter.setSizes([260, 660])

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(tr("Ready"))
        self._loading_settings = False

    def build_tray(self):
        self.tray = QSystemTrayIcon(self.app_icon, self)
        menu = QMenu()
        menu.addAction(QAction(tr("Show qGitSync"), self, triggered=self.show_window))
        menu.addAction(QAction(tr("Sync all"), self, triggered=self.sync_all))
        menu.addSeparator()
        menu.addAction(QAction(tr("Exit"), self, triggered=self.quit_app))
        self.tray.setContextMenu(menu)
        self.tray.setToolTip(APP_TITLE)
        self.tray.activated.connect(
            lambda r: self.show_window() if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def set_language(self, code):
        self.config.language = code
        self.config.save()
        i18n.set_language(code)
        QMessageBox.information(self, APP_TITLE,
                                tr("Restart qGitSync to apply the language."))

    # ---------------- git bootstrap

    def check_git(self):
        if core.find_git():
            return
        ans = QMessageBox.question(
            self, tr("Git not found"),
            tr("qGitSync needs Git, and it was not found on this computer.\n\n"
               "Download portable Git (~60 MB) automatically?\n"
               "It is installed only for this app; the system is not changed."),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if ans != QMessageBox.Yes:
            self.statusBar().showMessage(tr("Git is not installed — sync is unavailable."))
            return

        dlg = QProgressDialog(tr("Downloading portable Git..."), None, 0, 100, self)
        dlg.setWindowTitle(tr("Installing Git"))
        dlg.setWindowModality(Qt.WindowModal)
        dlg.show()
        self.signals.git_progress.connect(dlg.setValue)

        def on_done(ok, msg):
            dlg.close()
            self.statusBar().showMessage(msg)
            if not ok:
                QMessageBox.warning(self, tr("Installing Git"), msg)
        self.signals.git_done.connect(on_done)

        def progress(done, total):
            if total:
                self.signals.git_progress.emit(int(done * 100 / total))

        def worker():
            try:
                exe = core.install_mingit(progress)
                self.signals.git_done.emit(True, tr("Git installed: {path}", path=exe))
            except Exception as e:
                self.signals.git_done.emit(False, tr("Failed to install Git: {err}", err=e))
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- profiles

    def add_profile_item(self, p):
        item = QListWidgetItem(f"⚪ {p['name']}")
        item.setData(Qt.UserRole, p["id"])
        item.setToolTip(p["folder"])
        self.list.addItem(item)

    def current_profile(self):
        item = self.list.currentItem()
        if not item:
            return None
        return self.config.get(item.data(Qt.UserRole))

    def item_by_id(self, pid):
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == pid:
                return self.list.item(i)
        return None

    def add_folder(self):
        dlg = AddFolderDialog(self)
        if dlg.exec() != QDialog.Accepted or not dlg.result_profile:
            return
        p = dlg.result_profile
        self.config.profiles.append(p)
        self.config.save()
        self.add_profile_item(p)
        self.logs[p["id"]] = ""
        self.list.setCurrentRow(self.list.count() - 1)

        def worker():
            try:
                if dlg.create_repo_name:
                    self.signals.log.emit(p["id"], tr(
                        "Creating repository {name} on GitHub...", name=dlg.create_repo_name))
                    r = GitHub(core.load_token()).create_repo(
                        dlg.create_repo_name, private=dlg.create_repo_private)
                    p["remote_url"] = r["clone_url"]
                    self.config.save()
                    self.signals.log.emit(p["id"], tr("Repository created: {url}",
                                                      url=p["remote_url"]))
                repo = Repo(p["folder"])
                repo.setup(p["remote_url"], lambda m: self.signals.log.emit(p["id"], m))
                runner = ProfileRunner(p, self.signals)
                self.runners[p["id"]] = runner
                self.signals.log.emit(p["id"], tr("Folder connected. Ready to sync."))
                runner.request_sync(tr("first sync"))
            except Exception as e:
                self.signals.log.emit(p["id"], tr("Setup ERROR: {err}", err=e))
                self.signals.state.emit(p["id"], "error")
        threading.Thread(target=worker, daemon=True).start()

    def remove_selected(self):
        p = self.current_profile()
        if not p:
            return
        ans = QMessageBox.question(
            self, tr("Remove folder"),
            tr("Remove “{name}” from the sync list?\n\n"
               "The folder, its files and the GitHub repository are NOT deleted —\n"
               "the app just stops watching it.", name=p["name"]),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        runner = self.runners.pop(p["id"], None)
        if runner:
            runner.stop()
        self.logs.pop(p["id"], None)
        item = self.item_by_id(p["id"])
        self.config.remove(p["id"])
        if item:
            self.list.takeItem(self.list.row(item))

    def change_remote(self):
        p = self.current_profile()
        if not p:
            return
        url, ok = QInputDialog.getText(self, tr("Repository link"),
                                       tr("Repository URL (empty — unlink):"),
                                       text=p["remote_url"])
        if not ok:
            return
        url = url.strip()
        p["remote_url"] = url
        self.config.save()
        self.lbl_remote.setText(url or tr("not linked"))

        def worker():
            try:
                Repo(p["folder"]).set_remote(
                    url, lambda m: self.signals.log.emit(p["id"], m))
                self.signals.log.emit(p["id"], tr("Link updated."))
            except Exception as e:
                self.signals.log.emit(p["id"], tr("ERROR: {err}", err=e))
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- selection / settings

    def on_select(self, *_):
        p = self.current_profile()
        self._loading_settings = True
        try:
            if not p:
                self.grp.setEnabled(False)
                self.log_view.setPlainText("")
                return
            self.grp.setEnabled(True)
            self.grp.setTitle(p["name"])
            self.lbl_folder.setText(p["folder"])
            self.lbl_remote.setText(p["remote_url"] or tr("not linked"))
            self.cb_auto.setChecked(p["auto_sync"])
            self.sp_debounce.setValue(p["debounce_seconds"])
            self.cb_timer.setChecked(p["timer_enabled"])
            self.sp_timer.setValue(p["timer_minutes"])
            self.cb_remote.setChecked(p.get("remote_check", True))
            self.sp_remote.setValue(p.get("remote_check_minutes", 1))
            self.log_view.setPlainText(self.logs.get(p["id"], ""))
            sb = self.log_view.verticalScrollBar()
            sb.setValue(sb.maximum())
        finally:
            self._loading_settings = False

    def settings_changed(self, *_):
        if self._loading_settings:
            return
        p = self.current_profile()
        if not p:
            return
        p["auto_sync"] = self.cb_auto.isChecked()
        p["debounce_seconds"] = self.sp_debounce.value()
        p["timer_enabled"] = self.cb_timer.isChecked()
        p["timer_minutes"] = self.sp_timer.value()
        p["remote_check"] = self.cb_remote.isChecked()
        p["remote_check_minutes"] = self.sp_remote.value()
        self.config.save()
        runner = self.runners.get(p["id"])
        if runner:
            runner.apply_settings(p)

    def open_in_explorer(self):
        p = self.current_profile()
        if p and os.path.isdir(p["folder"]):
            subprocess.Popen(["explorer", p["folder"]])

    # ---------------- sync

    def sync_selected(self):
        p = self.current_profile()
        if not p:
            return
        runner = self.runners.get(p["id"])
        if runner:
            runner.request_sync(tr("manual"))

    def sync_all(self):
        for runner in self.runners.values():
            runner.request_sync(tr("sync all"))

    def on_tick(self):
        for runner in self.runners.values():
            if runner.timer_due():
                runner.last_sync = time.time()
                runner.request_sync(tr("on schedule"))
            elif runner.remote_due():
                runner.check_remote()

    def refresh_stats(self):
        def worker():
            for runner in list(self.runners.values()):
                if not runner.syncing:
                    runner.refresh_stats()
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- signal handlers

    def on_log(self, pid, line):
        self.logs[pid] = (self.logs.get(pid, "") + line + "\n")[-100000:]
        p = self.current_profile()
        if p and p["id"] == pid:
            self.log_view.appendPlainText(line)

    def on_state(self, pid, state):
        item = self.item_by_id(pid)
        p = self.config.get(pid)
        if not item or not p:
            return
        icon = STATE_ICON.get(state, "⚪")
        item.setText(f"{icon} {p['name']}")
        names = {"idle": tr("idle"), "watching": tr("watching"),
                 "syncing": tr("syncing..."), "ok": tr("synced"),
                 "error": tr("error (see log)"), "conflict": tr("conflict (see log)")}
        cur = self.current_profile()
        if cur and cur["id"] == pid:
            self.lbl_state.setText(names.get(state, state))
        if state == "syncing":
            self.signals.global_msg.emit(tr("Syncing: {name}...", name=p["name"]))
        elif state in ("ok", "error", "conflict"):
            self.signals.global_msg.emit(
                f"{p['name']}: {names.get(state)} ({datetime.now():%H:%M:%S})")
        if state in ("error", "conflict"):
            self.tray.showMessage(tr("qGitSync — problem"),
                                  f"{p['name']}: {names.get(state)}",
                                  QSystemTrayIcon.Warning, 5000)

    def on_stats(self, pid, text):
        item = self.item_by_id(pid)
        p = self.config.get(pid)
        if item and p:
            item.setToolTip(f"{p['folder']}\n{text}")
        cur = self.current_profile()
        if cur and cur["id"] == pid:
            runner = self.runners.get(pid)
            if runner and not runner.syncing and not runner.error_state:
                self.lbl_state.setText(text)

    # ---------------- dialogs

    def open_token_dialog(self):
        TokenDialog(self).exec()

    def open_repo_manager(self):
        if not core.load_token():
            QMessageBox.information(
                self, tr("Token required"),
                tr("To manage repositories, save a GitHub token first\n"
                   "(the “GitHub token” button on the toolbar)."))
            return
        RepoManagerDialog(self, self.config).exec()
        # remote links may have been unlinked after a deletion
        self.on_select()

    # ---------------- autostart / tray / exit

    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def autostart_command(self):
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'
        script = os.path.abspath(sys.argv[0])
        pyw = sys.executable.replace("python.exe", "pythonw.exe")
        return f'"{pyw}" "{script}"'

    def is_autostart_enabled(self):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY) as key:
                winreg.QueryValueEx(key, APP_TITLE)
            return True
        except OSError:
            return False

    def toggle_autostart(self, enabled):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY, 0,
                                winreg.KEY_SET_VALUE) as key:
                if enabled:
                    winreg.SetValueEx(key, APP_TITLE, 0, winreg.REG_SZ,
                                      self.autostart_command())
                else:
                    try:
                        winreg.DeleteValue(key, APP_TITLE)
                    except OSError:
                        pass
            self.statusBar().showMessage(
                tr("Autostart enabled") if enabled else tr("Autostart disabled"))
        except Exception as e:
            QMessageBox.warning(self, tr("Autostart"),
                                tr("Failed to change autostart: {err}", err=e))
            self.act_autostart.setChecked(not enabled)

    def toggle_start_minimized(self, enabled):
        self.config.start_minimized = enabled
        self.config.save()

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event: QCloseEvent):
        if self.quitting:
            for r in self.runners.values():
                r.stop()
            event.accept()
            return
        event.ignore()
        self.hide()
        if not self.tray_hint_shown:
            self.tray_hint_shown = True
            self.tray.showMessage(
                tr("qGitSync keeps running in the tray"),
                tr("Sync continues in the background. Click the tray icon to open, "
                   "right-click → Exit to quit."),
                QSystemTrayIcon.Information, 4000)

    def quit_app(self):
        self.quitting = True
        self.close()
        QApplication.quit()


# ================================================================ single instance

def already_running():
    """True if another instance is running (and ask it to show its window)."""
    sock = QLocalSocket()
    sock.connectToServer(INSTANCE_KEY)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return True
    return False


def start_instance_server(win):
    QLocalServer.removeServer(INSTANCE_KEY)  # clear a stale socket after a crash
    server = QLocalServer(win)

    def on_connect():
        conn = server.nextPendingConnection()
        if conn:
            conn.disconnected.connect(conn.deleteLater)
        win.show_window()

    server.newConnection.connect(on_connect)
    server.listen(INSTANCE_KEY)
    return server


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)

    if already_running():
        return 0

    config = Config()
    i18n.set_language(config.language)

    app.setQuitOnLastWindowClosed(False)
    win = MainWindow(config)
    win._instance_server = start_instance_server(win)
    if config.start_minimized:
        win.hide()
    else:
        win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
