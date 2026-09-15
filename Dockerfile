FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY competepulse/ ./competepulse/
COPY main.py server.py targets.example.json ./

# Reports and dead-lettered deliveries are written here
RUN mkdir -p reports failed_deliveries

ENV PORT=8080
EXPOSE 8080

CMD ["python", "server.py"]
