# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ('assets', 'assets'),
    ('databases', 'databases'),
    ('ui', 'ui'),
    ("resources/pg_client/win64/*", "resources/pg_client/win64"),
]
binaries = []
hiddenimports = [
    'psycopg2',
    'pandas',
    'openpyxl',
    'sqlglot',
    'keyring.backends.Windows',
]
# oracledb thin mode requires the full cryptography package (x509,
# hazmat bindings, _rust extension). A bare hiddenimports entry for
# 'cryptography'/'oracledb' is NOT enough under PyInstaller and produces
# DPY-3016 ("cryptography package cannot be imported / cannot import
# name x509") in the frozen exe — collect all submodules/binaries.
for _pkg in ('oracledb', 'cryptography', 'cffi'):
    tmp_pkg = collect_all(_pkg)
    datas += tmp_pkg[0]; binaries += tmp_pkg[1]; hiddenimports += tmp_pkg[2]
tmp_ret = collect_all('PySide6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('cdata')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('qtawesome')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('winpty')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

hiddenimports.append('PySide6.QtSvg')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Universal SQL Client',
    icon='assets/app_icon.ico',
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
    version='file_version_info.txt',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=['Qt6*.dll', 'PySide6*.dll', 'python*.dll'],
    name='Universal SQL Client',
)
