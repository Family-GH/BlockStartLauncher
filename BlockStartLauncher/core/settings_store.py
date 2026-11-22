import copy
import json
import os
import shutil

import config

DEFAULT_SETTINGS = {
    "theme": "dark",
    "animations": True,
    "max_memory_mb": 2048,
    "jvm_args": "",
    "download_threads": 8,
    "download_source": "auto",
    "ms_client_id": "",
    "java_path": "",
    "game_dir": "",
    "game_dirs": [],
    "window_width": 1100,
    "window_height": 720,
    "fullscreen": False,
    "game_args": "",
    "auto_join_server": "",
    "server_port": "25565",
    "background_image_path": "",
    "music_dir": "",
    "last_page_index": 0,
    "last_instance": "",
    "last_version_id": "",
    "last_account_uuid": "",
    "window_geometry": "",
    "window_state": "",
    "ignored_update_version": "",
    "last_update_check_ts": 0,
    "update_sources": [],
    "repair_history": [],
    "manual_verify_selection": {},
}


class SettingsStore:
    def __init__(self, path=None):
        self.path = path or os.path.join(config.base_dir(), "settings.json")
        self._data = copy.deepcopy(DEFAULT_SETTINGS)
        self.load()

    def load(self):
        raw = None
        try:
            if os.path.isfile(self.path):
                with open(self.path, "r", encoding="utf-8-sig") as handle:
                    raw = json.load(handle)
        except Exception:
            raw = None
        if isinstance(raw, dict):
            try:
                self._data = self._merge(raw)
                return
            except Exception:
                raw = None
        # Do not replace a damaged settings file with defaults before trying
        # the previous good copy saved by save().
        backup = self.path + ".bak"
        try:
            if os.path.isfile(backup):
                with open(backup, "r", encoding="utf-8-sig") as handle:
                    restored = json.load(handle)
                if isinstance(restored, dict):
                    try:
                        if os.path.isfile(self.path):
                            os.replace(self.path, self.path + ".corrupt")
                    except Exception:
                        pass
                    self._data = self._merge(restored)
                    return
        except Exception:
            pass
        if os.path.isfile(self.path) and raw is None:
            try:
                os.replace(self.path, self.path + ".corrupt")
            except Exception:
                pass
        self._data = copy.deepcopy(DEFAULT_SETTINGS)

    def _merge(self, raw):
        if not isinstance(raw, dict):
            raise ValueError("settings root is not an object")
        merged = copy.deepcopy(DEFAULT_SETTINGS)
        for key, value in raw.items():
            merged[key] = value
        for key, value in DEFAULT_SETTINGS.items():
            if key not in raw:
                merged[key] = copy.deepcopy(value)

        def integer(key, fallback, minimum, maximum):
            try:
                value = int(merged.get(key, fallback))
            except (TypeError, ValueError, OverflowError):
                value = fallback
            merged[key] = max(minimum, min(maximum, value))

        def text(key, fallback=""):
            value = merged.get(key)
            merged[key] = fallback if value is None else str(value)

        def boolean(key, fallback=False):
            value = merged.get(key, fallback)
            if isinstance(value, str):
                value = value.strip().lower() in ("1", "true", "yes", "on")
            merged[key] = bool(value)

        if merged.get("theme") not in ("dark", "light"):
            merged["theme"] = "dark"
        boolean("animations", True)
        integer("max_memory_mb", 2048, 512, 32768)
        integer("download_threads", 8, 1, 64)
        integer("window_width", 1100, 0, 7680)
        integer("window_height", 720, 0, 4320)
        integer("last_page_index", 0, 0, 7)
        boolean("fullscreen", False)
        text("jvm_args")
        text("game_args")
        text("auto_join_server")
        text("ms_client_id")
        text("java_path")
        text("game_dir")
        text("last_instance")
        text("last_version_id")
        text("last_account_uuid")
        text("window_geometry")
        text("background_image_path")
        text("music_dir")
        text("ignored_update_version")
        port = str(merged.get("server_port") or "25565").strip()
        merged["server_port"] = port if port.isdigit() else "25565"
        source = str(merged.get("download_source") or "auto")
        merged["download_source"] = source if source in ("auto", "bmclapi", "official") else "auto"
        if not isinstance(merged.get("repair_history"), list):
            merged["repair_history"] = []
        if not isinstance(merged.get("manual_verify_selection"), dict):
            merged["manual_verify_selection"] = {}
        directories = merged.get("game_dirs")
        if not isinstance(directories, list):
            directories = []
        merged["game_dirs"] = [str(item) for item in directories if item]
        sources = merged.get("update_sources")
        if isinstance(sources, str):
            sources = [sources]
        if not isinstance(sources, list):
            sources = []
        merged["update_sources"] = [str(item).strip() for item in sources if str(item).strip()]
        return merged

    def save(self):
        try:
            directory = os.path.dirname(self.path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            if os.path.isfile(self.path):
                try:
                    shutil.copy2(self.path, self.path + ".bak")
                except Exception:
                    pass
            temp = self.path + ".tmp"
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump(self._data, handle, ensure_ascii=False, indent=2)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except Exception:
                    pass
            os.replace(temp, self.path)
            return True
        except Exception:
            return False

    def get(self, key, default=None):
        if key in self._data:
            return self._data.get(key)
        if key in DEFAULT_SETTINGS:
            return copy.deepcopy(DEFAULT_SETTINGS[key])
        return default

    def set(self, key, value):
        self._data[key] = value

    def update(self, values):
        if isinstance(values, dict):
            self._data.update(values)

    def append_repair_history(self, record):
        history = self._data.get("repair_history")
        if not isinstance(history, list):
            history = []
        history.append(record)
        self._data["repair_history"] = history[-20:]

    def get_manual_selection(self, version_id):
        selection = self._data.get("manual_verify_selection")
        if not isinstance(selection, dict):
            return []
        paths = selection.get(str(version_id))
        if not isinstance(paths, list):
            return []
        return [str(path) for path in paths]

    def set_manual_selection(self, version_id, paths):
        selection = self._data.get("manual_verify_selection")
        if not isinstance(selection, dict):
            selection = {}
        selection[str(version_id)] = [str(path) for path in (paths or [])]
        self._data["manual_verify_selection"] = selection

