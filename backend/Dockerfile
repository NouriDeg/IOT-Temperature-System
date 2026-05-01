# ============================================================================
# DOCKERFILE FÜR BACKEND API - PRODUKTIONS-OPTIMIERT (Multi-Stage)
# ============================================================================

# ----------------------------------------------------------------------------
# STAGE 1: BUILDER (für Abhängigkeiten)
# ----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

# ----------------------------------------------------------------------------
# METADATA (Label für Dokumentation)
# ----------------------------------------------------------------------------
LABEL maintainer="IoT Temperature Monitoring System"
LABEL description="Backend REST API für Temperaturdaten"
LABEL version="3.0"
# ----------------------------------------------------------------------------
# ARBEITSVERZEICHNIS
# ----------------------------------------------------------------------------
# Wechselt in das Verzeichnis /app im Container
# Alle folgenden Befehle werden relativ zu diesem Pfad ausgeführt
WORKDIR /app

# ----------------------------------------------------------------------------
# ABHÄNGIGKEITEN INSTALLIEREN
# ----------------------------------------------------------------------------
# Zuerst nur die requirements.txt kopieren (optimiertes Caching)
# Docker cached diesen Layer solange sich requirements.txt nicht ändert
# Das spart Zeit bei Neubuilds, weil pip install nicht wiederholt wird
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ----------------------------------------------------------------------------
# STAGE 2: RUNTIME (schmales Produktions-Image)
# ----------------------------------------------------------------------------
FROM python:3.11-slim

# Nur ausführen als nicht-root Benutzer (Sicherheit!)
RUN addgroup --system app && adduser --system --group app

WORKDIR /app

# Python Pfad für --user Installation setzen
ENV PATH="/root/.local/bin:$PATH"

# Abhängigkeiten aus Builder kopieren
COPY --from=builder /root/.local /root/.local

# ============================================================================
# ANWENDUNGSCODE KOPIEREN
# ============================================================================
# Kopiere alle Dateien aus dem Host (aktuelles Verzeichnis) nach /app im Container
# Docker ignoriert dabei Dateien aus .dockerignore (falls vorhanden)
COPY . .

# ----------------------------------------------------------------------------
# FIRMWARE VERZEICHNIS ERSTELLEN
# ----------------------------------------------------------------------------
# Erstelle ein Verzeichnis für OTA Firmware Uploads
# Existiert bereits auf dem Host, aber muss auch im Container existieren
# mkdir -p: Erstellt Elternverzeichnisse falls nötig (kein Fehler wenn bereits vorhanden)
# Firmware Verzeichnis erstellen
RUN mkdir -p /app/firmware && chown -R app:app /app

# Zu nicht-root Benutzer wechseln (Sicherheit!)
USER app

# ----------------------------------------------------------------------------
# PORT EXPOSIEREN
# ----------------------------------------------------------------------------
# Dokumentiert dass der Container auf Port 5000 lauscht (Flask Standard)
# Wichtig: Nur Dokumentation - das eigentliche Port-Mapping erfolgt in docker-compose.yml
EXPOSE 5000

# Gesundheitscheck für Docker
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:5000/api/health || exit 1

# ----------------------------------------------------------------------------
# STARTKOMMANDO
# ----------------------------------------------------------------------------
# Ausführungs-Befehl wenn der Container startet
# ["python", "-u", "app.py"]:
#   -u: Unbuffered Mode (sofortige Log-Ausgabe, wichtig für Docker Logs)
#   app.py: Hauptanwendungsdatei (Flask API)
# 
# Alternative: CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
# Aber mit python -u app.py haben wir mehr Kontrolle  
CMD ["python", "-u", "app.py"]