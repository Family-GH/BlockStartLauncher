# Quick Start (no previous experience needed)

Applies to BlockStart Launcher V0.5.3b on Windows.

The steps follow the order of a first launch and name the buttons you will actually see. A complete first setup usually takes ten to fifteen minutes. The later sections list the mistakes that cause most failures; worth a read before you start changing anything.

## 1. Download and unpack

1. Open the Releases page and download `BlockStartLauncherPortable.zip` (recommended).
2. Unpack it to a path that is ASCII only and contains no spaces, for example `D:\Games\BSL`.
   - Avoid `C:\Program Files`, the desktop and the Downloads folder, and do not run the exe straight from inside the archive.
3. The unpacked folder must contain `BlockStartLauncherPortable.exe` together with the `_internal` folder. Copying the exe alone will not work.

The single-file `BlockStartLauncher.exe` can run from any folder; on first start it unpacks itself into `%LOCALAPPDATA%\BlockStartLauncher`.

## 2. First launch

Double-click `BlockStartLauncherPortable.exe`.

- If Windows shows "Windows protected your PC", choose **More info → Run anyway**. The build has no commercial code-signing certificate, and the prompt is not a virus report.
- If a security suite blocks it, allow the operation or trust the folder. The single-file build is more likely to be blocked than the portable one; prefer the portable build in that case.
- The launcher asks for administrator rights because it writes into the game directory. Choose Yes; choosing No exits the program.

Do not press "Launch game" yet. Configure the points below once, and later launches are one click.

## 3. Account

1. Open **Accounts** and press **Microsoft login (recommended)**.
2. The launcher requests a device code, copies it to the clipboard, and tries to open the sign-in page.
3. If no browser appears, use the blue link in the login window, or press **Copy login link** and open `https://www.microsoft.com/link` yourself, then paste the code.
4. Complete the sign-in in the browser; the account is added automatically.
5. Without a Microsoft account, use **Offline account**. It works for single-player and offline play only, and official skins and capes are unavailable.

Do not click repeatedly during login, and do not close the login window: closing it cancels the pending sign-in.

## 4. Java

The launcher searches for Java on its own. To confirm or override it:

1. Open **Settings → Java runtime**.
2. Pick one of the detected entries; otherwise press **Choose manually** and select `bin\java.exe`.
3. If nothing is installed, let the launcher download a matching runtime, or follow the prompt shown at launch.

Typical locations: `C:\Program Files\Java\jdk-17\bin\java.exe`, `C:\Program Files\Eclipse Adoptium\...\bin\java.exe`. Launchers such as PCL keep theirs under `.minecraft\runtime` or `PCL\runtime`.

## 5. Create an instance and launch

1. Go to **Home** and press **New instance**.
2. Pick a game version, confirm the instance name, and press **Create**.
3. For modded play, choose the loader in the same window: Fabric, Forge, NeoForge or Quilt. Leave it empty for vanilla.
4. Press **Launch game** on the Home page. The first launch downloads the game files; progress is shown and the task can be stopped.
5. Memory, window size, fullscreen, extra arguments and an auto-join server can be set per instance under **Instances → Instance settings**. Anything left blank follows the global values in **Settings**.

An instance is a self-contained environment: mods, saves, configuration and resource packs do not leak into other instances. Keep a vanilla instance and a heavy modpack side by side by creating two instances.

## 6. Installing mods

1. Open **Mods** and check that the target instance is shown at the top.
2. Search by a mod name, preferably its English name (`JEI`, `Create`, `Sodium`), and press **Search**.
3. Open a result to read the description, categories, supported game versions and loaders. Choose a release that matches your game version and loader, then press **Download to current instance**.
4. Installed mods appear under **Installed mods**: ticked means enabled, unticked means disabled (the file is renamed, not removed).
5. If a mixed-loader or duplicate mod id warning appears before launch, resolve it first; ignoring it usually ends in a crash.

## 7. Importing a modpack

1. Open **Modpacks** and drag the pack file into the window, or press **Choose modpack file**.
2. Supported: `.mrpack`, CurseForge archives, MultiMC instances and plain `.minecraft` layouts.
3. The launcher detects the game version and loader, creates an instance and pulls missing mods from Modrinth. Resolve everything listed under **Missing files** before launching.

## 8. Resource and shader packs

Search on the **Resources** page and download into the current instance. Shaders additionally need a shader loader inside the game (Iris or OptiFine) before they can be enabled.

## 9. Saves and backups

- **Back up saves** on the Instances page writes into the `backups` folder of the data directory and leaves the original untouched.
- **Save management** can import, delete and list existing backups.
- Cancelling a backup does not leave a broken archive; the partial file is cleaned up.

## 10. When something goes wrong

1. **Repair tools → Check files** lists missing or mismatched files; repair the selection or everything. Use **Repair runtime only** when the natives are the problem.
2. After a crash, open **Settings → Diagnostics → View crash reason**. The newest crash report and the tail of the log are read, and common causes (Java mismatch, mod conflict, insufficient memory) are named.
3. An empty version list: press **Retry version list**, or switch the download route under **Settings → Downloads**.
4. Launcher misbehaving: **Repair tools → Diagnose launcher → Run repair**.

## 11. Avoid these

- Do not delete the `.bsl_runtime` folder while the launcher is running.
- Do not share `accounts.json` with anyone, and do not copy someone else's account file in. Credentials are encrypted per Windows user and cannot be decrypted elsewhere.
- Do not hand-edit `settings.json`. A `.bak` rollback exists, but there is no reason to risk it.
- Do not run two launchers against the same game directory at once.
- Do not delete an instance folder by hand; use **Delete instance**.
- Do not replace downloaded files with third-party "optimisers"; checksum verification will fail.

## 12. Moving and uninstalling

- Move: copy the launcher and the whole `%LOCALAPPDATA%\BlockStartLauncher` directory. Accounts must sign in again on the new machine.
- Uninstall: delete both directories. No registry keys and no system services are installed.

## 13. Versions and updates

**Settings → Launcher update** checks GitHub Releases by default; **Check for updates** runs it manually. Extra JSON manifest URLs can be listed as additional sources; all sources are merged, the highest version wins, and a failing source is skipped.
