import json
import os
import re
import shutil
import subprocess
import sys
import time

import minecraft_launcher_lib
import requests

import config
from core import bmclapi_source

_INVALID_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def minecraft_directory():
    return config.minecraft_dir()


def _manifest_versions(url):
    try:
        response = requests.get(url, timeout=8, headers={"User-Agent": config.USER_AGENT})
        if response.status_code == 200:
            data = response.json() or {}
            versions = data.get("versions")
            if isinstance(versions, list):
                return versions
    except Exception:
        pass
    return []


def get_version_list():
    raw = _manifest_versions(config.BMCLAPI_BASE + "/mc/game/version_manifest_v2.json")
    if not raw:
        raw = _manifest_versions("https://launchermeta.mojang.com/mc/game/version_manifest_v2.json")
    if not raw:
        try:
            raw = minecraft_launcher_lib.utils.get_version_list()
        except Exception:
            raw = []
    versions = []
    for item in raw or []:
        try:
            version_id = str(item.get("id") or "")
            if not version_id:
                continue
            versions.append(
                {
                    "id": version_id,
                    "type": str(item.get("type") or "release"),
                    "url": str(item.get("url") or ""),
                }
            )
        except Exception:
            continue
    return versions


def installed_versions():
    directory = os.path.join(minecraft_directory(), "versions")
    try:
        names = os.listdir(directory)
    except Exception:
        return []
    return sorted(name for name in names if os.path.isfile(os.path.join(directory, name, name + ".json")))


def is_version_installed(version_id):
    if not version_id:
        return False
    return os.path.isfile(os.path.join(minecraft_directory(), "versions", version_id, version_id + ".json"))


def required_java_major(version_id):
    """按版本 JSON 或版本号推断需要的 Java 主版本。"""
    version_id = str(version_id or "").strip()
    if not version_id:
        return 17
    version_json = os.path.join(minecraft_directory(), "versions", version_id, version_id + ".json")
    try:
        with open(version_json, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
        major = int(((data.get("javaVersion") or {}).get("majorVersion")) or 0)
        if major > 0:
            return major
    except Exception:
        pass
    release = re.match(r"^1\.(\d+)(?:\.(\d+))?", version_id)
    if release:
        minor = int(release.group(1))
        patch = int(release.group(2) or 0)
        if minor <= 16:
            return 8
        if minor == 17:
            return 17
        if minor <= 19:
            return 17
        if minor == 20:
            return 21 if patch >= 5 else 17
        return 21
    snapshot = re.match(r"^(\d{2})w\d{2}[a-z]$", version_id)
    if snapshot:
        year = int(snapshot.group(1))
        if year >= 24:
            return 21
        return 17
    return 17


def instances_root():
    return os.path.join(minecraft_directory(), "instances")


def instance_path(name):
    return os.path.join(instances_root(), name)


def sanitize_instance_name(name):
    cleaned = _INVALID_NAME.sub("", str(name or "")).strip().strip(".")
    return cleaned[:64]


def _read_instance_meta(path):
    meta_file = os.path.join(path, "instance.json")
    meta = {}
    try:
        with open(meta_file, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            meta = data
    except Exception:
        meta = {}
    return meta


def _count_files(directory, suffixes):
    try:
        return len(
            [
                name
                for name in os.listdir(directory)
                if os.path.isfile(os.path.join(directory, name)) and name.lower().endswith(suffixes)
            ]
        )
    except Exception:
        return 0


def _count_dirs(directory):
    try:
        return len([name for name in os.listdir(directory) if os.path.isdir(os.path.join(directory, name))])
    except Exception:
        return 0


def instance_stats(name):
    path = instance_path(name)
    return {
        "mods": _count_files(os.path.join(path, "mods"), (".jar", ".jar.disabled")),
        "saves": _count_dirs(os.path.join(path, "saves")),
        "resourcepacks": _count_files(os.path.join(path, "resourcepacks"), (".zip",)),
        "shaderpacks": _count_files(os.path.join(path, "shaderpacks"), (".zip",)),
    }


def list_instances():
    root = instances_root()
    try:
        names = sorted(os.listdir(root))
    except Exception:
        return []
    instances = []
    for name in names:
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        meta = _read_instance_meta(path)
        version_id = str(meta.get("version_id") or "")
        instances.append(
            {
                "name": name,
                "version_id": version_id,
                "created": meta.get("created") or 0,
                "loader": str(meta.get("loader") or ""),
                "path": path,
                "mods": _count_files(os.path.join(path, "mods"), (".jar", ".jar.disabled")),
                "saves": _count_dirs(os.path.join(path, "saves")),
            }
        )
    return instances


def get_instance(name):
    for instance in list_instances():
        if instance["name"] == name:
            return instance
    return None


def create_instance(name, version_id, loader="", loader_version="", loader_version_id=""):
    clean = sanitize_instance_name(name)
    if not clean:
        raise RuntimeError("实例名称无效")
    path = instance_path(clean)
    if os.path.isdir(path):
        raise RuntimeError("实例已存在：" + clean)
    for sub in ("mods", "resourcepacks", "shaderpacks", "saves"):
        os.makedirs(os.path.join(path, sub), exist_ok=True)
    meta = {
        "name": clean,
        "version_id": version_id or "",
        "created": time.time(),
        "loader": loader or "",
        "loader_version": loader_version or "",
        "loader_version_id": loader_version_id or "",
    }
    with open(os.path.join(path, "instance.json"), "w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)
    return meta


def update_instance_version(name, version_id):
    path = instance_path(name)
    if not os.path.isdir(path):
        raise RuntimeError("实例不存在：" + name)
    meta = _read_instance_meta(path)
    meta.update({"name": name, "version_id": version_id})
    with open(os.path.join(path, "instance.json"), "w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)


def _remove_tree(path):
    def on_error(func, target, _exc):
        try:
            os.chmod(target, 0o700)
            func(target)
        except Exception:
            pass

    try:
        shutil.rmtree(path, onerror=on_error)
    except TypeError:
        shutil.rmtree(path, onexc=on_error)


def delete_instance(name):
    root = os.path.realpath(instances_root())
    target = os.path.realpath(instance_path(name))
    if os.path.commonpath([root, target]) != root or target == root:
        raise RuntimeError("拒绝删除非法路径")
    if not os.path.isdir(target):
        raise RuntimeError("实例不存在：" + name)
    _remove_tree(target)


def ensure_instance_dirs(name):
    path = instance_path(name)
    for sub in ("mods", "resourcepacks", "shaderpacks", "saves"):
        os.makedirs(os.path.join(path, sub), exist_ok=True)
    return path


def mll_callback(progress_cb=None, status_cb=None):
    state = {"max": 0, "value": 0}

    def set_max(value):
        state["max"] = max(0, int(value or 0))
        if progress_cb:
            progress_cb(state["value"], state["max"])

    def set_progress(value):
        state["value"] = max(0, int(value or 0))
        if progress_cb:
            progress_cb(state["value"], state["max"])

    def set_status(text):
        if status_cb:
            status_cb(str(text))

    return {"setStatus": set_status, "setProgress": set_progress, "setMax": set_max}


def install_version(version_id, callback=None, source="auto"):
    if not version_id:
        raise RuntimeError("版本号为空")
    bmclapi_source.install_version_with_source(
        version_id, minecraft_directory(), callback, source=source
    )


def _java_launcher(java_path):
    if not java_path:
        return "java"
    if sys.platform == "win32" and os.path.basename(java_path).lower() == "java.exe":
        javaw = os.path.join(os.path.dirname(java_path), "javaw.exe")
        if os.path.isfile(javaw):
            return javaw
    return java_path


def get_instance_settings(name):
    meta = _read_instance_meta(instance_path(name))
    result = {
        "java_path": str(meta.get("java_path") or ""),
        "max_memory_mb": int(meta.get("max_memory_mb") or 0),
        "jvm_args": str(meta.get("jvm_args") or ""),
        "width": int(meta.get("width") or 0),
        "height": int(meta.get("height") or 0),
        "fullscreen": bool(meta.get("fullscreen") or False),
        "game_args": str(meta.get("game_args") or ""),
        "server": str(meta.get("server") or ""),
        "server_port": str(meta.get("server_port") or "25565"),
        "loader": str(meta.get("loader") or ""),
        "loader_version": str(meta.get("loader_version") or ""),
        "loader_version_id": str(meta.get("loader_version_id") or ""),
    }
    return result


def update_instance_settings(name, values):
    path = instance_path(name)
    if not os.path.isdir(path):
        raise RuntimeError("实例不存在：" + name)
    meta = _read_instance_meta(path)
    meta["name"] = name
    allowed = (
        "java_path",
        "max_memory_mb",
        "jvm_args",
        "width",
        "height",
        "fullscreen",
        "game_args",
        "server",
        "server_port",
        "loader",
        "loader_version",
        "loader_version_id",
    )
    for key in allowed:
        if key in values:
            meta[key] = values[key]
    with open(os.path.join(path, "instance.json"), "w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)
    return get_instance_settings(name)


def instance_game_version(name):
    meta = _read_instance_meta(instance_path(name))
    return str(meta.get("version_id") or "")


def instance_launch_version(name):
    settings = get_instance_settings(name)
    return settings.get("loader_version_id") or instance_game_version(name)


def split_game_args(text):
    import re

    result = []
    for match in re.finditer(r'"([^"]*)"|\'([^\']*)\'|(\S+)', str(text or "")):
        value = match.group(1)
        if value is None:
            value = match.group(2)
        if value is None:
            value = match.group(3)
        if value:
            result.append(value)
    return result


def build_launch_options(account_options, max_memory_mb, extra_jvm_args, java_path, game_dir, game_settings=None):
    game = dict(game_settings or {})
    memory = max(512, min(16384, int(max_memory_mb or 2048)))
    jvm_arguments = [f"-Xmx{memory}M", "-Xms512M"]
    jvm_arguments.extend([part for part in split_game_args(extra_jvm_args) if part])
    options = {
        "username": account_options.get("username") or config.DEFAULT_USERNAME,
        "uuid": account_options.get("uuid") or "",
        "token": account_options.get("token") or "0",
        "user_type": account_options.get("user_type") or "legacy",
        "gameDirectory": game_dir,
        "launcherName": config.LAUNCHER_NAME,
        "launcherVersion": config.LAUNCHER_VERSION,
        "executablePath": _java_launcher(java_path),
        "jvmArguments": jvm_arguments,
        "_bsl_width": int(game.get("width") or 0),
        "_bsl_height": int(game.get("height") or 0),
        "_bsl_fullscreen": bool(game.get("fullscreen") or False),
        "_bsl_server": str(game.get("server") or "").strip(),
        "_bsl_port": str(game.get("server_port") or "25565").strip() or "25565",
        "_bsl_game_args": split_game_args(game.get("game_args") or ""),
    }
    return options


def launch_game(version_id, game_dir, java_path, options_dict):
    options = dict(options_dict or {})
    width = int(options.pop("_bsl_width", 0) or 0)
    height = int(options.pop("_bsl_height", 0) or 0)
    fullscreen = bool(options.pop("_bsl_fullscreen", False))
    server = str(options.pop("_bsl_server", "") or "").strip()
    port = str(options.pop("_bsl_port", "25565") or "25565").strip()
    extra_args = list(options.pop("_bsl_game_args", []) or [])
    options["gameDirectory"] = game_dir
    if java_path:
        options["executablePath"] = _java_launcher(java_path)
    os.makedirs(game_dir, exist_ok=True)
    command = list(minecraft_launcher_lib.command.get_minecraft_command(version_id, minecraft_directory(), options))
    if width > 0 and height > 0:
        command.extend(["--width", str(width), "--height", str(height)])
    if fullscreen:
        command.append("--fullscreen")
    if server:
        command.extend(["--server", server, "--port", port or "25565"])
    command.extend(extra_args)
    creationflags = 0
    if sys.platform == "win32":
        creationflags = 0x08000000
    process = subprocess.Popen(
        command,
        cwd=game_dir,
        creationflags=creationflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    return process
