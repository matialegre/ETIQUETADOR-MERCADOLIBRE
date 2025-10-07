# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main_caba.py'],
    pathex=[],
    binaries=[],
    datas=[('config_caba.py', '.'), ('api', 'api'), ('utils', 'utils'), ('models', 'models'), ('gui', 'gui'), ('services', 'services')],
    hiddenimports=['tkinter', 'tkinter.ttk', 'tkinter.messagebox', 'ttkbootstrap', 'requests', 'pyodbc', 'reportlab.lib.pagesizes', 'reportlab.platypus', 'config_caba', 'gui.state', 'gui.order_refresher', 'api.dragonfish_api_caba', 'utils.db_caba', 'services.picker_service_caba', 'services.print_service_caba'],
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
    name='ClienteMatias_CABA',
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
