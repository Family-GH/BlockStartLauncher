import hashlib
import os
import re
import subprocess
import sys

import requests

import config

_VERSION_PATTERN = re.compile(r"^[vV]?(\d+)\.(\d+)\.(\d+)([a-z]?)$")


def parse_version(text):
    match = _VERSION_PATTERN.match(str(text or "").strip())
    if not match:
        return (0, 0, 0, 0)
    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    # 同一版本号的正式版应高于带字母的预发布版，因此正式版标记为 1。
    stable = 0 if match.group(4) else 1
    return (major, minor, patch, stable)


def _source_type(source):
    kind = str(source.get("type") or "").lower()
    if kind:
        return kind
    url = str(source.get("url") or "").lower()
    if "api.github.com" in url:
        return "github"
    if "gitee.com/api" in url:
        return "gitee"
    return "manifest"


def _default_sources():
    sources = [{"type": "github", "url": config.GITHUB_RELEASES_API, "name": "GitHub"}]
    if getattr(config, "GITEE_RELEASES_API", ""):
        sources.append({"type": "gitee", "url": config.GITEE_RELEASES_API, "name": "Gitee"})
    for url in getattr(config, "EXTRA_UPDATE_SOURCES", []) or []:
        if str(url).strip():
            sources.append({"type": _source_type({"url": url}), "url": str(url).strip(), "name": "自定义源"})
    return sources


def _normalize_sources(sources):
    if not sources:
        return _default_sources()
    normalized = []
    if isinstance(sources, str):
        sources = [line.strip() for line in sources.replace(",", "\n").splitlines() if line.strip()]
    for item in sources:
        if isinstance(item, str):
            item = {"url": item.strip()}
        if not isinstance(item, dict) or not str(item.get("url") or "").strip():
            continue
        source = dict(item)
        source["type"] = _source_type(source)
        source["url"] = str(source["url"]).strip()
        source.setdefault("name", source["type"])
        normalized.append(source)
    return normalized


def _get_json(url, params=None, accept=None):
    headers = {"User-Agent": config.USER_AGENT}
    if accept:
        headers["Accept"] = accept
    try:
        response = requests.get(url, params=params, timeout=12, headers=headers)
        if response.status_code != 200:
            return None
        return response.json()
    except Exception:
        return None


def _asset_urls(assets, keyword=None):
    urls = []
    for asset in assets or []:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        url = str(asset.get("browser_download_url") or asset.get("download_url") or "")
        if not url:
            continue
        if name.lower().endswith(".exe") and (
            not keyword or keyword.lower() in name.lower() or "blockstart" in name.lower()
        ):
            urls.append(url)
    return urls


def _candidate(data, current, source):
    if not isinstance(data, dict):
        return None
    tag = str(data.get("tag_name") or data.get("version") or data.get("name") or "")
    version = parse_version(tag)
    if version <= current:
        return None
    urls = _asset_urls(data.get("assets"), config.UPDATE_ASSET_KEYWORD)
    direct = str(data.get("download_url") or data.get("download") or "")
    if direct:
        urls.append(direct)
    if not urls:
        return None
    digest = data.get("digest") or data.get("sha256") or ""
    if not digest and isinstance(data.get("asset"), dict):
        digest = data["asset"].get("digest") or ""
    size = data.get("size") or 0
    if not size and data.get("assets"):
        size = (data["assets"][0] or {}).get("size") or 0
    return {
        "sort_key": version,
        "version": tag.lstrip("vV") or tag,
        "tag_name": tag,
        "name": data.get("name") or tag,
        "body": data.get("body") or data.get("notes") or data.get("description") or "",
        "html_url": data.get("html_url") or data.get("url") or "",
        "download_url": urls[0],
        "download_urls": urls,
        "asset_name": os.path.basename(urls[0].split("?", 1)[0]),
        "size": int(size or 0),
        "digest": str(digest or ""),
        "prerelease": bool(data.get("prerelease")),
        "source": source.get("name") or source.get("type") or "更新源",
    }


def _fetch_source(source, current):
    kind = source["type"]
    data = None
    if kind == "github":
        data = _get_json(
            source["url"],
            params={"per_page": 30},
            accept="application/vnd.github+json",
        )
        if isinstance(data, list):
            return [_candidate(item, current, source) for item in data]
        return []
    if kind == "gitee":
        data = _get_json(source["url"], params={"per_page": 30})
        if isinstance(data, list):
            return [_candidate(item, current, source) for item in data]
        return []
    data = _get_json(source["url"])
    if isinstance(data, dict) and isinstance(data.get("releases"), list):
        data = data["releases"]
    if isinstance(data, dict):
        data = [data]
    if isinstance(data, list):
        return [_candidate(item, current, source) for item in data]
    return []


def check_for_update(current_version=None, sources=None):
    current = parse_version(current_version or config.LAUNCHER_VERSION)
    best = None
    for source in _normalize_sources(sources):
        try:
            candidates = _fetch_source(source, current)
        except Exception:
            candidates = []
        for item in candidates:
            if not item:
                continue
            if best is None or item["sort_key"] > best["sort_key"]:
                if best is not None:
                    item["download_urls"] = list(
                        dict.fromkeys(item["download_urls"] + best.get("download_urls", []))
                    )
                best = item
            elif item["sort_key"] == best["sort_key"]:
                best["download_urls"] = list(
                    dict.fromkeys(best.get("download_urls", []) + item.get("download_urls", []))
                )
    if not best:
        return None
    best.pop("sort_key", None)
    return best


def download_update(update, progress_cb=None):
    update = dict(update or {})
    urls = update.get("download_urls") or [update.get("download_url") or ""]
    urls = [url for url in urls if url]
    if not urls:
        raise RuntimeError("更新下载地址为空")
    version = str(update.get("version") or "new")
    safe_version = re.sub(r'[<>:"/\\|?*]', "_", version)
    target_dir = os.path.join(config.minecraft_dir(), "updates")
    os.makedirs(target_dir, exist_ok=True)
    target = os.path.join(target_dir, f"BlockStartLauncher_{safe_version}.exe")
    expected = str(update.get("digest") or "")
    if expected.lower().startswith("sha256:"):
        expected = expected.split(":", 1)[1]
    errors = []
    for index, url in enumerate(urls):
        temp = target + f".part{index}"
        digest = hashlib.sha256()
        try:
            with requests.get(
                url, stream=True, timeout=60, headers={"User-Agent": config.USER_AGENT}
            ) as response:
                response.raise_for_status()
                total = int(response.headers.get("Content-Length") or update.get("size") or 0)
                done = 0
                with open(temp, "wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 256):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        digest.update(chunk)
                        done += len(chunk)
                        if progress_cb:
                            progress_cb(done, total)
            if expected and digest.hexdigest().lower() != expected.lower():
                raise RuntimeError("SHA256 校验失败")
            os.replace(temp, target)
            return target
        except Exception as exc:
            errors.append(f"{url}: {exc}")
            try:
                if os.path.isfile(temp):
                    os.remove(temp)
            except Exception:
                pass
    raise RuntimeError("所有更新源均下载失败；" + " | ".join(errors[-3:]))


def apply_update(new_exe_path, current_exe=None):
    if not getattr(sys, "frozen", False):
        raise RuntimeError("当前不是打包后的程序，无法自动更新")
    current_exe = current_exe or sys.executable
    if not os.path.isfile(new_exe_path):
        raise RuntimeError("新版本文件不存在")
    exe_dir = os.path.dirname(current_exe)
    work_dir = os.path.join(config.data_dir(), "updates")
    try:
        os.makedirs(work_dir, exist_ok=True)
    except Exception:
        work_dir = os.path.dirname(current_exe)
    bat_path = os.path.join(work_dir, f"bsl_update_{os.getpid()}.bat")
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        "timeout /t 2 /nobreak >nul",
        ":wait",
        f'tasklist /FI "PID eq {os.getpid()}" 2>nul | find "{os.getpid()}" >nul',
        "if not errorlevel 1 (",
        "  timeout /t 1 /nobreak >nul",
        "  goto wait",
        ")",
        f'if exist "{current_exe}.old.exe" del /f /q "{current_exe}.old.exe" >nul 2>nul',
        f'move /y "{current_exe}" "{current_exe}.old.exe" >nul',
        f'copy /y "{new_exe_path}" "{current_exe}" >nul',
        f'start "" /D "{exe_dir}" "{current_exe}"',
        'del "%~f0" >nul 2>nul',
    ]
    content = "\r\n".join(lines) + "\r\n"
    try:
        with open(bat_path, "w", encoding="mbcs", errors="replace") as handle:
            handle.write(content)
    except Exception:
        with open(bat_path, "w", encoding="utf-8") as handle:
            handle.write(content)
    creationflags = 0
    if sys.platform == "win32":
        creationflags = 0x08000000
    subprocess.Popen(
        ["cmd.exe", "/c", bat_path],
        creationflags=creationflags,
        close_fds=True,
        cwd=work_dir,
    )
    sys.exit(0)
