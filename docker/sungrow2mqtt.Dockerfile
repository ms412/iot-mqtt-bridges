# sungrow2mqtt bridge image.
# Build from the repository root:
#   docker build -f docker/sungrow2mqtt.Dockerfile -t sungrow2mqtt .
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY common/ ./common/
COPY sungrow2mqtt/ ./sungrow2mqtt/

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "sungrow2mqtt.main", "sungrow2mqtt/config/sungrow2mqtt.yaml"]
