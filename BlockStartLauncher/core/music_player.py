"""Tiny Windows MCI background-music player.

The launcher does not need QtMultimedia (which would add several megabytes to
the one-file build) just to loop a local music folder.  MCI is part of Windows
and handles MP3/WAV files well enough for menu music.
"""

import ctypes
import os
import random


_ALIAS = "bsl_menu_music"
_EXTENSIONS = (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".wma")
_MCI_ERROR = ctypes.c_uint(0)


def _mci(command):
    if os.name != "nt":
        raise OSError("background music is only available on Windows")
    winmm = ctypes.windll.winmm
    buffer = ctypes.create_unicode_buffer(512)
    code = winmm.mciSendStringW(
        ctypes.c_wchar_p(command), buffer, len(buffer), None
    )
    if code:
        error = ctypes.create_unicode_buffer(512)
        try:
            winmm.mciGetErrorStringW(code, error, len(error))
        except Exception:
            error = ctypes.create_unicode_buffer("MCI error %s" % code)
        raise OSError(str(error.value or ("MCI error %s" % code)))
    return buffer.value


class MusicPlayer:
    """Loop the first playable file from a user-selected directory."""

    def __init__(self):
        self._open = False

    def play(self, directory):
        self.stop()
        path = self._pick(directory)
        if not path:
            return False
        try:
            quoted = path.replace('"', '\\"')
            try:
                _mci('open "%s" type mpegvideo alias %s' % (quoted, _ALIAS))
            except OSError:
                _mci('open "%s" alias %s' % (quoted, _ALIAS))
            self._open = True
            try:
                _mci("setaudio %s volume to 420" % _ALIAS)
            except OSError:
                pass
            try:
                _mci("play %s repeat" % _ALIAS)
            except OSError:
                _mci("play %s" % _ALIAS)
            return True
        except Exception:
            self.stop()
            return False

    def stop(self):
        if self._open:
            try:
                _mci("stop %s" % _ALIAS)
            except Exception:
                pass
            try:
                _mci("close %s" % _ALIAS)
            except Exception:
                pass
            self._open = False

    @staticmethod
    def _pick(directory):
        directory = str(directory or "").strip()
        if not directory or not os.path.isdir(directory):
            return ""
        candidates = []
        try:
            for name in sorted(os.listdir(directory)):
                path = os.path.join(directory, name)
                if os.path.isfile(path) and os.path.splitext(name)[1].lower() in _EXTENSIONS:
                    candidates.append(path)
        except Exception:
            return ""
        return random.choice(candidates) if candidates else ""
