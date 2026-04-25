# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_SYSTEM_PYTHON=1

# uv 安裝
RUN pip install --no-cache-dir uv==0.11.2

WORKDIR /app

# HF Space 的容器使用 uid 1000，需要可寫入工作目錄
RUN useradd -m -u 1000 user && chown -R user:user /app
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# 先複製依賴清單以利快取
COPY --chown=user:user pyproject.toml README.md ./
RUN uv sync --no-dev

# 再複製程式
COPY --chown=user:user app/ ./app/

# HF Space 預設端口為 7860
EXPOSE 7860

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
