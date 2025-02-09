import logging
import requests
from pathlib import Path
from typing import Optional
import io
import pandas as pd
import pdfplumber
from PIL import Image
import pytesseract

logger = logging.getLogger(__name__)

def download_file(url: str, save_path: Optional[str] = None) -> Optional[str]:
    """下载文件到本地"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return save_path
        return None
    except Exception as e:
        logger.error(f"文件下载失败: {url} - {str(e)}")
        return None

def extract_text(file_path: str) -> str:
    """提取文本内容（支持多种格式）"""
    try:
        ext = Path(file_path).suffix.lower()
        
        if ext == '.pdf':
            with pdfplumber.open(file_path) as pdf:
                return '\n'.join(page.extract_text() for page in pdf.pages)
                
        elif ext in ['.csv', '.tsv']:
            df = pd.read_csv(file_path)
            return df.to_string()
            
        elif ext == '.txt':
            with open(file_path, 'r') as f:
                return f.read()
                
        elif ext in ['.png', '.jpg', '.jpeg']:
            with Image.open(file_path) as img:
                return pytesseract.image_to_string(img)
                
        else:
            logger.warning(f"不支持的文件格式: {ext}")
            return ""
            
    except Exception as e:
        logger.error(f"内容提取失败: {file_path} - {str(e)}")
        return "" 