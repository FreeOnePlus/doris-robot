from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class JiraAttachment(BaseModel):
    filename: str
    url: str
    content_type: str
    content: Optional[str] = None
    is_image: bool

class JiraComment(BaseModel):
    author: str
    created: datetime
    body: str

class JiraIssue(BaseModel):
    key: str
    summary: str
    description: str
    status: str
    versions: List[str]
    assignee: str
    created: datetime
    updated: datetime
    comments: List[JiraComment]
    attachments: List[JiraAttachment]
    priority: str
    issue_type: str
    labels: List[str] 