from os import getcwd
import os.path as op
import sys
import json
from . import archdetect

# 判断是否为打包环境
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS          # 打包后的临时资源目录
else:
    BASE_DIR = getcwd()              # 开发时使用当前工作目录

# 内置的移植方案字典（与原来 configs.py 中的完全相同）
_default_portstep = {
    'mt6572/mt6582/mt6592 kernel-3.4.67': {
        'partitions': {
            'system': '/dev/block/mmcblk0p4',
            'boot': '/dev/block/bootimg',
        },
        'flags': {
            'generate_script': True,
            'replace_kernel': True,
            'replace_fstab': False,
            'selinux_permissive': True,
            'enable_adb': True,
            'replace_firmware': True,
            'replace_mddb': True,
            'replace_malidriver': True,
            'replace_audiodriver': False,
            'replace_libshowlogo': False,
            'replace_mtk-kpd': True,
            'replace_gralloc': True,
            'replace_hwcomposer': True,
            'replace_ril': False,
            'single_simcard': False,
            'dual_simcard': False,
            'fit_density': True,
            'change_model': True,
            'change_timezone': True,
            'change_locale': True,
            'use_custom_update-binary': True,
        },
        'replace': {
            'kernel': [
                "kernel",
            ],
            'fstab': [
                "initrd/fstab",
                "initrd/fstab.mt6572",
                "initrd/fstab.mt6582",
                "initrd/fstab.mt6592",
            ],
            'firmware': [
                "etc/firmware"
            ],
            'mddb': [
                "etc/mddb"
            ],
            'malidriver': [
                "lib/libMali.so"
            ],
            'audiodriver': [
                "lib/libaudio.primary.default.so",
                "etc/audio_effects.conf",
                "etc/audio_policy.conf"
            ],
            'libshowlogo': [
                "lib/libshowlogo.so"
            ],
            'mtk-kpd': [
                "usr/keylayout/mtk-kpd.kl"
            ],
            'ril': [
                "bin/ccci_fsd",
                "bin/ccci_mdinit",
                "bin/gsm0710muxd",
                "bin/gsm0710muxdmd2 ",
                "bin/rild",
                "bin/rildmd2",
                "lib/librilmtk.so",
                "lib/librilmtkmd2.so",
                "lib/librilutils.so ",
                "lib/mtk-ril.so",
                "lib/mtk-rilmd2.so",
            ],
            'gralloc': [
                "lib/hw/gralloc.mt6572.so",
                "lib/hw/gralloc.mt6582.so",
                "lib/hw/gralloc.mt6592.so",
            ],
            'hwcomposer': [
                "lib/hw/hwcomposer.mt6572.so",
                "lib/hw/hwcomposer.mt6582.so",
                "lib/hw/hwcomposer.mt6592.so",
            ]
        },
    },
    'kernel only (only replace kernel)': {
        'partitions': {},
        'flags': {
            'generate_script': False,
            'replace_kernel': True,
            'selinux_permissive': True,
            'enable_adb': True,
            'replace_firmware': True,
            'replace_mddb': True,
        },
        'replace': {
            'kernel': [
                "kernel",
                "kernel.gz"
            ],
            'firmware': [
                "etc/firmware"
            ],
            'mddb': [
                "etc/mddb"
            ],
        },
    },
    'G79 (mt6735/mt6735m/mt6737) kernel-3.18.19': {
        'partitions': {},
        'flags': {
            'generate_script': False,
            'replace_kernel': True,
            'replace_fstab': False,
            'selinux_permissive': True,
            'enable_adb': True,
            'replace_firmware': True,
            'replace_mddb': True,
            'replace_malidriver': False,
            'replace_audiodriver': False,
            'replace_libshowlogo': False,
            'replace_mtk-kpd': False,
            'replace_wifi': False,
            'replace_camera': False,
            'single_simcard': False,
            'dual_simcard': False,
            'fit_density': True,
            'change_model': True,
            'change_timezone': True,
            'change_locale': True,
            'use_custom_update-binary': True,
        },
        'replace': {
            'kernel': [
                "kernel",
            ],
            'fstab': [
                "initrd/fstab",
                "initrd/fstab.mt6735",
                "initrd/fstab.mt6737",
            ],
            'firmware': [
                "etc/firmware"
            ],
            'mddb': [
                "etc/mddb"
            ],
            'malidriver': [
                "lib/libMali.so"
            ],
            'audiodriver': [
                "lib/hw/audio.primary.mt6735.so",
                "lib/hw/audio.primary.mt6735m.so",
                "lib/hw/audio.primary.mt6737.so",
                "lib/hw/audio.primary.mt6737m.so",
            ],
            'libshowlogo': [
                "lib/libshowlogo.so"
            ],
            'mtk-kpd': [
                "usr/keylayout/mtk-kpd.kl"
            ],
            'wifi': [
                "bin/netcfg",
                "bin/dhcpcd",
                "bin/ifconfig",
                "bin/hostap",
                "bin/hostapd",
                "bin/hostapd_bin",
                "bin/pcscd",
                "bin/wlan*",
                "bin/wpa*",
                "bin/netd",
                "lib/libhardware_legacy.so",
                "etc/wifi",
            ],
            'camera': [
                "lib/lib3a.so",
                "lib/libcamalgo.so",
                "lib/libcamdrv.so",
                "lib/libcameracustom.so",
                "lib/libfeatureio.so",
                "lib/libimageio.so",
                "lib/libimageio_plat_drv.so",
                "lib/libJpgDecPipe.so",
                "lib/libJpgEncPipe.so",
                "lib/libmhalImageCodec.so",
                "lib/libmtkcamera_client.so",
                "lib/libmtkjpeg.so",
                "lib/libcam.paramsmgr.so",
            ]
        },
    },
}

# 尝试加载外部 configs.json
config_path = op.join(BASE_DIR, "configs.json")
if op.isfile(config_path):
    with open(config_path, 'r') as c:
        support_chipset_portstep = json.load(c)
else:
    # 如果打包资源中没有（开发环境可能没有），使用内置默认并写入当前目录
    support_chipset_portstep = _default_portstep.copy()
    # 只有在非打包环境且当前目录下没有 configs.json 时才创建
    if not getattr(sys, 'frozen', False):
        with open(op.join(getcwd(), "configs.json"), 'w') as c:
            json.dump(support_chipset_portstep, c, indent=4)

support_chipset = list(support_chipset_portstep.keys())
support_packtype = ['zip', 'img']

ostype, arch = archdetect.retTypeAndMachine()
ext_ext = '.exe' if ostype == 'win' else ''

# 工具路径
make_ext4fs_bin = op.join(BASE_DIR, "bin", ostype, arch, "make_ext4fs"+ext_ext)
magiskboot_bin  = op.join(BASE_DIR, "bin", ostype, arch, "magiskboot"+ext_ext)
simg2img_bin    = op.join(BASE_DIR, "bin", ostype, arch, "simg2img"+ext_ext)
img2simg_bin    = op.join(BASE_DIR, "bin", ostype, arch, "img2simg"+ext_ext)