# BlockStart Launcher

> A third-party Minecraft: Java Edition launcher for Windows.

BlockStart Launcher (BSL) is a Minecraft launcher developed by MC_Family with Python and PySide6, packaged with PyInstaller. The current version is V0.5.3b. It brings game version downloading, instance management, account authentication, mod and modpack installation, resource management and file repair into a single window, aimed at players who need to keep several separate game environments on Windows.

[中文说明](README.zh-CN.md) · [Changelog](CHANGELOG.md)

## Features

### Instances

- Multiple isolated instances, each with its own `mods`, saves, configuration and resource pack folders.
- An instance is created by picking a game version; the name is editable. Instances can be deleted, a version can be downloaded on its own, and the version list can be retried.
- Per-instance settings for mod loader, Java path, maximum memory, window size, fullscreen, extra game arguments and an auto-join server address. Anything left blank follows the global defaults.
- Fabric, Forge, NeoForge and Quilt are supported; the loader is installed automatically at launch, so no separate installer is needed.

### Accounts and skins

- Microsoft account login through the device code flow, plus offline accounts. Credentials are kept locally, so later launches do not ask again.
- For Microsoft accounts, the skin and cape page shows front and back previews, accepts 64×64 or 64×32 PNG skins, switches between the classic Steve and slim Alex models (auto-detected first, manual override available), restores the default skin, and enables or hides owned capes. The second overlay layer can be hidden from the preview.
- Legacy 64×32 skins get their missing left arm and left leg mirrored automatically.

### Downloads and Java

- Three download routes: automatic (mirror first), BMCLAPI mirror, and the official source. A failing address falls back to the next one.
- Java is searched for before launch, including the registry, common install folders and runtime directories shipped by other launchers. If nothing suitable is found, a `java.exe` can be chosen manually or a matching runtime can be downloaded inside the launcher.
- Missing version files, assets and natives are fetched in the background at launch, with visible progress and a stop button.

### Mods

- Built-in Modrinth search. Descriptions, categories, supported game versions and loaders are shown in the launcher, and a chosen release installs straight into the active instance.
- Installed mods can be enabled or disabled (by renaming, files are kept), deleted, or revealed in Explorer.
- A scan warns about mixed loaders and duplicated mod IDs.

### Modpacks

- Imports `.mrpack`, CurseForge archives, MultiMC and plain `.minecraft` directory layouts, by picking a file or dragging it in.
- The game version and loader are detected, an instance is created, and missing mods are pulled from Modrinth. Missing entries are listed, and the import can be cancelled.

### Resource and shader packs

- Search Modrinth for resource packs and shader packs and download them into the active instance's folders.

### Repair and diagnostics

- File verification compares jars, assets and libraries against the version manifest, lists missing or mismatched files, and repairs either the selection or everything. An advanced option rebuilds only the natives.
- The launcher can check and repair itself.
- After a crash, the newest crash report and the tail of the log are read and common causes (Java mismatch, mod conflicts, too little memory) are identified.

### Dashboard

- The home page shows the launch workflow, Java, memory and disk results, and the player count and latency of the auto-join server over Server List Ping.
- Shortcuts to the instance folder, save backup and repair tools. New versions are announced here, and a specific version can be ignored.

### Interface and personalisation

- Light and dark themes; page animations can be turned off for weaker machines.
- Custom background image, plus background music played from a chosen folder through Windows MCI.
- Global settings for memory, advanced JVM arguments, window size, fullscreen and auto-join; the game directory can move to another drive, with recent locations remembered.

### Launcher updates

- Update checks go to GitHub Releases by default. Extra JSON manifest URLs can be added; all sources are merged, the highest version wins, and a failing source is skipped.

## Download and run

Get the latest build from the [Releases page](https://github.com/Family-GH/BlockStartLauncher/releases/latest).

| Build | File | How to run |
| --- | --- | --- |
| Portable | `BlockStartLauncherPortable.zip` | Recommended. Unpack it anywhere and run `BlockStartLauncherPortable.exe`. Nothing is extracted at startup, so the security-software prompts tied to one-file builds do not appear. |
| Single file | `BlockStartLauncher.exe` | Run it directly; the first start unpacks into `%LOCALAPPDATA%\BlockStartLauncher`. |

The same builds are versioned inside `BlockStartLauncher/dist`, split into sub-25 MB chunks because of GitHub's per-file limit, with a manifest holding the SHA-256 of every chunk. `start_blockstart.bat` joins the single-file chunks on first use and starts the launcher.

The launcher needs administrator rights to write into the game directory; a UAC prompt appears otherwise.

To verify or restore the chunks by hand (Python 3.9+, standard library only):

```bat
python tools\release_chunks.py verify BlockStartLauncher\dist\BlockStartLauncher.exe.manifest.json
python tools\release_chunks.py restore BlockStartLauncher\dist\BlockStartLauncher.exe.manifest.json --dest BlockStartLauncher\dist\BlockStartLauncher.exe
```

## Data and security

- Data lives in `%LOCALAPPDATA%\BlockStartLauncher`: game files, instances, saves, accounts and settings. Copy the folder to move to another machine; accounts have to sign in again.
- Account tokens are encrypted with Windows DPAPI for the current Windows user. Settings and account files keep a `.bak` copy and roll back if the main file is unreadable.
- Save backups are written to a temporary file first and renamed when complete; a cancelled or failed backup is cleaned up instead of leaving a broken archive.

## Build from source

```bat
py -3 -m pip install -r BlockStartLauncher\requirements.txt
py -3 BlockStartLauncher\build_exe.py
```

The single-file build outputs `dist/BlockStartLauncher.exe`. Setting `BSL_ONEDIR=1` before the build produces the portable variant instead. Split the result again with `tools/release_chunks.py`; if the number of chunks changes, update the part list in the startup script.

## Known limitations

- No code-signing certificate, so a new machine may show the SmartScreen warning on first run. Choose "More info → Run anyway".
- The single-file build unpacks into `.bsl_runtime` on every start, which some security software blocks; the portable build avoids that specific prompt, though unsigned executables may still be flagged.
- Microsoft login has only been verified in failure branches and headless runs, not with a real account through the whole authorisation flow.
- Windows only.
- The launcher does not ship the game itself; online play and official skins still require a Microsoft account that owns Minecraft: Java Edition.

## Repository layout

```text
BlockStartLauncher/
  run.py                 entry point, UAC check, QApplication
  config.py              version, paths and update sources
  build_exe.py           PyInstaller build script
  version_info.txt       Windows version resource
  core/                  logic without UI
  ui/                    pages and widgets
  dist/                  release chunks and launch scripts
tools/
  release_chunks.py      split, verify and restore release chunks
```

