import os
import uuid
from werkzeug.utils import secure_filename


def secure_filename_cn(filename):
    """
    安全地处理中文文件名
    1. 使用UUID生成唯一文件名前缀
    2. 保留原文件的扩展名
    """
    if not filename:
        return ""

    # 生成唯一文件名前缀
    unique_prefix = uuid.uuid4().hex

    # 提取扩展名
    _, ext = os.path.splitext(filename)

    # 组合新的文件名
    safe_filename = unique_prefix + ext

    return safe_filename
