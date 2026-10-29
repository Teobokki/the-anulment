#!/bin/bash
# Windows build via Wine: PyInstaller onedir + Inno Setup per-user installer + onefile portable + zip
set -e
export WINEPREFIX=/workspace/exwifi/.wine WINEDEBUG=-all
cd "$(dirname "$0")"
V=$(grep -oP 'APP_VERSION = "\K[^"]+' the_anulment.py)
PY='C:\Python311\python.exe'
[ -d piper_win ] || cp -r /workspace/an_dl/piper/win/piper piper_win
wine "$PY" -m PyInstaller --noconfirm "THE ANULMENT.spec" > build_dir.log 2>&1; echo DIR_DONE
wine "C:\\InnoSetup\\ISCC.exe" installer.iss > build_iss.log 2>&1; echo ISS_DONE
wine "$PY" -m PyInstaller --noconfirm --workpath build_onefile --distpath dist_onefile "THE ANULMENT onefile.spec" > build_1f.log 2>&1
cp "dist_onefile/THE ANULMENT.exe" dist/THE-ANULMENT-Portable.exe; echo ONEFILE_DONE
cd dist && rm -f THE-ANULMENT-$V-Windows-x64.zip && python3 -c "import shutil; shutil.make_archive('THE-ANULMENT-$V-Windows-x64', 'zip', '.', 'THE ANULMENT')" && echo ZIP_DONE
ls -la
