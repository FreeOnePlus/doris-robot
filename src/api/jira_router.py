from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from src.data_loader.jira_loader import JiraLoader
from src.vectorstore.milvus_store import MilvusStore
from settings import config
from src.qa.rag_engine import RAGEngine
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

router = APIRouter()

class RefreshRequest(BaseModel):
    full_refresh: bool = False

security = HTTPBearer()

@router.post("/jira/refresh")
async def refresh_jira_data(
    req: RefreshRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    # 验证访问令牌
    if credentials.credentials != config.jira.api_token:
        raise HTTPException(status_code=403, detail="无访问权限")
    
    loader = JiraLoader(config)
    milvus = MilvusStore()
    
    if req.full_refresh:
        milvus.create_jira_collection()
    
    count = 0
    for doc in loader.load_documents(req.full_refresh):
        milvus.insert("jira_issues", doc)
        count += 1
    
    return {"status": "success", "inserted": count}

@router.post("/jira/refresh/incremental")
async def incremental_refresh(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """增量刷新Jira数据"""
    if credentials.credentials != config.jira.api_token:
        raise HTTPException(status_code=403, detail="无访问权限")
    
    loader = JiraLoader(config)
    milvus = MilvusStore()
    
    count = 0
    for doc in loader.load_documents(full_refresh=False):
        # 使用upsert操作更新现有数据
        milvus.upsert("jira_issues", doc)
        count += 1
    
    return {"status": "success", "updated": count}

@router.get("/jira/search")
async def search_jira(
    query: str,
    rag: RAGEngine = Depends(),
    limit: int = 5
):
    try:
        # 生成查询向量
        query_vector = rag.get_embedding(query)
        
        # 执行Jira专用搜索
        results = rag.milvus_store.search_jira(query_vector, limit)
        
        # 格式化结果
        return {
            "code": 0,
            "data": [{
                "issue_key": res["id"],
                "score": res["score"],
                "summary": res["metadata"].get("summary", ""),
                "status": res["metadata"].get("status", ""),
                "url": f"{config.jira.base_url}/browse/{res['id']}"
            } for res in results]
        }
    except Exception as e:
        logging.error(f"Jira搜索失败: {str(e)}")
        raise HTTPException(status_code=500, detail="搜索失败") 