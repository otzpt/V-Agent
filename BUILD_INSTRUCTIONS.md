# V-Agent v0.7 — Building a Setup Installer

This guide explains how to create a professional Windows installer (`.exe`) for V-Agent.

## What You Get

After following these steps, you'll have:
- `V-Agent-Setup.exe` — Professional Windows installer
- Automatic installation to `%LOCALAPPDATA%\V-Agent\`
- Start Menu shortcuts
- Desktop shortcut (optional during install)
- Uninstall support

## Prerequisites

### 1. Python 3.9+
```bash
python --version
```
If not installed, download from [python.org](https://www.python.org/downloads/)

### 2. PyInstaller
```bash
pip install pyinstaller
```

### 3. Inno Setup 6.x
Download from: **https://jrsoftware.org/isinfo.php**

Choose the full installer (not the QuickStart Pack).

---

## Step-by-Step Build

### Step 1: Prepare the Icon (Optional)

If you have a custom icon, place it at:
```
V-Agent/assets/vagent.ico
```

If not, the build will still work (uses default Windows icon).

### Step 2: Run the Build Script

Double-click `build.bat` from the V-Agent folder.

This script will:
1. Install PyInstaller (if needed)
2. Install dependencies (`requests`, `watchdog`)
3. Compile `vagent.py` → `V-Agent.exe`
4. Compile `automator.py` → `V-Agent-Automator.exe`
5. Copy all necessary files to the `dist/` folder
6. Show you the next steps

Expected output:
```
[1/5] Checking PyInstaller...
[2/5] Installing dependencies...
[3/5] Building vagent.exe...
[4/5] Building automator.exe...
[5/5] Preparing distribution...

Build Complete!
```

### Step 3: Create the Installer

Now you have two options:

#### Option A: Using Inno Setup GUI (Easier)
1. Open **Inno Setup** (from Start Menu or Programs)
2. File → Open → select `setup.iss`
3. Click **Build → Compile**
4. Wait for the build to complete
5. `V-Agent-Setup.exe` will be created in the current folder ✓

#### Option B: Command Line
```bash
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" setup.iss
```

### Step 4: Test the Installer

Run `V-Agent-Setup.exe`:
- Choose installation location (default: `C:\Users\{YourName}\AppData\Local\V-Agent`)
- Choose shortcuts (Start Menu, Desktop)
- Click "Finish" to launch V-Agent

---

## Troubleshooting

### "PyInstaller not found"
```bash
pip install pyinstaller
```

### "Inno Setup not found"
Download from: https://jrsoftware.org/isdl.php

### "build.bat didn't create dist folder"
Check for Python version issues:
```bash
python --version
pip list | find "PyInstaller"
```

### "V-Agent.exe crashes on startup"
Check that `vagent.py` works standalone:
```bash
python vagent.py
```

If it crashes, check the console output or check for missing dependencies:
```bash
pip install requests
```

---

## Customization

### Change App Name
Edit `setup.iss`:
```
AppName=My Cool AI App
AppVersion=1.0
```

### Change Installation Folder
Edit `setup.iss`:
```
DefaultDirName={localappdata}\My App Name
```

### Add a Custom Icon
1. Create or find a `.ico` file (256×256 recommended)
2. Save it to `assets/vagent.ico`
3. The build script will use it automatically

---

## Distribution

Once you have `V-Agent-Setup.exe`, you can:
- Share it directly
- Upload to GitHub Releases
- Create a website download page
- Distribute via USB/email

Users just need to:
1. Download and install Ollama
2. Run `V-Agent-Setup.exe`
3. Click "Launch V-Agent"

---

## Advanced: Code Signing

To add a digital signature (optional, but recommended for distribution):

1. Get a code signing certificate
2. Modify `setup.iss`:
```
SignTool=signtool
SignedUninstaller=yes
```

3. Sign the executable:
```bash
signtool sign /f certificate.pfx /p password /tr http://timestamp.comodoca.com /td sha256 V-Agent-Setup.exe
```

---

## Uninstall

Users can uninstall via:
- Windows Settings → Apps & Features → V-Agent → Uninstall
- Start Menu → V-Agent → Uninstall V-Agent
- Control Panel → Programs and Features

---

## Next Steps

After building the installer, you can:

1. **Test it** — Install on a fresh Windows machine
2. **Share it** — Upload to GitHub or your website
3. **Update it** — Rebuild with new versions by running `build.bat` again
4. **Customize it** — Edit `setup.iss` for your branding

Good luck! 🚀
