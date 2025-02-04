import logging
from openai import OpenAI
from settings import DEEPSEEK_API_KEY, SILICONFLOW_API_KEY, load_config

logger = logging.getLogger(__name__)

class UnifiedLLMClient:
    def __init__(self, config):
        self.config = config
        self.clients = {
            'deepseek': OpenAI(
                api_key=config["api_keys"]["deepseek"],
                base_url=config["model_config"]["endpoints"]["deepseek"]
            ),
            'custom': OpenAI(
                api_key=config["api_keys"]["custom_llm"],
                base_url=config["model_config"]["endpoints"]["custom_llm"]
            )
        }

    def get_client(self, model_name):
        if 'deepseek' in model_name:
            return self.clients['deepseek']
        else:
            return self.clients['custom']

class LLMClients:
    def __init__(self):
        """使用同步客户端"""
        config = load_config()
        self.chat = self._init_client(config, "chat")
        self.moderation = self._init_client(config, "moderation")
        self.embedding = self._init_client(config, "embedding")

    def _init_client(self, config, service_type):
        """初始化同步客户端"""
        from openai import OpenAI
        provider = config["model_config"]["services"][service_type]["provider"]
        logger.info(f"初始化同步客户端: {provider}")
        return OpenAI(
            api_key=config["model_config"]["providers"][provider]["api_key"],
            base_url=config["model_config"]["providers"][provider]["endpoint"]
        ) 