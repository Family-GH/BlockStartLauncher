"""Small, dependency-free protection layer for launcher-owned secrets.

Account tokens are encrypted with Windows DPAPI for the *current Windows user*.
The ciphertext cannot be decrypted by another Windows account or by simply
copying accounts.json to another computer.  Files are still written atomically
and the previous good copy is kept as a .bak file.
"""

import base64
import ctypes
import json
import os
import shutil
from ctypes import wintypes

import config

FORMAT = "bsl-secure"
VERSION = 2
_ENTROPY = b"BlockStartLauncher/account-store/v2"
_CRYPTPROTECT_UI_FORBIDDEN = 0x1


class SecureStoreError(RuntimeError):
    pass


def available():
    return os.name == "nt" and hasattr(ctypes, "windll")


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _configure():
    if not available():
        return
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL


_configure()


def _blob(data):
    buffer = ctypes.create_string_buffer(bytes(data), len(data))
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


def _take_blob(blob):
    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        if blob.pbData:
            ctypes.windll.kernel32.LocalFree(blob.pbData)


def _crypt(protect, data):
    if not available():
        raise SecureStoreError("当前系统不支持 Windows DPAPI 加密")
    data_in, keep_in = _blob(data)
    entropy_in, keep_entropy = _blob(_ENTROPY)
    data_out = _DataBlob()
    function = (
        ctypes.windll.crypt32.CryptProtectData
        if protect
        else ctypes.windll.crypt32.CryptUnprotectData
    )
    if protect:
        ok = function(
            ctypes.byref(data_in),
            "BlockStart Launcher 账户数据",
            ctypes.byref(entropy_in),
            None,
            None,
            _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(data_out),
        )
    else:
        ok = function(
            ctypes.byref(data_in),
            None,
            ctypes.byref(entropy_in),
            None,
            None,
            _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(data_out),
        )
    if not ok:
        raise SecureStoreError("Windows 数据保护失败（错误码 %s）" % ctypes.GetLastError())
    return _take_blob(data_out)


def protect(data):
    return _crypt(True, data)


def unprotect(data):
    return _crypt(False, data)


def seal_payload(payload):
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    cipher = protect(raw)
    return {
        "format": FORMAT,
        "version": VERSION,
        "cipher": "dpapi-current-user",
        "payload": base64.b64encode(cipher).decode("ascii"),
    }


def open_payload(envelope):
    if not isinstance(envelope, dict) or envelope.get("format") != FORMAT:
        raise SecureStoreError("不是受保护的账户文件")
    try:
        cipher = base64.b64decode(str(envelope.get("payload") or ""), validate=True)
    except Exception as exc:
        raise SecureStoreError("账户数据损坏") from exc
    return json.loads(unprotect(cipher).decode("utf-8"))


def _write_bytes(path, data):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    temp = path + ".tmp"
    with open(temp, "wb") as handle:
        handle.write(data)
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except Exception:
            pass
    os.replace(temp, path)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def write_envelope(path, payload):
    """Write an encrypted JSON envelope and keep the previous file as .bak."""
    data = json.dumps(seal_payload(payload), ensure_ascii=False, indent=2).encode("utf-8")
    if os.path.isfile(path):
        try:
            shutil.copy2(path, path + ".bak")
        except Exception:
            pass
    _write_bytes(path, data)


def read_json(path):
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def read_envelope(path):
    raw = read_json(path)
    if raw is None:
        return None
    return open_payload(raw)


def is_envelope(path):
    try:
        raw = read_json(path)
        return isinstance(raw, dict) and raw.get("format") == FORMAT
    except Exception:
        return False


def data_path(name):
    return os.path.join(config.data_dir(), name)
