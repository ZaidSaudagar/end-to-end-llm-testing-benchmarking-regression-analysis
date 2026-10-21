FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/models/huggingface

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home-dir /home/app app \
    && mkdir -p /data /models/huggingface \
    && chown -R app:app /data /models /home/app

COPY pyproject.toml README.md ./
COPY backend ./backend
COPY dashboard ./dashboard
COPY datasets ./datasets

RUN python -m pip install --no-cache-dir .

USER app

EXPOSE 8000 8501
