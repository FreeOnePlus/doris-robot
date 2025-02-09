import hashlib
import os
from pathlib import Path

def save_attachment(content: bytes, filename: str) -> str:
    """保存附件到本地并返回路径"""
    # 创建存储目录
    save_dir = Path(config.data_paths.jira_attachments)
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成唯一文件名
    file_hash = hashlib.md5(content).hexdigest()
    ext = Path(filename).suffix
    save_path = save_dir / f"{file_hash}{ext}"
    
    # 保存文件
    with open(save_path, 'wb') as f:
        f.write(content)
    
    return str(save_path) 