# so2mqtt bridge image.
# Build from the repository root:
#   docker build -f docker/so2mqtt.Dockerfile -t so2mqtt .
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY common/ ./common/
COPY so2mqtt/ ./so2mqtt/

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "so2mqtt.main", "so2mqtt/config/so2mqtt.yaml"]
