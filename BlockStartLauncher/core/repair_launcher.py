import json
import os

import config
from core import java_manager
from core.settings_store import DEFAULT_SETTINGS


def _settings_path(settings_path=None):
    return settings_path or os.path.join(config.base_dir(), "settings.json")


def _accounts_path():
    return os.path.join(config.base_dir(), "accounts.json")


def _check_json(path, expect_type, label):
    if not os.path.isfile(path):
        return {"name": label, "status": "missing", "detail": "文件不存在"}
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
        if not isinstance(data, expect_type):
            raise ValueError("结构不正确")
        return {"name": label, "status": "ok", "detail": "读取正常"}
    except Exception as exc:
        return {"name": label, "status": "corrupt", "detail": f"解析失败：{exc}"}


def diagnose_launcher(settings_path=None):
    checks = []
    checks.append(_check_json(_settings_path(settings_path), dict, "settings.json"))
    accounts = _check_json(_accounts_path(), list, "accounts.json")
    accounts["name"] = "accounts.json"
    checks.append(accounts)
    java_path = java_manager.find_existing_java()
    checks.append(
        {
            "name": "Java 运行环境",
            "status": "ok" if java_path else "missing",
            "detail": java_path or "未找到 Java",
        }
    )
    checks.append(
        {
            "name": "mc 目录",
            "status": "ok" if os.path.isdir(config.minecraft_dir()) else "missing",
            "detail": config.minecraft_dir(),
        }
    )
    return checks


def _backup_corrupt(path, actions, preserved):
    backup = path + ".bak"
    try:
        os.replace(path, backup)
        preserved.append(backup)
        actions.append(f"已将损坏文件重命名为 {os.path.basename(backup)}")
    except Exception:
        pass


def _write_defaults(settings_path, actions):
    try:
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        with open(settings_path, "w", encoding="utf-8") as handle:
            json.dump(DEFAULT_SETTINGS, handle, ensure_ascii=False, indent=2)
        actions.append("已写入默认 settings.json")
    except Exception:
        pass


def repair_launcher(settings_path=None, status_cb=None):
    settings_file = _settings_path(settings_path)
    result = {"repaired": False, "actions": [], "preserved": []}

    def status(text):
        if status_cb:
            status_cb(text)

    checks = diagnose_launcher(settings_file)
    status("正在检查启动器文件")
    for check in checks:
        if check["name"] == "settings.json" and check["status"] != "ok":
            if os.path.isfile(settings_file):
                _backup_corrupt(settings_file, result["actions"], result["preserved"])
            _write_defaults(settings_file, result["actions"])
            result["repaired"] = True
        if check["name"] == "accounts.json" and check["status"] != "ok":
            accounts_file = _accounts_path()
            if os.path.isfile(accounts_file):
                _backup_corrupt(accounts_file, result["actions"], result["preserved"])
            try:
                with open(accounts_file, "w", encoding="utf-8") as handle:
                    json.dump([], handle)
                result["actions"].append("已重建空的 accounts.json")
                result["repaired"] = True
            except Exception:
                pass
        if check["name"] == "Java 运行环境" and check["status"] != "ok":
            status("正在准备 Java 运行环境")
            try:
                java_path = java_manager.ensure_java(status_cb=status)
                result["actions"].append("已安装 Java：" + java_path)
                result["repaired"] = True
            except Exception as exc:
                result["actions"].append("Java 修复失败：" + str(exc))
        if check["name"] == "mc 目录" and check["status"] != "ok":
            try:
                os.makedirs(config.minecraft_dir(), exist_ok=True)
                result["actions"].append("已创建 mc 目录")
                result["repaired"] = True
            except Exception:
                pass
    if not result["actions"]:
        result["actions"].append("未发现需要修复的问题")
    return result
