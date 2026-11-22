import os
import re

_PATTERNS = (
    (
        re.compile(r"java\.lang\.OutOfMemoryError"),
        "内存不足 (OutOfMemoryError)",
        "请在设置页提高最大内存，或减少 Mod 数量、降低视距与画质。",
    ),
    (
        re.compile(r"GLFW error|Failed to create window|OpenGL|WGL", re.IGNORECASE),
        "图形驱动问题 (GLFW/OpenGL)",
        "请更新显卡驱动，关闭光影，或降低渲染设置后重试。",
    ),
    (
        re.compile(r"Missing or unsupported mandatory dependencies|Missing dependencies|missing dependency", re.IGNORECASE),
        "缺失依赖 (Missing dependencies)",
        "请检查 Mod 依赖与整合包完整性，可尝试修复 Minecraft 或重新安装整合包。",
    ),
    (
        re.compile(r"java\.lang\.ClassNotFoundException|NoClassDefFoundError"),
        "类缺失 (ClassNotFoundException)",
        "请确认 Java 版本与 Mod 兼容，并检查版本库文件是否损坏。",
    ),
)

_TAIL_LIMIT = 200000


def _latest_crash_file(instance_path):
    reports = os.path.join(instance_path, "crash-reports")
    try:
        files = [
            os.path.join(reports, name)
            for name in os.listdir(reports)
            if name.lower().endswith(".txt") and os.path.isfile(os.path.join(reports, name))
        ]
    except Exception:
        files = []
    if files:
        files.sort(key=lambda path: os.path.getmtime(path), reverse=True)
        return files[0]
    log = os.path.join(instance_path, "logs", "latest.log")
    if os.path.isfile(log):
        return log
    return ""


def _degraded(source, reason):
    return {
        "source": source,
        "summary": reason,
        "matches": [],
        "tail": "",
        "degraded": True,
    }


def analyze_crash(instance_path):
    try:
        if not instance_path or not os.path.isdir(instance_path):
            return None
        source = _latest_crash_file(instance_path)
        if not source:
            return None
        try:
            with open(source, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except Exception as exc:
            return _degraded(source, f"无法读取崩溃日志：{exc}")
        text = text[-_TAIL_LIMIT:]
        matches = []
        for pattern, title, advice in _PATTERNS:
            found = pattern.search(text)
            if not found:
                continue
            start = max(0, found.start() - 120)
            evidence = text[start : found.end() + 160].strip().splitlines()
            matches.append(
                {
                    "title": title,
                    "advice": advice,
                    "evidence": evidence[-1] if evidence else found.group(0),
                }
            )
        tail = "\n".join(text.strip().splitlines()[-40:])
        summary = matches[0]["title"] if matches else "未识别的崩溃原因"
        return {
            "source": source,
            "summary": summary,
            "matches": matches,
            "tail": tail,
            "degraded": False,
        }
    except Exception as exc:
        return _degraded(instance_path, f"崩溃日志解析失败：{exc}")
