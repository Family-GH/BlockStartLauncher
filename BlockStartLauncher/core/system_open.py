"""Open URLs, folders and files through the Windows shell.

The launcher requests administrator rights.  External programs (browsers,
Explorer, image viewers, ...) normally run at medium integrity, and some of
them refuse to start as an elevated child.  In that case ShellExecute simply
fails, which is why "open browser" and "open folder" can do nothing at all.

This module keeps the normal path first, then falls back to launching through
the token of the current desktop shell (explorer.exe).  The result is a
de-elevated helper process, which behaves exactly like a double click in
Explorer.  Every public function returns ``(ok, error_message)`` so the UI can
show a useful message instead of silently ignoring a failure.
"""

from __future__ import annotations

import ctypes
import os
import re
import subprocess
import sys
import webbrowser
from ctypes import wintypes

_IS_WINDOWS = os.name == "nt"
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)

# Windows constants
_TOKEN_ASSIGN_PRIMARY = 0x0001
_TOKEN_DUPLICATE = 0x0002
_TOKEN_QUERY = 0x0008
_TOKEN_ADJUST_PRIVILEGES = 0x0020
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_MAXIMUM_ALLOWED = 0x02000000
_SECURITY_IMPERSONATION = 2
_TOKEN_PRIMARY = 1
_LOGON_WITH_PROFILE = 0x00000001
_CREATE_UNICODE_ENVIRONMENT = 0x00000400
_SE_PRIVILEGE_ENABLED = 0x00000002
_ERROR_NOT_ALL_ASSIGNED = 1300
_SW_SHOWNORMAL = 1
_STARTF_USESHOWWINDOW = 0x00000001


def _is_admin():
    if not _IS_WINDOWS:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _error_text(exc=None):
    if exc is not None:
        try:
            return str(exc)
        except Exception:
            pass
    try:
        code = ctypes.get_last_error()
    except Exception:
        code = 0
    if code:
        try:
            return ctypes.FormatError(code).strip()
        except Exception:
            return "Windows error %s" % code
    return "未知错误"


def _shell_execute(target):
    """Last-resort ShellExecuteW; returns (ok, message)."""
    if not _IS_WINDOWS:
        return False, "仅支持 Windows"
    try:
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        shell32.ShellExecuteW.argtypes = [
            wintypes.HWND,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            ctypes.c_int,
        ]
        shell32.ShellExecuteW.restype = ctypes.c_void_p
        result = shell32.ShellExecuteW(None, "open", str(target), None, None, _SW_SHOWNORMAL)
        if int(result or 0) > 32:
            return True, ""
        return False, "ShellExecute 返回失败（%s）" % _error_text()
    except Exception as exc:
        return False, _error_text(exc)


def _startfile(target):
    if not _IS_WINDOWS:
        return False, "仅支持 Windows"
    try:
        os.startfile(str(target))  # type: ignore[attr-defined]
        return True, ""
    except Exception as exc:
        return False, _error_text(exc)


def _popen(application, arguments):
    try:
        subprocess.Popen(
            [str(application)] + [str(item) for item in arguments],
            close_fds=True,
            cwd=os.path.expanduser("~"),
        )
        return True, ""
    except Exception as exc:
        return False, _error_text(exc)


# ---------------------------------------------------------------------------
# Medium-integrity helper through the desktop shell token
# ---------------------------------------------------------------------------

class _STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", _LUID), ("Attributes", wintypes.DWORD)]


class _TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", _LUID_AND_ATTRIBUTES * 1)]


def _enable_impersonate_privilege():
    """CreateProcessWithTokenW needs SeImpersonatePrivilege enabled."""
    try:
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        advapi32.OpenProcessToken.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        advapi32.OpenProcessToken.restype = wintypes.BOOL
        advapi32.LookupPrivilegeValueW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            ctypes.POINTER(_LUID),
        ]
        advapi32.LookupPrivilegeValueW.restype = wintypes.BOOL
        advapi32.AdjustTokenPrivileges.argtypes = [
            wintypes.HANDLE,
            wintypes.BOOL,
            ctypes.POINTER(_TOKEN_PRIVILEGES),
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        advapi32.AdjustTokenPrivileges.restype = wintypes.BOOL
        token = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(
            kernel32.GetCurrentProcess(),
            _TOKEN_ADJUST_PRIVILEGES | _TOKEN_QUERY,
            ctypes.byref(token),
        ):
            return
        try:
            luid = _LUID()
            if not advapi32.LookupPrivilegeValueW(
                None, "SeImpersonatePrivilege", ctypes.byref(luid)
            ):
                return
            privileges = _TOKEN_PRIVILEGES()
            privileges.PrivilegeCount = 1
            privileges.Privileges[0].Luid = luid
            privileges.Privileges[0].Attributes = _SE_PRIVILEGE_ENABLED
            advapi32.AdjustTokenPrivileges(
                token, False, ctypes.byref(privileges), 0, None, None
            )
        finally:
            kernel32.CloseHandle(token)
    except Exception:
        return


def _shell_token():
    """Duplicate the primary token of the interactive explorer shell."""
    if not _IS_WINDOWS:
        return None
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

        user32.GetShellWindow.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        kernel32.OpenProcess.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        advapi32.OpenProcessToken.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        advapi32.OpenProcessToken.restype = wintypes.BOOL
        advapi32.DuplicateTokenEx.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        advapi32.DuplicateTokenEx.restype = wintypes.BOOL
        hwnd = user32.GetShellWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None
        process = kernel32.OpenProcess(
            _PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
        )
        if not process:
            return None
        try:
            token = wintypes.HANDLE()
            if not advapi32.OpenProcessToken(
                process,
                _TOKEN_DUPLICATE | _TOKEN_ASSIGN_PRIMARY | _TOKEN_QUERY,
                ctypes.byref(token),
            ):
                return None
            try:
                duplicate = wintypes.HANDLE()
                if not advapi32.DuplicateTokenEx(
                    token,
                    _MAXIMUM_ALLOWED,
                    None,
                    _SECURITY_IMPERSONATION,
                    _TOKEN_PRIMARY,
                    ctypes.byref(duplicate),
                ):
                    return None
                return duplicate
            finally:
                kernel32.CloseHandle(token)
        finally:
            kernel32.CloseHandle(process)
    except Exception:
        return None


def _launch_with_shell_token(application, arguments):
    """Start application at the shell's (usually medium) integrity level."""
    if not _IS_WINDOWS or not _is_admin():
        return False, ""
    token = _shell_token()
    if not token:
        return False, "无法取得桌面 shell 令牌"
    _enable_impersonate_privilege()
    try:
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        advapi32.CreateProcessWithTokenW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.LPCWSTR,
            ctypes.POINTER(_STARTUPINFO),
            ctypes.POINTER(_PROCESS_INFORMATION),
        ]
        advapi32.CreateProcessWithTokenW.restype = wintypes.BOOL
        command_line = subprocess.list2cmdline(
            [str(application)] + [str(item) for item in arguments]
        )
        startup = _STARTUPINFO()
        startup.cb = ctypes.sizeof(startup)
        startup.dwFlags = _STARTF_USESHOWWINDOW
        startup.wShowWindow = _SW_SHOWNORMAL
        info = _PROCESS_INFORMATION()
        cwd = os.environ.get("USERPROFILE") or os.path.dirname(str(application)) or None
        ok = advapi32.CreateProcessWithTokenW(
            token,
            _LOGON_WITH_PROFILE,
            str(application),
            ctypes.create_unicode_buffer(command_line),
            _CREATE_UNICODE_ENVIRONMENT,
            None,
            cwd,
            ctypes.byref(startup),
            ctypes.byref(info),
        )
        if not ok:
            return False, "以普通权限启动失败（%s）" % _error_text()
        try:
            if info.hProcess:
                kernel32.CloseHandle(info.hProcess)
            if info.hThread:
                kernel32.CloseHandle(info.hThread)
        finally:
            return True, ""
    except Exception as exc:
        return False, _error_text(exc)
    finally:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle(token)


def _system32(name):
    root = os.environ.get("SystemRoot") or r"C:\Windows"
    return os.path.join(root, "System32", name)


def _windows_dir(name):
    root = os.environ.get("SystemRoot") or r"C:\Windows"
    return os.path.join(root, name)


def open_url(url):
    """Open an http(s) URL; returns (ok, error_message)."""
    url = str(url or "").strip()
    if not _URL_RE.match(url):
        return False, "不是有效的 http/https 链接"
    errors = []
    if _IS_WINDOWS and _is_admin():
        # Rundll32 is a tiny helper which calls the real default-browser
        # association; starting it with Explorer's token avoids the elevated
        # child being rejected by browsers and AppX apps.
        ok, message = _launch_with_shell_token(
            _system32("rundll32.exe"), ["url.dll,FileProtocolHandler", url]
        )
        if ok:
            return True, ""
        if message:
            errors.append(message)
    for opener in (_shell_execute, _startfile):
        ok, message = opener(url)
        if ok:
            return True, ""
        if message:
            errors.append(message)
    try:
        if webbrowser.open(url, new=2):
            return True, ""
    except Exception as exc:
        errors.append(_error_text(exc))
    return False, "；".join(dict.fromkeys(errors)) or "系统没有可用的浏览器"


def open_folder(path):
    """Open a folder in Explorer; returns (ok, error_message)."""
    path = os.path.abspath(os.path.expanduser(str(path or "")))
    if not os.path.isdir(path):
        return False, "文件夹不存在：%s" % path
    errors = []
    if _IS_WINDOWS and _is_admin():
        ok, message = _launch_with_shell_token(
            _windows_dir("explorer.exe"), [path]
        )
        if ok:
            return True, ""
        if message:
            errors.append(message)
    for opener in (_startfile, lambda target: _popen(_windows_dir("explorer.exe"), [target]), _shell_execute):
        ok, message = opener(path)
        if ok:
            return True, ""
        if message:
            errors.append(message)
    return False, "；".join(dict.fromkeys(errors)) or "无法打开文件夹"


def open_file(path):
    """Open a file with its default application."""
    path = os.path.abspath(os.path.expanduser(str(path or "")))
    if not os.path.exists(path):
        return False, "文件不存在：%s" % path
    errors = []
    if _IS_WINDOWS and _is_admin():
        ok, message = _launch_with_shell_token(
            _system32("rundll32.exe"),
            ["shell32.dll,ShellExec_RunDLL", path],
        )
        if ok:
            return True, ""
        if message:
            errors.append(message)
    for opener in (_startfile, _shell_execute):
        ok, message = opener(path)
        if ok:
            return True, ""
        if message:
            errors.append(message)
    return False, "；".join(dict.fromkeys(errors)) or "无法打开文件"


def reveal_path(path):
    """Open the parent folder and select the given file/folder."""
    path = os.path.abspath(os.path.expanduser(str(path or "")))
    if not os.path.exists(path):
        return False, "路径不存在：%s" % path
    parent = path if os.path.isdir(path) else os.path.dirname(path)
    if os.path.isdir(path):
        return open_folder(path)
    if _IS_WINDOWS:
        args = ["/select," + path]
        errors = []
        if _is_admin():
            ok, message = _launch_with_shell_token(
                _windows_dir("explorer.exe"), args
            )
            if ok:
                return True, ""
            if message:
                errors.append(message)
        ok, message = _popen(_windows_dir("explorer.exe"), args)
        if ok:
            return True, ""
        if message:
            errors.append(message)
        ok, message = _shell_execute(parent)
        if ok:
            return True, ""
        if message:
            errors.append(message)
        return False, "；".join(dict.fromkeys(errors))
    return open_folder(parent)
