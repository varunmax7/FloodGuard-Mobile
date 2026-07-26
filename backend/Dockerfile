# ──────────────────────────────────────────────────────────────────────────────
# FloodGuard Backend — Dockerfile
# Python 3.12 slim + GDAL system libraries for GeoDjango/PostGIS
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm

LABEL maintainer="FloodGuard Solutions Pvt. Ltd."
LABEL description="FloodGuard Django backend with GeoDjango/PostGIS support"

# ── System deps ───────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # GDAL for GeoDjango
    gdal-bin \
    libgdal-dev \
    # PostgreSQL client
    libpq-dev \
    # GEOS + PROJ (PostGIS geometry)
    libgeos-dev \
    libproj-dev \
    # eccodes for ECMWF GRIB files
    libeccodes-dev \
    # Build tools
    build-essential \
    # curl for healthcheck
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── GDAL env for GeoDjango (architecture-agnostic symlinks) ──────────────────
RUN LIBDIR=$(find /usr/lib -maxdepth 1 -type d -name "*-linux-gnu" | head -1) && \
    ln -sf $(ls ${LIBDIR}/libgdal.so* | head -1) /usr/local/lib/libgdal.so && \
    ln -sf $(ls ${LIBDIR}/libgeos_c.so* | head -1) /usr/local/lib/libgeos_c.so.1 && \
    ldconfig
ENV GDAL_LIBRARY_PATH=/usr/local/lib/libgdal.so
ENV GEOS_LIBRARY_PATH=/usr/local/lib/libgeos_c.so.1
ENV PROJ_LIB=/usr/share/proj

# ── Python setup ──────────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ── Install Python dependencies ───────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Copy application source ───────────────────────────────────────────────────
COPY . .

# ── Default port ──────────────────────────────────────────────────────────────
EXPOSE 8000

# ── Default command (overridden in docker-compose) ────────────────────────────
CMD ["gunicorn", "floodguard.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
