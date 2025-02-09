class JiraError(Exception):
    """Jira相关异常基类"""
    pass

class JiraGatewayError(JiraError):
    """网关错误异常"""
    pass

class JiraConnectionError(JiraError):
    """连接错误异常"""
    pass 