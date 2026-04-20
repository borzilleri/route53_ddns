FROM python:3.13-slim

WORKDIR /app

ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    CONFIG_FILE=/config.yaml

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn route53_ddns.main:create_app --factory --host \"${HOST:-0.0.0.0}\" --port \"${PORT:-8080}\""]
