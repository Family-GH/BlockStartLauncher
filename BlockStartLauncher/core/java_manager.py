import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

import requests

import config

_CACHE = {"time": 0.0, "items": []}
_CACHE_SECONDS = 60
_MAX_CANDIDATES = 80


def _hidden_flags():
    if sys.platform == "win32":
        return 0x08000000
    return 0


def java_info(path):
    if not path:
        return None
    if os.path.isdir(path):
        path = os.path.join(path, "bin", "java.exe" if sys.platform == "win32" else "java")
    if os.path.basename(path).lower() == "javaw.exe":
        sibling = os.path.join(os.path.dirname(path), "java.exe")
        if os.path.isfile(sibling):
            path = sibling
    if not os.path.isfile(path):
        return None
    try:
        completed = subprocess.run(
            [path, "-version"],
            capture_output=True,
            timeout=8,
            creationflags=_hidden_flags(),
        )
        text = (completed.stderr or b"").decode("utf-8", "replace") + (completed.stdout or b"").decode(
            "utf-8", "replace"
        )
    except Exception:
        return None
    match = re.search(r'version "([^"]+)"', text)
    if not match:
        return None
    version = match.group(1)
    numbers = re.match(r"(\d+)", version)
    if not numbers:
        return None
    major = int(numbers.group(1))
    if major == 1:
        parts = version.split(".")
        if len(parts) > 1 and parts[1].isdigit():
            major = int(parts[1])
    return {"path": path, "version": version, "major": major}


def _registry_homes():
    if sys.platform != "win32":
        return []
    try:
        import winreg
    except Exception:
        return []
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\Java Development Kit"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\Java Runtime Environment"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\JDK"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\JRE"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Eclipse Adoptium\JDK"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Eclipse Adoptium\JRE"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Eclipse Foundation\JDK"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\JDK"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Azul Systems\Zulu"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Semeru\JDK"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Amazon Corretto"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\BellSoft\Liberica"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\JavaSoft\Java Development Kit"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\JavaSoft\Java Runtime Environment"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\JavaSoft\Java Development Kit"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\JavaSoft\Java Runtime Environment"),
    ]
    homes = []

    def read_values(key):
        for value_name in ("JavaHome", "Path", "InstallationPath", "InstallLocation"):
            try:
                value, _kind = winreg.QueryValueEx(key, value_name)
                if value:
                    homes.append(str(value))
                    return
            except OSError:
                continue

    for root, subkey in roots:
        try:
            with winreg.OpenKey(root, subkey) as key:
                read_values(key)
                try:
                    count = winreg.QueryInfoKey(key)[0]
                except Exception:
                    count = 0
                for index in range(min(count, 20)):
                    try:
                        name = winreg.EnumKey(key, index)
                        with winreg.OpenKey(key, name) as child:
                            read_values(child)
                    except OSError:
                        continue
        except OSError:
            continue
    return homes


def _walk_java(root, max_depth=5, limit=20):
    results = []
    root = os.path.expandvars(os.path.expanduser(root or ""))
    if not root or not os.path.isdir(root):
        return results
    root_depth = root.rstrip(os.sep).count(os.sep)
    try:
        for current, dirs, files in os.walk(root):
            depth = current.rstrip(os.sep).count(os.sep) - root_depth
            if depth >= max_depth:
                dirs[:] = []
            if "java.exe" in files:
                results.append(os.path.join(current, "java.exe"))
            elif "java" in files:
                results.append(os.path.join(current, "java"))
            if len(results) >= limit:
                break
    except Exception:
        pass
    return results


def _candidate_sources():
    candidates = []

    def add(path, source):
        if path:
            candidates.append((str(path), source))

    home = os.path.expanduser("~")
    appdata = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    localappdata = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
    program_files = os.environ.get("ProgramFiles") or r"C:\Program Files"
    program_files_x86 = os.environ.get("ProgramFiles(x86)") or r"C:\Program Files (x86)"
    program_data = os.environ.get("ProgramData") or r"C:\ProgramData"

    for home_dir in _registry_homes():
        add(os.path.join(home_dir, "bin", "java.exe"), "注册表")
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        add(os.path.join(java_home, "bin", "java.exe"), "JAVA_HOME")
    for name in ("java.exe", "javaw.exe", "java"):
        found = shutil.which(name)
        if found:
            add(found, "系统 PATH")

    for root in (
        os.path.join(config.minecraft_dir(), "runtime"),
        os.path.join(appdata, ".minecraft", "runtime"),
        os.path.join(appdata, "PCL", "runtime"),
        os.path.join(appdata, "PCL", "Java"),
        os.path.join(appdata, "HMCL", "runtime"),
        os.path.join(appdata, ".hmcl", "runtime"),
        os.path.join(appdata, "BakaXL", "runtime"),
        os.path.join(appdata, "PrismLauncher", "java"),
        os.path.join(appdata, "MultiMC", "java"),
        os.path.join(localappdata, "Programs"),
        os.path.join(home, "scoop", "apps"),
        r"D:\PCL\runtime",
        r"D:\PCL\Java",
        r"D:\PCL\PCL\runtime",
        r"D:\PCL\.minecraft\runtime",
    ):
        for path in _walk_java(root, max_depth=5 if "runtime" in root else 4, limit=12):
            add(path, "已安装运行环境")

    for drive in ("C:", "D:", "E:", "F:"):
        for folder in ("Java", "jdk", "jre", "Environment", "software", "tools", "dev"):
            try:
                for path in glob.glob(os.path.join(drive + os.sep, folder, "*", "bin", "java.exe")):
                    add(path, "常见安装目录")
                for path in glob.glob(os.path.join(drive + os.sep, folder, "*", "*", "bin", "java.exe")):
                    add(path, "常见安装目录")
            except Exception:
                continue
        for pattern in (
            os.path.join(drive + os.sep, "PCL", "runtime", "*", "*", "bin", "java.exe"),
            os.path.join(drive + os.sep, "PCL", ".minecraft", "runtime", "*", "*", "bin", "java.exe"),
        ):
            try:
                for path in glob.glob(pattern):
                    add(path, "PCL 运行环境")
            except Exception:
                continue

    patterns = [
        os.path.join(program_files, "Java", "*", "bin", "java.exe"),
        os.path.join(program_files_x86, "Java", "*", "bin", "java.exe"),
        os.path.join(program_files, "Eclipse Adoptium", "*", "bin", "java.exe"),
        os.path.join(program_files, "Eclipse Foundation", "*", "bin", "java.exe"),
        os.path.join(program_files, "Microsoft", "jdk-*", "bin", "java.exe"),
        os.path.join(program_files, "Zulu", "*", "bin", "java.exe"),
        os.path.join(program_files, "Amazon Corretto", "*", "bin", "java.exe"),
        os.path.join(program_files, "BellSoft", "*", "bin", "java.exe"),
        os.path.join(program_files, "Semeru", "*", "bin", "java.exe"),
        os.path.join(program_files, "GraalVM", "*", "bin", "java.exe"),
        os.path.join(program_files, "Android", "Android Studio", "jbr", "bin", "java.exe"),
        os.path.join(program_files, "JetBrains", "*", "jbr", "bin", "java.exe"),
        os.path.join(localappdata, "Programs", "Eclipse Adoptium", "*", "bin", "java.exe"),
        os.path.join(localappdata, "Programs", "Microsoft", "jdk-*", "bin", "java.exe"),
        os.path.join(localappdata, "Programs", "Java", "*", "bin", "java.exe"),
        os.path.join(program_data, "chocolatey", "lib", "temurin*", "tools", "bin", "java.exe"),
        os.path.join(home, "scoop", "apps", "openjdk*", "current", "bin", "java.exe"),
        os.path.join(home, "scoop", "apps", "temurin*", "current", "bin", "java.exe"),
        os.path.join(home, ".jdks", "*", "bin", "java.exe"),
    ]
    for pattern in patterns:
        try:
            for path in glob.glob(pattern):
                add(path, "常见安装目录")
        except Exception:
            continue
    return candidates


def detect_java_installations(force=False, cancel=None):
    now = time.time()
    if not force and _CACHE["items"] and now - _CACHE["time"] < _CACHE_SECONDS:
        return [dict(item) for item in _CACHE["items"]]
    found = []
    seen = set()
    started = time.time()
    for path, source in _candidate_sources():
        if cancel and cancel():
            break
        if len(found) >= 20 or len(seen) >= _MAX_CANDIDATES:
            break
        if time.time() - started > 8:
            break
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen:
            continue
        seen.add(normalized)
        info = java_info(path)
        if not info:
            continue
        info["source"] = source
        found.append(info)
    found.sort(key=lambda item: (item["major"], item["version"]), reverse=True)
    _CACHE["items"] = found
    _CACHE["time"] = now
    return [dict(item) for item in found]


def find_existing_java(preferred_path="", required_major=0):
    if preferred_path:
        info = java_info(preferred_path)
        if info and (not required_major or info["major"] == required_major):
            return info["path"]
    installations = detect_java_installations()
    if not installations:
        return ""
    if required_major:
        compatible = [item for item in installations if item["major"] == required_major]
        if compatible:
            compatible.sort(key=lambda item: (item["major"], item["version"]))
            return compatible[0]["path"]
        return ""
    for item in installations:
        if item["major"] >= 17:
            return item["path"]
    return installations[0]["path"]


def _adoptium_asset(major=17):
    major = max(8, min(21, int(major or 17)))
    url = (
        f"https://api.adoptium.net/v3/assets/latest/{major}/hotspot"
        "?architecture=x64&image_type=jdk&os=windows&vendor=eclipse"
    )
    response = requests.get(url, timeout=30, headers={"User-Agent": config.USER_AGENT})
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list) or not data:
        raise RuntimeError("Adoptium 未返回可用 JDK")
    package = data[0]["binary"]["package"]
    return package["link"], package.get("name") or f"jdk{major}.zip"


def _find_java_under(root):
    for current, _dirs, files in os.walk(root):
        if "java.exe" in files:
            return os.path.join(current, "java.exe")
        if "java" in files:
            return os.path.join(current, "java")
    return ""


def _download_adoptium(progress_cb=None, status_cb=None, required_major=17):
    major = max(8, min(21, int(required_major or 17)))
    link, name = _adoptium_asset(major)
    if status_cb:
        status_cb(f"正在下载 Java {major}（约 180MB）")
    download_dir = tempfile.mkdtemp(prefix="bsl_java_")
    archive = os.path.join(download_dir, name if name.lower().endswith(".zip") else name + ".zip")
    try:
        with requests.get(
            link, stream=True, timeout=120, headers={"User-Agent": config.USER_AGENT}
        ) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            with open(archive, "wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    done += len(chunk)
                    if progress_cb:
                        progress_cb(done, total)
        if status_cb:
            status_cb(f"正在解压 Java {major}")
        target = os.path.join(config.minecraft_dir(), "runtime", f"bsl-jdk{major}")
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
        os.makedirs(target, exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(target)
        java_path = _find_java_under(target)
        if not java_path:
            raise RuntimeError("解压后未找到 java.exe")
        return java_path
    finally:
        shutil.rmtree(download_dir, ignore_errors=True)


def _runtime_install(progress_cb=None, status_cb=None, required_major=17):
    import minecraft_launcher_lib

    runtime_name = "java-runtime-gamma"
    if required_major <= 8:
        runtime_name = "java-runtime-alpha"
    elif required_major >= 21:
        runtime_name = "java-runtime-delta"
    if status_cb:
        status_cb("正在安装 Mojang Java 运行时")
    try:
        minecraft_launcher_lib.runtime.install_jvm_runtime(
            runtime_name, config.minecraft_dir(), callback=None
        )
    except TypeError:
        minecraft_launcher_lib.runtime.install_jvm_runtime(runtime_name, config.minecraft_dir())
    java_path = _find_java_under(os.path.join(config.minecraft_dir(), "runtime"))
    if not java_path:
        raise RuntimeError("运行时安装完成但未找到 Java")
    return java_path


def ensure_java(callback=None, status_cb=None, preferred_path="", required_major=0):
    required_major = int(required_major or 0)
    if preferred_path:
        info = java_info(preferred_path)
        if info and (not required_major or info["major"] == required_major):
            return info["path"]
        if status_cb:
            if info:
                status_cb(f"已选 Java {info['major']} 不满足游戏要求，正在自动查找")
            else:
                status_cb("指定的 Java 不可用，正在自动查找")
    existing = find_existing_java("", required_major)
    if existing:
        return existing
    errors = []
    target_major = required_major or 17
    try:
        return _download_adoptium(callback, status_cb, target_major)
    except Exception as exc:
        errors.append(f"Adoptium: {exc}")
    try:
        return _runtime_install(callback, status_cb, target_major)
    except Exception as exc:
        errors.append(f"Mojang 运行时: {exc}")
    required_text = f"Java {required_major}" if required_major else "Java"
    raise RuntimeError(
        f"没有找到可用的 {required_text}，自动下载也失败了。请在设置页点击“手动选择 Java”，选择电脑中的 java.exe。"
        "（" + "；".join(errors) + "）"
    )
