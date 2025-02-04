import os
from dotenv import load_dotenv
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# 配置日志
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": "DEBUG"  # 允许输出DEBUG日志
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "src.qa": {
            "level": "DEBUG",  # 启用RAG引擎的DEBUG日志
            "propagate": False
        }
    }
}

load_dotenv()

# Milvus配置
MILVUS_HOST = "milvus_host"  # 确保这是正确的内网地址
MILVUS_PORT = 19530  # 确认端口开放

# DeepSeek配置
DEEPSEEK_API_KEY = "sk-xxx"

# SiliconFlow配置
SILICONFLOW_API_KEY = "sk-yyy"  

# 文档路径配置
DORIS_DOCS_PATH = "docs_path"  # 本地clone的文档路径
JIRA_DATA_PATH = "./jira_data"    # Jira数据存放路径

# 向量维度配置
VECTOR_DIMENSION = 1024  # bge-large-zh-v1.5的维度

# 关键词配置
DORIS_KEYWORDS = [
    "doris", "数据库", "apache", 
    "查询", "表", "分区", 
    "分桶", "物化视图", "rollup",
    "bitmap", "olap", "broker"
]

# 审核模型配置
MODERATION_MODEL = "deepseek-chat"  # 可切换为其他轻量级模型
MODERATION_TEMP = 0.1

# 审核配置增强
MODERATION_CONFIG = {
    "enable_keyword": True,
    "enable_model_check": True,
    "fallback_strategy": "allow",  # allow/deny
    "timeout": 5.0  # 模型调用超时时间
}

# 新增嵌入模型配置
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

SUPPORTED_EMBEDDING_MODELS = {
    'Pro/BAAI/bge-m3': {'dim': 1024},  
    'Pro/BAAI/bge-base-zh-v1.5': {'dim': 768},
    'text-embedding-3-small': {'dim': 1536},  # 保留原有配置
    'text-embedding-3-large': {'dim': 3072}
} 

# 新增搜索配置
SEARCH_CONFIG = {
    "min_similarity": 0.65,  # 最低相似度阈值
    "version_weights": {
        "3.0": 1.5,
        "2.1": 1.3,
        "2.0": 1.0,
        "dev": 0.7
    },
    "diversity_ratio": 0.3  # 多样性保留比例
} 

DEFAULT_MODEL_CONFIG = {
    "chat_model": "deepseek-chat",
    "embedding_model": "Pro/BAAI/bge-m3",
    "generation_model": "deepseek-ai/DeepSeek-V3", 
    "moderation_model": "deepseek-moderation"
}

def load_config():
    logger.info("=== 开始加载配置 ===")
    config_path = Path(__file__).parent / "config.json"
    logger.debug("配置文件路径: %s", config_path)
    
    # 打印路径详细信息
    logger.debug("当前工作目录: %s", Path.cwd())
    logger.debug("配置文件绝对路径: %s", config_path.absolute())
    
    if not config_path.exists():
        logger.error("配置文件不存在！搜索路径：%s", config_path)
        logger.error("当前目录内容：%s", list(Path.cwd().iterdir()))
        raise FileNotFoundError(f"找不到配置文件: {config_path}")
    
    logger.info("找到配置文件，开始解析...")
    try:
        with open(config_path) as f:
            config = json.load(f)
            logger.debug("配置内容预览: %s", str(config)[:200] + "...")  # 防止泄露敏感信息
        return config
    except Exception as e:
        logger.exception("配置文件解析失败！")
        raise

class Settings:
    def __init__(self):
        self.data = load_config()
        
    def __getattr__(self, name):
        return self.data.get(name) 