#!/usr/bin/env python
"""
================================================================================
WSS (WebSocket Secure) MQTT Client - MIT Zertifikatsprüfung
================================================================================
Dieses Skript stellt eine verschlüsselte WSS (WebSocket Secure) Verbindung 
zu einem MQTT Broker her und empfängt Temperaturdaten von ESP8266 Sensoren.

Sicherheitsmerkmale:
- Passwörter werden aus .env Datei geladen (nicht im Code!)
- TLS mit Zertifikatsprüfung (CA Zertifikat)
- Keine hardcoded Secrets

Verwendung:
1. .env Datei mit Zugangsdaten erstellen
2. Skript ausführen: python wss_client_secure.py
3. Temperaturdaten werden live in der Konsole angezeigt


IoT Temperature Monitoring System
Autor: Nouri Deg
Datum: 24.04.2026 
================================================================================
"""

# =============================================================================
# IMPORTE
# =============================================================================

import paho.mqtt.client as mqtt      # MQTT Client Bibliothek
import ssl                            # TLS/SSL für verschlüsselte Verbindungen
import json                           # JSON Parsing für Temperaturdaten
import logging                        # Logging für Konsolenausgaben
import os                             # Betriebssystem-Funktionen (Dateipfade)
from dotenv import load_dotenv        # Lädt Umgebungsvariablen aus .env Datei

# =============================================================================
# UMGEBUNGSVARIABLEN LADEN
# =============================================================================
# Läd die Konfiguration aus der .env Datei (nicht auf GitHub!)
# Die .env Datei enthält sensible Daten wie Passwörter
load_dotenv()

# =============================================================================
# KONFIGURATION (aus .env Datei)
# =============================================================================

# WSS Verbindungsparameter (mit Default-Werten falls nicht in .env)
WSS_HOST = os.getenv('WSS_HOST', '192.168.0.105')      # Broker IP-Adresse
WSS_PORT = int(os.getenv('WSS_PORT', 8084))            # WSS Port (verschlüsselt)
WSS_USER = os.getenv('WSS_USER', 'test_device')        # MQTT Benutzername
WSS_PASSWORD = os.getenv('WSS_PASSWORD', '')           # MQTT Passwort (MUSS in .env sein!)
CA_CERT_PATH = os.getenv('CA_CERT_PATH', '../../certs/ca.crt')  # Pfad zum CA Zertifikat

# =============================================================================
# LOGGING KONFIGURATION
# =============================================================================
# Konfiguriert die Konsolenausgaben mit Zeitstempeln
logging.basicConfig(
    level=logging.INFO,                                # Zeige INFO und höhere Level
    format='%(asctime)s - %(levelname)s - %(message)s' # Format: Zeit - Level - Nachricht
)
logger = logging.getLogger(__name__)                   # Logger für dieses Modul

# =============================================================================
# MQTT CALLBACK FUNKTIONEN
# =============================================================================

def on_connect(client, userdata, flags, rc, properties=None):
    """
    Callback-Funktion, die aufgerufen wird, wenn die MQTT Verbindung hergestellt ist.
    
    Parameter:
        client: Der MQTT Client (wird automatisch übergeben)
        userdata: Benutzerdefinierte Daten (optional)
        flags: Server-Flags (nicht relevant)
        rc: Return Code (0 = Erfolg, andere Werte = Fehler)
        properties: Zusätzliche Eigenschaften (optional)
    
    Bei erfolgreicher Verbindung (rc == 0):
        - Gibt eine Bestätigung in der Konsole aus
        - Abonniert relevante Topics (Temperatur, Status, LWT)
    """
    if rc == 0:
        # Erfolgreiche Verbindung
        logger.info(f"✅ Verbunden mit WSS Broker auf {WSS_HOST}:{WSS_PORT}!")
        
        # Topics abonnieren, um Nachrichten zu empfangen
        client.subscribe("sensor/temperatur")      # Temperaturdaten von ESP8266
        client.subscribe("status/+/online")        # Online/Offline Status (+ ist Wildcard)
        client.subscribe("lwt/#")                  # Last Will Testament Nachrichten
        
        logger.info("📡 Abonniert: sensor/temperatur, status/+, lwt/#")
    else:
        # Verbindungsfehler
        logger.error(f"❌ Verbindungsfehler: {rc}")

def on_message(client, userdata, msg):
    """
    Callback-Funktion, die bei jeder empfangenen MQTT Nachricht aufgerufen wird.
    
    Parameter:
        client: Der MQTT Client
        userdata: Benutzerdefinierte Daten
        msg: Das Nachrichtenobjekt mit topic und payload
    
    Die Funktion versucht, JSON zu parsen. Bei Temperaturdaten wird eine
    spezielle Formatierung mit Emoji verwendet.
    """
    try:
        # Versuche den Payload als JSON zu parsen
        payload = json.loads(msg.payload.decode())
        
        # Spezielle Behandlung für Temperaturdaten
        if msg.topic == "sensor/temperatur" and 'temp' in payload:
            # Extrahiere Temperatur und Geräte-ID
            temp = payload['temp']
            device_id = payload.get('device_id', 'unknown')
            logger.info(f"🌡️ {temp}°C von {device_id}")
        else:
            # Andere Nachrichten (Status, LWT, etc.)
            logger.info(f"📨 {msg.topic}: {json.dumps(payload, ensure_ascii=False)}")
            
    except json.JSONDecodeError:
        # Fallback: Nachricht ist kein JSON - zeige als einfachen Text an
        logger.info(f"📨 {msg.topic}: {msg.payload.decode()}")

# =============================================================================
# HAUPTFUNKTION
# =============================================================================

def main():
    """
    Hauptfunktion des WSS Clients.
    
    Ablauf:
    1. Prüft ob das Passwort in der .env Datei gesetzt ist
    2. Erstellt den MQTT Client mit WebSocket Transport
    3. Konfiguriert TLS mit CA Zertifikat (falls vorhanden)
    4. Setzt Benutzername und Passwort
    5. Verbindet zum Broker
    6. Startet die Event-Loop (endlos)
    """
    
    # =========================================================================
    # SICHERHEITSCHECK: Passwort muss in .env Datei sein!
    # =========================================================================
    if not WSS_PASSWORD:
        logger.error("❌ Kein Passwort in .env Datei! Bitte .env Datei konfigurieren.")
        logger.info("   Beispiel: WSS_PASSWORD=dein_passwort")
        return  # Beende das Programm
    
    # =========================================================================
    # CLIENT INITIALISIERUNG
    # =========================================================================
    logger.info(f" Starte Python WSS Client von {WSS_HOST}:{WSS_PORT}")
    
    # Erstelle MQTT Client mit:
    # - Version 2 der Callback API (moderner)
    # - WebSocket Transport (für WSS)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, transport="websockets")
    
    # =========================================================================
    # TLS KONFIGURATION (Verschlüsselung)
    # =========================================================================
    # Prüfe ob CA Zertifikat existiert
    if os.path.exists(CA_CERT_PATH):
        # Konfiguriere TLS mit Zertifikatsprüfung (sicher!)
        client.tls_set(
            ca_certs=CA_CERT_PATH,                 # CA Zertifikat Datei
            cert_reqs=ssl.CERT_REQUIRED,           # Zertifikat ist erforderlich
            tls_version=ssl.PROTOCOL_TLSv1_2       # Verwende TLS 1.2 (sicher)
        )
        logger.info("✅ TLS mit Zertifikatsprüfung aktiviert")
    else:
        # Fallback: Keine Zertifikatsprüfung (nur für Entwicklung!)
        logger.warning(f"⚠️ CA Zertifikat nicht gefunden: {CA_CERT_PATH}")
        logger.warning("   Verbindung ohne Zertifikatsprüfung (unsicher!)")
        client.tls_set(cert_reqs=ssl.CERT_NONE)    # Keine Zertifikatsprüfung
        client.tls_insecure_set(True)              # Akzeptiere alle Zertifikate
    
    # =========================================================================
    # AUTHENTIFIZIERUNG
    # =========================================================================
    # Setze Benutzername und Passwort für den MQTT Broker
    client.username_pw_set(WSS_USER, WSS_PASSWORD)
    
    # =========================================================================
    # CALLBACKS REGISTRIEREN
    # =========================================================================
    client.on_connect = on_connect      # Wird bei Verbindung aufgerufen
    client.on_message = on_message      # Wird bei jeder Nachricht aufgerufen
    
    # =========================================================================
    # VERBINDUNG AUFBAUEN
    # =========================================================================
    try:
        # Verbinde zum Broker (non-blocking)
        client.connect(WSS_HOST, WSS_PORT, 60)  # Keepalive: 60 Sekunden
        
        # Starte die Event-Loop (blockiert, läuft endlos)
        # Hier werden eingehende Nachrichten verarbeitet
        client.loop_forever()
        
    except KeyboardInterrupt:
        # Benutzer hat Ctrl+C gedrückt
        logger.info("\n Client wird beendet... ")
    except Exception as e:
        # Andere Fehler (z.B. Verbindungsfehler)
        logger.error(f"❌ Fehler: {e}")

# =============================================================================
# PROGRAMMSTART
# =============================================================================
# Diese Bedingung ist True, wenn das Skript direkt ausgeführt wird
# (nicht wenn es als Modul importiert wird)
if __name__ == "__main__":
    main()