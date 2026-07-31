@echo off
REM ─────────────────────────────────────────────────────────────────────────
REM  Discord Rich Presence Manager – EXE build script
REM  Run from the project folder.
REM ─────────────────────────────────────────────────────────────────────────

echo [Build] Installing / verifying dependencies...
pip install pypresence pystray pillow requests pyinstaller --quiet

echo [Build] Cleaning previous build...
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist
if exist DiscordRPC.spec del /q DiscordRPC.spec

REM Check for app.ico
if not exist app.ico (
    echo [Warning] app.ico not found – EXE will have no custom icon.
    echo           Place app.ico in the same folder as this script and rebuild.
    set ICON_ARG=
) else (
    echo [Build] Found app.ico – embedding...
    set ICON_ARG=--icon app.ico
)

echo [Build] Running PyInstaller...
pyinstaller ^
    --noconsole ^
    --onefile ^
    --name "DiscordRPC" ^
    %ICON_ARG% ^
    --add-data "app.ico;." ^
    --collect-all pypresence ^
    --collect-all pystray ^
    --hidden-import pypresence ^
    --hidden-import pypresence.presence ^
    --hidden-import pystray ^
    --hidden-import PIL ^
    --hidden-import PIL.Image ^
    --hidden-import PIL.ImageDraw ^
    --hidden-import winreg ^
    --hidden-import requests ^
    presence_server.py

echo.
if exist dist\DiscordRPC.exe (
    echo [Build] SUCCESS -^> dist\DiscordRPC.exe
    echo.
    echo  Copy config.json and app.ico next to the .exe before first run.
    echo  config.json is created automatically on first run if missing.
) else (
    echo [Build] FAILED – check errors above.
)
echo.
pause
