import logging
from typing import List
from .base_loader import BaseLoader
from ..clients.jira_client import JiraClient
from ..utils.file_parser import download_file, extract_text
from tenacity import retry, stop_after_attempt, wait_exponential
import re
from datetime import datetime
from ..exceptions.jira_exceptions import JiraGatewayError, JiraConnectionError

logger = logging.getLogger(__name__)

class JiraLoader(BaseLoader):
    def __init__(self, config: dict):
        self.client = JiraClient(
            base_url=config['jira']['base_url'],
            auth_token=config['jira']['auth_token']
        )
        self.data_path = config['data_paths']['jira_data']
        self.max_retries = 3

    def process_document(self, document) -> dict:
        """实现基类要求的文档处理方法"""
        return self._process_issue(document)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def load_documents(self, full_refresh: bool = False):
        """加载Jira数据"""
        try:
            # 使用新的filter_id参数
            filter_id = config.jira.filter_id
            for issue in self.client.get_issues(filter_id):
                try:
                    doc = self._process_issue(issue)
                    yield doc
                except Exception as e:
                    logger.error(f"处理问题 {issue.key} 失败: {str(e)}")
        except JiraGatewayError as e:
            logger.error(f"Jira服务暂时不可用: {str(e)}")
            raise
        except JiraConnectionError as e:
            logger.error(f"无法连接Jira服务器: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"未知错误: {str(e)}")
            raise

    def _process_issue(self, issue) -> dict:
        """处理单个Jira问题"""
        try:
            # 构建文档内容
            content = f"问题: {issue.summary}\n状态: {issue.status}\n版本: {','.join(issue.versions)}"
            content += f"\n描述: {issue.description}\n负责人: {issue.assignee}"
            
            # 处理评论
            if issue.comments:
                content += "\n\n评论:\n" + "\n".join(
                    f"{c.author} ({c.created}): {c.body}" 
                    for c in issue.comments
                )
            
            # 处理附件
            attachment_texts = []
            for att in issue.attachments:
                if att.is_image:
                    attachment_texts.append(f"图片附件: {att.url}")
                else:
                    attachment_texts.append(f"附件 {att.filename}:\n{att.content}")
            
            if attachment_texts:
                content += "\n\n附件内容:\n" + "\n\n".join(attachment_texts)
            
            return {
                "id": issue.key,
                "text": content,
                "metadata": {
                    "type": "jira_issue",
                    "status": issue.status,
                    "versions": issue.versions,
                    "assignee": issue.assignee,
                    "created": issue.created.isoformat(),
                    "updated": issue.updated.isoformat()
                }
            }
        except Exception as e:
            logger.error(f"处理问题 {issue.key} 失败: {str(e)}")
            return None  # 返回空值由上层处理 

    def _clean_content(self, text: str) -> str:
        """数据清洗处理"""
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        # 标准化空白字符
        text = re.sub(r'\s+', ' ', text)
        # 过滤敏感信息
        sensitive_patterns = [
            r'\b\d{4}-\d{4}-\d{4}-\d{4}\b',  # 信用卡号
            r'\b\d{3}-\d{2}-\d{4}\b'         # 社保号
        ]
        for pattern in sensitive_patterns:
            text = re.sub(pattern, '[REDACTED]', text)
        return text.strip() 

    def _get_last_sync_time(self) -> str:
        """获取上次同步时间"""
        try:
            with open(f"{self.data_path}/last_sync.txt", "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            return "1970-01-01 00:00:00"

    def _save_sync_time(self):
        """保存本次同步时间"""
        with open(f"{self.data_path}/last_sync.txt", "w") as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S")) 