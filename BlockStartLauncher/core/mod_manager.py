import json
import os
import re
import zipfile


def mods_dir(instance_dir):
    return os.path.join(instance_dir, "mods")


def list_mods(instance_dir):
    directory = mods_dir(instance_dir)
    try:
        names = sorted(os.listdir(directory))
    except Exception:
        return []
    mods = []
    for name in names:
        lower = name.lower()
        if not (lower.endswith(".jar") or lower.endswith(".jar.disabled")):
            continue
        path = os.path.join(directory, name)
        try:
            size = os.path.getsize(path)
        except Exception:
            size = 0
        mods.append({"name": name, "path": path, "enabled": lower.endswith(".jar"), "size": size})
    return mods


def toggle_mod(path):
    lower = path.lower()
    if lower.endswith(".jar.disabled"):
        target = path[: -len(".disabled")]
    elif lower.endswith(".jar"):
        target = path + ".disabled"
    else:
        raise RuntimeError("不是有效的 Mod 文件")
    try:
        os.replace(path, target)
    except PermissionError as exc:
        raise RuntimeError("无法修改 Mod 状态：文件被占用或无权限") from exc
    return target


def delete_mod(path):
    if not os.path.isfile(path):
        raise RuntimeError("模组文件不存在")
    try:
        os.remove(path)
    except PermissionError as exc:
        raise RuntimeError("无法删除模组：文件被占用或无权限") from exc
    return True


def _read_metadata(path):
    metadata = {"loader": "", "ids": []}
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "fabric.mod.json" in names:
                metadata["loader"] = "fabric"
                try:
                    data = json.loads(archive.read("fabric.mod.json").decode("utf-8", "replace"))
                    if data.get("id"):
                        metadata["ids"].append(str(data["id"]))
                except Exception:
                    pass
            for toml_name in ("META-INF/neoforge.mods.toml", "META-INF/mods.toml"):
                if toml_name not in names:
                    continue
                try:
                    text = archive.read(toml_name).decode("utf-8", "replace")
                    match = re.search(r'modLoader\s*=\s*"([^"]+)"', text)
                    loader = match.group(1) if match else ""
                    if loader == "lowcodefml" or "neoforge" in toml_name:
                        metadata["loader"] = metadata["loader"] or "neoforge"
                    elif loader == "javafml":
                        metadata["loader"] = metadata["loader"] or "forge"
                    elif loader:
                        metadata["loader"] = metadata["loader"] or loader
                    metadata["ids"].extend(re.findall(r'modId\s*=\s*"([^"]+)"', text))
                except Exception:
                    continue
    except Exception:
        return metadata
    return metadata


def detect_loader_conflicts(instance_dir):
    loaders = set()
    for mod in list_mods(instance_dir):
        loader = _read_metadata(mod["path"]).get("loader")
        if loader:
            loaders.add(loader)
    if len(loaders) > 1:
        return ["检测到混用 Mod 加载器：" + "、".join(sorted(loaders)) + "，游戏可能无法启动。"]
    return []


def detect_duplicate_modids(instance_dir):
    seen = {}
    for mod in list_mods(instance_dir):
        metadata = _read_metadata(mod["path"])
        for mod_id in metadata.get("ids") or []:
            seen.setdefault(mod_id, []).append(mod["name"])
    return [{"modid": mod_id, "files": files} for mod_id, files in sorted(seen.items()) if len(files) > 1]
