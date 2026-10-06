FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    PYTHONPATH=/workspace/src:/workspace/config

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 bash \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["bash", "scripts/run_experiments.sh", "validate"]
