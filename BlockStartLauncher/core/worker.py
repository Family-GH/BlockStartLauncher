import os
import time
import zipfile

import requests
from PySide6.QtCore import QThread, Signal

import config
from core import (
    account_manager,
    java_manager,
    launcher_core,
    loader_installer,
    manual_verify,
    mod_manager,
    modpack_installer,
    modrinth_client,
    repair_launcher,
    repair_minecraft,
    server_status,
    updater,
)


class Worker(QThread):
    progress = Signal(int, int)
    status_changed = Signal(str)
    finished_ok = Signal(object)
    finished_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def _progress_cb(self):
        def callback(done, total):
            if self._cancelled:
                raise RuntimeError("操作已取消")
            self.progress.emit(int(done or 0), int(total or 0))

        return callback

    def _status_cb(self):
        return lambda text: self.status_changed.emit(str(text))

    def _mll_callback(self):
        return launcher_core.mll_callback(self._progress_cb(), self._status_cb())


class InstallWorker(Worker):
    def __init__(self, version_id, parent=None, source="auto"):
        super().__init__(parent)
        self.version_id = version_id
        self.source = source or "auto"

    def _mll_callback(self):
        def progress_cb(value, maximum):
            if self._cancelled:
                raise RuntimeError("下载已取消")
            self.progress.emit(int(value or 0), int(maximum or 0))

        return launcher_core.mll_callback(progress_cb, self._status_cb())

    def run(self):
        try:
            self.status_changed.emit("正在安装 Minecraft " + str(self.version_id))
            launcher_core.install_version(
                self.version_id, callback=self._mll_callback(), source=self.source
            )
            self.finished_ok.emit({"version_id": self.version_id})
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            if self._cancelled:
                message = "下载已停止。已经下载的文件会保留，下次启动会自动补全。"
            self.finished_error.emit(message)


class LaunchWorker(Worker):
    def __init__(self, version_id, game_dir, java_path, account_id, max_memory_mb, extra_jvm_args, client_id="", game_settings=None, parent=None):
        super().__init__(parent)
        self.version_id = version_id
        self.game_dir = game_dir
        self.java_path = java_path
        self.account_id = account_id
        self.max_memory_mb = max_memory_mb
        self.extra_jvm_args = extra_jvm_args
        self.client_id = client_id
        self.game_settings = dict(game_settings or {})

    def run(self):
        try:
            self.status_changed.emit("正在准备登录信息")
            account_options = account_manager.get_launch_options(self.account_id, self.client_id or None)
            options = launcher_core.build_launch_options(
                account_options,
                self.max_memory_mb,
                self.extra_jvm_args,
                self.java_path,
                self.game_dir,
                self.game_settings,
            )
            process = launcher_core.launch_game(self.version_id, self.game_dir, self.java_path, options)
            self.finished_ok.emit({"pid": process.pid, "version_id": self.version_id})
        except Exception as exc:
            self.finished_error.emit(str(exc) or exc.__class__.__name__)


class JavaSetupWorker(Worker):
    def __init__(self, preferred_path="", required_major=0, version_id="", parent=None):
        super().__init__(parent)
        self.preferred_path = preferred_path
        self.required_major = int(required_major or 0)
        self.version_id = version_id

    def run(self):
        try:
            major = self.required_major or launcher_core.required_java_major(self.version_id)
            tip = f"（需要 Java {major}）" if major else ""
            self.status_changed.emit("正在检测 Java" + tip)
            java_path = java_manager.ensure_java(
                self._progress_cb(),
                self._status_cb(),
                self.preferred_path,
                required_major=major,
            )
            self.finished_ok.emit(java_path)
        except Exception as exc:
            self.finished_error.emit(str(exc) or exc.__class__.__name__)


class JavaDetectWorker(Worker):
    def run(self):
        try:
            self.finished_ok.emit(
                java_manager.detect_java_installations(
                    force=True, cancel=lambda: self._cancelled
                )
            )
        except Exception as exc:
            self.finished_error.emit(str(exc) or exc.__class__.__name__)


class LoaderInstallWorker(Worker):
    def __init__(self, loader_id, minecraft_version, loader_version="", java_path="", parent=None):
        super().__init__(parent)
        self.loader_id = loader_id
        self.minecraft_version = minecraft_version
        self.loader_version = loader_version
        self.java_path = java_path

    def run(self):
        try:
            self.status_changed.emit("正在安装 " + loader_installer.loader_label(self.loader_id))
            version_id = loader_installer.install_loader(
                self.loader_id,
                self.minecraft_version,
                self.loader_version,
                self.java_path,
                self._mll_callback(),
            )
            self.finished_ok.emit({"loader": self.loader_id, "version_id": version_id})
        except Exception as exc:
            self.finished_error.emit(str(exc) or exc.__class__.__name__)


class MSLoginWorker(Worker):
    device_code_ready = Signal(str, str)

    def __init__(self, client_id="", parent=None):
        super().__init__(parent)
        self.client_id = client_id
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            client_id = str(self.client_id or config.MS_CLIENT_ID or "").strip()
            flow = account_manager.start_device_flow(client_id)
            self.device_code_ready.emit(flow.get("user_code", ""), flow.get("verification_uri", ""))
            token = account_manager.poll_device_token(
                flow,
                client_id,
                cancel=lambda: self._cancelled,
                status_cb=self._status_cb(),
            )
            account = account_manager.complete_login(token)
            self.finished_ok.emit(account)
        except Exception as exc:
            self.finished_error.emit(str(exc) or exc.__class__.__name__)


class SkinProfileWorker(Worker):
    def __init__(self, account_id, client_id="", parent=None):
        super().__init__(parent)
        self.account_id = account_id
        self.client_id = client_id

    def run(self):
        try:
            self.status_changed.emit("正在获取皮肤与披风…")
            profile = account_manager.get_profile(self.account_id, self.client_id or None)
            skins = profile.get("skins") or []
            skin = b""
            if skins:
                active = next((item for item in skins if item.get("state") == "ACTIVE"), skins[0])
                try:
                    skin = account_manager.download_texture(active.get("url"))
                except Exception:
                    skin = b""
            capes = []
            active_cape = ""
            for index, cape in enumerate(profile.get("capes") or []):
                if index >= 8:
                    break
                item = {
                    "id": str(cape.get("id") or ""),
                    "alias": str(cape.get("alias") or "披风"),
                    "active": cape.get("state") == "ACTIVE",
                }
                if item["active"]:
                    active_cape = item["id"]
                try:
                    item["data"] = account_manager.download_texture(cape.get("url"))
                except Exception:
                    item["data"] = b""
                capes.append(item)
            self.finished_ok.emit(
                {
                    "profile": profile,
                    "skin": skin,
                    "capes": capes,
                    "active_cape": active_cape,
                }
            )
        except Exception as exc:
            self.finished_error.emit(str(exc) or exc.__class__.__name__)


class SkinActionWorker(Worker):
    def __init__(self, action, account_id, client_id="", **kwargs):
        super().__init__(kwargs.pop("parent", None))
        self.action = action
        self.account_id = account_id
        self.client_id = client_id
        self.kwargs = kwargs

    def run(self):
        try:
            if self.action == "upload":
                self.status_changed.emit("正在上传皮肤…")
                account_manager.upload_skin(
                    self.account_id,
                    self.kwargs.get("file_path") or "",
                    self.kwargs.get("variant") or "classic",
                    self.client_id or None,
                )
            elif self.action == "reset":
                self.status_changed.emit("正在恢复默认皮肤…")
                account_manager.reset_skin(self.account_id, self.client_id or None)
            elif self.action == "cape":
                self.status_changed.emit("正在更换披风…")
                account_manager.set_cape(
                    self.account_id,
                    self.kwargs.get("cape_id") or "",
                    self.client_id or None,
                )
            else:
                raise RuntimeError("未知的皮肤操作")
            self.finished_ok.emit({"action": self.action})
        except Exception as exc:
            self.finished_error.emit(str(exc) or exc.__class__.__name__)


class ModSearchWorker(Worker):
    def __init__(self, query, limit=20, project_type="mod", parent=None):
        super().__init__(parent)
        self.query = query
        self.limit = limit
        self.project_type = project_type

    def run(self):
        try:
            self.status_changed.emit("正在搜索 Modrinth")
            self.finished_ok.emit(
                modrinth_client.search(self.query, self.limit, project_type=self.project_type)
            )
        except Exception as exc:
            self.finished_error.emit(str(exc) or exc.__class__.__name__)


class ModDetailsWorker(Worker):
    def __init__(self, project_id, parent=None):
        super().__init__(parent)
        self.project_id = project_id

    def run(self):
        try:
            self.status_changed.emit("正在获取模组介绍")
            project = modrinth_client.get_project(self.project_id)
            versions = modrinth_client.get_versions(self.project_id)
            icon = b""
            icon_url = str((project or {}).get("icon_url") or "")
            if icon_url:
                try:
                    response = requests.get(
                        icon_url, timeout=15, headers={"User-Agent": config.USER_AGENT}
                    )
                    if response.status_code == 200:
                        icon = response.content
                except Exception:
                    icon = b""
            self.finished_ok.emit({"project": project, "versions": versions, "icon": icon})
        except Exception as exc:
            self.finished_error.emit(str(exc) or exc.__class__.__name__)


class ModDownloadWorker(Worker):
    def __init__(self, project_id, game_version, target_dir, version_id="", parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.game_version = game_version
        self.target_dir = target_dir
        self.version_id = version_id

    def run(self):
        try:
            self.status_changed.emit("正在获取版本列表")
            versions = modrinth_client.get_versions(self.project_id)
            if not versions:
                raise RuntimeError("没有找到可下载的版本")
            version = None
            if self.version_id:
                version = next(
                    (item for item in versions if str(item.get("id")) == str(self.version_id)), None
                )
                if version is None:
                    raise RuntimeError("这个模组版本已经不存在，请重新选择")
            else:
                candidates = []
                if self.game_version:
                    candidates = [
                        item for item in versions if self.game_version in (item.get("game_versions") or [])
                    ]
                version = (candidates or versions)[0]
            self.status_changed.emit("正在下载 " + str(version.get("name") or version.get("version_number") or ""))
            path = modrinth_client.download_version(version, self.target_dir, self._progress_cb())
            self.finished_ok.emit(
                {
                    "path": path,
                    "name": version.get("name") or version.get("version_number") or os.path.basename(path),
                }
            )
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            if self._cancelled:
                message = "下载已停止"
            self.finished_error.emit(message)


class ModpackInstallWorker(Worker):
    def __init__(self, pack_path, instance_name, overwrite=False, parent=None):
        super().__init__(parent)
        self.pack_path = pack_path
        self.instance_name = instance_name
        self.overwrite = overwrite

    def run(self):
        try:
            target = launcher_core.instance_path(self.instance_name)
            if os.path.isdir(target) and not self.overwrite:
                raise RuntimeError("实例已存在：" + self.instance_name)
            if os.path.isdir(target) and self.overwrite:
                import shutil

                shutil.rmtree(target)
            self.status_changed.emit("正在安装整合包")
            result = modpack_installer.install_pack(
                self.pack_path,
                target,
                callback=self._progress_cb(),
                status_cb=self._status_cb(),
            )
            result["instance"] = self.instance_name
            self.finished_ok.emit(result)
        except Exception as exc:
            self.finished_error.emit(str(exc) or exc.__class__.__name__)


class SaveBackupWorker(Worker):
    def __init__(self, instance_name, parent=None):
        super().__init__(parent)
        self.instance_name = instance_name

    def run(self):
        target = ""
        temp = ""
        try:
            source = os.path.join(launcher_core.instance_path(self.instance_name), "saves")
            if not os.path.isdir(source):
                raise RuntimeError("当前实例没有存档目录")
            backup_dir = os.path.join(launcher_core.minecraft_directory(), "backups")
            os.makedirs(backup_dir, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            target = os.path.join(backup_dir, f"{self.instance_name}_{stamp}.zip")
            temp = target + ".part"
            files = []
            for root, _dirs, names in os.walk(source):
                for name in names:
                    files.append(os.path.join(root, name))
            if not files:
                raise RuntimeError("当前实例没有可备份的存档")
            with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as archive:
                for index, path in enumerate(files):
                    if self._cancelled:
                        raise RuntimeError("备份已停止")
                    archive.write(path, os.path.relpath(path, source))
                    self.progress.emit(index + 1, len(files))
            if self._cancelled:
                raise RuntimeError("备份已停止")
            os.replace(temp, target)
            self.status_changed.emit("存档备份完成")
            self.finished_ok.emit({"path": target, "count": len(files)})
        except Exception as exc:
            for path in (temp, target):
                if path and os.path.isfile(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass
            message = "备份已停止" if self._cancelled else (str(exc) or exc.__class__.__name__)
            self.finished_error.emit(message)


class RepairMinecraftWorker(Worker):
    def __init__(self, version_id, mode="auto", minecraft_dir=None, parent=None):
        super().__init__(parent)
        self.version_id = version_id
        self.mode = mode
        self.minecraft_dir = minecraft_dir or launcher_core.minecraft_directory()

    def run(self):
        try:
            self.status_changed.emit("正在修复 Minecraft")
            result = repair_minecraft.repair_version(
                self.version_id, self.minecraft_dir, callback=self._progress_cb(), mode=self.mode
            )
            self.finished_ok.emit(result)
        except Exception as exc:
            self.finished_error.emit(str(exc) or exc.__class__.__name__)


class RepairLauncherWorker(Worker):
    diagnoses_ready = Signal(list)

    def __init__(self, do_repair=False, parent=None):
        super().__init__(parent)
        self.do_repair = do_repair

    def run(self):
        try:
            checks = repair_launcher.diagnose_launcher()
            self.diagnoses_ready.emit(checks)
            if self.do_repair:
                self.status_changed.emit("正在修复启动器")
                result = repair_launcher.repair_launcher(status_cb=self._status_cb())
            else:
                result = {"repaired": False, "actions": [], "preserved": [], "diagnoses": checks}
            result["diagnoses"] = checks
            self.finished_ok.emit(result)
        except Exception as exc:
            self.finished_error.emit(str(exc) or exc.__class__.__name__)


class ManualVerifyWorker(Worker):
    inventory_ready = Signal(list)

    def __init__(self, version_id, parent=None):
        super().__init__(parent)
        self.version_id = version_id

    def run(self):
        try:
            self.status_changed.emit("正在扫描版本文件")
            inventory = manual_verify.build_file_inventory(self.version_id)
            self.inventory_ready.emit(inventory)
            self.finished_ok.emit(inventory)
        except Exception as exc:
            self.finished_error.emit(str(exc) or exc.__class__.__name__)


class ManualRepairWorker(Worker):
    def __init__(self, version_id, paths, parent=None):
        super().__init__(parent)
        self.version_id = version_id
        self.paths = list(paths or [])

    def run(self):
        try:
            self.status_changed.emit("正在修复选中文件")
            result = manual_verify.repair_selected(
                self.version_id, self.paths, progress_cb=self._progress_cb()
            )
            self.finished_ok.emit(result)
        except Exception as exc:
            self.finished_error.emit(str(exc) or exc.__class__.__name__)


class ServerPingWorker(Worker):
    def __init__(self, address, port=None, parent=None):
        super().__init__(parent)
        self.address = address
        self.port = port

    def run(self):
        try:
            self.status_changed.emit("正在连接服务器")
            result = server_status.ping(self.address, self.port)
            self.finished_ok.emit(result)
        except Exception as exc:
            self.finished_error.emit(str(exc) or exc.__class__.__name__)


class VersionListWorker(Worker):
    def run(self):
        try:
            self.finished_ok.emit(launcher_core.get_version_list())
        except Exception as exc:
            self.finished_error.emit(str(exc) or exc.__class__.__name__)


class AccountRefreshWorker(Worker):
    def __init__(self, account_id, client_id="", parent=None):
        super().__init__(parent)
        self.account_id = account_id
        self.client_id = client_id

    def run(self):
        try:
            self.status_changed.emit("正在刷新登录令牌")
            account = account_manager.refresh(self.account_id, self.client_id or None)
            self.finished_ok.emit(account)
        except Exception as exc:
            self.finished_error.emit(str(exc) or exc.__class__.__name__)


class UpdaterWorker(Worker):
    check_done = Signal(dict)
    check_empty = Signal()

    def __init__(self, mode="check", update_info=None, sources=None, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.update_info = update_info
        self.sources = sources

    def run(self):
        try:
            if self.mode == "check":
                self.status_changed.emit("正在检查更新")
                info = updater.check_for_update(sources=self.sources)
                if info:
                    self.check_done.emit(info)
                else:
                    self.check_empty.emit()
                return
            self.status_changed.emit("正在下载更新")
            path = updater.download_update(self.update_info, self._progress_cb())
            self.finished_ok.emit(path)
        except Exception as exc:
            self.finished_error.emit(str(exc) or exc.__class__.__name__)
