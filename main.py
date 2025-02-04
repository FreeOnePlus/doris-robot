import logging
import sys
import asyncio
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.data_loader.doris_loader import DorisLoader
from src.vectorstore.milvus_store import MilvusStore
from src.qa.rag_engine import RAGEngine
from settings import DORIS_DOCS_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def process_documents():
    """处理文档：加载、向量化和存储"""
    try:
        logger.info("初始化组件")
        doris_loader = DorisLoader(DORIS_DOCS_PATH)
        milvus_store = MilvusStore()
        rag_engine = RAGEngine()
        
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
        
        # 修改后的异步调用
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

def test_qa():
    """测试QA功能"""
    try:
        logger.info("初始化QA组件")
        rag_engine = RAGEngine()
        collection_name = "doris_docs"
        
        query = "如何优化Doris的查询性能？"
        logger.info(f"测试查询: {query}")
        
        response = rag_engine.process_query(query, collection_name)
        logger.info("查询完成")
        print(f"\n问题: {query}")
        print(f"回答: {response}")
        
    except Exception as e:
        logger.error(f"QA测试失败: {str(e)}")
        raise

def interactive_qa():
    """交互式问答"""
    rag_engine = RAGEngine()
    collection_name = "doris_docs"
    
    while True:
        query = input("\n请输入您的问题（输入q退出）: ")
        if query.lower() == 'q':
            break
        response = rag_engine.process_query(query, collection_name)
        print("\n" + response)

def start_api():
    """启动API服务"""
    from src.api.server import app
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

def main():
    if len(sys.argv) < 2:
        print("请指定操作: process | test | api")
        sys.exit(1)
        
    command = sys.argv[1]
    
    try:
        logger.info("程序启动")
        
        if command == "process":
            asyncio.run(process_documents())
        elif command == "test":
            test_qa()
        elif command == "api":
            start_api()
        else:
            print("无效命令")
            sys.exit(1)
            
        logger.info("程序运行完成")
        
    except Exception as e:
        logger.error(f"程序执行失败: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 