"""Cheap, local-only environment facts used by the dashboard status card."""

import ctypes
import os
import platform
import shutil

import config
from core import launcher_core


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def system_memory():
    if os.name != "nt":
        return {"total_mb": 0, "available_mb": 0, "percent": 0}
    try:
        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(_MemoryStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return {"total_mb": 0, "available_mb": 0, "percent": 0}
        return {
            "total_mb": int(status.ullTotalPhys // (1024 * 1024)),
            "available_mb": int(status.ullAvailPhys // (1024 * 1024)),
            "percent": int(status.dwMemoryLoad),
        }
    except Exception:
        return {"total_mb": 0, "available_mb": 0, "percent": 0}


def disk_space(path=None):
    # The selected game directory may not exist yet (fresh install, another
    # drive, or an instance that was removed).  Walk up to the nearest existing
    # folder instead of showing a misleading "0.0 GB".
    candidates = []
    for value in (path, config.minecraft_dir(), config.data_dir(), os.path.abspath(os.sep)):
        if value:
            candidates.append(os.path.abspath(str(value)))
    for target in candidates:
        while target and not os.path.exists(target):
            parent = os.path.dirname(target)
            if parent == target:
                break
            target = parent
        try:
            usage = shutil.disk_usage(target)
            return {
                "total_gb": round(usage.total / (1024 ** 3), 1),
                "free_gb": round(usage.free / (1024 ** 3), 1),
            }
        except Exception:
            continue
    return {"total_gb": 0.0, "free_gb": 0.0}


def recommended_memory():
    total = system_memory().get("total_mb") or 0
    if total <= 0:
        return 2048
    if total < 8 * 1024:
        return 1024
    if total < 16 * 1024:
        return 2048
    if total < 32 * 1024:
        return 4096
    return min(8192, max(4096, total // 4))


def summary():
    memory = system_memory()
    disk = disk_space()
    return {
        "os": platform.platform(terse=True),
        "cpu_count": os.cpu_count() or 0,
        "memory_total_mb": memory["total_mb"],
        "memory_available_mb": memory["available_mb"],
        "memory_percent": memory["percent"],
        "disk_total_gb": disk["total_gb"],
        "disk_free_gb": disk["free_gb"],
        "recommended_memory_mb": recommended_memory(),
    }


def instance_health(instance_name, account, java_path=""):
    """Return four small status rows for the dashboard, in display order."""
    instance = launcher_core.get_instance(str(instance_name or "")) if instance_name else None
    rows = []

    if not instance:
        rows.append({
            "key": "instance", "label": "实例", "level": "warn",
            "text": "尚未选择实例", "detail": "点击“新建实例”开始",
        })
        rows.append({
            "key": "version", "label": "游戏文件", "level": "warn",
            "text": "等待实例", "detail": "创建实例后自动检查",
        })
    else:
        version = str(instance.get("version_id") or "")
        version_json = os.path.join(
            launcher_core.minecraft_directory(), "versions", version, version + ".json"
        )
        if version and os.path.isfile(version_json):
            rows.append({
                "key": "instance", "label": "实例", "level": "good",
                "text": str(instance.get("name") or ""), "detail": "Minecraft " + version,
            })
            rows.append({
                "key": "version", "label": "游戏文件", "level": "good",
                "text": "已就绪", "detail": version + ".json",
            })
        else:
            rows.append({
                "key": "instance", "label": "实例", "level": "warn",
                "text": str(instance.get("name") or ""), "detail": "版本文件尚未下载",
            })
            rows.append({
                "key": "version", "label": "游戏文件", "level": "warn",
                "text": "需要补全", "detail": "启动时自动下载",
            })

    if account:
        rows.append({
            "key": "account", "label": "账户", "level": "good",
            "text": str(account.get("username") or "已登录"),
            "detail": "微软正版" if account.get("type") == "msa" else "离线账户",
        })
    else:
        rows.append({
            "key": "account", "label": "账户", "level": "bad",
            "text": "未登录", "detail": "请到账户页添加",
        })

    if java_path and os.path.isfile(str(java_path)):
        rows.append({
            "key": "java", "label": "Java", "level": "good",
            "text": os.path.basename(os.path.dirname(os.path.dirname(str(java_path)))),
            "detail": str(java_path),
        })
    else:
        rows.append({
            "key": "java", "label": "Java", "level": "good",
            "text": "自动检测", "detail": "启动时按版本选择",
        })
    return rows
