FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pytest==8.4.2 mpmath==1.3.0 urllib3==2.5.0 charset-normalizer==3.4.3 idna==3.10 certifi==2025.8.3
WORKDIR /repo
