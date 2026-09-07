# mbus2mqtt bridge image.
# Build from the repository root:
#   docker build -f docker/mbus2mqtt.Dockerfile -t mbus2mqtt .
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY common/ ./common/
COPY mbus2mqtt/ ./mbus2mqtt/

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "mbus2mqtt.main", "mbus2mqtt/config/mbus2mqtt.yaml"]
