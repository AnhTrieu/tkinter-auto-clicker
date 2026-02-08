@echo off
REM Build script for Windows Auto Clicker
REM Run this on Windows to create the standalone executable

echo Installing PyInstaller...
pip install pyinstaller

echo Building executable...
pyinstaller windows_autoclicker.spec --clean

echo Build complete!
echo Executable location: dist\WindowsAutoClicker.exe
pause
