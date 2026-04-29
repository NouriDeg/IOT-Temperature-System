#!/usr/bin/env python
"""
MQTT to PostgreSQL Bridge
Empfängt Sensordaten, validiert sie und speichert sie in PostgreSQL

ZEITZONE: Europe/Berlin (CET/CEST)
- Alle Zeitstempel werden in lokaler Berliner Zeit gespeichert
- Empfängt Daten vom ESP8266 über MQTT
- Speichert Temperaturdaten in sensor_data Tabelle
- Aktualisiert Gerätestatus in device_status Tabelle
- Verarbeitet Heartbeat Nachrichten (status/+/online)
- Verarbeitet LWT Nachrichten (lwt/+)
"""

import paho.mqtt.client as mqtt
import psycopg2
import json
import os
import logging
from jsonschema import validate, ValidationError
from datetime import datetime
import pytz
from dotenv import load_dotenv

# Umgebungsvariablen aus .env laden
load_dotenv()

# ==========================================
# 1. ZEITZONE KONFIGURATION (Berlin)
# ==========================================
# Setze die lokale Zeitzone auf Europe/Berlin (CET/CEST)
LOCAL_TZ = pytz.timezone('Europe/Berlin')

# ==========================================
# 2. MQTT KONFIGURATION
# ==========================================
MQTT_HOST = os.getenv('MQTT_HOST', 'mosquitto')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USER = os.getenv('MQTT_BRIDGE_USER', 'bridge_user')
MQTT_PASSWORD = os.getenv('MQTT_BRIDGE_PASSWORD', '')
MQTT_TOPICS = ["sensor/temperatur", "sensor/#", "status/#", "lwt/#"]  # Heartbeat & LWT dazu!

# ==========================================
# 3. POSTGRESQL KONFIGURATION
# ==========================================
DB_HOST = os.getenv('DB_HOST', 'postgres')
DB_PORT = int(os.getenv('DB_PORT', 5432))
DB_NAME = os.getenv('DB_NAME', 'sensordb')
DB_USER = os.getenv('DB_USER', 'sensor_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

# ==========================================
# 4. LOGGING KONFIGURATION
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==========================================
# 5. JSON SCHEMA VALIDIERUNG
# ==========================================
# Definiert das erwartete JSON Format vom ESP8266
SENSOR_SCHEMA = {
    "type": "object",
    "required": ["device_id", "temp", "unit"],  # Pflichtfelder
    "properties": {
        "device_id": {"type": "string"},      # Eindeutige Geräte-ID
        "device_type": {"type": "string"},    # Gerätetyp (z.B. esp8266)
        "sensor": {"type": "string"},         # Sensortyp (z.B. max6675)
        "temp": {"type": "number"},           # Temperaturwert
        "unit": {"type": "string"},           # Einheit (celsius)
        "rssi": {"type": "number"},           # Signalstärke (optional)
        "heap": {"type": "number"},           # Freier RAM (optional)
        "uptime": {"type": "number"}          # Betriebszeit in Sekunden (optional)
    }
}

# ==========================================
# 6. HILFSFUNKTIONEN
# ==========================================
def get_local_now():
    """
    Gibt die aktuelle lokale Zeit in Europe/Berlin zurück
    Verwendet für received_at Zeitstempel in der Datenbank
    """
    return datetime.now(LOCAL_TZ)

def get_local_time_from_utc(utc_time):
    """
    Konvertiert UTC Zeit in lokale Berliner Zeit
    (Falls benötigt für andere Komponenten)
    """
    if utc_time is None:
        return None
    if utc_time.tzinfo is None:
        utc_time = pytz.UTC.localize(utc_time)
    return utc_time.astimezone(LOCAL_TZ)

# ==========================================
# 7. DATABASE MANAGER
# ==========================================
class DatabaseManager:
    """
    Verwaltet die PostgreSQL Datenbankverbindung und speichert Sensordaten.
    Alle Zeitstempel werden in lokaler Berliner Zeit gespeichert.
    """
    
    def __init__(self):
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
        """
        try:
            with self.conn.cursor() as cur:
                # Extrahiere Daten aus dem JSON Payload
                device_id = payload.get('device_id')
                device_type = payload.get('device_type', 'esp8266')
                sensor_type = payload.get('sensor', 'max6675')
                value = payload.get('temp')  # 'temp' wird zu 'value'
                unit = payload.get('unit', 'celsius')
                raw_payload = json.dumps(payload)  # Vollständiges JSON speichern
                
                # Extrahiere optionale Felder für device_status
                rssi = payload.get('rssi')
                heap = payload.get('heap')
                
                # Lokale Berliner Zeit
                local_received_at = get_local_now()
                
                # INSERT in sensor_data Tabelle
                cur.execute("""
                    INSERT INTO sensor_data 
                    (device_id, device_type, sensor_type, value, unit, raw_payload, received_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (device_id, device_type, sensor_type, value, unit, raw_payload, local_received_at))
                
                # UPDATE device_status Tabelle (durch Temperaturdaten)
                self._update_device_status(device_id, 'online', local_received_at, rssi, heap)
                
                self.conn.commit()
                
                time_str = local_received_at.strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"✅ Gespeichert: {device_id} -> {value}°C (Berlin: {time_str})")
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"❌ Insert Fehler: {e}")
    
    def update_heartbeat(self, device_id, status):
        """
        Verarbeitet Heartbeat Nachrichten (status/+/online)
        Aktualisiert last_seen und status in device_status
        """
        try:
            with self.conn.cursor() as cur:
                local_now = get_local_now()
                online_status = (status == 'true' or status == True)
                status_text = 'online' if online_status else 'offline'
                
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
        """
        try:
            with self.conn.cursor() as cur:
                local_now = get_local_now()
                status = payload.get('status', 'offline')
                
                cur.execute("""
                    INSERT INTO device_status (device_id, status, last_seen, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (device_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        last_seen = EXCLUDED.last_seen,
                        updated_at = EXCLUDED.updated_at
                """, (device_id, status, local_now, local_now))
                
                self.conn.commit()
                logger.info(f"⚠️ LWT: {device_id} -> {status}")
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"❌ LWT Fehler: {e}")
    
    def _update_device_status(self, device_id, status, timestamp, rssi=None, heap=None):
        """
        Interne Methode zum Aktualisieren des Gerätestatus
        """
        try:
            with self.conn.cursor() as cur:
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
        """Schließt die Datenbankverbindung"""
        if self.conn:
            self.conn.close()
            logger.info("Datenbankverbindung geschlossen")

# ==========================================
# 8. MQTT BRIDGE
# ==========================================
class MQTTBridge:
    """
    MQTT Bridge Service
    Empfängt MQTT Nachrichten, validiert sie und speichert sie in PostgreSQL
    Unterstützt:
    - Temperaturdaten (sensor/temperatur)
    - Heartbeat (status/+/online)
    - LWT Nachrichten (lwt/+)
    """
    
    def __init__(self):
        self.db = DatabaseManager()
        self.setup_mqtt()
    
    def setup_mqtt(self):
        """Initialisiert die MQTT Verbindung"""
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        self.mqtt_client.loop_start()
        logger.info(f" MQTT Bridge gestartet ({MQTT_HOST}:{MQTT_PORT})")
        logger.info(f" Zeitzone: Europe/Berlin (CET/CEST)")
    
    def on_connect(self, client, userdata, flags, rc):
        """
        Callback wenn MQTT Verbindung hergestellt wurde
        Abonniert alle konfigurierten Topics
        """
        if rc == 0:
            logger.info("✅ MQTT verbunden")
            for topic in MQTT_TOPICS:
                client.subscribe(topic)
                logger.info(f"  Abonniert: {topic}")
        else:
            logger.error(f"❌ MQTT Fehler (rc={rc})")
    
    def on_message(self, client, userdata, msg):
        """
        Callback wenn eine MQTT Nachricht empfangen wird
        Verarbeitet je nach Topic verschiedene Nachrichtentypen:
        - sensor/temperatur: Temperaturdaten (mit JSON Validierung)
        - status/+/online: Heartbeat Nachrichten
        - lwt/+: Last Will Testament Nachrichten
        """
        topic = msg.topic
        topic_parts = topic.split('/')
        
        try:
            # ==========================================
            # 1. HEARTBEAT NACHRICHTEN (status/+/online)
            # ==========================================
            if topic.startswith("status/") and topic.endswith("/online"):
                # Extrahiere device_id aus Topic: status/esp8266_xxx/online
                device_id = topic_parts[1]
                status = msg.payload.decode()
                
                logger.info(f" Heartbeat empfangen: {device_id} -> {status}")
                self.db.update_heartbeat(device_id, status)
                return
            
            # ==========================================
            # 2. LWT NACHRICHTEN (lwt/+)
            # ==========================================
            if topic.startswith("lwt/"):
                # Extrahiere device_id aus Topic: lwt/esp8266_xxx
                device_id = topic_parts[1]
                
                try:
                    payload = json.loads(msg.payload.decode())
                except:
                    payload = {"status": msg.payload.decode()}
                
                logger.info(f"⚠️ LWT empfangen: {device_id} -> {payload}")
                self.db.update_lwt(device_id, payload)
                return
            
            # ==========================================
            # 3. SENSOR DATEN (sensor/temperatur)
            # ==========================================
            if topic == "sensor/temperatur" or topic.startswith("sensor/"):
                # JSON Payload parsen
                payload = json.loads(msg.payload.decode())
                device_id = payload.get('device_id', 'unknown')
                logger.info(f" Empfangen von {topic}: {device_id}")
                
                # JSON Schema Validierung
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
            logger.warning(f"⚠️ Unbekanntes Topic: {topic} - wird ignoriert")
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON Parse Fehler: {e}")
        except Exception as e:
            logger.error(f"❌ Allgemeiner Fehler: {e}")
    
    def stop(self):
        """Stoppt die Bridge sauber"""
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        self.db.close()
        logger.info(" Bridge gestoppt")

# ==========================================
# 9. MAIN
# ==========================================
if __name__ == "__main__":
    # Zeige die aktuelle Zeitzone beim Start an
    current_time = get_local_now()
    time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
    logger.info(f" Bridge gestartet um: {time_str} (Europe/Berlin)")
    logger.info(f" Zeitzone Offset: UTC{current_time.strftime('%z')}")
    
    bridge = MQTTBridge()
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info(" Bridge wird gestoppt...")
########################################################################################################