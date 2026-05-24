#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, re, gzip, shutil, tempfile, zipfile, subprocess
from pathlib import Path
from . import bootimg, imgextractor
from .configs import magiskboot_bin

def _extract_linux_ver(kernel_raw, log_func=None):
    """从内核二进制数据中提取版本字符串（放宽提取条件）"""
    if not kernel_raw:
        return "", ""
    for keyword in [b"Linux version", b"Linux kernel", b"Linux"]:
        pos = kernel_raw.find(keyword)
        if pos != -1:
            end = pos + len(keyword)
            while end < len(kernel_raw):
                byte = kernel_raw[end]
                if byte == 0x00 or byte == 0x0A or byte == 0x0D:
                    break
                end += 1
            raw_str = kernel_raw[pos:end].decode('latin-1', errors='replace')
            linux_ver = raw_str.strip()
            if linux_ver:
                if log_func:
                    log_func(f"通过关键字 '{keyword.decode()}' 找到：{linux_ver}\n")
                gcc_ver = ""
                gcc_match = re.search(r'gcc version\s+([^\s\)]+)', linux_ver)
                if gcc_match:
                    gcc_ver = gcc_match.group(1)
                return linux_ver, gcc_ver
    # 最后在文本中搜索
    text = kernel_raw.decode('latin-1', errors='ignore')
    match = re.search(r'Linux[ \t]+(?:version|kernel)[ \t]*([^\n\x00\r]+)', text, re.IGNORECASE)
    if match:
        linux_ver = match.group(0).strip()
        if log_func:
            log_func(f"通过文本搜索找到：{linux_ver}\n")
        gcc_ver = ""
        gcc_match = re.search(r'gcc version\s+([^\s\)]+)', linux_ver)
        if gcc_match:
            gcc_ver = gcc_match.group(1)
        return linux_ver, gcc_ver
    return "", ""

def get_boot_info(boot_path, log_func=None):
    """解包 boot.img 并提取内核版本、GCC 版本等信息（使用 magiskboot 以确保兼容性）"""
    if not os.path.isfile(boot_path):
        if log_func: log_func("【错误】boot.img 文件不存在\n")
        return None
    work_dir = tempfile.mkdtemp(prefix="info_")
    try:
        # 1. 复制 boot.img 到临时目录
        shutil.copy(boot_path, os.path.join(work_dir, "boot.img"))
        old = os.getcwd()
        os.chdir(work_dir)
        try:
            # 2. 使用 magiskboot 解包（支持多种压缩格式）
            if log_func: log_func("正在使用 magiskboot 解包 boot.img ...\n")
            result = subprocess.run(
                [magiskboot_bin, "unpack", "boot.img"],
                capture_output=True,
                text=True,
                cwd=work_dir
            )
            if result.returncode != 0:
                if log_func: log_func(f"magiskboot 解包失败：{result.stderr}\n")
                return None
            if log_func: log_func("解包完成。\n")
        finally:
            os.chdir(old)

        # 3. 读取解包后的文件
        kernel_raw = None
        kernel_path = os.path.join(work_dir, "kernel")
        kernel_gz_path = os.path.join(work_dir, "kernel.gz")
        # magiskboot 解包后 kernel 通常是未压缩的，直接读取即可
        if os.path.exists(kernel_path):
            with open(kernel_path, "rb") as f:
                kernel_raw = f.read()
            if log_func: log_func(f"读取到 kernel 文件，大小 {len(kernel_raw)} 字节\n")
        elif os.path.exists(kernel_gz_path):
            if log_func: log_func("发现 kernel.gz，尝试解压...\n")
            try:
                with gzip.open(kernel_gz_path, "rb") as f:
                    kernel_raw = f.read()
            except Exception:
                # 可能不是标准 gzip，直接读取原始数据
                with open(kernel_gz_path, "rb") as f:
                    kernel_raw = f.read()
                if log_func: log_func("无法解压 kernel.gz，以原始数据读取\n")
        else:
            if log_func: log_func("未找到 kernel 文件\n")

        # 4. 提取内核版本信息
        linux_ver, gcc_ver = _extract_linux_ver(kernel_raw, log_func)

        # 5. 尝试从 magiskboot 输出的 bootinfo.txt 获取参数（如果有）
        # magiskboot 可能不会生成 bootinfo.txt，我们也可以回退到 bootimg.py 解包获取
        bootinfo = {}
        bootinfo_path = os.path.join(work_dir, "bootinfo.txt")
        if not os.path.exists(bootinfo_path):
            # 回退到 bootimg.py 解包（仅在 magiskboot 没有生成 bootinfo 时使用）
            try:
                os.chdir(work_dir)
                # 需要把 boot.img 复制一份（因为可能已被 magiskboot 解包后删除？但还在）
                # 实际上 magiskboot unpack 后 boot.img 应该还在，但 bootimg.unpack_bootimg 可能要求文件名
                if os.path.exists("boot.img"):
                    bootimg.unpack_bootimg(bootimg="boot.img", directory="initrd")
                    if log_func: log_func("通过 bootimg.py 补提 bootinfo\n")
            except Exception as e:
                if log_func: log_func(f"回退解包失败：{e}\n")
            os.chdir(old)

        if os.path.exists(bootinfo_path):
            with open(bootinfo_path) as f:
                for line in f:
                    if ':' in line:
                        k, v = line.strip().split(':', 1)
                        bootinfo[k.strip()] = v.strip()

        return {
            "cmdline": bootinfo.get("cmdline", ""),
            "base": bootinfo.get("base", ""),
            "page_size": bootinfo.get("page_size", ""),
            "name": bootinfo.get("name", ""),
            "kernel_version": linux_ver,
            "gcc_version": gcc_ver,
        }
    except Exception as e:
        if log_func: log_func(f"解析 boot 信息出错: {e}\n")
        return {"error": str(e)}
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        if log_func: log_func("临时文件已清理\n")

def get_system_info(sys_path, log_func=None):
    """解包 system.img 并读取 build.prop 信息（输出中文标签）"""
    if not os.path.isfile(sys_path):
        if log_func: log_func("【错误】system.img 文件不存在\n")
        return None
    work_dir = tempfile.mkdtemp(prefix="info_")
    try:
        if log_func: log_func("正在解包 system.img ...\n")
        extractor = imgextractor.Extractor()
        extractor.main(sys_path, work_dir)
        if log_func: log_func("解包完成。\n")
        sys_dir = os.path.join(work_dir, "system")
        if not os.path.isdir(sys_dir):
            sys_dir = work_dir
        build_prop = os.path.join(sys_dir, "build.prop")
        info = {}
        if os.path.exists(build_prop):
            with open(build_prop, 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        k, v = line.strip().split('=', 1)
                        info[k.strip()] = v.strip()
        return {
            "CPU 架构": info.get("ro.product.cpu.abi", ""),
            "CPU 架构 (辅助)": info.get("ro.product.cpu.abi2", ""),
            "主板": info.get("ro.product.board", ""),
            "制造商": info.get("ro.product.manufacturer", ""),
            "型号": info.get("ro.product.model", ""),
            "Android 版本": info.get("ro.build.version.release", ""),
            "SDK 版本": info.get("ro.build.version.sdk", ""),
            "构建指纹": info.get("ro.build.fingerprint", ""),
        }
    except Exception as e:
        if log_func: log_func(f"解析 system 信息出错: {e}\n")
        return {"错误": str(e)}
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        if log_func: log_func("临时文件已清理\n")

def get_zip_info(zip_path, log_func=None):
    """从卡刷包 zip 中提取 build.prop 信息"""
    if not os.path.isfile(zip_path):
        if log_func: log_func("【错误】卡刷包文件不存在\n")
        return None
    work_dir = tempfile.mkdtemp(prefix="info_")
    try:
        if log_func: log_func("正在解压卡刷包...\n")
        with zipfile.ZipFile(zip_path, 'r') as z:
            build_prop = None
            for name in z.namelist():
                if name.endswith("build.prop") and 'system' in name.lower():
                    build_prop = name
                    break
            if not build_prop:
                for name in z.namelist():
                    if name == "build.prop" or name.endswith("/build.prop"):
                        build_prop = name
                        break
            if not build_prop:
                if log_func: log_func("未在卡刷包中找到 build.prop\n")
                return {"错误": "未找到 build.prop"}
            z.extract(build_prop, work_dir)
            prop_file = os.path.join(work_dir, build_prop)
        info = {}
        if os.path.exists(prop_file):
            with open(prop_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        k, v = line.strip().split('=', 1)
                        info[k.strip()] = v.strip()
        return {
            "CPU 架构": info.get("ro.product.cpu.abi", ""),
            "CPU 架构 (辅助)": info.get("ro.product.cpu.abi2", ""),
            "主板": info.get("ro.product.board", ""),
            "制造商": info.get("ro.product.manufacturer", ""),
            "型号": info.get("ro.product.model", ""),
            "Android 版本": info.get("ro.build.version.release", ""),
            "SDK 版本": info.get("ro.build.version.sdk", ""),
            "构建指纹": info.get("ro.build.fingerprint", ""),
        }
    except Exception as e:
        if log_func: log_func(f"解析卡刷包信息出错: {e}\n")
        return {"错误": str(e)}
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        if log_func: log_func("临时文件已清理\n")