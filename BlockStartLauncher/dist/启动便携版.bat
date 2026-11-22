@echo off
cd /d "%~dp0"
if not exist "BlockStartLauncherPortable\BlockStartLauncherPortable.exe" (
  echo Portable folder is missing.
  pause
  exit /b 1
)
start "" "%~dp0BlockStartLauncherPortable\BlockStartLauncherPortable.exe"
