import logging
import requests
from typing import Iterator
from src.clients.jira_schema import JiraIssue, JiraComment, JiraAttachment
from datetime import datetime
import pytz
from PIL import Image
import pytesseract
import io
from bs4 import BeautifulSoup
import json

logger = logging.getLogger(__name__)

class JiraClient:
    def __init__(self, base_url: str, auth_token: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Authorization': f'Basic {auth_token}',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7'
        }
        self.timeout = 30

    def _fetch_issues_html(self, filter_id: str, start: int = 0) -> str:
        """获取问题列表HTML"""
        url = f"{self.base_url}/secure/IssueNavigator.jspa"
        params = {
            'reset': 'true',
            'jqlQuery': f'project = CIR ORDER BY updated DESC',
            'filterId': filter_id,
            'startIndex': start
        }
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"获取问题列表失败: {str(e)}")
            raise

    def _extract_issues_data(self, html: str) -> dict:
        """从HTML中提取问题数据"""
        soup = BeautifulSoup(html, 'html.parser')
        script_tag = soup.find('script', {'id': 'issue-table-model-state'})
        
        if not script_tag:
            raise ValueError("未找到问题数据")
            
        json_str = script_tag.string
        json_str = json_str.replace('&quot;', '"')
        return json.loads(json_str)

    def get_issues(self, filter_id: str = "10813") -> Iterator[JiraIssue]:
        """获取问题列表（分页处理）"""
        start = 0
        page_size = 50  # 每页数量
        
        while True:
            html = self._fetch_issues_html(filter_id, start)
            data = self._extract_issues_data(html)
            
            # 解析问题数据
            for issue in data.get('issues', []):
                yield self._parse_issue(issue)
                
            # 判断是否还有更多数据
            if start + page_size >= data.get('total', 0):
                break
                
            start += page_size

    def _parse_issue(self, raw_issue: dict) -> JiraIssue:
        fields = raw_issue['fields']
        
        # 解析自定义字段
        custom_fields = {
            'environment': fields.get('customfield_12345'),  # 示例自定义字段
            'severity': fields.get('customfield_67890')
        }
        
        issue = JiraIssue(
            key=raw_issue['key'],
            summary=fields.get('summary', ''),
            description=fields.get('description', ''),
            status=fields.get('status', {}).get('name', ''),
            versions=[v['name'] for v in fields.get('versions', [])],
            assignee=fields.get('assignee', {}).get('displayName', ''),
            created=self._parse_datetime(fields['created']),
            updated=self._parse_datetime(fields['updated']),
            comments=self._parse_comments(fields.get('comment', {}).get('comments', [])),
            attachments=self._parse_attachments(fields.get('attachment', [])),
            priority=fields.get('priority', {}).get('name', ''),
            issue_type=fields.get('issuetype', {}).get('name', ''),
            labels=fields.get('labels', []),
            environment=custom_fields['environment'],
            severity=custom_fields['severity'],
            resolution=fields.get('resolution', {}).get('name', 'Unresolved')
        )
        return issue

    def _parse_datetime(self, dt_str: str) -> datetime:
        return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(pytz.UTC)

    def _parse_comments(self, raw_comments: list) -> list[JiraComment]:
        return [
            JiraComment(
                author=comment['author']['displayName'],
                created=self._parse_datetime(comment['created']),
                body=comment['body']
            )
            for comment in raw_comments
        ]

    def _parse_attachments(self, raw_attachments: list) -> list[JiraAttachment]:
        attachments = []
        for att in raw_attachments:
            try:
                content = self._download_attachment(att['content'])
                is_image = att['mimeType'].startswith('image/')
                
                attachments.append(JiraAttachment(
                    filename=att['filename'],
                    url=att['content'],
                    content_type=att['mimeType'],
                    content=content if not is_image else self._ocr_image(content),
                    is_image=is_image
                ))
            except Exception as e:
                logger.error(f"处理附件失败: {att['filename']} - {str(e)}")
        return attachments

    def _download_attachment(self, url: str) -> bytes:
        response = requests.get(
            url,
            headers=self.headers,
            timeout=30
        )
        response.raise_for_status()
        return response.content

    def _ocr_image(self, image_data: bytes) -> str:
        try:
            image = Image.open(io.BytesIO(image_data))
            text = pytesseract.image_to_string(image, lang='chi_sim+eng')
            return text.strip()
        except Exception as e:
            logger.error(f"OCR处理失败: {str(e)}")
            return "" 