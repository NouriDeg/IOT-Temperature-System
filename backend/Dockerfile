# ============================================================================
# BACKEND DOCKERFILE - PRODUKTION & TESTS
# ============================================================================
# 
# Version: 2.0
# Datum: 07.05.2026
# 
# Multi-Stage Build:
# - Stage 1: Builder (nur für Abhängigkeiten)
# - Stage 2: Production (schlankes Image)
# ============================================================================

# ----------------------------------------------------------------------------
# STAGE 1: BUILDER (Abhängigkeiten installieren)
# ----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# Installiere Build-Abhängigkeiten (falls nötig für psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Kopiere requirements und installiere Abhängigkeiten
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ----------------------------------------------------------------------------
# STAGE 2: PRODUCTION (schlankes Image)
# ----------------------------------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

# Installiere Runtime-Abhängigkeiten (nur libpq für psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Kopiere installierte Pakete vom Builder
COPY --from=builder /root/.local /root/.local

# Stelle sicher, dass die Pakete im PATH sind
ENV PATH=/root/.local/bin:$PATH

# Kopiere Anwendungscode
COPY . .

# Erstelle notwendige Verzeichnisse
RUN mkdir -p /app/firmware /app/logs && \
    chmod 755 /app/firmware

# Erstelle einen nicht-root Benutzer für Sicherheit
RUN addgroup --system app && \
    adduser --system --group app && \
    chown -R app:app /app

# Wechsle zu nicht-root Benutzer
USER app

# Expose Port
EXPOSE 5000

# Healthcheck (mit curl für bessere Kompatibilität)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:5000/api/health || exit 1

# Starte die Applikation
CMD ["python", "-u", "app.py"]