from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from src.data_loader.doris_loader import DorisLoader
from src.qa.rag_engine import RAGEngine
from src.data_loader.jira_loader import JiraLoader
from src.vectorstore.milvus_store import MilvusStore
import logging
import uvicorn
import logging.handlers
from src.moderation import ModerationService
from settings import config
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)

class DocProcessRequest(BaseModel):
    content: str = Field(..., min_length=10, description="需要处理的文档内容")

class JiraProcessRequest(BaseModel):
    full_refresh: bool = Field(False, description="是否全量刷新")

def create_app():
    app = FastAPI(title="Doris智能问答API")
    
    # 统一日志配置（确保所有模块使用相同配置）
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(process)d] %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    # 禁用uvicorn的访问日志（避免干扰）
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.propagate = False
    
    # 直接初始化RAG引擎实例
    rag_engine = RAGEngine()
    collection_name = config.doc_collection_name

    # 独立初始化审核服务（使用配置）
    moderation = ModerationService()
    
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

    @app.get("/api/process/doc")
    async def process_document(background_tasks: BackgroundTasks):
        """复用现有文档处理流程"""
        def process_task():
            # 继承主线程日志配置
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - [%(process)d] %(name)s - %(levelname)s - %(message)s',
                handlers=[logging.StreamHandler()]
            )
            
            loader = DorisLoader(config.doris_docs_path)
            
            def progress_callback(current, total):
                logger.info(f"处理进度: {current}/{total} ({current/total:.1%})")
            
            try:
                processed_count = loader.full_process(progress_callback)
                logger.info(f"文档处理完成，共处理 {processed_count} 个文档")
            except Exception as e:
                logger.error(f"文档处理失败: {str(e)}")
                raise
            
            return {"processed": processed_count}
        
        background_tasks.add_task(process_task)
        return {"message": "文档处理已开始"}

    @app.get("/api/process/jira")
    def process_jira_data(full_refresh: bool = False):
        """处理Jira数据"""
        try:
            logger.info(f"收到Jira处理请求，全量模式: {full_refresh}")
            loader = JiraLoader(config)
            milvus = MilvusStore()
            
            if full_refresh:
                milvus.create_jira_collection()
                
            count = 0
            for doc in loader.load_documents(full_refresh=full_refresh):
                milvus.insert("jira_issues", doc)
                count += 1
                
            return {"code": 0, "processed": count}
        except Exception as e:
            logger.error(f"Jira数据处理失败: {str(e)}")
            return {"code": 500, "message": "Jira数据处理失败"}

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    @app.get("/test")
    def test():
        return {"status": "ok"}

    return app

app = create_app()  # 创建app实例

if __name__ == "__main__":
    logger.info("启动API服务")
    uvicorn.run(app, host="0.0.0.0", port=8000) 