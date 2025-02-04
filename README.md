# Doris智能问答机器人

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

基于RAG架构的Apache Doris知识库问答系统，提供智能文档检索和问答服务。

## 功能特性

- 🔍 多版本Doris文档向量检索
- 🤖 DeepSeek大模型问答生成
- 🛡️ 问题相关性审核机制
- 📊 Milvus向量数据库支持
- 🔌 支持多平台消息接入

## 项目结构

```bash
.
├── config/                 # 配置管理
│   └── settings.py         # 系统配置
│   └── config.json        # 服务配置
├── src/
│   ├── api/                # API服务模块
│   ├── data_loader/        # 数据加载器
│   ├── qa/                 # 问答处理引擎
│   ├── vectorstore/        # 向量数据库操作
│   ├── moderation/         # 内容审核模块
│   ├── plugin/             # 微信插件核心模块
│   │   └── handlers.py   # 消息处理器
│   └── clients/           # 第三方服务客户端
│   └── llm_client.py      # 大模型客户端管理
├── tests/                  # 单元测试
├── main.py                 # 主程序入口
└── requirements.txt        # 依赖清单
```

## 快速开始

### 环境要求

- Python 3.11
- Milvus 2.3.4
- Redis（可选，用于缓存）

### 安装依赖

```bash
pip install -r requirements.txt
# 安装微信插件依赖
pip install fop-wechat>=1.2.0
```

### 配置说明

1. 复制配置文件模板：
```bash
cp config/config.json.template config/config.json
```

2. 修改`config.json`：
```json
{
  "model_config": {
    "services": {
      "chat": {
        "provider": "deepseek",
        "model": "deepseek-chat"
      }
    },
    "providers": {
      "deepseek": {
        "api_key": "your_api_key",
        "endpoint": "https://api.deepseek.com/v1"
      }
    }
  }
}
```

### 运行模式

# API服务模式
python main.py api --port 8000

# 微信插件模式（通过fop-wechat启动）
fop_wechat --config plugins/doris_robot/config.json

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

## 开发指南

### 代码规范
- 使用Google风格Python文档字符串
- 重要函数添加类型注解
- 模块间通过接口解耦

### 测试流程
```bash
# 运行单元测试
pytest tests/

# 代码覆盖率检查
pytest --cov=src tests/
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

`plugins/doris_robot/config.json` 示例：
```json
{
  "plugin_name": "Doris助手",
  "command_prefix": "/doris",
  "api_endpoint": "http://localhost:8000/api/ask"
}
``` 