#!/bin/bash

# 设置默认值
export MILVUS_HOST=${MILVUS_HOST:-127.0.0.1}
export MILVUS_PORT=${MILVUS_PORT:-19530}
export DORIS_COLLECTION_NAME=${DORIS_COLLECTION_NAME:-doris_docs}

# 检查必需变量
required_vars=(
  SILICONFLOW_API_KEY
)

for var in "${required_vars[@]}"; do
  if [ -z "${!var}" ]; then
    echo "错误：必须设置 $var 环境变量"
    exit 1
  fi
done

# 替换配置文件
CONFIG_FILE="/app/config.json"

# 安全替换函数
safe_replace() {
  local key=$1
  local value=${!key}
  # 转义特殊字符
  value=$(printf '%s\n' "$value" | sed -e 's/[\/&]/\\&/g')
  sed -i "s/\${$key}/$value/g" "$CONFIG_FILE"
}

# 执行替换
replace_keys=(
  MILVUS_HOST
  MILVUS_PORT
  DORIS_COLLECTION_NAME
  DEEPSEEK_API_KEY
  SILICONFLOW_API_KEY
)

for key in "${replace_keys[@]}"; do
  safe_replace "$key"
  echo "$key : ${!key}"
done

# 启动服务
exec python main.py api