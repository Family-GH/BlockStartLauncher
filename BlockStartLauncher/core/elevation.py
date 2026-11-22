"""Windows 管理员权限检查与 UAC 提权。"""

import ctypes
import os
import subprocess
import sys


def is_admin():
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _show_message(text):
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.MessageBoxW(
            None, str(text), "BlockStart Launcher", 0x00000030
        )
    except Exception:
        pass


def _launch_as_admin():
    if getattr(sys, "frozen", False):
        executable = os.path.abspath(sys.executable)
        arguments = sys.argv[1:]
        working_directory = os.path.dirname(executable)
    else:
        executable = os.path.abspath(sys.executable)
        script = os.path.abspath(sys.argv[0])
        arguments = [script] + list(sys.argv[1:])
        working_directory = os.path.dirname(script)
    params = subprocess.list2cmdline(arguments)
    try:
        os.environ["BSL_ELEVATED"] = "1"
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable, params, working_directory, 1
        )
        return int(result) > 32
    except Exception as exc:
        _show_message("请求管理员权限失败：" + str(exc))
        return False


def ensure_admin():
    """返回 True 表示当前进程应继续运行。"""
    if os.name != "nt" or is_admin():
        return True
    if os.environ.get("BSL_SKIP_ELEVATION") == "1":
        return True
    if os.environ.get("BSL_ELEVATED") == "1":
        _show_message(
            "启动器需要管理员权限才能管理游戏文件和更新，但提权没有成功。\n"
            "请右键 BlockStartLauncher.exe，选择“以管理员身份运行”。"
        )
        return False
    if _launch_as_admin():
        return False
    _show_message(
        "启动器需要管理员权限才能管理游戏文件和更新。\n"
        "如果你刚刚取消了系统提示，可以重新启动并选择“是”。"
    )
    return False
