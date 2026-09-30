FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set container environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HEADLESS=true \
    KEEP_IDLE=false \
    SCREENSHOT_DIR=/app/screenshots

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and default configuration
COPY src/ ./src/
COPY main.py .
COPY config/ ./config/

# Ensure screenshots directory exists
RUN mkdir -p /app/screenshots

# Default command
ENTRYPOINT ["python", "main.py"]
