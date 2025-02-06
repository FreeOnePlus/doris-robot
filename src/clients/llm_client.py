import logging
from openai import OpenAI
from settings import config

logger = logging.getLogger(__name__)

class UnifiedLLMClient:
    def __init__(self, config):
        self.config = config
        self.clients = {
            'deepseek': OpenAI(
                api_key=config["model_config"]["providers"]["deepseek"]["api_key"],
                base_url=config["model_config"]["providers"]["deepseek"]["endpoint"]
            ),
            'custom': OpenAI(
                api_key=config["model_config"]["providers"]["custom_llm"]["api_key"],
                base_url=config["model_config"]["providers"]["custom_llm"]["endpoint"]
            ),
            'siliconflow': OpenAI(
                api_key=config["model_config"]["providers"]["siliconflow"]["api_key"],
                base_url=config["model_config"]["providers"]["siliconflow"]["endpoint"]
            )
        }

    def get_client(self, model_name):
        if 'deepseek' in model_name:
            return self.clients['deepseek']
        elif 'siliconflow' in model_name:
            return self.clients['siliconflow']
        else:
            return self.clients['custom']

class LLMClients:
    def __init__(self):
        """使用同步客户端"""
        self.config = config._config  # 直接使用全局配置实例
        self.chat = OpenAI(
            api_key=config.llm_api_key(provider="deepseek"),
            base_url=config.llm_endpoint(provider="deepseek")
        )
        self.embedding = OpenAI(
            api_key=config.llm_api_key(provider="siliconflow"),
            base_url=config.llm_endpoint(provider="siliconflow")
        )

    def _init_client(self, config, service_type):
        """初始化同步客户端"""
        from openai import OpenAI
        provider = config["model_config"]["services"][service_type]["provider"]
        logger.info(f"初始化同步客户端: {provider}")
        return OpenAI(
            api_key=config["model_config"]["providers"][provider]["api_key"],
            base_url=config["model_config"]["providers"][provider]["endpoint"]
        ) 