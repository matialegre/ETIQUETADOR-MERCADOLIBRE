# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['gui\\launch_caba_cuenta2.py'],
    pathex=[],
    binaries=[],
    datas=[('.env', '.'), ('config_override_caba.py', '.'), ('api', 'api'), ('services', 'services'), ('models', 'models'), ('utils', 'utils'), ('printing', 'printing')],
    hiddenimports=['ttkbootstrap', 'requests', 'python-dotenv', 'tkinter'],
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
    name='Cliente_Matias_GUI_v3_CABA_CTA2',
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
