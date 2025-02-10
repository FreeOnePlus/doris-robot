# 构建阶段
FROM python:3.11.11-slim

COPY  resource/doris-robot /app

# 安装运行时依赖
RUN pip install --user --no-cache-dir -r /app/requirements.txt && \
    pip cache purge

# 设置环境变量
ENV APP_HOME=/app

WORKDIR $APP_HOME

# 服务端口
EXPOSE 8000

# 复制Entrypoint脚本
COPY resource/entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# 设置入口点
ENTRYPOINT ["/app/entrypoint.sh"]