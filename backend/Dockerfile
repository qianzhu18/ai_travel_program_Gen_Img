FROM python:3.10-slim

WORKDIR /app

# 系统依赖（libglib2.0-0 是 opencv-headless 运行时需要的）
RUN apt-get update && \
    apt-get install -y --no-install-recommends libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# 非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

# 先装依赖，利用 Docker 层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 数据 & 模型目录（运行时通过 volume 挂载）
RUN mkdir -p /app/data /app/models && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
