FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gdal-bin \
        libgdal-dev \
        libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

COPY assets/backend/requirements.txt /app/assets/backend/requirements.txt
COPY assets/wildcat /app/assets/wildcat

WORKDIR /app/assets/backend
RUN pip install -r requirements.txt

WORKDIR /app
COPY assets/backend /app/assets/backend
COPY assets/asbpa_data /app/assets/asbpa_data

WORKDIR /app/assets/backend
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
