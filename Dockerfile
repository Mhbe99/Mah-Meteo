FROM python:3.11.9-slim

WORKDIR /app

# Install system dependencies
# Cache bust: 2026-04-09-postgresql
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
# Cache bust: 2026-04-01 (force Render to not use Docker cache)
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose port
EXPOSE 8080

# Run command
CMD ["uvicorn", "meteo_saas.backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
