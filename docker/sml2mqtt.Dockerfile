# sml2mqtt bridge image.
# Build from the repository root:
#   docker build -f docker/sml2mqtt.Dockerfile -t sml2mqtt .
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY common/ ./common/
COPY sml2mqtt/ ./sml2mqtt/

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "sml2mqtt.main", "sml2mqtt/config/sml2mqtt.yaml"]
