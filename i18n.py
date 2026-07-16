# -*- coding: utf-8 -*-
"""
qGitSync i18n — simple translation layer.

Keys are the English strings themselves; a missing translation falls back
to English. Use tr("text with {placeholder}", placeholder=value).
"""

LANGUAGES = {"en": "English", "ru": "Русский", "es": "Español"}

_current = "en"


def set_language(code):
    global _current
    _current = code if code in LANGUAGES else "en"


def current_language():
    return _current


def tr(text, **kwargs):
    table = _TABLES.get(_current)
    s = table.get(text, text) if table else text
    return s.format(**kwargs) if kwargs else s


_RU = {
    # ---- core: repo setup / sync
    "Folder is already a git repository.": "Папка уже является git-репозиторием.",
    "Folder is empty — cloning repository...": "Папка пустая — клонирую репозиторий...",
    "Clone finished.": "Клонирование завершено.",
    "Initializing git repository in the folder...": "Инициализирую git-репозиторий в папке...",
    "Remote repository: {url}": "Удалённый репозиторий: {url}",
    "Checking remote repository...": "Проверяю удалённый репозиторий...",
    "Could not fetch remote data (the repository may be empty — that's fine).":
        "Не удалось получить данные (возможно, репозиторий пустой — это нормально).",
    "Remote repository already has files — merging with local ones...":
        "В репозитории уже есть файлы — объединяю с локальными...",
    "Could not merge with the remote repository:\n{err}":
        "Не удалось объединить с удалённым репозиторием:\n{err}",
    "Setup finished.": "Настройка завершена.",
    "Commit created: {msg}": "Создан коммит: {msg}",
    "No remote configured — changes saved locally only.":
        "Удалённый репозиторий не настроен — изменения сохранены только локально.",
    "Pulling changes...": "Получаю изменения...",
    "Remote branch doesn't exist yet — it will be created on push.":
        "Удалённая ветка ещё не создана — будет создана при отправке.",
    "CONFLICT: the same file was changed on two computers.\n"
    "Sync stopped, resolve the conflict manually:\n{err}":
        "КОНФЛИКТ: один и тот же файл изменён на двух компьютерах.\n"
        "Синхронизация остановлена, разрешите конфликт вручную:\n{err}",
    "Pull failed:\n{err}": "Ошибка при получении изменений:\n{err}",
    "Pushing changes...": "Отправляю изменения...",
    "Push failed:\n{err}": "Ошибка отправки:\n{err}",
    "Changes pushed.": "Изменения отправлены.",
    "Nothing to push — everything is in sync.": "Отправлять нечего — всё синхронизировано.",
    "git not found": "git не найден",
    "Remote link removed.": "Ссылка на репозиторий отвязана.",
    "Conflict — keeping both versions...": "Конфликт — сохраняю обе версии...",
    "Conflict in {file}: both versions kept (copy: {copy})":
        "Конфликт в {file}: сохранены обе версии (копия: {copy})",
    "Merge failed:\n{err}": "Не удалось объединить:\n{err}",
    "Saving local files before merging...":
        "Сохраняю локальные файлы перед объединением...",

    # ---- core: GitHub API
    "GitHub token is not set": "Токен GitHub не задан",
    "GitHub rejected the token (401). Check the token.":
        "Токен не принят GitHub (401). Проверьте токен.",
    "Permission denied (403): {detail}. The token needs the repo scope "
    "(and delete_repo for deletion).":
        "Нет прав (403): {detail}. Токену нужны права repo (и delete_repo для удаления).",
    "Not found (404): {detail}": "Не найдено (404): {detail}",
    "GitHub replied {code}: {detail}": "GitHub ответил {code}: {detail}",
    "No connection to GitHub: {reason}": "Нет связи с GitHub: {reason}",
    "MinGit downloaded, but git.exe was not found after unpacking":
        "MinGit скачан, но git.exe не найден после распаковки",
    "keyring library is not installed": "Библиотека keyring не установлена",

    # ---- app: runner / log
    "Watching enabled (sync {sec} sec. after changes)":
        "Слежение включено (синк через {sec} сек. после изменений)",
    "— Sync ({reason}) —": "— Синхронизация ({reason}) —",
    "ERROR: {err}": "ОШИБКА: {err}",
    "changes in folder": "изменения в папке",
    "remote changes": "изменения на GitHub",
    "Check GitHub for changes, every": "Проверять изменения на GitHub, каждые",
    "{name}: conflict — both versions kept":
        "{name}: конфликт — сохранены обе версии",
    "GitHub repository not found or access denied — check the link ({url})":
        "Репозиторий на GitHub не найден или нет доступа — проверьте ссылку ({url})",
    "{name}: GitHub repository not found":
        "{name}: репозиторий на GitHub не найден",
    "on schedule": "по таймеру",
    "manual": "по кнопке",
    "sync all": "синхронизировать всё",
    "queued changes": "накопленные изменения",
    "first sync": "первая синхронизация",
    "not set up": "не настроено",
    "changes: {n}": "изменений: {n}",
    "not pushed: {n}": "не отправлено: {n}",
    "in sync": "синхронизировано",

    # ---- app: main window
    "qGitSync — sync folders with GitHub": "qGitSync — синхронизация папок с GitHub",
    "Add folder": "Добавить папку",
    "Sync all": "Синхронизировать всё",
    "GitHub repositories": "Репозитории GitHub",
    "GitHub token": "Токен GitHub",
    "Settings": "Настройки",
    "Language": "Язык",
    "Run at Windows startup": "Запускать при входе в Windows",
    "Start minimized to tray": "Запускать свёрнутым в трей",
    "Exit": "Выход",
    "Folders:": "Папки:",
    "Folder": "Папка",
    "Path:": "Путь:",
    "Open in Explorer": "Открыть в Проводнике",
    "GitHub:": "GitHub:",
    "not linked": "не привязан",
    "State:": "Состояние:",
    "Automatically on changes, after": "Автоматически при изменениях, через",
    " sec.": " сек.",
    "On a schedule, every": "По таймеру, каждые",
    " min.": " мин.",
    "Sync now": "Синхронизировать сейчас",
    "Change repository link...": "Сменить ссылку репозитория...",
    "Remove from list...": "Убрать из списка...",
    "Log:": "Журнал:",
    "Ready": "Готов",
    "Restart qGitSync to apply the language.":
        "Перезапустите qGitSync, чтобы применить язык.",
    "Autostart enabled": "Автозапуск включён",
    "Autostart disabled": "Автозапуск выключен",
    "Autostart": "Автозапуск",
    "Failed to change autostart: {err}": "Не удалось изменить автозапуск: {err}",
    "Show qGitSync": "Показать qGitSync",
    "qGitSync keeps running in the tray": "qGitSync работает в фоне",
    "Sync continues in the background. Click the tray icon to open, "
    "right-click → Exit to quit.":
        "Синхронизация продолжается. Открыть — щелчок по иконке в трее, "
        "выход — правой кнопкой → Выход.",
    "qGitSync — problem": "qGitSync — проблема",
    "idle": "ожидание",
    "watching": "слежение включено",
    "syncing...": "синхронизация...",
    "synced": "синхронизировано",
    "error (see log)": "ошибка (см. журнал)",
    "conflict (see log)": "конфликт (см. журнал)",
    "Syncing: {name}...": "Синхронизация: {name}...",
    "Setup ERROR: {err}": "ОШИБКА настройки: {err}",
    "Folder connected. Ready to sync.": "Папка подключена. Можно синхронизировать.",
    "Creating repository {name} on GitHub...": "Создаю репозиторий {name} на GitHub...",
    "Repository created: {url}": "Репозиторий создан: {url}",
    "Git is not installed — sync is unavailable.":
        "Git не установлен — синхронизация недоступна.",
    "Git not found": "Git не найден",
    "qGitSync needs Git, and it was not found on this computer.\n\n"
    "Download portable Git (~60 MB) automatically?\n"
    "It is installed only for this app; the system is not changed.":
        "Для работы нужен Git — он не найден на этом компьютере.\n\n"
        "Скачать портативный Git (~60 МБ) автоматически?\n"
        "Он ставится только для этой программы, система не изменяется.",
    "Downloading portable Git...": "Скачиваю портативный Git...",
    "Installing Git": "Установка Git",
    "Git installed: {path}": "Git установлен: {path}",
    "Failed to install Git: {err}": "Не удалось установить Git: {err}",
    "Remove folder": "Убрать папку",
    "Remove “{name}” from the sync list?\n\n"
    "The folder, its files and the GitHub repository are NOT deleted —\n"
    "the app just stops watching it.":
        "Убрать «{name}» из списка синхронизации?\n\n"
        "Сама папка, файлы и репозиторий на GitHub НЕ удаляются —\n"
        "программа просто перестанет за ней следить.",
    "Token required": "Нужен токен",
    "To manage repositories, save a GitHub token first\n"
    "(the “GitHub token” button on the toolbar).":
        "Для управления репозиториями сохраните токен GitHub\n"
        "(кнопка «Токен GitHub» на панели).",
    "Repository link": "Ссылка репозитория",
    "Repository URL (empty — unlink):": "Ссылка репозитория (пусто — отвязать):",
    "Link updated.": "Ссылка обновлена.",

    # ---- token dialog
    "A token lets the app create and list your repositories\n"
    "and push changes without asking for a password.\n\n"
    "1. Click “Open the tokens page” (github.com)\n"
    "2. Generate new token (classic), check scopes: repo, delete_repo\n"
    "3. Copy the token and paste it here":
        "Токен позволяет программе создавать и просматривать ваши репозитории\n"
        "и отправлять изменения без запроса пароля.\n\n"
        "1. Нажмите «Открыть страницу токенов» (github.com)\n"
        "2. Generate new token (classic), отметьте права: repo, delete_repo\n"
        "3. Скопируйте токен и вставьте сюда",
    "Open the tokens page in a browser": "Открыть страницу токенов в браузере",
    "Check and save": "Проверить и сохранить",
    "Delete token": "Удалить токен",
    "Close": "Закрыть",
    "Enter the token.": "Введите токен.",
    "Checking the token...": "Проверяю токен...",
    "Token accepted. Signed in as {login}.": "Токен принят. Вы вошли как {login}.",
    "Token removed from Windows credential storage.":
        "Токен удалён из хранилища Windows.",

    # ---- repo manager
    "My GitHub repositories": "Мои репозитории на GitHub",
    "Name": "Название",
    "Access": "Доступ",
    "Updated": "Обновлён",
    "Link": "Ссылка",
    "Refresh": "Обновить",
    "Create repository...": "Создать репозиторий...",
    "Copy link": "Копировать ссылку",
    "Delete...": "Удалить...",
    "Loading repository list...": "Загружаю список репозиториев...",
    "private": "приватный",
    "public": "публичный",
    "Repositories: {n}": "Репозиториев: {n}",
    "Copied: {url}": "Скопировано: {url}",
    "New repository": "Новый репозиторий",
    "Name (Latin letters, no spaces):": "Название (латиница, без пробелов):",
    "Visibility": "Доступ",
    "Make the repository private (visible only to you)?":
        "Сделать репозиторий приватным (видите только вы)?",
    "Created: {url}": "Создан: {url}",
    "Delete repository": "Удаление репозитория",
    "WARNING: the repository “{name}” will be deleted on GitHub PERMANENTLY\n"
    "together with its history. Local files are not affected.\n\n"
    "Type its name to confirm:":
        "ВНИМАНИЕ: репозиторий «{name}» будет удалён на GitHub БЕЗВОЗВРАТНО\n"
        "вместе со всей историей. Локальные файлы не пострадают.\n\n"
        "Для подтверждения введите его название:",
    "Deletion cancelled.": "Удаление отменено.",
    "Repository {name} deleted.": "Репозиторий {name} удалён.",
    "Unlinked folder “{name}” from the deleted repository.":
        "Папка «{name}» отвязана от удалённого репозитория.",

    # ---- add folder dialog
    "Add a folder": "Добавить папку",
    "Browse...": "Обзор...",
    "(default — folder name)": "(по умолчанию — имя папки)",
    "Name:": "Название:",
    "GitHub repository": "Репозиторий на GitHub",
    "Create a new repository (token required)":
        "Создать новый репозиторий (нужен токен)",
    "Pick one of my repositories (token required)":
        "Выбрать из моих репозиториев (нужен токен)",
    "Enter a link manually": "Указать ссылку вручную",
    "No GitHub for now (local only)": "Пока без GitHub (только локально)",
    "new repository name": "название нового репозитория",
    "load list": "Загрузить список",
    "Load list": "Загрузить список",
    "Add": "Добавить",
    "Cancel": "Отмена",
    "Select a folder": "Выберите папку",
    "Choose a folder.": "Выберите папку.",
    "Save a GitHub token first (toolbar button).":
        "Сначала сохраните токен GitHub (кнопка на панели).",
    "Loading list...": "Загружаю список...",
    "Repositories loaded: {n}": "Загружено репозиториев: {n}",
    "A token is required to create a repository.":
        "Для создания репозитория нужен токен GitHub.",
    "Enter a name for the new repository.": "Укажите название нового репозитория.",
    "Load the list and pick a repository.": "Загрузите список и выберите репозиторий.",
    "Paste the repository link.": "Вставьте ссылку на репозиторий.",
    "Already running": "Уже запущено",
}

_ES = {
    "Folder is already a git repository.": "La carpeta ya es un repositorio git.",
    "Folder is empty — cloning repository...": "La carpeta está vacía — clonando el repositorio...",
    "Clone finished.": "Clonación completada.",
    "Initializing git repository in the folder...": "Inicializando el repositorio git en la carpeta...",
    "Remote repository: {url}": "Repositorio remoto: {url}",
    "Checking remote repository...": "Comprobando el repositorio remoto...",
    "Could not fetch remote data (the repository may be empty — that's fine).":
        "No se pudieron obtener datos remotos (el repositorio puede estar vacío — no pasa nada).",
    "Remote repository already has files — merging with local ones...":
        "El repositorio remoto ya tiene archivos — combinando con los locales...",
    "Could not merge with the remote repository:\n{err}":
        "No se pudo combinar con el repositorio remoto:\n{err}",
    "Setup finished.": "Configuración completada.",
    "Commit created: {msg}": "Commit creado: {msg}",
    "No remote configured — changes saved locally only.":
        "Sin repositorio remoto — los cambios se guardan solo localmente.",
    "Pulling changes...": "Recibiendo cambios...",
    "Remote branch doesn't exist yet — it will be created on push.":
        "La rama remota aún no existe — se creará al enviar.",
    "CONFLICT: the same file was changed on two computers.\n"
    "Sync stopped, resolve the conflict manually:\n{err}":
        "CONFLICTO: el mismo archivo fue modificado en dos equipos.\n"
        "Sincronización detenida, resuelva el conflicto manualmente:\n{err}",
    "Pull failed:\n{err}": "Error al recibir cambios:\n{err}",
    "Pushing changes...": "Enviando cambios...",
    "Push failed:\n{err}": "Error al enviar:\n{err}",
    "Changes pushed.": "Cambios enviados.",
    "Nothing to push — everything is in sync.": "Nada que enviar — todo está sincronizado.",
    "git not found": "git no encontrado",
    "Remote link removed.": "Enlace del repositorio desvinculado.",
    "Conflict — keeping both versions...": "Conflicto — conservando ambas versiones...",
    "Conflict in {file}: both versions kept (copy: {copy})":
        "Conflicto en {file}: se conservaron ambas versiones (copia: {copy})",
    "Merge failed:\n{err}": "No se pudo combinar:\n{err}",
    "Saving local files before merging...":
        "Guardando archivos locales antes de combinar...",

    "GitHub token is not set": "El token de GitHub no está configurado",
    "GitHub rejected the token (401). Check the token.":
        "GitHub rechazó el token (401). Compruebe el token.",
    "Permission denied (403): {detail}. The token needs the repo scope "
    "(and delete_repo for deletion).":
        "Permiso denegado (403): {detail}. El token necesita el permiso repo "
        "(y delete_repo para eliminar).",
    "Not found (404): {detail}": "No encontrado (404): {detail}",
    "GitHub replied {code}: {detail}": "GitHub respondió {code}: {detail}",
    "No connection to GitHub: {reason}": "Sin conexión con GitHub: {reason}",
    "MinGit downloaded, but git.exe was not found after unpacking":
        "MinGit descargado, pero git.exe no se encontró tras descomprimir",
    "keyring library is not installed": "La biblioteca keyring no está instalada",

    "Watching enabled (sync {sec} sec. after changes)":
        "Vigilancia activada (sincronizar {sec} seg. después de los cambios)",
    "— Sync ({reason}) —": "— Sincronización ({reason}) —",
    "ERROR: {err}": "ERROR: {err}",
    "changes in folder": "cambios en la carpeta",
    "remote changes": "cambios en GitHub",
    "Check GitHub for changes, every": "Comprobar cambios en GitHub, cada",
    "{name}: conflict — both versions kept":
        "{name}: conflicto — se conservaron ambas versiones",
    "GitHub repository not found or access denied — check the link ({url})":
        "No se encontró el repositorio de GitHub o no hay acceso — compruebe el enlace ({url})",
    "{name}: GitHub repository not found":
        "{name}: no se encontró el repositorio de GitHub",
    "on schedule": "programada",
    "manual": "manual",
    "sync all": "sincronizar todo",
    "queued changes": "cambios acumulados",
    "first sync": "primera sincronización",
    "not set up": "sin configurar",
    "changes: {n}": "cambios: {n}",
    "not pushed: {n}": "sin enviar: {n}",
    "in sync": "sincronizado",

    "qGitSync — sync folders with GitHub": "qGitSync — sincroniza carpetas con GitHub",
    "Add folder": "Añadir carpeta",
    "Sync all": "Sincronizar todo",
    "GitHub repositories": "Repositorios de GitHub",
    "GitHub token": "Token de GitHub",
    "Settings": "Ajustes",
    "Language": "Idioma",
    "Run at Windows startup": "Iniciar con Windows",
    "Start minimized to tray": "Iniciar minimizado en la bandeja",
    "Exit": "Salir",
    "Folders:": "Carpetas:",
    "Folder": "Carpeta",
    "Path:": "Ruta:",
    "Open in Explorer": "Abrir en el Explorador",
    "GitHub:": "GitHub:",
    "not linked": "sin vincular",
    "State:": "Estado:",
    "Automatically on changes, after": "Automáticamente al cambiar, tras",
    " sec.": " seg.",
    "On a schedule, every": "Programado, cada",
    " min.": " min.",
    "Sync now": "Sincronizar ahora",
    "Change repository link...": "Cambiar enlace del repositorio...",
    "Remove from list...": "Quitar de la lista...",
    "Log:": "Registro:",
    "Ready": "Listo",
    "Restart qGitSync to apply the language.":
        "Reinicie qGitSync para aplicar el idioma.",
    "Autostart enabled": "Inicio automático activado",
    "Autostart disabled": "Inicio automático desactivado",
    "Autostart": "Inicio automático",
    "Failed to change autostart: {err}": "No se pudo cambiar el inicio automático: {err}",
    "Show qGitSync": "Mostrar qGitSync",
    "qGitSync keeps running in the tray": "qGitSync sigue ejecutándose en la bandeja",
    "Sync continues in the background. Click the tray icon to open, "
    "right-click → Exit to quit.":
        "La sincronización continúa en segundo plano. Clic en el icono de la bandeja "
        "para abrir, clic derecho → Salir para cerrar.",
    "qGitSync — problem": "qGitSync — problema",
    "idle": "en espera",
    "watching": "vigilancia activada",
    "syncing...": "sincronizando...",
    "synced": "sincronizado",
    "error (see log)": "error (ver registro)",
    "conflict (see log)": "conflicto (ver registro)",
    "Syncing: {name}...": "Sincronizando: {name}...",
    "Setup ERROR: {err}": "ERROR de configuración: {err}",
    "Folder connected. Ready to sync.": "Carpeta conectada. Lista para sincronizar.",
    "Creating repository {name} on GitHub...": "Creando el repositorio {name} en GitHub...",
    "Repository created: {url}": "Repositorio creado: {url}",
    "Git is not installed — sync is unavailable.":
        "Git no está instalado — la sincronización no está disponible.",
    "Git not found": "Git no encontrado",
    "qGitSync needs Git, and it was not found on this computer.\n\n"
    "Download portable Git (~60 MB) automatically?\n"
    "It is installed only for this app; the system is not changed.":
        "qGitSync necesita Git y no se encontró en este equipo.\n\n"
        "¿Descargar Git portátil (~60 MB) automáticamente?\n"
        "Se instala solo para esta aplicación; el sistema no se modifica.",
    "Downloading portable Git...": "Descargando Git portátil...",
    "Installing Git": "Instalando Git",
    "Git installed: {path}": "Git instalado: {path}",
    "Failed to install Git: {err}": "No se pudo instalar Git: {err}",
    "Remove folder": "Quitar carpeta",
    "Remove “{name}” from the sync list?\n\n"
    "The folder, its files and the GitHub repository are NOT deleted —\n"
    "the app just stops watching it.":
        "¿Quitar “{name}” de la lista de sincronización?\n\n"
        "La carpeta, sus archivos y el repositorio de GitHub NO se eliminan —\n"
        "la aplicación simplemente deja de vigilarla.",
    "Token required": "Se requiere token",
    "To manage repositories, save a GitHub token first\n"
    "(the “GitHub token” button on the toolbar).":
        "Para gestionar repositorios, guarde primero un token de GitHub\n"
        "(botón “Token de GitHub” en la barra).",
    "Repository link": "Enlace del repositorio",
    "Repository URL (empty — unlink):": "URL del repositorio (vacío — desvincular):",
    "Link updated.": "Enlace actualizado.",

    "A token lets the app create and list your repositories\n"
    "and push changes without asking for a password.\n\n"
    "1. Click “Open the tokens page” (github.com)\n"
    "2. Generate new token (classic), check scopes: repo, delete_repo\n"
    "3. Copy the token and paste it here":
        "Un token permite a la aplicación crear y listar sus repositorios\n"
        "y enviar cambios sin pedir contraseña.\n\n"
        "1. Pulse “Abrir la página de tokens” (github.com)\n"
        "2. Generate new token (classic), marque los permisos: repo, delete_repo\n"
        "3. Copie el token y péguelo aquí",
    "Open the tokens page in a browser": "Abrir la página de tokens en el navegador",
    "Check and save": "Comprobar y guardar",
    "Delete token": "Eliminar token",
    "Close": "Cerrar",
    "Enter the token.": "Introduzca el token.",
    "Checking the token...": "Comprobando el token...",
    "Token accepted. Signed in as {login}.": "Token aceptado. Sesión iniciada como {login}.",
    "Token removed from Windows credential storage.":
        "Token eliminado del almacén de credenciales de Windows.",

    "My GitHub repositories": "Mis repositorios de GitHub",
    "Name": "Nombre",
    "Access": "Acceso",
    "Updated": "Actualizado",
    "Link": "Enlace",
    "Refresh": "Actualizar",
    "Create repository...": "Crear repositorio...",
    "Copy link": "Copiar enlace",
    "Delete...": "Eliminar...",
    "Loading repository list...": "Cargando la lista de repositorios...",
    "private": "privado",
    "public": "público",
    "Repositories: {n}": "Repositorios: {n}",
    "Copied: {url}": "Copiado: {url}",
    "New repository": "Nuevo repositorio",
    "Name (Latin letters, no spaces):": "Nombre (letras latinas, sin espacios):",
    "Visibility": "Visibilidad",
    "Make the repository private (visible only to you)?":
        "¿Hacer el repositorio privado (visible solo para usted)?",
    "Created: {url}": "Creado: {url}",
    "Delete repository": "Eliminar repositorio",
    "WARNING: the repository “{name}” will be deleted on GitHub PERMANENTLY\n"
    "together with its history. Local files are not affected.\n\n"
    "Type its name to confirm:":
        "ATENCIÓN: el repositorio “{name}” se eliminará de GitHub PERMANENTEMENTE\n"
        "junto con su historial. Los archivos locales no se ven afectados.\n\n"
        "Escriba su nombre para confirmar:",
    "Deletion cancelled.": "Eliminación cancelada.",
    "Repository {name} deleted.": "Repositorio {name} eliminado.",
    "Unlinked folder “{name}” from the deleted repository.":
        "Carpeta “{name}” desvinculada del repositorio eliminado.",

    "Add a folder": "Añadir una carpeta",
    "Browse...": "Examinar...",
    "(default — folder name)": "(por defecto — nombre de la carpeta)",
    "Name:": "Nombre:",
    "GitHub repository": "Repositorio de GitHub",
    "Create a new repository (token required)":
        "Crear un repositorio nuevo (se requiere token)",
    "Pick one of my repositories (token required)":
        "Elegir uno de mis repositorios (se requiere token)",
    "Enter a link manually": "Introducir un enlace manualmente",
    "No GitHub for now (local only)": "Sin GitHub por ahora (solo local)",
    "new repository name": "nombre del nuevo repositorio",
    "Load list": "Cargar lista",
    "Add": "Añadir",
    "Cancel": "Cancelar",
    "Select a folder": "Seleccione una carpeta",
    "Choose a folder.": "Elija una carpeta.",
    "Save a GitHub token first (toolbar button).":
        "Guarde primero un token de GitHub (botón de la barra).",
    "Loading list...": "Cargando la lista...",
    "Repositories loaded: {n}": "Repositorios cargados: {n}",
    "A token is required to create a repository.":
        "Se requiere un token para crear un repositorio.",
    "Enter a name for the new repository.": "Introduzca un nombre para el nuevo repositorio.",
    "Load the list and pick a repository.": "Cargue la lista y elija un repositorio.",
    "Paste the repository link.": "Pegue el enlace del repositorio.",
    "Already running": "Ya está en ejecución",
}

_TABLES = {"ru": _RU, "es": _ES}
