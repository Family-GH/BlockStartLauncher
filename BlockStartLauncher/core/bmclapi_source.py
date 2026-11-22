import os
import threading

import minecraft_launcher_lib
import requests

import config

_REPLACEMENTS = (
    ("https://launchermeta.mojang.com", config.BMCLAPI_BASE),
    ("http://launchermeta.mojang.com", config.BMCLAPI_BASE),
    ("https://piston-data.mojang.com", config.BMCLAPI_BASE),
    ("http://piston-data.mojang.com", config.BMCLAPI_BASE),
    ("https://launcher.mojang.com", config.BMCLAPI_BASE),
    ("http://launcher.mojang.com", config.BMCLAPI_BASE),
    ("https://libraries.minecraft.net", config.BMCLAPI_BASE + "/maven"),
    ("http://libraries.minecraft.net", config.BMCLAPI_BASE + "/maven"),
)

_PATCH_LOCK = threading.RLock()


def resolve_url(url):
    if not url:
        return url
    for original, mirrored in _REPLACEMENTS:
        if url.startswith(original):
            return mirrored + url[len(original) :]
    return url


class _MirrorPatcher:
    def __enter__(self):
        self._original = requests.get

        def patched(url, *args, **kwargs):
            return self._original(resolve_url(url), *args, **kwargs)

        requests.get = patched
        return self

    def __exit__(self, exc_type, exc, tb):
        requests.get = self._original
        return False


def _is_mojang_url(url):
    return resolve_url(url) != url


def _stream_download(url, target, progress_cb=None, timeout=60):
    directory = os.path.dirname(target)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temp = target + ".part"
    try:
        with requests.get(url, stream=True, timeout=timeout, headers={"User-Agent": config.USER_AGENT}) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            with open(temp, "wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 128):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    done += len(chunk)
                    if progress_cb:
                        try:
                            progress_cb(done, total)
                        except Exception:
                            pass
        os.replace(temp, target)
        return target
    except Exception:
        try:
            if os.path.isfile(temp):
                os.remove(temp)
        except Exception:
            pass
        raise


def download_with_fallback(url, target, progress_cb=None):
    candidates = []
    for candidate in (resolve_url(url), url):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    errors = []
    for candidate in candidates:
        try:
            return _stream_download(candidate, target, progress_cb)
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError("下载失败：" + " | ".join(errors))


def _install_plain(version_id, minecraft_directory, callback=None):
    try:
        minecraft_launcher_lib.install.install_minecraft_version(
            version_id, minecraft_directory, callback=callback
        )
    except TypeError:
        minecraft_launcher_lib.install.install_minecraft_version(version_id, minecraft_directory)


def install_version_with_source(version_id, minecraft_directory, callback=None, source="auto"):
    if source == "official":
        _install_plain(version_id, minecraft_directory, callback)
        return
    try:
        with _PATCH_LOCK:
            with _MirrorPatcher():
                _install_plain(version_id, minecraft_directory, callback)
        return
    except Exception as mirror_error:
        if source == "bmclapi":
            raise RuntimeError(f"版本安装失败：{mirror_error}") from mirror_error
        try:
            _install_plain(version_id, minecraft_directory, callback)
            return
        except Exception as official_error:
            raise RuntimeError(f"版本安装失败：{official_error}") from official_error
