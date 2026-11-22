"""Mod loader installation built on minecraft-launcher-lib.

Only public library APIs are used. No code or assets from other launchers
are copied.
"""

import minecraft_launcher_lib

from core import launcher_core

LOADERS = [
    ("", "原版（不加模组加载器）"),
    ("fabric", "Fabric"),
    ("forge", "Forge"),
    ("neoforge", "NeoForge"),
    ("quilt", "Quilt"),
]


def loader_label(loader_id):
    for key, label in LOADERS:
        if key == loader_id:
            return label
    return loader_id or "原版"


def _mod_loader_api():
    return getattr(minecraft_launcher_lib, "mod_loader", None)


def available_loaders():
    api = _mod_loader_api()
    if api is None:
        return ["fabric", "forge", "quilt"]
    try:
        return list(api.list_mod_loader())
    except Exception:
        return ["fabric", "forge", "neoforge", "quilt"]


def is_supported(loader_id, minecraft_version):
    if not loader_id:
        return True
    api = _mod_loader_api()
    if api is not None:
        try:
            return bool(api.get_mod_loader(loader_id).is_minecraft_version_supported(minecraft_version))
        except Exception:
            return False
    return False


def latest_loader_version(loader_id, minecraft_version):
    api = _mod_loader_api()
    if api is not None:
        return str(api.get_mod_loader(loader_id).get_latest_loader_version(minecraft_version))
    if loader_id == "fabric":
        import minecraft_launcher_lib.fabric as fabric

        versions = fabric.get_fabric_versions(minecraft_version)
        return str(versions[0]) if versions else ""
    if loader_id == "forge":
        import minecraft_launcher_lib.forge as forge

        versions = forge.find_forge_version(minecraft_version)
        return str(versions or "")
    raise RuntimeError("当前安装的 minecraft-launcher-lib 不支持 " + loader_label(loader_id))


def installed_version_id(loader_id, minecraft_version, loader_version):
    api = _mod_loader_api()
    if api is None:
        return ""
    try:
        return str(api.get_mod_loader(loader_id).get_installed_version(minecraft_version, loader_version))
    except Exception:
        return ""


def install_loader(loader_id, minecraft_version, loader_version="", java_path="", callback=None):
    if not loader_id:
        return ""
    if not minecraft_version:
        raise RuntimeError("请先选择 Minecraft 版本")
    api = _mod_loader_api()
    if api is not None:
        loader = api.get_mod_loader(loader_id)
        if not loader.is_minecraft_version_supported(minecraft_version):
            raise RuntimeError(
                "{} 不支持 Minecraft {}，请换一个版本或加载器。".format(
                    loader_label(loader_id), minecraft_version
                )
            )
        version = str(loader_version or "").strip() or None
        return str(
            loader.install(
                minecraft_version,
                launcher_core.minecraft_directory(),
                loader_version=version,
                callback=callback,
                java=java_path or None,
            )
        )
    if loader_id == "fabric":
        import minecraft_launcher_lib.fabric as fabric

        return str(
            fabric.install_fabric(
                minecraft_version,
                launcher_core.minecraft_directory(),
                loader_version=loader_version or None,
                callback=callback,
            )
        )
    if loader_id == "forge":
        import minecraft_launcher_lib.forge as forge

        target = loader_version or forge.find_forge_version(minecraft_version)
        if not target:
            raise RuntimeError("找不到适用于 Minecraft {} 的 Forge 版本".format(minecraft_version))
        forge.install_forge_version(target, launcher_core.minecraft_directory(), callback=callback)
        return str(forge.forge_to_version_id(target))
    if loader_id == "quilt":
        import minecraft_launcher_lib.quilt as quilt

        return str(
            quilt.install_quilt(
                minecraft_version,
                launcher_core.minecraft_directory(),
                loader_version=loader_version or None,
                callback=callback,
            )
        )
    raise RuntimeError("当前安装的 minecraft-launcher-lib 不支持 " + loader_label(loader_id))


def is_installed(loader_version_id):
    if not loader_version_id:
        return False
    import os

    return os.path.isfile(os.path.join(launcher_core.minecraft_directory(), "versions", loader_version_id, loader_version_id + ".json"))
