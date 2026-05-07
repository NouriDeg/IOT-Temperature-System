#!/usr/bin/env python
# ============================================================================
# MQTT TO POSTGRESQL BRIDGE - IOT TEMPERATURE MONITORING SYSTEM
# ============================================================================
# 
# Version: 3.0 (mit Heartbeat & LWT Unterstützung)
# Datum: 30.04.2026 
# Autor: Nouri Deg.
# 
# Diese Bridge verbindet MQTT mit PostgreSQL:
# - Empfängt Temperaturdaten vom ESP8266 über MQTT
# - Validiert JSON Payloads gegen ein Schema
# - Speichert Daten in der sensor_data Tabelle
# - Aktualisiert Gerätestatus in der device_status Tabelle
# - Verarbeitet Heartbeat Nachrichten (status/+/online)
# - Verarbeitet LWT Nachrichten (lwt/+)
# 
# ZEITZONE: Europe/Berlin (CET/CEST)
# Alle Zeitstempel werden in lokaler Berliner Zeit gespeichert
# ============================================================================
# Stelle sicher dass SENSOR_SCHEMA exportiert wird
__all__ = ['DatabaseManager', 'MQTTBridge', 'SENSOR_SCHEMA', 'get_local_now', 'LOCAL_TZ']
# ============================================================================
# IMPORTS
# ============================================================================

import paho.mqtt.client as mqtt      # MQTT Client für Nachrichtenempfang
import psycopg2                       # PostgreSQL Datenbank Treiber
import json                           # JSON Parsing für Payloads
import os                             # Betriebssystem-Funktionen (Dateipfade, Umgebungsvariablen)
import logging                        # Logging für Konsolenausgaben
from jsonschema import validate, ValidationError  # JSON Schema Validierung
from datetime import datetime          # Datums- und Zeitfunktionen
import pytz                           # Zeitzonen-Unterstützung (Europe/Berlin)
from dotenv import load_dotenv        # Lädt Umgebungsvariablen aus .env Datei

# ============================================================================
# UMWELTVARIABLEN LADEN
# ============================================================================
# Läd die Konfiguration aus der .env Datei (nicht auf GitHub!)
load_dotenv()

# ============================================================================
# 1. ZEITZONE KONFIGURATION (Berlin)
# ============================================================================
# Setze die lokale Zeitzone auf Europe/Berlin (CET/CEST)
# Alle Zeitstempel werden in dieser Zeitzone gespeichert
LOCAL_TZ = pytz.timezone('Europe/Berlin')

# ============================================================================
# 2. MQTT KONFIGURATION
# ============================================================================
# Verbindungsparameter für den MQTT Broker
MQTT_HOST = os.getenv('MQTT_HOST', 'mosquitto')            # Broker Hostname (Docker DNS)
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))              # MQTT Port (1883 = unverschlüsselt)
MQTT_USER = os.getenv('MQTT_BRIDGE_USER', 'bridge_user')   # MQTT Benutzername (aus .env)
MQTT_PASSWORD = os.getenv('MQTT_BRIDGE_PASSWORD', '')      # MQTT Passwort (aus .env)

# Topics die abonniert werden:
# - sensor/temperatur: Temperaturdaten vom ESP8266
# - sensor/#: Alle Sensor-Topics (Wildcard)
# - status/#: Heartbeat und Status Nachrichten
# - lwt/#: Last Will Testament Nachrichten
MQTT_TOPICS = ["sensor/temperatur", "sensor/#", "status/#", "lwt/#"]

# ============================================================================
# 3. POSTGRESQL KONFIGURATION
# ============================================================================
# Verbindungsparameter für die PostgreSQL Datenbank
DB_HOST = os.getenv('DB_HOST', 'postgres')                         # Datenbank Hostname (Docker DNS)
DB_PORT = int(os.getenv('DB_PORT', 5432))                           # PostgreSQL Standardport
DB_NAME = os.getenv('DB_NAME', 'sensordb')                          # Datenbankname
DB_USER = os.getenv('DB_USER', 'sensor_user')                       # Datenbankbenutzer
DB_PASSWORD = os.getenv('DB_PASSWORD', '')                          # Datenbank Passwort (aus .env)

# ============================================================================
# 4. LOGGING KONFIGURATION
# ============================================================================
# Konfiguriert die Konsolenausgaben mit Zeitstempeln
logging.basicConfig(
    level=logging.INFO,                                             # Zeige INFO und höhere Level
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'  # Format: Zeit - Name - Level - Nachricht
)
logger = logging.getLogger(__name__)                                # Logger für dieses Modul

# ============================================================================
# 5. JSON SCHEMA VALIDIERUNG
# ============================================================================
# Definiert das erwartete JSON Format vom ESP8266
# Das Schema wird verwendet um ungültige Nachrichten zu filtern
SENSOR_SCHEMA = {
    "type": "object",                                               # JSON muss ein Objekt sein
    "required": ["device_id", "temp", "unit"],                      # Pflichtfelder
    "properties": {
        # Eindeutige Geräte-ID (z.B. "esp8266_ECFABC5F0")
        "device_id": {"type": "string"},
        # Gerätetyp (z.B. "esp8266")
        "device_type": {"type": "string"},
        # Sensortyp (z.B. "max6675")
        "sensor": {"type": "string"},
        # Temperaturwert (z.B. 25.75)
        "temp": {"type": "number"},
        # Einheit (z.B. "celsius")
        "unit": {"type": "string"},
        # Signalstärke in dBm (optional, z.B. -62)
        "rssi": {"type": "number"},
        # Freier RAM in Bytes (optional, z.B. 14768)
        "heap": {"type": "number"},
        # Betriebszeit in Sekunden (optional, z.B. 12345)
        "uptime": {"type": "number"}
    }
}

# ============================================================================
# 6. HILFSFUNKTIONEN
# ============================================================================

def get_local_now():
    """
    Gibt die aktuelle lokale Zeit in Europe/Berlin zurück
    Verwendet für received_at Zeitstempel in der Datenbank
    
    @return: datetime Objekt mit aktueller Berliner Zeit
    """
    return datetime.now(LOCAL_TZ)

def get_local_time_from_utc(utc_time):
    """
    Konvertiert UTC Zeit in lokale Berliner Zeit
    (Falls benötigt für andere Komponenten)
    
    @param utc_time: UTC Zeitstempel (datetime Objekt)
    @return: Lokaler Zeitstempel oder None
    """
    if utc_time is None:
        return None
    if utc_time.tzinfo is None:
        utc_time = pytz.UTC.localize(utc_time)      # Füge UTC Zeitzone hinzu
    return utc_time.astimezone(LOCAL_TZ)            # Konvertiere nach Europe/Berlin

# ============================================================================
# 7. DATABASE MANAGER
# ============================================================================

class DatabaseManager:
    """
    Verwaltet die PostgreSQL Datenbankverbindung und speichert Sensordaten.
    Alle Zeitstempel werden in lokaler Berliner Zeit gespeichert.
    """
    
    def __init__(self):
        """Initialisiert die Datenbankverbindung beim Erstellen des Objekts"""
        self.conn = None
        self.connect()
    
    def connect(self):
        """Stellt Verbindung zur PostgreSQL Datenbank her"""
        try:
            self.conn = psycopg2.connect(
                host=DB_HOST, port=DB_PORT, database=DB_NAME,
                user=DB_USER, password=DB_PASSWORD
            )
            logger.info("✅ PostgreSQL verbunden (Europe/Berlin Zeitzone)")
        except Exception as e:
            logger.error(f"❌ DB Fehler: {e}")
            raise
    
    def insert_sensor_data(self, payload):
        """
        Speichert Sensordaten in der sensor_data Tabelle.
        Verwendet die lokale Berliner Zeit für received_at.
        
        @param payload: JSON Payload vom ESP8266 (device_id, temp, unit, etc.)
        """
        try:
            with self.conn.cursor() as cur:
                # Extrahiere Daten aus dem JSON Payload
                device_id = payload.get('device_id')                         # Geräte-ID
                device_type = payload.get('device_type', 'esp8266')          # Gerätetyp (Default: esp8266)
                sensor_type = payload.get('sensor', 'max6675')               # Sensortyp (Default: max6675)
                value = payload.get('temp')                                  # 'temp' wird zu 'value' in DB
                unit = payload.get('unit', 'celsius')                        # Einheit (Default: celsius)
                raw_payload = json.dumps(payload)                            # Vollständiges JSON speichern
                
                # Extrahiere optionale Felder für device_status
                rssi = payload.get('rssi')                                   # Signalstärke (optional)
                heap = payload.get('heap')                                   # Freier RAM (optional)
                
                # Lokale Berliner Zeit für Zeitstempel
                local_received_at = get_local_now()
                
                # INSERT in sensor_data Tabelle
                cur.execute("""
                    INSERT INTO sensor_data 
                    (device_id, device_type, sensor_type, value, unit, raw_payload, received_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (device_id, device_type, sensor_type, value, unit, raw_payload, local_received_at))
                
                # UPDATE device_status Tabelle (durch Temperaturdaten)
                self._update_device_status(device_id, 'online', local_received_at, rssi, heap)
                
                self.conn.commit()                                          # Transaktion speichern
                
                time_str = local_received_at.strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"✅ Gespeichert: {device_id} -> {value}°C (Berlin: {time_str})")
                
        except Exception as e:
            self.conn.rollback()                # Fehler: Transaktion rückgängig machen
            logger.error(f"❌ Insert Fehler: {e}")
    
    def update_heartbeat(self, device_id, status):
        """
        Verarbeitet Heartbeat Nachrichten (status/+/online)
        Aktualisiert last_seen und status in device_status
        
        @param device_id: Eindeutige Geräte-ID
        @param status: Status als String ("true" oder "false")
        """
        try:
            with self.conn.cursor() as cur:
                local_now = get_local_now()
                # Konvertiere String "true"/"false" zu boolean
                online_status = (status == 'true' or status == True)
                status_text = 'online' if online_status else 'offline'
                
                # UPSERT: Update oder Insert wenn nicht vorhanden
                cur.execute("""
                    INSERT INTO device_status (device_id, status, last_seen, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (device_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        last_seen = EXCLUDED.last_seen,
                        updated_at = EXCLUDED.updated_at
                """, (device_id, status_text, local_now, local_now))
                
                self.conn.commit()
                logger.info(f" Heartbeat: {device_id} -> {status_text} (Berlin: {local_now.strftime('%H:%M:%S')})")
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"❌ Heartbeat Fehler: {e}")
    
    def update_lwt(self, device_id, payload):
        """
        Verarbeitet LWT (Last Will Testament) Nachrichten
        Wird aufgerufen wenn ein Gerät unerwartet offline geht
        
        @param device_id: Eindeutige Geräte-ID
        @param payload: LWT JSON Payload mit Statusinformationen
        """
        try:
            with self.conn.cursor() as cur:
                local_now = get_local_now()
                status = payload.get('status', 'offline')
                
                # UPSERT: Update oder Insert wenn nicht vorhanden
                cur.execute("""
                    INSERT INTO device_status (device_id, status, last_seen, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (device_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        last_seen = EXCLUDED.last_seen,
                        updated_at = EXCLUDED.updated_at
                """, (device_id, status, local_now, local_now))
                
                self.conn.commit()
                logger.info(f" LWT: {device_id} -> {status}")
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"❌ LWT Fehler: {e}")
    
    def _update_device_status(self, device_id, status, timestamp, rssi=None, heap=None):
        """
        Interne Methode zum Aktualisieren des Gerätestatus
        Wird bei jeder Temperaturmessung aufgerufen
        
        @param device_id: Eindeutige Geräte-ID
        @param status: Status ('online' oder 'offline')
        @param timestamp: Zeitstempel der Messung
        @param rssi: Signalstärke (optional)
        @param heap: Freier RAM (optional)
        """
        try:
            with self.conn.cursor() as cur:
                # UPSERT mit RSSI und Heap Informationen
                cur.execute("""
                    INSERT INTO device_status (device_id, status, last_seen, last_rssi, last_free_heap, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (device_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        last_seen = EXCLUDED.last_seen,
                        last_rssi = COALESCE(EXCLUDED.last_rssi, device_status.last_rssi),
                        last_free_heap = COALESCE(EXCLUDED.last_free_heap, device_status.last_free_heap),
                        updated_at = EXCLUDED.updated_at
                """, (device_id, status, timestamp, rssi, heap, timestamp))
        except Exception as e:
            logger.error(f"❌ Status Update Fehler: {e}")
            raise
    
    def close(self):
        """Schließt die Datenbankverbindung sauber"""
        if self.conn:
            self.conn.close()
            logger.info("Datenbankverbindung geschlossen")

# ============================================================================
# 8. MQTT BRIDGE
# ============================================================================

class MQTTBridge:
    """
    MQTT Bridge Service
    Empfängt MQTT Nachrichten, validiert sie und speichert sie in PostgreSQL
    Unterstützt verschiedene Nachrichtentypen:
    - Temperaturdaten (sensor/temperatur) - mit JSON Validierung
    - Heartbeat (status/+/online) - Online-Status Updates
    - LWT Nachrichten (lwt/+) - Offline Benachrichtigungen
    """
    
    def __init__(self):
        """Initialisiert die Bridge: Datenbankverbindung und MQTT Client"""
        self.db = DatabaseManager()
        self.setup_mqtt()
    
    def setup_mqtt(self):
        """Initialisiert die MQTT Verbindung und konfiguriert Callbacks"""
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)   # Authentifizierung
        self.mqtt_client.on_connect = self.on_connect                # Callback bei Verbindung
        self.mqtt_client.on_message = self.on_message                # Callback bei Nachricht
        self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)           # Verbindung herstellen
        self.mqtt_client.loop_start()                                # Starte MQTT Loop (non-blocking)
        logger.info(f" MQTT Bridge gestartet ({MQTT_HOST}:{MQTT_PORT})")
        logger.info(f" Zeitzone: Europe/Berlin (CET/CEST)")
    
    def on_connect(self, client, userdata, flags, rc):
        """
        Callback wenn MQTT Verbindung hergestellt wurde
        Abonniert alle konfigurierten Topics
        
        @param client: MQTT Client Instanz
        @param userdata: Benutzerdefinierte Daten
        @param flags: Server-Flags
        @param rc: Return Code (0 = Erfolg)
        """
        if rc == 0:
            logger.info("✅ MQTT verbunden")
            for topic in MQTT_TOPICS:
                client.subscribe(topic)    # Topic abonnieren
                logger.info(f"   Abonniert: {topic}")
        else:
            logger.error(f"❌ MQTT Fehler (rc={rc})")
    
    def on_message(self, client, userdata, msg):
        """
        Callback wenn eine MQTT Nachricht empfangen wird
        Verarbeitet je nach Topic verschiedene Nachrichtentypen:
        - sensor/temperatur: Temperaturdaten (mit JSON Validierung)
        - status/+/online: Heartbeat Nachrichten
        - lwt/+: Last Will Testament Nachrichten
        
        @param client: MQTT Client Instanz
        @param userdata: Benutzerdefinierte Daten
        @param msg: Nachricht mit Topic und Payload
        """
        topic = msg.topic
        topic_parts = topic.split('/')
        
        try:
            # ==========================================
            # 1. HEARTBEAT NACHRICHTEN (status/+/online)
            # ==========================================
            # Format: status/esp8266_ECFABC5F0/online
            if topic.startswith("status/") and topic.endswith("/online"):
                # Extrahiere device_id aus Topic
                device_id = topic_parts[1]               # z.B. "esp8266_ECFABC5F0"
                status = msg.payload.decode()            # "true" oder "false"
                
                logger.info(f" Heartbeat empfangen: {device_id} -> {status}")
                self.db.update_heartbeat(device_id, status)
                return
            
            # ==========================================
            # 2. LWT NACHRICHTEN (lwt/+)
            # ==========================================
            # Format: lwt/esp8266_ECFABC5F0
            if topic.startswith("lwt/"):
                # Extrahiere device_id aus Topic
                device_id = topic_parts[1]          # z.B. "esp8266_ECFABC5F0"
                
                # Versuche JSON zu parsen, sonst einfacher String
                try:
                    payload = json.loads(msg.payload.decode())
                except:
                    payload = {"status": msg.payload.decode()}
                
                logger.info(f"⚠ LWT empfangen: {device_id} -> {payload}")
                self.db.update_lwt(device_id, payload)
                return
            
            # ==========================================
            # 3. SENSOR DATEN (sensor/temperatur)
            # ==========================================
            # Format: sensor/temperatur
            if topic == "sensor/temperatur" or topic.startswith("sensor/"):
                # JSON Payload parsen
                payload = json.loads(msg.payload.decode())
                device_id = payload.get('device_id', 'unknown')
                logger.info(f" Empfangen von {topic}: {device_id}")
                
                # JSON Schema Validierung (stellt Datenqualität sicher)
                try:
                    validate(instance=payload, schema=SENSOR_SCHEMA)
                except ValidationError as e:
                    logger.error(f"❌ Schema Fehler: {e.message}")
                    return
                
                # Daten in PostgreSQL speichern
                self.db.insert_sensor_data(payload)
                return
            
            # ==========================================
            # 4. UNBEKANNTE TOPICS
            # ==========================================
            logger.warning(f" Unbekanntes Topic: {topic} - wird ignoriert")
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON Parse Fehler: {e}")
        except Exception as e:
            logger.error(f"❌ Allgemeiner Fehler: {e}")
    
    def stop(self):
        """Stoppt die Bridge sauber (MQTT Client und Datenbank)"""
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        self.db.close()
        logger.info(" Bridge gestoppt")

# ============================================================================
# 9. MAIN
# ============================================================================

if __name__ == "__main__":
    """
    Hauptprogramm - Startet die MQTT Bridge
    """
    # Zeige die aktuelle Zeitzone beim Start an
    current_time = get_local_now()
    time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
    logger.info(f" Bridge gestartet um: {time_str} (Europe/Berlin)")
    logger.info(f" Zeitzone Offset: UTC{current_time.strftime('%z')}")
    
    # Bridge instanziieren und starten
    bridge = MQTTBridge()
    
    try:
        # Hauptschleife - läuft bis Ctrl+C
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info(" Bridge wird gestoppt...")
        bridge.stop()