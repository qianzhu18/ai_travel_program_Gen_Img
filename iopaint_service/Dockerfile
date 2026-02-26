FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖（IOPaint 需要 OpenCV 相关库）
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8090

CMD ["python", "-m", "iopaint", "start", "--model=lama", "--device=cpu", "--port=8090"]
