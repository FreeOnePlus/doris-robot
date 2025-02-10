from fastapi import FastAPI, HTTPException, Request
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

logger = logging.getLogger(__name__)

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)

class DocProcessRequest(BaseModel):
    content: str = Field(..., min_length=10, description="需要处理的文档内容")

class JiraProcessRequest(BaseModel):
    full_refresh: bool = Field(False, description="是否全量刷新")

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
    async def process_document(content: str):
        """处理文档：加载、向量化和存储"""
        try:
            logger.info("初始化组件")
            doris_loader = DorisLoader(config.doris_docs_path)
            milvus_store = MilvusStore()
            # 加载文档
            logger.info("开始加载文档")
            documents = doris_loader.load_documents()
            if not documents:
                raise ValueError("没有加载到任何文档")
            logger.info(f"文档加载完成，共 {len(documents)} 个文档块")
            
            # 创建collection
            collection_name = "doris_docs"
            logger.info(f"创建集合: {collection_name}")
            milvus_store.create_collection(collection_name)
            
            # 处理并存储文档
            logger.info("开始处理文档向量化")
            texts = [doc["content"] for doc in documents]
            
            # 异步调用（保持await但使用依赖注入的实例）
            await rag_engine.batch_get_embeddings(
                texts=texts,
                documents=documents,
                collection_name=collection_name,
                batch_size=50,
                concurrency=10
            )
            
            logger.info("文档处理完成")
            
        except Exception as e:
            logger.error(f"文档处理失败: {str(e)}")
            raise

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
        return {"status": "ok", "version": "2.0.0"}

    @app.get("/test")
    def test():
        return {"status": "ok"}

    return app

app = create_app()  # 创建app实例

if __name__ == "__main__":
    logger.info("启动API服务")
    uvicorn.run(app, host="0.0.0.0", port=8000) 