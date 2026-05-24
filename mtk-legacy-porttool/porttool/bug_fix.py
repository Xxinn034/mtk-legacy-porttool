#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import shutil
import subprocess
import struct
import tempfile
import zipfile
import traceback
from pathlib import Path
from glob import glob
from . import imgextractor
from .configs import simg2img_bin, img2simg_bin, make_ext4fs_bin

SPARSE_MAGIC = 0xED26FF3A

# ---------- 修复项定义 ----------
BUG_FIX_ITEMS = {
    "keys": {
        "name": "修复按键",
        "description": "替换按键配置文件",
        "patterns": [
            "usr/keychars/Generic.kcm",
            "usr/keychars/qwerty.kcm",
            "usr/keychars/qwerty2.kcm",
            "usr/keychars/Virtual.kcm",
            "usr/keylayout",
        ]
    },
    "radio": {
        "name": "修复插卡",
        "description": "修复基带与RIL",
        "patterns": [
            "bin/rild",
            "bin/rildmd2",
            "framework/telephony-common.jar",
            "lib/libril.so",
            "lib/librilmtk.so",
            "lib/librilmtkmd2.so",
            "lib/librilutils.so",
            "lib/mtk-ril.so",
            "lib/mtk-rilmd2.so",
        ]
    },
    "audio": {
        "name": "修复声音",
        "description": "替换音频 HAL 库",
        "patterns": [
            "lib/hw/audio.primary.*.so",
        ]
    },
    "camera": {
        "name": "修复相机",
        "description": "替换相机相关库",
        "patterns": [
            "lib/lib3a.so",
            "lib/libcamalgo.so",
            "lib/libcamdrv.so",
            "lib/libcameracustom.so",
            "lib/libfeatureio.so",
            "lib/libfeatureiodrv.so",
            "lib/libimageio.so",
            "lib/libimageio_plat_drv.so",
            "lib/libJpgDecPipe.so",
            "lib/libJpgEncPipe.so",
            "lib/libmhalImageCodec.so",
            "lib/libmtkcamera_client.so",
            "lib/libmtkjpeg.so",
            "lib/hw/camera.*.so",
        ]
    },
}

def _is_sparse(filepath):
    try:
        with open(filepath, 'rb') as f:
            return struct.unpack('<I', f.read(4))[0] == SPARSE_MAGIC
    except:
        return False

def _simg2img(src, dst):
    subprocess.run([simg2img_bin, src, dst], check=True)

def _img2simg(src, dst):
    subprocess.run([img2simg_bin, src, dst], check=True)

def _get_dir_size(path):
    """递归计算目录总大小（字节）"""
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return total

def _find_system_in_zip(zip_path, extract_dir):
    """从卡刷包中提取 system 目录，返回 (system_dir, system_img_path_or_None)"""
    with zipfile.ZipFile(zip_path, 'r') as z:
        namelist = z.namelist()
        if any(name.startswith("system/") and not name.endswith('/') for name in namelist):
            z.extractall(extract_dir)
            sys_dir = os.path.join(extract_dir, "system")
            if os.path.isdir(sys_dir):
                return sys_dir, None
        if "system.img" in namelist:
            z.extract("system.img", extract_dir)
            img_path = os.path.join(extract_dir, "system.img")
            return None, img_path
        if "system.new.dat" in namelist and "system.transfer.list" in namelist:
            z.extract("system.new.dat", extract_dir)
            z.extract("system.transfer.list", extract_dir)
            dat_path = os.path.join(extract_dir, "system.new.dat")
            list_path = os.path.join(extract_dir, "system.transfer.list")
            img_path = os.path.join(extract_dir, "system.img")
            from . import sdat2img
            sdat2img.main(list_path, dat_path, img_path)
            return None, img_path
    return None, None

def _replace_patterns(base_sys_dir, port_sys_dir, patterns, log):
    total = 0
    for pattern in patterns:
        if '*' in pattern:
            full_pattern = os.path.join(base_sys_dir, pattern)
            matches = glob(full_pattern)
            for src in matches:
                rel = os.path.relpath(src, base_sys_dir)
                dst = os.path.join(port_sys_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
                log.write(f"  ✓ 替换 {rel}\n")
                total += 1
        else:
            src = os.path.join(base_sys_dir, pattern)
            if not os.path.exists(src):
                log.write(f"  - 跳过 {pattern}（底包中不存在）\n")
                continue
            dst = os.path.join(port_sys_dir, pattern)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            log.write(f"  ✓ 替换 {pattern}\n")
            total += 1
    return total

def fix_bugs(base_sys_img, port_rom_path, selected_fixes, log, output_dir=None):
    try:
        if not os.path.exists(base_sys_img):
            log.write("[错误] 底包系统文件不存在\n")
            return False
        if not os.path.exists(port_rom_path):
            log.write("[错误] 要修复的 ROM 不存在\n")
            return False

        if output_dir is None:
            output_dir = os.path.join(os.getcwd(), "bug_fix_output")
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        work_dir = tempfile.mkdtemp(prefix="bug_fix_")

        # ---------- 1. 准备底包 system ----------
        base_sys_raw = None
        if base_sys_img.endswith(".zip"):
            log.write("[底包] 检测到 ZIP 包，正在提取 system...\n")
            zip_extract = os.path.join(work_dir, "base_zip")
            os.makedirs(zip_extract)
            sys_dir, img_path = _find_system_in_zip(base_sys_img, zip_extract)
            if img_path:
                base_sys_raw = img_path
            elif sys_dir:
                log.write("[错误] 底包 ZIP 中未找到 system.img，无法确定分区大小\n")
                shutil.rmtree(work_dir)
                return False
            else:
                log.write("[错误] 底包 ZIP 中未找到有效 system 文件\n")
                shutil.rmtree(work_dir)
                return False
        else:
            base_sys_raw = base_sys_img

        if _is_sparse(base_sys_raw):
            log.write("[底包] 检测到 sparse 镜像，转换为 raw...\n")
            raw_img = os.path.join(work_dir, "base_system_raw.img")
            _simg2img(base_sys_raw, raw_img)
            base_sys_raw = raw_img
            log.write("转换完成。\n")

        base_size = os.path.getsize(base_sys_raw)
        log.write(f"底包原始分区大小：{base_size} 字节\n")

        # 解包底包
        base_dir = os.path.join(work_dir, "base_system")
        os.makedirs(base_dir)
        extractor = imgextractor.Extractor()
        old_cwd = os.getcwd()
        os.chdir(work_dir)
        try:
            extractor.main(base_sys_raw, base_dir)
        finally:
            os.chdir(old_cwd)
        base_sys_dir = base_dir
        if os.path.isdir(os.path.join(base_dir, "system")):
            base_sys_dir = os.path.join(base_dir, "system")
        log.write(f"底包 system 目录：{base_sys_dir}\n")

        # ---------- 2. 处理待修复 ROM ----------
        port_sys_dir = None
        port_is_zip = False
        if port_rom_path.endswith(".zip"):
            port_is_zip = True
            log.write("[待修复 ROM] 检测到 ZIP 包，正在提取 system...\n")
            zip_dir = os.path.join(work_dir, "port_zip")
            os.makedirs(zip_dir)
            sys_dir, img_path = _find_system_in_zip(port_rom_path, zip_dir)
            if sys_dir:
                port_sys_dir = sys_dir
            elif img_path:
                port_ext = os.path.join(work_dir, "port_img")
                os.makedirs(port_ext)
                extractor2 = imgextractor.Extractor()
                os.chdir(work_dir)
                try:
                    extractor2.main(img_path, port_ext)
                finally:
                    os.chdir(old_cwd)
                if os.path.isdir(os.path.join(port_ext, "system")):
                    port_sys_dir = os.path.join(port_ext, "system")
                else:
                    port_sys_dir = port_ext
            else:
                log.write("[错误] 待修复 ROM 中未找到 system 内容\n")
                shutil.rmtree(work_dir)
                return False
        elif port_rom_path.endswith(".img"):
            port_dir = os.path.join(work_dir, "port_system")
            os.makedirs(port_dir)
            extractor2 = imgextractor.Extractor()
            os.chdir(work_dir)
            try:
                extractor2.main(port_rom_path, port_dir)
            finally:
                os.chdir(old_cwd)
            port_sys_dir = port_dir
            if os.path.isdir(os.path.join(port_dir, "system")):
                port_sys_dir = os.path.join(port_dir, "system")
        elif os.path.isdir(port_rom_path):
            port_sys_dir = port_rom_path
        else:
            log.write("[错误] 不支持的 ROM 格式\n")
            shutil.rmtree(work_dir)
            return False

        if not port_sys_dir:
            log.write("[错误] 未能获取待修复 ROM 的 system 目录\n")
            shutil.rmtree(work_dir)
            return False

        # ---------- 3. 执行修复 ----------
        log.write(f"\n开始修复，选中项目：{', '.join(selected_fixes)}\n")
        total = 0
        for fix_key in selected_fixes:
            item = BUG_FIX_ITEMS[fix_key]
            log.write(f"\n--- {item['name']} ---\n")
            cnt = _replace_patterns(base_sys_dir, port_sys_dir, item['patterns'], log)
            total += cnt
        log.write(f"\n共替换 {total} 个文件/目录\n")

        # ---------- 4. 打包输出 ----------
        if port_is_zip:
            log.write("\n打包为卡刷包...\n")
            out_zip = os.path.join(output_dir, os.path.basename(port_rom_path))
            tmp_repack = tempfile.mkdtemp(prefix="repack_")
            shutil.unpack_archive(port_rom_path, tmp_repack, 'zip')
            old_sys = os.path.join(tmp_repack, "system")
            if os.path.exists(old_sys):
                shutil.rmtree(old_sys)
            shutil.copytree(port_sys_dir, old_sys)
            shutil.make_archive(out_zip[:-4], 'zip', tmp_repack)
            shutil.rmtree(tmp_repack)
            log.write(f"✅ 卡刷包已保存到：{out_zip}\n")
        else:
            # 计算实际需要的镜像大小（实际内容 + 100MB 余量）
            actual_size = _get_dir_size(port_sys_dir)
            img_size = max(base_size, actual_size + 100 * 1024 * 1024)  # 至少比原分区大，且留有足够空间
            log.write(f"系统目录实际大小：{actual_size} 字节，生成的镜像大小：{img_size} 字节\n")

            out_raw = os.path.join(output_dir, "system_raw.img")
            cmd = [make_ext4fs_bin, "-l", str(img_size), "-a", "/system", out_raw, port_sys_dir]
            log.write(f"打包命令：{' '.join(cmd)}\n")
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                log.write(f"[错误] make_ext4fs 执行失败：{proc.stderr}\n")
                shutil.rmtree(work_dir)
                return False
            if not os.path.exists(out_raw):
                log.write("[错误] 未生成 raw 镜像\n")
                shutil.rmtree(work_dir)
                return False

            # 根据原底包格式决定是否转 sparse
            if _is_sparse(base_sys_img):
                log.write("转换为 sparse 格式...\n")
                out_sparse = os.path.join(output_dir, "system.img")
                _img2simg(out_raw, out_sparse)
                os.remove(out_raw)
                log.write(f"✅ sparse 镜像已保存到：{out_sparse}\n")
            else:
                final_img = os.path.join(output_dir, "system.img")
                os.rename(out_raw, final_img)
                log.write(f"✅ raw 镜像已保存到：{final_img}\n")

        shutil.rmtree(work_dir)
        return True
    except Exception as e:
        log.write(f"\n[异常] {traceback.format_exc()}\n")
        return False