import os
import shutil
import time
import zipfile

import config
from core import launcher_core


def saves_dir(instance_name):
    return os.path.join(launcher_core.instance_path(instance_name), "saves")


def list_saves(instance_name):
    root = saves_dir(instance_name)
    try:
        names = [
            name
            for name in os.listdir(root)
            if os.path.isdir(os.path.join(root, name)) and not name.startswith(".")
        ]
    except Exception:
        names = []
    result = []
    for name in sorted(names, key=str.lower):
        path = os.path.join(root, name)
        try:
            mtime = os.path.getmtime(path)
        except Exception:
            mtime = 0
        result.append({"name": name, "path": path, "mtime": mtime})
    return result


def _safe_name(name):
    clean = os.path.basename(str(name or "").strip())
    if not clean or clean in (".", "..") or clean.startswith("."):
        raise RuntimeError("存档名称无效")
    return clean


def _remove_tree(path):
    try:
        shutil.rmtree(path)
    except Exception:
        for root, dirs, files in os.walk(path):
            for item in files:
                try:
                    os.chmod(os.path.join(root, item), 0o700)
                except Exception:
                    pass
            for item in dirs:
                try:
                    os.chmod(os.path.join(root, item), 0o700)
                except Exception:
                    pass
        shutil.rmtree(path)


def delete_save(instance_name, save_name):
    safe = _safe_name(save_name)
    target = os.path.join(saves_dir(instance_name), safe)
    root = os.path.realpath(saves_dir(instance_name))
    if os.path.commonpath([root, os.path.realpath(target)]) != root:
        raise RuntimeError("拒绝删除非法路径")
    if not os.path.isdir(target):
        raise RuntimeError("存档不存在：" + safe)
    _remove_tree(target)


def backup_dir(instance_name):
    return os.path.join(config.data_dir(), "backups", "saves", _safe_name(instance_name))


def backup_save(instance_name, save_name, progress_cb=None):
    safe = _safe_name(save_name)
    source = os.path.join(saves_dir(instance_name), safe)
    if not os.path.isdir(source):
        raise RuntimeError("存档不存在：" + safe)
    target_dir = backup_dir(instance_name)
    os.makedirs(target_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    target = os.path.join(target_dir, f"{safe}_{stamp}.zip")
    files = []
    for root, _dirs, names in os.walk(source):
        for name in names:
            files.append(os.path.join(root, name))
    total = len(files)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, path in enumerate(files, 1):
            arc = os.path.join(safe, os.path.relpath(path, source))
            archive.write(path, arc)
            if progress_cb:
                progress_cb(index, total)
    return target


def import_backup(instance_name, zip_path, overwrite=False):
    if not os.path.isfile(zip_path):
        raise RuntimeError("备份文件不存在")
    root = saves_dir(instance_name)
    os.makedirs(root, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as archive:
        names = [name for name in archive.namelist() if name.strip("/")]
        roots = {name.replace("\\", "/").split("/")[0] for name in names}
        save_name = next(iter(roots)) if len(roots) == 1 else os.path.splitext(os.path.basename(zip_path))[0]
        save_name = _safe_name(save_name)
        target = os.path.join(root, save_name)
        if os.path.isdir(target) and not overwrite:
            raise RuntimeError("同名存档已存在：" + save_name)
        if os.path.isdir(target):
            _remove_tree(target)
        os.makedirs(target, exist_ok=True)
        target_real = os.path.realpath(target)
        for item in archive.infolist():
            normalized = item.filename.replace("\\", "/").lstrip("/")
            if not normalized or normalized.endswith("/"):
                continue
            parts = normalized.split("/")
            if len(parts) == 1:
                relative = parts[0]
            else:
                relative = "/".join(parts[1:])
            if not relative:
                continue
            destination = os.path.realpath(os.path.join(target, relative))
            if os.path.commonpath([target_real, destination]) != target_real:
                continue
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            with archive.open(item, "r") as source, open(destination, "wb") as output:
                shutil.copyfileobj(source, output)
    return save_name
