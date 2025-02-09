# Doris智能问答机器人

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

基于RAG架构的Apache Doris知识库问答系统，提供智能文档检索和问答服务。

## 功能特性

- 🔍 多版本Doris文档向量检索
- 🤖 DeepSeek大模型问答生成
- 🛡️ 问题相关性审核机制
- 📊 Milvus向量数据库支持
- 🔌 支持微信插件接入

## 项目结构

```project_structure.txt
project_root/
├── config/                 # 配置管理
│   ├── settings.py         # 系统级配置
│   └── config.json        # 服务连接配置
├── src/
│   ├── api/                # API服务模块
│   ├── data_loader/        # 数据加载器
│   ├── qa/                 # 问答处理引擎
│   ├── vectorstore/        # 向量数据库操作
│   ├── plugin/             # 插件核心模块
│   └── utils/              # 工具类
├── plugins/                # 插件实现
├── tests/                  # 单元测试
└── main.py                 # 主程序入口
```

## 快速开始

### 环境要求
- Python 3.11+
- Milvus 2.3.x
- Redis 6.2+（可选缓存）

### 安装依赖
```bash
pip install -r requirements.txt
```

### 配置说明
1. 初始化配置文件：
```bash
cp config/config.json.template config/config.json
```

2. 修改核心配置：
```json
{
  "milvus": {
    "host": "localhost",
    "port": 19530
  },
  "deepseek": {
    "api_key": "your_api_key",
    "endpoint": "https://api.deepseek.com/v1"
  }
}
```

## 运行模式

### API服务模式
```bash
python main.py api --port 8000
```

### 微信插件模式
```bash
fop_wechat --config plugins/wechat/config.json
```

## 核心模块说明

### 数据加载（data_loader）
```python
# src/data_loader/doris_loader.py
class DorisLoader:
    def load_documents(self, version: str):
        """加载指定版本的Doris文档"""
        # 实现文档解析逻辑
```

### 问答引擎（qa/rag_engine.py）
```python
class RAGEngine:
    def generate_answer(self, question: str):
        """实现RAG问答流程"""
        # 1. 向量检索 2. 结果审核 3. 生成回答
```

## 开发指南
1. 新增数据加载器需实现统一接口
2. 插件消息处理函数需注册到adapter
3. 使用统一日志接口：
```python
from utils.logger import get_logger
logger = get_logger(__name__)
logger.info("Document processed")
```

## API文档

### 问答接口（POST）
```http
POST /api/v1/ask
Content-Type: application/json

{
  "question": "如何创建Doris表？"
}
```

**示例请求**：
```bash
curl -X POST "http://localhost:8000/api/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "如何创建Doris表？"}'
```

**成功响应**：
```json
{
  "code": 0,
  "data": {
    "answer": "创建Doris表的步骤如下...",
    "references": [
      {
        "version": "3.0",
        "title": "数据表设计",
        "url": "/zh-CN/docs/3.0/data-table-design"
      }
    ]
  }
}
```

### 健康检查
```http
GET /health
```

## 生产部署

### 使用Gunicorn
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker src.api.server:app
```

### Nginx配置示例
```nginx
location /doris-api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## 常见问题

### 如何处理文档更新？
1. 更新本地文档仓库
2. 重新运行处理命令：
```bash
python main.py process
```

### 如何调整审核严格度？
修改`config/settings.py`：
```python
MODERATION_CONFIG = {
    "enable_keyword": True,    # 启用关键词过滤
    "enable_model_check": True,# 启用模型审核
    "fallback_strategy": "allow" # 审核失败时默认允许
}
```

## 授权许可
本项目基于 [Apache License 2.0](LICENSE) 授权。

## 监控指标
| 指标名称          | 类型    | 描述                  |
|-------------------|---------|---------------------|
| query_count       | Counter | 总查询次数            |
| plugin_usage      | Gauge   | 插件使用率            |
| response_time     | Summary | 响应时间分布          |

## 微信插件配置

`plugins/wechat/config.json` 示例：
```json
{
  "plugin_name": "Doris助手",
  "command_prefix": "/doris",
  "api_endpoint": "http://localhost:8000/api/ask"
}
``` 