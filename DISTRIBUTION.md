# Distribution Guide - Windows Auto Clicker

## For End Users (Non-Technical)

### Download & Run
1. Download `WindowsAutoClicker.exe`
2. Double-click to run
3. No installation needed!

### First Run
- Windows may show a security warning ("Windows protected your PC")
- Click **"More info"** → **"Run anyway"**
- This is normal for unsigned executables

### Usage
1. Select your monitor from the dropdown
2. Set click position (X, Y coordinates relative to selected monitor)
3. Set click interval in milliseconds (1000 = 1 second)
4. Click **Start (F8)** or press **F8** to begin clicking
5. Press **F8** again to stop

---

## For Developers - Building the Executable

### Prerequisites
- Windows 10/11
- Python 3.8+
- Git

### Build Steps

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd windows_auto_clicker
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -e .
   pip install pyinstaller
   ```

4. **Run the build script:**
   ```bash
   build.bat
   ```

5. **Find the executable:**
   - Location: `dist/WindowsAutoClicker.exe`
   - Size: ~15-20 MB (includes Python runtime)

### Distribution

Package the executable:
- Compress `WindowsAutoClicker.exe` into a ZIP file
- Upload to GitHub Releases or file hosting
- Share the download link

### Optional: Add Icon

1. Place `icon.ico` in the project root
2. Edit `windows_autoclicker.spec`, change:
   ```python
   icon=None  # to
   icon='icon.ico'
   ```
3. Rebuild with `build.bat`

### Optional: Code Signing (Removes Security Warnings)

To eliminate Windows security warnings:
1. Purchase a code signing certificate (~$100-400/year)
2. Sign the executable using `signtool.exe`:
   ```bash
   signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com WindowsAutoClicker.exe
   ```

---

## Troubleshooting

### Build fails with "module not found"
- Ensure all dependencies in `pyproject.toml` are installed
- Add missing imports to `hiddenimports` in the spec file

### Executable too large
- Remove UPX compression (set `upx=False` in spec file)
- Use `--onedir` mode instead of `--onefile` (split into folder)

### Antivirus flags the executable
- Normal for unsigned executables
- Upload to VirusTotal to verify (should be clean)
- Consider code signing for professional distribution

---

## Alternative: Quick Build Command

Instead of using the spec file, you can build with a single command:

```bash
pyinstaller --name=WindowsAutoClicker ^
            --onefile ^
            --windowed ^
            --hidden-import=screeninfo.enumerators.windows ^
            --hidden-import=pynput.keyboard ^
            --hidden-import=pynput.mouse ^
            autoclicker/__main__.py
```

This produces the same result as `build.bat`.
