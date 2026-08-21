# backend/Dockerfile
FROM python:3.11-slim

# Setze Arbeitsverzeichnis
WORKDIR /app

# Kopiere requirements zuerst (für besseren Cache)
COPY requirements.txt .

# Zeige requirements Inhalt (Debug)
RUN echo "=== requirements.txt ===" && cat requirements.txt

# Installiere Abhängigkeiten mit verbose output
RUN pip install --no-cache-dir -v -r requirements.txt

# Kopiere den Rest des Codes
COPY . .

# Erstelle Firmware Verzeichnis
RUN mkdir -p /app/firmware

# Expose Port
EXPOSE 5000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:5000/api/health')" || exit 1

# Starte die Applikation
CMD ["python", "-u", "app.py"]