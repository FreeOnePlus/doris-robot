import pytest
from unittest.mock import Mock, patch
from src.clients.jira_client import JiraClient

@pytest.fixture
def mock_jira_response():
    return {
        "issues": [{
            "key": "CIR-123",
            "fields": {
                "summary": "Test Issue",
                # ...其他字段模拟数据...
            }
        }]
    }

def test_parse_issue(mock_jira_response):
    client = JiraClient("http://test.com", "token")
    parsed = client._parse_issue(mock_jira_response['issues'][0])
    assert parsed.key == "CIR-123"
    assert "Test Issue" in parsed.summary 