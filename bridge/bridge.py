#!/usr/bin/env python
"""
MQTT to PostgreSQL Bridge
Empfängt Sensordaten, validiert sie und speichert sie in PostgreSQL

ANGEPASST für Tabellenstruktur:
- sensor_data: device_id, device_type, sensor_type, value, unit, raw_payload, received_at
- device_status: device_id, status, last_seen, last_rssi, last_free_heap
- devices: device_id, mac_address, mqtt_username, status, firmware_version
"""

import paho.mqtt.client as mqtt
import psycopg2
import json
import os
import logging
from jsonschema import validate, ValidationError
from dotenv import load_dotenv

# Umgebungsvariablen aus .env laden
load_dotenv()

# ==========================================
# 1. KONFIGURATION
# ==========================================

# MQTT Konfiguration
MQTT_HOST = os.getenv('MQTT_HOST', 'mosquitto')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USER = os.getenv('MQTT_BRIDGE_USER', 'bridge_user')
MQTT_PASSWORD = os.getenv('MQTT_BRIDGE_PASSWORD', '')
MQTT_TOPICS = ["sensor/temperatur", "sensor/#"]  # Zu abonnierende Topics

# PostgreSQL Konfiguration
DB_HOST = os.getenv('DB_HOST', 'postgres')
DB_PORT = int(os.getenv('DB_PORT', 5432))
DB_NAME = os.getenv('DB_NAME', 'sensordb')
DB_USER = os.getenv('DB_USER', 'sensor_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

# ==========================================
# 2. LOGGING KONFIGURATION
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==========================================
# 3. JSON SCHEMA VALIDIERUNG
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
# 4. DATABASE MANAGER
# ==========================================
class DatabaseManager:
    """
    Verwaltet die PostgreSQL Datenbankverbindung und speichert Sensordaten.
    Angepasst an die vorhandene Tabellenstruktur.
    """
    
    def __init__(self):
        self.conn = None
        self.connect()
        # Tabellen werden nicht mehr erstellt, da sie bereits existieren
        # self.create_tables()  # AUSKOMMENTIERT - Tabellen existieren bereits!
    
    def connect(self):
        """Stellt Verbindung zur PostgreSQL Datenbank her"""
        try:
            self.conn = psycopg2.connect(
                host=DB_HOST, port=DB_PORT, database=DB_NAME,
                user=DB_USER, password=DB_PASSWORD
            )
            logger.info(" PostgreSQL verbunden")
        except Exception as e:
            logger.error(f" DB Fehler: {e}")
            raise
    
    # create_tables() wurde ENTFERNT, da die Tabellen bereits existieren
    # Die vorhandenen Tabellen haben die Struktur:
    # - sensor_data: id, device_id, device_type, sensor_type, value, unit, raw_payload, received_at
    # - device_status: device_id, status, last_seen, last_rssi, last_free_heap, updated_at
    # - devices: id, device_id, mac_address, mqtt_username, mqtt_password_hash, status, ...
    
    def insert_sensor_data(self, payload):
        """
        Speichert Sensordaten in der sensor_data Tabelle.
        Verwendet die Spalten: device_id, device_type, sensor_type, value, unit, raw_payload
        """
        try:
            with self.conn.cursor() as cur:
                # Extrahiere Daten aus dem JSON Payload
                device_id = payload.get('device_id')
                device_type = payload.get('device_type', 'esp8266')     # Fallback auf esp8266
                sensor_type = payload.get('sensor', 'max6675')          # Fallback auf max6675
                value = payload.get('temp')                              # 'temp' wird zu 'value'
                unit = payload.get('unit', 'celsius')                   # Fallback auf celsius
                raw_payload = json.dumps(payload)                       # Vollständiges JSON speichern
                
                # Extrahiere optionale Felder für device_status
                rssi = payload.get('rssi')
                heap = payload.get('heap')
                
                # ==========================================
                # INSERT in sensor_data Tabelle
                # ==========================================
                cur.execute("""
                    INSERT INTO sensor_data 
                    (device_id, device_type, sensor_type, value, unit, raw_payload, received_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (device_id, device_type, sensor_type, value, unit, raw_payload))
                
                # ==========================================
                # UPDATE device_status Tabelle
                # ==========================================
                cur.execute("""
                    INSERT INTO device_status (device_id, status, last_seen, last_rssi, last_free_heap, updated_at)
                    VALUES (%s, 'online', NOW(), %s, %s, NOW())
                    ON CONFLICT (device_id) DO UPDATE SET
                        status = 'online',
                        last_seen = NOW(),
                        last_rssi = EXCLUDED.last_rssi,
                        last_free_heap = EXCLUDED.last_free_heap,
                        updated_at = NOW()
                """, (device_id, rssi, heap))
                
                self.conn.commit()
                logger.info(f" Gespeichert: {device_id} -> {value}°C")
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f" Insert Fehler: {e}")
    
    def update_device_status(self, device_id, status='online', rssi=None, heap=None):
        """
        Aktualisiert den Status eines Geräts in der device_status Tabelle
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO device_status (device_id, status, last_seen, last_rssi, last_free_heap, updated_at)
                    VALUES (%s, %s, NOW(), %s, %s, NOW())
                    ON CONFLICT (device_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        last_seen = NOW(),
                        last_rssi = COALESCE(EXCLUDED.last_rssi, device_status.last_rssi),
                        last_free_heap = COALESCE(EXCLUDED.last_free_heap, device_status.last_free_heap),
                        updated_at = NOW()
                """, (device_id, status, rssi, heap))
                self.conn.commit()
        except Exception as e:
            logger.error(f" Status Update Fehler: {e}")
    
    def close(self):
        """Schließt die Datenbankverbindung"""
        if self.conn:
            self.conn.close()
            logger.info("Datenbankverbindung geschlossen")

# ==========================================
# 5. MQTT BRIDGE
# ==========================================
class MQTTBridge:
    """
    MQTT Bridge Service
    Empfängt MQTT Nachrichten, validiert sie und speichert sie in PostgreSQL
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
    
    def on_connect(self, client, userdata, flags, rc):
        """
        Callback wenn MQTT Verbindung hergestellt wurde
        Abonniert alle konfigurierten Topics
        """
        if rc == 0:
            logger.info(" MQTT verbunden")
            for topic in MQTT_TOPICS:
                client.subscribe(topic)
                logger.info(f"    Abonniert: {topic}")
        else:
            logger.error(f" MQTT Fehler (rc={rc})")
    
    def on_message(self, client, userdata, msg):
        """
        Callback wenn eine MQTT Nachricht empfangen wird
        Verarbeitet und speichert die Sensordaten
        """
        try:
            # JSON Payload parsen
            payload = json.loads(msg.payload.decode())
            logger.info(f" Empfangen von {msg.topic}: {payload.get('device_id', 'unknown')}")
            
            # JSON Schema Validierung
            try:
                validate(instance=payload, schema=SENSOR_SCHEMA)
            except ValidationError as e:
                logger.error(f" Schema Fehler: {e.message}")
                return
            
            # Daten in PostgreSQL speichern
            self.db.insert_sensor_data(payload)
            
        except json.JSONDecodeError as e:
            logger.error(f" JSON Parse Fehler: {e}")
        except Exception as e:
            logger.error(f" Allgemeiner Fehler: {e}")
    
    def stop(self):
        """Stoppt die Bridge sauber"""
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        self.db.close()
        logger.info("Bridge gestoppt")

# ==========================================
# 6. MAIN
# ==========================================
if __name__ == "__main__":
    bridge = MQTTBridge()
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info(" Bridge wird gestoppt...")
        bridge.stop()