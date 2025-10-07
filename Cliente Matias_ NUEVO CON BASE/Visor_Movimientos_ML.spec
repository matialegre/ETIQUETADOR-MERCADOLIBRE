# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['meli_movements_viewer.py'],
    pathex=[],
    binaries=[],
    datas=[('.env', '.')],
    hiddenimports=['tkinter', 'ttkbootstrap', 'requests', 'python-dotenv'],
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
    a.binaries,
    a.datas,
    [],
    name='Visor_Movimientos_ML',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
