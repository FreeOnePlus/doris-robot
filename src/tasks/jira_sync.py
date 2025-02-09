import schedule
import logging
import time
from data_loader import JiraLoader
from settings import config
from src.api.jira_router import RefreshRequest, incremental_refresh, refresh_jira_data
from src.vectorstore.milvus_store import MilvusStore

def start_sync_job():
    def job():
        try:
            loader = JiraLoader(config)
            milvus = MilvusStore()
            
            logging.info("开始增量同步Jira数据")
            count = 0
            for doc in loader.load_documents(full_refresh=False):
                milvus.insert("jira_issues", doc)
                count += 1
            logging.info(f"增量同步完成，更新{count}条数据")
            
        except Exception as e:
            logging.error(f"定时任务执行失败: {str(e)}")
    
    # 每小时执行增量同步
    schedule.every(config.jira.poll_interval).seconds.do(
        lambda: incremental_refresh()
    )
    
    # 每周日凌晨执行全量同步
    schedule.every().sunday.at("02:00").do(
        lambda: refresh_jira_data(RefreshRequest(full_refresh=True))
    )
    
    while True:
        schedule.run_pending()
        time.sleep(1) 