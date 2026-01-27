# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ('app/bootstrap/prompts', 'app/bootstrap/prompts'),
    ('app/bootstrap/knowledge', 'app/bootstrap/knowledge'),
    ('alembic.ini', '.'),
    ('alembic', 'alembic'),
    ('full_schemas.json', '.'),
]
binaries = []
hiddenimports = [
    'uvicorn',
    'fastapi',
    'sqlmodel',
    'chromadb',
    'sentence_transformers',
    'engineio.async_drivers.threading',
    'sqlite3',
    'app.api.endpoints.ai',
    'app.api.endpoints.cards',
    'app.api.endpoints.chat',
    'app.api.endpoints.files',
    'app.api.endpoints.graphs',
    'app.api.endpoints.projects',
    'app.api.endpoints.settings',
    'app.api.endpoints.system',
    'app.api.endpoints.workflows',
]

# Collect chromadb and sentence_transformers dependencies
tmp_ret = collect_all('chromadb')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

tmp_ret = collect_all('sentence_transformers')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

tmp_ret = collect_all('langchain')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

tmp_ret = collect_all('langchain_community')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

block_cipher = None

a = Analysis(
    ['run_backend.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='novel_forge_backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='novel_forge_backend',
)
