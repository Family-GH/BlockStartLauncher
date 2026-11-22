@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "TARGET_DIR=%LOCALAPPDATA%\BlockStartLauncher\release"
set "TARGET=%TARGET_DIR%\BlockStartLauncher.exe"
set "STAMP=%TARGET%.b3612229"

if exist "%TARGET%" if exist "%STAMP%" goto run

if not exist "BlockStartLauncher.exe.part01" goto missing
if not exist "BlockStartLauncher.exe.part02" goto missing
if not exist "BlockStartLauncher.exe.part03" goto missing

if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%" >nul 2>nul
if exist "%TARGET%.tmp" del /f /q "%TARGET%.tmp" >nul 2>nul

echo Restoring BlockStartLauncher from split parts...
copy /b "BlockStartLauncher.exe.part01"+"BlockStartLauncher.exe.part02"+"BlockStartLauncher.exe.part03" "%TARGET%.tmp" >nul
if errorlevel 1 goto failed
move /y "%TARGET%.tmp" "%TARGET%" >nul
if errorlevel 1 goto failed
> "%STAMP%" echo b3612229

:run
start "" "%TARGET%"
exit /b 0

:missing
echo.
echo Split parts are missing. Keep this .bat file in the dist folder
echo together with all BlockStartLauncher.exe.partXX files.
echo.
pause
exit /b 1

:failed
echo.
echo Could not restore BlockStartLauncher.exe.
echo Check free disk space and write permission for:
echo %TARGET_DIR%
echo.
pause
exit /b 1





