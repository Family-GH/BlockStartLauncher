import os
import shutil
import sys

MINECRAFT_DIR = "mc"
LAUNCHER_NAME = "BlockStart"
LAUNCHER_VERSION = "0.5.2b"
LAUNCHER_AUTHOR = "MC_Family"
DEFAULT_USERNAME = "Player"
USER_AGENT = f"{LAUNCHER_NAME}/{LAUNCHER_VERSION} ({LAUNCHER_AUTHOR})"

MS_CLIENT_ID = "c36a9fb6-4f2a-41ff-90bd-ae7cc92031eb"
BMCLAPI_BASE = "https://bmclapi2.bangbang93.com"
MIRROR_MODRINTH_API = "https://api.modrinth.com"
OFFICIAL_MODRINTH_API = "https://api.modrinth.com"
GITHUB_REPO = "MC_Family/BlockStartLauncher"
GITHUB_RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
GITEE_REPO = ""
GITEE_RELEASES_API = f"https://gitee.com/api/v5/repos/{GITEE_REPO}/releases" if GITEE_REPO else ""
UPDATE_ASSET_KEYWORD = "BlockStartLauncher"
# Extra update sources: separated by semicolons or newlines.
EXTRA_UPDATE_SOURCES = [
    item.strip()
    for item in os.environ.get("BSL_UPDATE_SOURCES", "").replace(";", "\n").splitlines()
    if item.strip()
]

_GAME_DIR = ""


def executable_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _migrate_file(name, target):
    legacy = os.path.join(executable_dir(), name)
    if os.path.isfile(legacy) and not os.path.isfile(target):
        try:
            shutil.copy2(legacy, target)
        except Exception:
            pass


def data_dir():
    portable = executable_dir()
    if not getattr(sys, "frozen", False):
        return portable
    root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
    target = os.path.join(root, "BlockStartLauncher")
    try:
        os.makedirs(target, exist_ok=True)
    except Exception:
        return portable
    for name in ("settings.json", "accounts.json"):
        _migrate_file(name, os.path.join(target, name))
    return target


def base_dir():
    return data_dir()


def legacy_minecraft_dir():
    return os.path.join(executable_dir(), MINECRAFT_DIR)


def set_game_dir(path):
    global _GAME_DIR
    _GAME_DIR = str(path or "").strip()


def minecraft_dir():
    if _GAME_DIR:
        return _GAME_DIR
    return os.path.join(data_dir(), MINECRAFT_DIR)

