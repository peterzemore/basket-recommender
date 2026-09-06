FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 RECSYS_ROOT=/app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --quiet ".[serve]"
# The public snapshot and the validated configuration are part of the image:
# the container needs no credentials to serve; credentials only add live stock.
COPY data/public ./data/public
COPY results/serving_config.json results/test.json ./results/
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"
CMD ["uvicorn", "recsys.serve:app", "--host", "0.0.0.0", "--port", "8000"]
