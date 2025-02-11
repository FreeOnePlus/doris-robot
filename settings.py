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

class ConfigManager:
    """统一配置管理类"""
    def __init__(self):
        self._load_config()
        self._validate_config()
    
    def _load_config(self):
        """从config.json加载配置"""
        config_path = Path(__file__).parent / "config.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Missing config file: {config_path}")
        
        with open(config_path) as f:
            self._config = json.load(f)
    
    @property
    def milvus_host(self) -> str:
        return self._config["milvus"]["host"]
    
    @property
    def milvus_port(self) -> int:
        return self._config["milvus"]["port"]
    
    @property
    def vector_dimension(self) -> int:
        return self._config["vector_dimension"]
    
    @property
    def doris_docs_path(self) -> Path:
        return Path(self._config["data_paths"]["doris_docs"])
    
    @property
    def doc_collection_name(self) -> str:
        return self._config["collection_name"]
    
    @property
    def jira_docs_path(self) -> Path:
        return Path(self._config["data_paths"]["jira_docs"])
    
    @property
    def chat_provider(self) -> str:
        return self._config["model_config"]["services"]["chat"]["provider"]
    
    @property
    def embedding_provider(self) -> str:
        return self._config["model_config"]["services"]["embedding"]["provider"]
    
    @property
    def embedding_model(self) -> str:
        return self._config["model_config"]["services"]["embedding"]["model"]
    
    @property
    def moderation_keywords(self) -> list:
        return self._config["moderation"]["keywords"]
    
    @property
    def logging_level(self) -> str:
        return self._config["logging_config"]["level"]
    
    @property
    def moderation_model(self) -> str:
        return self._config["model_config"]["services"]["moderation"]["model"]
    
    @property
    def moderation_config(self) -> dict:
        return self._config["moderation"]
    
    @property
    def moderation_temperature(self) -> float:
        return self._config["model_config"]["services"]["moderation"]["temperature"]
    
    @property
    def moderation_max_tokens(self) -> int:
        return self._config["model_config"]["services"]["moderation"]["max_tokens"]
    
    @property
    def moderation_provider(self) -> str:
        return self._config["model_config"]["services"]["moderation"]["provider"]
    
    def llm_endpoint(self, provider: str) -> str:
        return self._config["model_config"]["providers"][provider]["endpoint"]
    
    def llm_api_key(self, provider: str) -> str:
        return self._config["model_config"]["providers"][provider]["api_key"]
    
    @property
    def get_enable_keyword(self) -> bool:
        return self._config["moderation"]["enable_keyword"]
    
    @property
    def get_enable_model_check(self) -> bool:
        return self._config["moderation"]["enable_model_check"]
    
    @property
    def get_fallback_strategy(self) -> str:
        return self._config["moderation"]["fallback_strategy"]
    
    @property
    def get_min_similarity(self) -> float:
        return self._config["search_config"]["min_similarity"]
    
    @property
    def get_version_weights(self) -> dict:
        return self._config["search_config"]["version_weights"]
    
    @property
    def get_chat_model(self) -> str:
        return self._config["model_config"]["services"]["chat"]["model"]
    
    @property
    def get_generation_model(self) -> str:
        return self._config["model_config"]["services"]["generation"]["model"]
    
    @property
    def get_chat_temperature(self) -> float:
        return self._config["model_config"]["services"]["chat"]["temperature"]
    
    @property
    def get_generation_temperature(self) -> float:
        return self._config["model_config"]["services"]["generation"]["temperature"]
    
    @property
    def get_chat_max_tokens(self) -> int:
        return self._config["model_config"]["services"]["chat"]["max_tokens"]
    
    @property
    def jira_config(self) -> dict:
        """获取Jira相关配置"""
        return {
            "jira": self._config["jira"],
            "data_paths": self._config["data_paths"]
        }
    
    def __getattr__(self, name):
        """通用访问方法"""
        return self._config.get(name)

    def _validate_config(self):
        required = [
            'jira.base_url',
            'jira.auth_token',
            'milvus.host',
            'milvus.port',
            'data_paths.jira_data',
            'vector_dimension'
        ]
        for key in required:
            current = self._config
            for part in key.split('.'):
                if part not in current:
                    raise ValueError(f"缺少必要配置项: {key}")
                current = current[part]

# 全局配置实例
config = ConfigManager()

# 初始化日志配置（从配置文件读取）
logging.basicConfig(
    level=config.logging_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

class Settings:
    def __init__(self):
        self.data = config._config
        
    def __getattr__(self, name):
        return self.data.get(name)

class Config:
    # 日志配置
    logging_level = logging.INFO
    milvus_log_level = logging.DEBUG  # 单独控制Milvus日志级别
    
    @property
    def get_logging_config(self):
        return {
            "version": 1,
            "loggers": {
                "": {
                    "level": self.logging_level,
                    "handlers": ["console"]
                },
                "src.vectorstore.milvus_store": {
                    "level": self.milvus_log_level,
                    "propagate": False
                }
            }
        } 