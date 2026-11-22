import hashlib
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def make_icon(path):
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return ""
    scale = 4
    size = 256 * scale
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (int(size * 0.035), int(size * 0.035), int(size * 0.965), int(size * 0.965)),
        radius=int(size * 0.215),
        fill=255,
    )
    top_color = (11, 18, 32)
    bottom_color = (30, 58, 138)
    gradient = Image.new("RGBA", (size, size))
    pixels = gradient.load()
    for y in range(size):
        ratio = y / max(1, size - 1)
        color = tuple(int(top_color[i] + (bottom_color[i] - top_color[i]) * ratio) for i in range(3))
        for x in range(size):
            pixels[x, y] = color + (255,)
    image.paste(gradient, (0, 0), mask)
    draw = ImageDraw.Draw(image, "RGBA")

    def pt(x, y):
        return (int(size * x), int(size * y))

    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(
        (int(size * 0.10), int(size * 0.02), int(size * 0.78), int(size * 0.68)),
        fill=(56, 189, 248, 42),
    )
    image.alpha_composite(glow)

    draw.rounded_rectangle(
        (int(size * 0.035), int(size * 0.035), int(size * 0.965), int(size * 0.965)),
        radius=int(size * 0.215),
        outline=(56, 189, 248, 255),
        width=max(2, int(size * 0.012)),
    )
    left = [pt(0.255, 0.385), pt(0.50, 0.525), pt(0.50, 0.795), pt(0.255, 0.655)]
    right = [pt(0.745, 0.385), pt(0.50, 0.525), pt(0.50, 0.795), pt(0.745, 0.655)]
    top = [pt(0.50, 0.245), pt(0.745, 0.385), pt(0.50, 0.525), pt(0.255, 0.385)]
    draw.polygon(left, fill=(14, 165, 198, 255))
    draw.polygon(right, fill=(109, 74, 224, 255))
    draw.polygon(top, fill=(15, 23, 42, 255))
    draw.line(top + [top[0]], fill=(103, 232, 249, 255), width=max(2, int(size * 0.016)), joint="curve")
    draw.polygon([pt(0.455, 0.325), pt(0.455, 0.445), pt(0.565, 0.385)], fill=(248, 250, 252, 255))
    draw.line([pt(0.265, 0.385), pt(0.49, 0.515)], fill=(255, 255, 255, 85), width=max(1, int(size * 0.009)))
    draw.line([pt(0.51, 0.525), pt(0.51, 0.785)], fill=(255, 255, 255, 85), width=max(1, int(size * 0.009)))

    image = image.resize((256, 256), Image.LANCZOS)
    image.save(path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return path


def main():
    import PySide6

    build_env = os.environ.get("BSL_BUILD_ENV") or ""
    qwindows = os.path.join(os.path.dirname(PySide6.__file__), "plugins", "platforms", "qwindows.dll")
    icon = make_icon(os.path.join(ROOT, "build_icon.ico"))
    hidden_imports = [
        "minecraft_launcher_lib.utils",
        "minecraft_launcher_lib.install",
        "minecraft_launcher_lib.command",
        "minecraft_launcher_lib.types",
        "minecraft_launcher_lib.runtime",
        "minecraft_launcher_lib.mrpack",
        "minecraft_launcher_lib.mod_loader",
        "minecraft_launcher_lib.microsoft_account",
    ]
    onedir = os.environ.get("BSL_ONEDIR") == "1"
    app_name = "BlockStartLauncherPortable" if onedir else "BlockStartLauncher"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onedir" if onedir else "--onefile",
        "--noconsole",
        "--name",
        app_name,
        "--clean",
        "--noconfirm",
        "--optimize",
        "2",
        "--runtime-tmpdir",
        ".bsl_runtime",
    ]
    for module in hidden_imports:
        command.extend(["--hidden-import", module])
    # None of these are used by the launcher at runtime.  Excluding them keeps
    # PyInstaller from pulling optional Qt/Python baggage into the onefile exe.
    for module in (
        "tkinter",
        "unittest",
        "pydoc",
        "doctest",
        "lib2to3",
        "PIL",
        "numpy",
        "PySide6.QtNetwork",
        "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets",
        "PySide6.QtPrintSupport",
        "PySide6.QtSvg",
        "PySide6.QtXml",
        "PySide6.QtDBus",
        "PySide6.QtDesigner",
        "PySide6.QtHelp",
        "PySide6.QtUiTools",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.QtMultimedia",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets",
    ):
        command.extend(["--exclude-module", module])
    if build_env:
        command.extend(["--paths", build_env])
    if os.path.isfile(qwindows):
        command.extend(["--add-binary", qwindows + os.pathsep + "PySide6/plugins/platforms"])
    if icon:
        command.extend(["--icon", icon])
    version_file = os.path.join(ROOT, "version_info.txt")
    if os.path.isfile(version_file):
        command.extend(["--version-file", version_file])
    command.append(os.path.join(ROOT, "run.py"))
    print("执行：" + " ".join(command))
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        print("打包失败，退出码：" + str(result.returncode))
        raise SystemExit(result.returncode)
    dist = os.path.join(ROOT, "dist")
    executables = []
    if os.path.isdir(dist):
        executables = [
            os.path.join(dist, name)
            for name in os.listdir(dist)
            if name.lower().endswith(".exe") and os.path.isfile(os.path.join(dist, name))
        ]
    if len(executables) != 1:
        print("警告：dist 目录中的 exe 数量为 " + str(len(executables)))
    for path in executables:
        print("产物：" + path)
        print("大小：" + str(os.path.getsize(path)) + " 字节")
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        print("SHA256：" + digest.hexdigest())
        try:
            with open(path + ".sha256", "w", encoding="ascii") as handle:
                handle.write(digest.hexdigest() + "  " + os.path.basename(path) + "\n")
        except Exception:
            pass
    starter = os.path.join(ROOT, "启动 BlockStart Launcher.bat")
    if os.path.isfile(starter) and os.path.isdir(dist):
        try:
            shutil.copy2(starter, os.path.join(dist, os.path.basename(starter)))
            print("启动脚本：" + os.path.join(dist, os.path.basename(starter)))
        except Exception:
            pass


if __name__ == "__main__":
    main()
