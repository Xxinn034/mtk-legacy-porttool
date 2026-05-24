# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

# 项目根目录，用于收集额外的数据文件
PROJECT_ROOT = Path('.').resolve()

# 需要打包进 exe 的额外数据（文件夹/文件）
# 格式：('源路径', '目标路径（在 exe 临时目录中）')
datas = [
    ('configs.json', '.'),                # 配置文件放到根目录
    ('bin/', 'bin'),                       # 存放 magiskboot 等工具
    ('porttool/', 'porttool'),             # 自定义模块
]

# 如果有 assets 或 其他文件夹也一并加入
# datas += [('assets/', 'assets')]

a = Analysis(
    ['main.py'],
    pathex=[str(PROJECT_ROOT)],            # 让 PyInstaller 能找到项目根目录下的模块
    binaries=[],
    datas=datas,                           # 使用上面定义的数据
    hiddenimports=[
        # 因为 import 路径是相对的，确保包被正确收集
        'porttool',
        'porttool.ui',
        'porttool.utils',
        'porttool.configs',
        'porttool.imgextractor',
        'porttool.ext4',
        'porttool.bootimg',
        'porttool.boot_patch',
        'porttool.archdetect',
        'porttool.hexpatch',
        'porttool.sdat2img',
        'porttool.twrp_port',
        'porttool.bug_fix',
        # 隐式依赖
        'tkinter',
        'tkinter.filedialog',
        'multiprocessing',
        'multiprocessing.dummy',
        'ctypes',
        'json',
        'shutil',
        'zipfile',
        'subprocess',
        'hashlib',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],            # 可以排除不需要的大型库减小体积，如 'numpy', 'pandas' 等（你的项目没有则不用动）
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
    name='MTK_Port_Tool',                  # 生成的可执行文件名
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                              # 使用 UPX 压缩，减小体积
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                          # 不保留控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico'                 # 如果你有图标文件，可以在这里指定，没有的话删掉这一行
)