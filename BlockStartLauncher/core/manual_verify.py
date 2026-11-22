import hashlib
import json
import os

import requests

import config


def _sha1_file(path):
    digest = hashlib.sha1()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _asset_index(version_data, minecraft_dir):
    info = version_data.get("assetIndex") or {}
    index_id = info.get("id")
    if not index_id:
        return {}
    local = os.path.join(minecraft_dir, "assets", "indexes", f"{index_id}.json")
    if os.path.isfile(local):
        try:
            return _read_json(local)
        except Exception:
            pass
    url = info.get("url")
    if url:
        try:
            response = requests.get(url, timeout=15, headers={"User-Agent": config.USER_AGENT})
            response.raise_for_status()
            return response.json()
        except Exception:
            return {}
    return {}


def _collect(version_id, minecraft_dir):
    version_json = os.path.join(minecraft_dir, "versions", version_id, version_id + ".json")
    with open(version_json, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    entries = []
    seen = set()

    def add(path, entry_type, sha1, size, url):
        if not path or path in seen:
            return
        seen.add(path)
        entries.append(
            {
                "path": path,
                "type": entry_type,
                "expected_sha1": str(sha1 or ""),
                "size": int(size or 0),
                "url": str(url or ""),
            }
        )

    client = (data.get("downloads") or {}).get("client") or {}
    add(f"versions/{version_id}/{version_id}.jar", "client", client.get("sha1"), client.get("size"), client.get("url"))
    for library in data.get("libraries") or []:
        downloads = library.get("downloads") or {}
        artifact = downloads.get("artifact") or {}
        if artifact.get("path"):
            add(
                "libraries/" + artifact["path"],
                "library",
                artifact.get("sha1"),
                artifact.get("size"),
                artifact.get("url") or ("https://libraries.minecraft.net/" + artifact["path"]),
            )
        natives = library.get("natives") or {}
        classifier_key = natives.get("windows")
        if classifier_key:
            classifier_key = str(classifier_key).replace("${arch}", "64")
            classifier = (downloads.get("classifiers") or {}).get(classifier_key)
            if classifier and classifier.get("path"):
                add(
                    "libraries/" + classifier["path"],
                    "native",
                    classifier.get("sha1"),
                    classifier.get("size"),
                    classifier.get("url") or ("https://libraries.minecraft.net/" + classifier["path"]),
                )
    assets = _asset_index(data, minecraft_dir)
    for _name, obj in (assets.get("objects") or {}).items():
        try:
            sha1 = str(obj.get("hash") or "")
            if not sha1:
                continue
            add(
                f"assets/objects/{sha1[:2]}/{sha1}",
                "asset",
                sha1,
                obj.get("size"),
                f"https://resources.download.minecraft.net/{sha1[:2]}/{sha1}",
            )
        except Exception:
            continue
    return entries, data


def build_file_inventory(version_id, minecraft_dir=None):
    minecraft_dir = minecraft_dir or config.minecraft_dir()
    if not version_id:
        return []
    try:
        entries, _data = _collect(version_id, minecraft_dir)
    except Exception:
        return []
    inventory = []
    for entry in entries:
        absolute = os.path.join(minecraft_dir, entry["path"].replace("/", os.sep))
        status = "missing"
        if os.path.isfile(absolute):
            try:
                if entry["expected_sha1"] and _sha1_file(absolute).lower() != entry["expected_sha1"].lower():
                    status = "mismatch"
                else:
                    status = "ok"
            except Exception:
                status = "mismatch"
        inventory.append(
            {
                "path": entry["path"],
                "type": entry["type"],
                "status": status,
                "expected_sha1": entry["expected_sha1"],
                "size": entry["size"],
            }
        )
    return inventory


def _download_file(url, target, progress_cb=None):
    os.makedirs(os.path.dirname(target), exist_ok=True)
    temp = target + ".part"
    try:
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
        os.replace(temp, target)
        return target
    except Exception:
        try:
            if os.path.isfile(temp):
                os.remove(temp)
        except Exception:
            pass
        raise


def repair_selected(version_id, paths, minecraft_dir=None, progress_cb=None):
    minecraft_dir = minecraft_dir or config.minecraft_dir()
    result = {"repaired": [], "failed": [], "log": []}
    try:
        entries, _data = _collect(version_id, minecraft_dir)
    except Exception as exc:
        result["log"].append(f"无法读取版本清单：{exc}")
        result["failed"] = [{"path": str(path), "error": "版本清单不可用"} for path in paths]
        return result
    by_path = {entry["path"]: entry for entry in entries}
    total = max(1, len(paths))
    for index, relative in enumerate(paths):
        try:
            entry = by_path.get(relative)
            if not entry:
                raise RuntimeError("不在当前版本清单中")
            if not entry["url"]:
                raise RuntimeError("没有可用下载地址")
            target = os.path.join(minecraft_dir, relative.replace("/", os.sep))
            _download_file(entry["url"], target)
            if entry["expected_sha1"]:
                if _sha1_file(target).lower() != entry["expected_sha1"].lower():
                    raise RuntimeError("SHA1 校验失败")
            result["repaired"].append(relative)
            result["log"].append("已修复：" + relative)
        except Exception as exc:
            result["failed"].append({"path": relative, "error": str(exc)})
            result["log"].append(f"修复失败：{relative}（{exc}）")
        if progress_cb:
            progress_cb(index + 1, total)
    return result
