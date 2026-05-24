#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import shutil
import tempfile
import traceback
from pathlib import Path

from . import bootimg


def _sanitize_name(name: str) -> str:
    """清理文件名中的特殊字符，用下划线替代"""
    return name.translate(str.maketrans({
        '[': '_',
        ']': '_',
        '{': '_',
        '}': '_',
        '(': '_',
        ')': '_',
        ' ': '_',
        '!': '_',
        '&': '_',
    }))


def port_twrp(official_rec_path, port_rec_path, log, output_dir=None):
    """
    执行 TWRP 移植（仅替换内核）：
    official_rec_path : 官方 recovery.img 路径
    port_rec_path     : 要移植的 recovery.img 路径
    log              : 日志输出对象（需要 write 方法）
    output_dir       : 输出目录，默认为当前目录下的 twrp_output
    """
    try:
        if not os.path.isfile(official_rec_path):
            log.write("[错误] 官方 recovery 文件不存在\n")
            return False
        if not os.path.isfile(port_rec_path):
            log.write("[错误] 移植 recovery 文件不存在\n")
            return False

        # 输出目录（使用绝对路径，并清理特殊字符）
        if output_dir is None:
            output_dir = os.path.join(os.getcwd(), "twrp_output")
        else:
            output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        # 创建临时工作目录
        work_dir = tempfile.mkdtemp(prefix="twrp_port_")
        official_dir = os.path.join(work_dir, "official")
        port_dir = os.path.join(work_dir, "port")
        os.makedirs(official_dir)
        os.makedirs(port_dir)

        log.write("[TWRP移植] 开始…\n")

        # ---------- 1. 解包官方 recovery ----------
        log.write("\n[1/4] 解包官方 recovery...\n")
        official_boot = os.path.join(official_dir, "boot.img")
        shutil.copy(official_rec_path, official_boot)

        old_cwd = os.getcwd()
        os.chdir(official_dir)
        try:
            if os.path.exists("initrd"):
                shutil.rmtree("initrd")
            bootimg.unpack_bootimg(bootimg="boot.img", directory="initrd")
        finally:
            os.chdir(old_cwd)

        # ---------- 2. 解包移植 recovery ----------
        log.write("[2/4] 解包移植 recovery...\n")
        port_boot = os.path.join(port_dir, "boot.img")
        shutil.copy(port_rec_path, port_boot)

        os.chdir(port_dir)
        try:
            if os.path.exists("initrd"):
                shutil.rmtree("initrd")
            bootimg.unpack_bootimg(bootimg="boot.img", directory="initrd")
        finally:
            os.chdir(old_cwd)

        # ---------- 3. 仅替换内核 ----------
        log.write("[3/4] 替换内核文件...\n")

        # 删除移植包中原有的内核
        for kernel_name in ["kernel", "kernel.gz"]:
            kernel_path = os.path.join(port_dir, kernel_name)
            if os.path.exists(kernel_path):
                os.remove(kernel_path)
                log.write(f"  已删除移植包中的: {kernel_name}\n")

        # 从官方包复制内核到移植包
        for kernel_name in ["kernel", "kernel.gz"]:
            src_path = os.path.join(official_dir, kernel_name)
            if os.path.exists(src_path):
                dst_path = os.path.join(port_dir, kernel_name)
                shutil.copy(src_path, dst_path)
                log.write(f"  已替换: {kernel_name}\n")

        # 复制官方 bootinfo.txt 到移植目录，以便 repack 使用正确的参数
        official_bootinfo = os.path.join(official_dir, "bootinfo.txt")
        port_bootinfo = os.path.join(port_dir, "bootinfo.txt")
        if os.path.exists(official_bootinfo):
            shutil.copy(official_bootinfo, port_bootinfo)
            log.write("  已复制官方 boot 参数\n")

        # ---------- 4. 重新打包移植 recovery ----------
        log.write("[4/4] 重新打包 recovery...\n")
        os.chdir(port_dir)
        try:
            bootimg.repack_bootimg()
            boot_new = os.path.join(port_dir, "boot-new.img")
            if os.path.exists(boot_new):
                twrp_img = os.path.join(output_dir, "twrp.img")
                os.makedirs(output_dir, exist_ok=True)

                # 移动文件，如果失败则尝试复制
                try:
                    shutil.move(boot_new, twrp_img)
                except Exception:
                    shutil.copy(boot_new, twrp_img)
                    os.remove(boot_new)

                # 验证文件是否成功生成
                if os.path.exists(twrp_img):
                    size = os.path.getsize(twrp_img)
                    log.write(f"\n✅ 移植完成！输出文件: {twrp_img}\n  文件大小: {size} 字节\n")
                else:
                    log.write(f"\n[错误] 移动文件失败，{twrp_img} 不存在\n")
                    return False
            else:
                log.write("\n[错误] 打包失败，未找到 boot-new.img\n")
                return False
        finally:
            os.chdir(old_cwd)

        # 清理临时目录
        shutil.rmtree(work_dir)
        return True

    except Exception as e:
        log.write(f"\n[异常] {traceback.format_exc()}\n")
        return False