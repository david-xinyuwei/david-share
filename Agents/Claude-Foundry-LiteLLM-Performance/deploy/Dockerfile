FROM ghcr.io/berriai/litellm:v1.106.2@sha256:7294b90f868c5c38c99b83021c7ba46f9b439e95f8e32964c925c7d2563a03f7
WORKDIR /app/claude-gateway
COPY config.yaml trace_hook.py ./
ENV PYTHONPATH=/app/claude-gateway
ENV PYTHONUNBUFFERED=1
RUN python -c "import azure.identity, httpx, yaml; from importlib.metadata import version; assert version('litellm') == '1.106.2'; yaml.safe_load(open('config.yaml'))"
ENTRYPOINT ["litellm"]
CMD ["--config", "/app/claude-gateway/config.yaml", "--host", "0.0.0.0", "--port", "4000", "--num_workers", "1"]
