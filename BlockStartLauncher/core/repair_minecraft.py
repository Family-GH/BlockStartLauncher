import os
import shutil

from core import launcher_core


def _bridge(callback, result):
    def status_cb(text):
        result["log"].append(str(text))

    return launcher_core.mll_callback(callback, status_cb)


def _manual_files(version_dir, version_id):
    known = {f"{version_id}.json", f"{version_id}.jar"}
    manual = []
    try:
        for name in os.listdir(version_dir):
            if name in known or name.endswith("-natives") or name.endswith(".log"):
                continue
            manual.append(name)
    except Exception:
        return []
    return manual


def repair_version(version_id, minecraft_dir, callback=None, mode="auto"):
    result = {"repaired": False, "actions": [], "warnings": [], "log": []}
    version_dir = os.path.join(minecraft_dir, "versions", version_id or "")
    try:
        if not version_id:
            raise RuntimeError("未选择要修复的版本")
        if mode not in ("auto", "reinstall", "natives"):
            mode = "auto"
        if not os.path.isfile(os.path.join(version_dir, version_id + ".json")):
            result["warnings"].append("版本尚未完整安装，将执行完整安装")
        if mode == "reinstall":
            manual = _manual_files(version_dir, version_id)
            if manual:
                result["warnings"].append("版本目录中存在手动添加的文件：" + "、".join(manual[:8]))
            if os.path.isdir(version_dir):
                shutil.rmtree(version_dir)
                result["actions"].append("已删除旧版本目录")
        elif mode == "natives":
            if os.path.isdir(version_dir):
                for name in os.listdir(version_dir):
                    if name.endswith("-natives"):
                        shutil.rmtree(os.path.join(version_dir, name), ignore_errors=True)
            result["actions"].append("已清理原生库目录")
        else:
            result["actions"].append("正在补全缺失或损坏的版本文件")
        launcher_core.install_version(version_id, callback=_bridge(callback, result))
        result["repaired"] = True
        result["actions"].append("版本文件修复完成")
        result["log"].append("修复完成：" + version_id)
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        result["warnings"].append(message)
        result["log"].append("修复失败：" + message)
        if "checksum" in message.lower():
            result["warnings"].append("检测到校验失败，已保留现有文件，请稍后重试")
        elif "not found" in message.lower() or "VersionNotFound" in message:
            result["warnings"].append("版本不存在或网络不可用，请检查版本号与下载源")
    return result
