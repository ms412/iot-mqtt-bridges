# modbus2mqtt bridge image.
# Build from the repository root:
#   docker build -f docker/modbus2mqtt.Dockerfile -t modbus2mqtt .
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the shared library and this bridge package.
COPY common/ ./common/
COPY modbus2mqtt/ ./modbus2mqtt/

ENV PYTHONUNBUFFERED=1

# Config is mounted at runtime (see docker-compose.yml); the path can be
# overridden by passing a different config as the container command argument.
CMD ["python", "-m", "modbus2mqtt.main", "modbus2mqtt/config/modbus2mqtt_photovoltaic.yaml"]
