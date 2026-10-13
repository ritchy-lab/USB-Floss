# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['usb-floss-gui.py'],
    pathex=[],
    binaries=[],
    datas=[('logo.png', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='USB-Floss',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='USB-Floss',
)
app = BUNDLE(
    coll,
    name='USB-Floss.app',
    icon='icon.icns',
    bundle_identifier='com.ritchy-lab.usb-floss',
    version='1.3',
    info_plist={
        'CFBundleShortVersionString': '1.3',
        'CFBundleVersion': '1.3',
        'NSHumanReadableCopyright': '© 2026 ritchy-lab',
        'LSMinimumSystemVersion': '11.0',
    },
)
