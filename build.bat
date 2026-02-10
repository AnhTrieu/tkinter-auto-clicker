@echo off
REM Build script for Windows Auto Clicker
REM Run this on Windows to create the standalone executable

echo Installing PyInstaller...
uv add --dev pyinstaller

echo Building executable...
uv run pyinstaller windows_autoclicker.spec --clean

echo Build complete!
echo Executable location: dist\WindowsAutoClicker.exe
pause
