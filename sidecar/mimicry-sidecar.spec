# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Mimicry sidecar binary."""

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'browser.actions',
        'browser.controller',
        'browser.recorder',
        'dsl',
        'dsl.parser',
        'dsl.compiler',
        'dsl.lexer',
        'dsl.ast_nodes',
        'dsl.rpc_methods',
        'engine',
        'engine.executor',
        'rpc.server',
        'rpc.methods',
        'loguru',
    ],
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
    name='mimicry-sidecar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)
