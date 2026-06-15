FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（部分 Python 包可能需要编译）
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码与 prompt 模板
COPY app/ ./app/
COPY prompts/ ./prompts/

# 创建非 root 用户运行应用（安全最佳实践）
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
