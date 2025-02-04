import logging
import settings
from openai import OpenAI  # 直接导入OpenAI客户端

logger = logging.getLogger(__name__)

class ModerationService:
    def __init__(self, config=None):
        if not config:
            raise ValueError("必须提供配置参数")
            
        self.config = config
        self.client = self._init_client()
        self.keywords = settings.DORIS_KEYWORDS
        self.model_name = settings.MODERATION_MODEL
        self.temperature = settings.MODERATION_TEMP

    def _init_client(self):
        provider = self.config["model_config"]["services"]["moderation"]["provider"]
        return OpenAI(
            api_key=self.config["model_config"]["providers"][provider]["api_key"],
            base_url=self.config["model_config"]["providers"][provider]["endpoint"]
        )

    def check_relevance(self, query: str) -> bool:
        """审核查询相关性"""
        logger.info(f"开始审核问题: {query}")
        
        if settings.MODERATION_CONFIG["enable_keyword"] and self._keyword_check(query):
            return True
        
        if settings.MODERATION_CONFIG["enable_model_check"]:
            return self._model_check(query)
        
        return settings.MODERATION_CONFIG["fallback_strategy"] == "allow"

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