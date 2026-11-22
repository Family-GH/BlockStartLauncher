import inspect
import json
import os
import shutil
import time
import zipfile

import requests

import config
from core import java_manager, launcher_core


def _callback_bridge(callback, status_cb):
    return launcher_core.mll_callback(callback, status_cb)


def _zip_names(pack_path):
    try:
        with zipfile.ZipFile(pack_path) as archive:
            return archive.namelist()
    except Exception as exc:
        raise RuntimeError(f"无法读取整合包：{exc}") from exc


def detect_format(pack_path):
    names = _zip_names(pack_path)
    lowered = [name.lower() for name in names]
    if "modrinth.index.json" in lowered:
        return "modrinth"
    if "manifest.json" in lowered and not any(name.startswith("addons/") for name in lowered):
        return "curseforge"
    if "mmc-pack.json" in lowered:
        return "multimc"
    if any(name.startswith(".minecraft/") for name in lowered) or any(
        name.startswith("versions/") and name.endswith(".json") for name in lowered
    ):
        return "minecraft"
    return "unknown"


def _read_json(pack_path, member):
    with zipfile.ZipFile(pack_path) as archive:
        return json.loads(archive.read(member).decode("utf-8", "replace"))


def _download(url, target, callback=None):
    os.makedirs(os.path.dirname(target), exist_ok=True)
    temp = target + ".part"
    mirror = url.replace("cdn.modrinth.com", "mod.mcimirror.top")
    candidates = []
    for candidate in (mirror, url):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    last_error = None
    for candidate in candidates:
        try:
            with requests.get(
                candidate, stream=True, timeout=60, headers={"User-Agent": config.USER_AGENT}
            ) as response:
                response.raise_for_status()
                total = int(response.headers.get("Content-Length") or 0)
                done = 0
                with open(temp, "wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 128):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        done += len(chunk)
                        if callback:
                            callback(done, total)
            os.replace(temp, target)
            return target
        except Exception as exc:
            last_error = exc
            try:
                if os.path.isfile(temp):
                    os.remove(temp)
            except Exception:
                pass
    raise RuntimeError(f"下载失败：{last_error}")


def _safe_extract(archive, target_root, prefix_strip=""):
    for name in archive.namelist():
        if name.endswith("/"):
            continue
        relative = name
        if prefix_strip:
            if not name.startswith(prefix_strip):
                continue
            relative = name[len(prefix_strip) :]
        if not relative or relative.startswith("/") or ".." in relative.split("/"):
            continue
        destination = os.path.join(target_root, relative.replace("/", os.sep))
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        with archive.open(name) as source, open(destination, "wb") as output:
            shutil.copyfileobj(source, output)


def _extract_dir(pack_path, member_prefix, target_root):
    with zipfile.ZipFile(pack_path) as archive:
        _safe_extract(archive, target_root, member_prefix)


def _install_loader(loader, loader_version, minecraft_version, result, bridge):
    if not loader or not loader_version or not minecraft_version:
        return ""
    try:
        import minecraft_launcher_lib

        mod_loader = minecraft_launcher_lib.mod_loader
        directory = launcher_core.minecraft_directory()
        java_path = java_manager.find_existing_java() or "java"
        if hasattr(mod_loader, "fabric"):
            if loader == "fabric":
                return mod_loader.fabric.install_fabric(
                    minecraft_version, directory, loader_version=loader_version
                ) or ""
            if loader == "quilt":
                return mod_loader.quilt.install_quilt(
                    minecraft_version, directory, loader_version=loader_version
                ) or ""
            if loader == "forge":
                return mod_loader.forge.install_forge_version(loader_version, directory) or ""
            if loader == "neoforge" and hasattr(mod_loader, "neoforge"):
                return mod_loader.neoforge.install_neoforge_version(loader_version, directory) or ""
            return ""
        classes = {
            "fabric": "Fabric",
            "quilt": "Quilt",
            "forge": "Forge",
            "neoforge": "Neoforge",
        }
        class_name = classes.get(loader)
        loader_class = getattr(mod_loader, class_name, None) if class_name else None
        if loader_class is None:
            result["warnings"].append(f"当前 minecraft-launcher-lib 不支持 {loader} 加载器")
            return ""
        instance = loader_class()
        instance.install(minecraft_version, directory, bridge, java_path, loader_version)
        return instance.get_installed_version(minecraft_version, loader_version)
    except Exception as exc:
        result["warnings"].append(f"{loader} 加载器安装失败：{exc}")
    return ""


def _detect_version_from_dir(instance_dir):
    versions = os.path.join(instance_dir, "versions")
    try:
        for name in os.listdir(versions):
            if os.path.isfile(os.path.join(versions, name, name + ".json")):
                return name
    except Exception:
        pass
    return ""


def _write_instance_meta(instance_dir, version_id, loader):
    meta_path = os.path.join(instance_dir, "instance.json")
    meta = {}
    try:
        with open(meta_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            meta = data
    except Exception:
        meta = {}
    meta.update(
        {
            "name": os.path.basename(instance_dir),
            "version_id": version_id or meta.get("version_id") or "",
            "created": meta.get("created") or time.time(),
            "loader": loader or meta.get("loader") or "",
        }
    )
    with open(meta_path, "w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)


def _install_modrinth(pack_path, instance_dir, result, callback, status_cb, bridge):
    index = _read_json(pack_path, "modrinth.index.json")
    dependencies = index.get("dependencies") or {}
    minecraft_version = str(dependencies.get("minecraft") or "")
    loader = ""
    loader_version = ""
    for key in ("fabric-loader", "quilt-loader", "forge", "neoforge"):
        if dependencies.get(key):
            loader = key.replace("-loader", "")
            loader_version = str(dependencies[key])
            break
    installed_by_mrpack = False
    try:
        from minecraft_launcher_lib import mrpack

        parameters = inspect.signature(mrpack.install_mrpack).parameters
        kwargs = {"callback": bridge}
        target_directory = instance_dir
        if "modpack_directory" in parameters:
            target_directory = launcher_core.minecraft_directory()
            kwargs["modpack_directory"] = instance_dir
        if "mrpack_install_options" in parameters:
            kwargs["mrpack_install_options"] = {"skipDependenciesInstall": True}
        mrpack.install_mrpack(pack_path, target_directory, **kwargs)
        installed_by_mrpack = True
        result["actions"].append("已通过 install_mrpack 安装整合包文件")
    except Exception as exc:
        result["warnings"].append(f"install_mrpack 不可用，改用内置安装：{exc}")
    if not installed_by_mrpack:
        for item in index.get("files") or []:
            path = str(item.get("path") or "")
            environment = (item.get("env") or {}).get("client")
            if not path or environment == "unsupported":
                continue
            urls = item.get("downloads") or []
            if not urls:
                result["missing_mods"].append(path)
                continue
            try:
                _download(urls[0], os.path.join(instance_dir, path.replace("/", os.sep)), callback)
            except Exception:
                result["missing_mods"].append(path)
        for prefix in ("overrides/", "client-overrides/"):
            try:
                _extract_dir(pack_path, prefix, instance_dir)
            except Exception:
                pass
        result["actions"].append("已解压整合包覆盖文件")
    if minecraft_version:
        if status_cb:
            status_cb(f"正在安装游戏版本 {minecraft_version}")
        launcher_core.install_version(minecraft_version, callback=bridge)
        result["version_id"] = minecraft_version
    loader_version_id = _install_loader(loader, loader_version, minecraft_version, result, bridge)
    if loader_version_id:
        result["version_id"] = loader_version_id
        result["actions"].append(f"已安装 {loader} 加载器")
    return result


def _install_curseforge(pack_path, instance_dir, result, callback, status_cb):
    bridge = _callback_bridge(callback, status_cb)
    manifest = _read_json(pack_path, "manifest.json")
    minecraft_version = str((manifest.get("minecraft") or {}).get("version") or "")
    loader_name = ""
    loader_version = ""
    for item in (manifest.get("minecraft") or {}).get("modLoaders") or []:
        if item.get("primary"):
            identifier = str(item.get("id") or "")
            if "-" in identifier:
                loader_name, loader_version = identifier.split("-", 1)
            break
    missing = []
    for item in manifest.get("files") or []:
        missing.append(f"CurseForge projectID={item.get('projectID')} fileID={item.get('fileID')}")
    if missing:
        result["missing_mods"].extend(missing)
        result["warnings"].append("CurseForge API 不可用，已记录缺失 Mod 清单，请手动补充。")
    try:
        _extract_dir(pack_path, "overrides/", instance_dir)
        result["actions"].append("已解压 CurseForge 覆盖文件")
    except Exception:
        pass
    if minecraft_version:
        launcher_core.install_version(minecraft_version, callback=bridge)
        result["version_id"] = minecraft_version
    loader_version_id = _install_loader(loader_name, loader_version, minecraft_version, result, bridge)
    if loader_version_id:
        result["version_id"] = loader_version_id
    return result


def _install_multimc(pack_path, instance_dir, result, callback, status_cb):
    bridge = _callback_bridge(callback, status_cb)
    pack = _read_json(pack_path, "mmc-pack.json")
    minecraft_version = ""
    for component in pack.get("components") or []:
        if str(component.get("uid") or "") == "net.minecraft":
            minecraft_version = str(component.get("version") or "")
    for prefix in ("minecraft/", ".minecraft/"):
        try:
            _extract_dir(pack_path, prefix, instance_dir)
            result["actions"].append(f"已解压 MultiMC 文件（{prefix}）")
            break
        except Exception:
            continue
    if minecraft_version:
        launcher_core.install_version(minecraft_version, callback=bridge)
        result["version_id"] = minecraft_version
    return result


def _install_plain_minecraft(pack_path, instance_dir, result):
    with zipfile.ZipFile(pack_path) as archive:
        names = archive.namelist()
        if any(name.startswith(".minecraft/") for name in names):
            _safe_extract(archive, instance_dir, ".minecraft/")
        else:
            _safe_extract(archive, instance_dir)
    result["actions"].append("已直接解压整合包")
    result["version_id"] = _detect_version_from_dir(instance_dir)
    return result


def install_pack(pack_path, instance_dir, callback=None, status_cb=None):
    if not os.path.isfile(pack_path):
        raise RuntimeError("整合包文件不存在")
    os.makedirs(instance_dir, exist_ok=True)
    for sub in ("mods", "resourcepacks", "shaderpacks", "saves"):
        os.makedirs(os.path.join(instance_dir, sub), exist_ok=True)
    fmt = detect_format(pack_path)
    result = {"format": fmt, "missing_mods": [], "warnings": [], "actions": [], "version_id": "", "loader": ""}
    bridge = _callback_bridge(callback, status_cb)
    if fmt == "modrinth":
        _install_modrinth(pack_path, instance_dir, result, callback, status_cb, bridge)
        try:
            dependencies = _read_json(pack_path, "modrinth.index.json").get("dependencies") or {}
            for key in ("fabric-loader", "quilt-loader", "forge", "neoforge"):
                if dependencies.get(key):
                    result["loader"] = key.replace("-loader", "")
                    break
        except Exception:
            pass
    elif fmt == "curseforge":
        _install_curseforge(pack_path, instance_dir, result, callback, status_cb)
    elif fmt == "multimc":
        _install_multimc(pack_path, instance_dir, result, callback, status_cb)
    elif fmt == "minecraft":
        _install_plain_minecraft(pack_path, instance_dir, result)
    else:
        raise RuntimeError("无法识别的整合包格式")
    if not result["version_id"]:
        result["version_id"] = _detect_version_from_dir(instance_dir)
    _write_instance_meta(instance_dir, result["version_id"], result["loader"])
    return result
