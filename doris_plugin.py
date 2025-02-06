from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
import plugins
from plugins import *
from .main import RAGEngine, process_documents
from src.moderation import ModerationService
from common.log import logger
from settings import *
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

@plugins.register(
    name="DorisAI", 
    desc="知识库问答系统", 
    enabled=True,
    version="2.0",
    author="suyijia",
    desire_priority=998
)
class DorisPlugin(Plugin):
    def __init__(self):
        logger.info("=== 开始初始化Doris插件 ===")
        super().__init__()
        # 确保配置加载优先
        self.config = self.load_config()  
        # 先加载配置再初始化日志
        self._init_logger()
        # 初始化顺序控制
        self._init_services()
        # 绑定消息处理事件
        self.handlers = {
            Event.ON_HANDLE_CONTEXT: self.handle_query
        }
        self.collection_name = "doris_docs"

    def _init_logger(self):
        # 从配置获取日志级别
        log_level = self.config.get("log_level", "INFO").upper()
        
        # 设置日志级别映射
        level_mapping = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        
        # 设置根日志级别
        logging.basicConfig(
            level=level_mapping.get(log_level, logging.INFO),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logger.info(f"日志级别已设置为: {log_level}")

    def _init_services(self):
        self.rag_engine = RAGEngine()
        self.moderation = ModerationService()

    def handle_query(self, e_context: EventContext):
        """消息处理入口"""
        context = e_context['context']
        
        # 仅处理文本消息
        if context.type != ContextType.TEXT:
            return
            
        question = context.content.strip()
        
        try:
            # 1.内容审核（移植原有审核逻辑）
            if self.moderation.check_relevance(question):
                reply = Reply(ReplyType.ERROR, "包含敏感内容")
                e_context.action = EventAction.BREAK
                return
                
            # 2.是否为其他 API 调用
            if question.startswith("#process"):
                # 判断是否为管理员
                if context.user_id not in self.config["admin_users"]:
                    reply = Reply(ReplyType.ERROR, "您不是管理员，无法开始处理文档！")
                    e_context.action = EventAction.BREAK
                    return
                logger.info("开始处理文档")
                process_documents()
                e_context.action = EventAction.BREAK
                return

            # 3.处理问答（移植原API逻辑）
            response = self.rag_engine.process_query(
                question, 
                self.collection_name
            )
            
            # 3.构建回复
            reply = Reply()
            reply.type = ReplyType.TEXT
            reply.content = f"知识库回答：\n{response}"
            e_context['reply'] = reply
            e_context.action = EventAction.BREAK_PASS
            
        except Exception as e:
            logger.error(f"处理失败: {str(e)}")
            reply = Reply(ReplyType.ERROR, f"查询失败：{str(e)}")
            e_context['reply'] = reply
            e_context.action = EventAction.BREAK

    def load_config(self):
        try:
            from settings import load_config  # 确保绝对导入
            return load_config()
        except Exception as e:
            logger.error(f"配置加载失败: {str(e)}")
            raise RuntimeError("无法加载插件配置") from e 