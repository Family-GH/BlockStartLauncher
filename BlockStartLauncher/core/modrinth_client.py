import json
import os

import requests

import config


def _request(path, params=None, timeout=15):
    urls = []
    for base in (config.MIRROR_MODRINTH_API, config.OFFICIAL_MODRINTH_API):
        base = (base or "").rstrip("/")
        if base and base not in urls:
            urls.append(base)
    last_error = None
    for base in urls:
        try:
            response = requests.get(
                base + path,
                params=params,
                timeout=timeout,
                headers={"User-Agent": config.USER_AGENT},
            )
            if response.status_code >= 500:
                last_error = f"HTTP {response.status_code}"
                continue
            if response.status_code == 404:
                raise RuntimeError("Modrinth 未找到请求的资源")
            if response.status_code >= 400:
                last_error = f"HTTP {response.status_code} {response.text[:160]}"
                continue
            return response.json()
        except requests.RequestException as exc:
            last_error = str(exc)
            continue
    raise RuntimeError("Modrinth 请求失败：" + str(last_error or "未知错误"))


def search(query, limit=20, project_type="mod"):
    params = {"query": str(query or ""), "limit": int(limit)}
    if project_type:
        params["facets"] = json.dumps([[f"project_type:{project_type}"]])
    data = _request("/v2/search", params)
    hits = data.get("hits") if isinstance(data, dict) else None
    return hits if isinstance(hits, list) else []


def get_project(project_id):
    return _request(f"/v2/project/{project_id}")


def get_versions(project_id, loaders=None, game_versions=None):
    params = {}
    if loaders:
        params["loaders"] = json.dumps(loaders)
    if game_versions:
        params["game_versions"] = json.dumps(game_versions)
    data = _request(f"/v2/project/{project_id}/version", params)
    return data if isinstance(data, list) else []


def _stream(url, temp, progress_cb=None):
    with requests.get(
        url, stream=True, timeout=60, headers={"User-Agent": config.USER_AGENT}
    ) as response:
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
                    progress_cb(done, total)


def download_version(version, target_dir, progress_cb=None):
    files = version.get("files") if isinstance(version, dict) else None
    if not files:
        raise RuntimeError("该版本没有可下载文件")
    chosen = next((item for item in files if item.get("primary")), files[0])
    url = chosen.get("url") or ""
    if not url:
        raise RuntimeError("下载链接为空")
    filename = chosen.get("filename") or os.path.basename(url.split("?")[0]) or "download.jar"
    target_dir = target_dir or os.path.join(config.minecraft_dir(), "mods")
    os.makedirs(target_dir, exist_ok=True)
    target = os.path.join(target_dir, filename)
    temp = target + ".part"
    mirror_url = url.replace("cdn.modrinth.com", "mod.mcimirror.top")
    try:
        try:
            _stream(mirror_url, temp, progress_cb)
        except Exception as exc:
            try:
                if os.path.isfile(temp):
                    os.remove(temp)
            except Exception:
                pass
            if isinstance(exc, RuntimeError) and "取消" in str(exc):
                raise
            _stream(url, temp, progress_cb)
        os.replace(temp, target)
        return target
    finally:
        if os.path.isfile(temp):
            try:
                os.remove(temp)
            except Exception:
                pass
