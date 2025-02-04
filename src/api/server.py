from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from src.qa.rag_engine import RAGEngine
import logging
import uvicorn
import logging.handlers
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
from src.moderation import ModerationService

logger = logging.getLogger(__name__)

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)

def create_app():
    app = FastAPI(title="Doris智能问答API")
    
    # 设置日志级别
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件输出（保留原有配置）
    file_handler = logging.handlers.RotatingFileHandler(
        'api.log',
        maxBytes=1024*1024*100,
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 直接初始化RAG引擎实例
    rag_engine = RAGEngine()
    collection_name = "doris_docs"

    # 独立初始化审核服务（使用配置）
    moderation = ModerationService(rag_engine.config)
    
    # 注册依赖项
    app.dependency_overrides.update({
        RAGEngine: lambda: rag_engine,
        ModerationService: lambda: moderation
    })

    @app.post("/api/ask")
    def ask_question(query_request: QueryRequest):
        """问答接口"""
        try:
            logger.info(f"收到新问题: {query_request.question}")
            # 同步处理无需async上下文
            response = rag_engine.process_query(query_request.question, collection_name)
            return {"code": 0, "data": response}
        except TimeoutError as e:
            logger.error("请求处理超时")
            raise HTTPException(status_code=504, detail="处理超时")
        except Exception as e:
            logger.exception("处理请求时发生异常")
            return {"code": 500, "message": "服务内部错误"}

    @app.get("/health")
    def health_check():
        return {"status": "ok", "version": "2.0.0"}

    @app.get("/test")
    def test():
        return {"status": "ok"}

    return app

app = create_app()  # 创建app实例

if __name__ == "__main__":
    logger.info("启动API服务")
    uvicorn.run(app, host="0.0.0.0", port=8000) 