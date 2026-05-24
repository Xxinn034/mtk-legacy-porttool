# mtk-garbage-porttool-master/porttool/simg2img.py

import struct
import os

# Android sparse image 的魔数 (magic number)
SPARSE_HEADER_MAGIC = 0xED26FF3A

# 文件头结构大小
SPARSE_HEADER_SIZE = 28
CHUNK_HEADER_SIZE = 12

# Chunk 类型
CHUNK_TYPE_RAW = 0xCAC1
CHUNK_TYPE_FILL = 0xCAC2
CHUNK_TYPE_DONT_CARE = 0xCAC3
CHUNK_TYPE_CRC32 = 0xCAC4

def is_sparse_image(filepath):
    """
    检查镜像文件是否为 Android sparse image 格式
    """
    if not os.path.exists(filepath):
        return False
    try:
        with open(filepath, 'rb') as f:
            # 读取文件头部的 magic number（小端序的32位整数）
            magic = struct.unpack('<I', f.read(4))[0]
            return magic == SPARSE_HEADER_MAGIC
    except Exception:
        return False

def simg2img(input_path, output_path):
    """
    将 Android sparse image 转换为 raw ext4 image

    Args:
        input_path (str): 输入的 sparse image 文件路径
        output_path (str): 输出的 raw ext4 image 文件路径

    Returns:
        bool: 转换成功返回 True，失败返回 False
    """
    try:
        with open(input_path, 'rb') as f_in:
            # --- 1. 解析文件头 (sparse_header) ---
            header_data = f_in.read(SPARSE_HEADER_SIZE)
            if len(header_data) < SPARSE_HEADER_SIZE:
                return False
            
            magic, major_version, minor_version, file_hdr_sz, chunk_hdr_sz, \
            block_sz, total_blks, total_chunks, image_checksum = \
                struct.unpack('<IHHHHIIII', header_data)

            # 验证魔数
            if magic != SPARSE_HEADER_MAGIC:
                return False

            # --- 2. 逐块处理 (chunk) ---
            with open(output_path, 'wb') as f_out:
                for i in range(total_chunks):
                    # 读取 chunk 头部
                    chunk_header = f_in.read(CHUNK_HEADER_SIZE)
                    if len(chunk_header) < CHUNK_HEADER_SIZE:
                        return False
                    
                    chunk_type, reserved1, chunk_sz, total_sz = \
                        struct.unpack('<HHII', chunk_header)

                    if chunk_type == CHUNK_TYPE_RAW:
                        # 如果是 RAW 类型，直接从输入文件读取 chunk_sz * block_sz 字节到输出文件
                        data = f_in.read(chunk_sz * block_sz)
                        f_out.write(data)

                    elif chunk_type == CHUNK_TYPE_FILL:
                        # 如果是 FILL 类型，读取4字节的填充数据，然后重复写入 total_sz * block_sz 字节
                        fill_data = f_in.read(4)
                        # 跳过保留的4字节
                        f_in.read(4)
                        for _ in range(chunk_sz * (block_sz // 4)):
                            f_out.write(fill_data)

                    elif chunk_type == CHUNK_TYPE_DONT_CARE:
                        # 如果是 DONT_CARE 类型，直接在输出文件填充0
                        total_bytes = chunk_sz * block_sz
                        f_out.write(b'\x00' * total_bytes)

                    elif chunk_type == CHUNK_TYPE_CRC32:
                        # CRC32 块，读取但不操作，跳过保留的4字节
                        f_in.read(4)
                        f_in.read(4)
                        continue
                    else:
                        # 未知的 chunk 类型，跳过
                        continue

            return True

    except Exception as e:
        print(f"   [simg2img] 转换过程发生错误: {e}")
        return False