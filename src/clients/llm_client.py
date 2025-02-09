import logging
from openai import OpenAI
from settings import config
logger = logging.getLogger(__name__)

class UnifiedLLMClient:
    def __init__(self, config):
        self.config = config
        self.clients = {
            'deepseek': OpenAI(
                api_key=config.llm_api_key(provider="deepseek"),
                base_url=config.llm_endpoint(provider="deepseek")
            ),
            'custom': OpenAI(
                api_key=config.llm_api_key(provider="custom_llm"),
                base_url=config.llm_endpoint(provider="custom_llm")
            ),
            'siliconflow': OpenAI(
                api_key=config.llm_api_key(provider="siliconflow"),
                base_url=config.llm_endpoint(provider="siliconflow")
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
            api_key=config.llm_api_key(provider=config.chat_provider),
            base_url=config.llm_endpoint(provider=config.chat_provider)
        )
        # 获取嵌入服务配置
        embedding_provider = config.embedding_provider
        
        self.embedding = OpenAI(
            api_key=config.llm_api_key(provider=embedding_provider),
            base_url=config.llm_endpoint(provider=embedding_provider)
        )
        logger.info(f"初始化嵌入客户端: {embedding_provider}")

    def _init_client(self, config, service_type):
        """初始化同步客户端"""
        from openai import OpenAI
        provider = config["model_config"]["services"][service_type]["provider"]
        logger.info(f"初始化同步客户端: {provider}")
        return OpenAI(
            api_key=config.llm_api_key(provider=provider),
            base_url=config.llm_endpoint(provider=provider)
        ) 