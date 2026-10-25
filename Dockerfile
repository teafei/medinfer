FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements.lock
COPY pyproject.toml README.md ./
COPY medinfer ./medinfer
RUN pip install --no-cache-dir --no-deps . && useradd --create-home --uid 10001 medinfer \
    && mkdir -p /app/results && chown -R medinfer:medinfer /app/results
USER medinfer
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=3s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["medinfer", "serve", "--host", "0.0.0.0", "--port", "8000"]
