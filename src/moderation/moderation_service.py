import logging
import settings
from settings import config
from openai import OpenAI  # 直接导入OpenAI客户端

logger = logging.getLogger(__name__)

class ModerationService:
    def __init__(self):
        self.client = self._init_client()
        self.keywords = config.moderation_keywords
        self.model_name = config.moderation_model
        self.temperature = config.moderation_temperature
        self.max_tokens = config.moderation_max_tokens

    def _init_client(self):
        from openai import OpenAI
        provider = config.moderation_provider
        return OpenAI(
            api_key=config.llm_api_key(provider=provider),
            base_url=config.llm_endpoint(provider=provider)
        )

    def check_relevance(self, query: str) -> bool:
        """审核查询相关性"""
        logger.info(f"开始审核问题: {query}")
        
        if config.get_enable_keyword and self._keyword_check(query):
            return True
        
        if config.get_enable_model_check:
            return self._model_check(query)
        
        return config.get_fallback_strategy == "allow"

    def _keyword_check(self, query: str) -> bool:
        """关键词匹配审核"""
        query_lower = query.lower()
        if any(kw in query_lower for kw in self.keywords):
            logger.info(f"关键词匹配通过: {query}")
            return True
        return False

    def _model_check(self, query: str) -> bool:
        """大模型审核"""
        messages = [
            {"role": "system", "content": "判断用户问题是否与Apache Doris数据库相关，仅回答Y/N"},
            {"role": "user", "content": f"问题：{query}"}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                max_tokens=1
            )
            result = response.choices[0].message.content.strip().upper() == "Y"
            logger.info(f"模型审核结果: {'通过' if result else '拒绝'}")
            return result
        except Exception as e:
            logger.error(f"审核查询失败: {str(e)}")
            return True  # 失败时默认通过 