#!/usr/bin/env python
"""
MQTT to PostgreSQL Bridge
Empfängt Sensordaten, validiert sie und speichert sie in PostgreSQL
"""

import paho.mqtt.client as mqtt
import psycopg2
import json
import os
import logging
from jsonschema import validate, ValidationError
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# KONFIGURATION
# ==========================================
MQTT_HOST = os.getenv('MQTT_HOST', 'mosquitto')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USER = os.getenv('MQTT_BRIDGE_USER', 'bridge_user')
MQTT_PASSWORD = os.getenv('MQTT_BRIDGE_PASSWORD', '')
MQTT_TOPICS = ["sensor/temperatur", "sensor/#"]  # Liste der Topics

DB_HOST = os.getenv('DB_HOST', 'postgres')
DB_PORT = int(os.getenv('DB_PORT', 5432))
DB_NAME = os.getenv('DB_NAME', 'sensordb')
DB_USER = os.getenv('DB_USER', 'sensor_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

# ==========================================
# LOGGING
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==========================================
# JSON SCHEMA
# ==========================================
SENSOR_SCHEMA = {
    "type": "object",
    "required": ["device_id", "temp", "unit"],
    "properties": {
        "device_id": {"type": "string"},
        "device_type": {"type": "string"},
        "sensor": {"type": "string"},
        "temp": {"type": "number"},
        "unit": {"type": "string"},
        "rssi": {"type": "number"},
        "heap": {"type": "number"},
        "uptime": {"type": "number"}
    }
}

# ==========================================
# DATABASE MANAGER
# ==========================================
class DatabaseManager:
    def __init__(self):
        self.conn = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        try:
            self.conn = psycopg2.connect(
                host=DB_HOST, port=DB_PORT, database=DB_NAME,
                user=DB_USER, password=DB_PASSWORD
            )
            logger.info("PostgreSQL verbunden")
        except Exception as e:
            logger.error(f"DB Fehler: {e}")
            raise
    
    def create_tables(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sensor_data (
                    id BIGSERIAL PRIMARY KEY,
                    device_id VARCHAR(64) NOT NULL,
                    temperature DECIMAL(10,2),
                    unit VARCHAR(16),
                    rssi INTEGER,
                    heap INTEGER,
                    uptime INTEGER,
                    raw_payload JSONB,
                    received_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            self.conn.commit()
            logger.info("Tabellen bereit")
    
    def insert_sensor_data(self, payload):
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO sensor_data 
                    (device_id, temperature, unit, rssi, heap, uptime, raw_payload)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    payload.get('device_id'),
                    payload.get('temp'),
                    payload.get('unit'),
                    payload.get('rssi'),
                    payload.get('heap'),
                    payload.get('uptime'),
                    json.dumps(payload)
                ))
                self.conn.commit()
                logger.info(f"Gespeichert: {payload.get('device_id')} -> {payload.get('temp')}°C")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Insert Fehler: {e}")

# ==========================================
# MQTT BRIDGE
# ==========================================
class MQTTBridge:
    def __init__(self):
        self.db = DatabaseManager()
        self.setup_mqtt()
    
    def setup_mqtt(self):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        self.mqtt_client.loop_start()
        logger.info(f"MQTT Bridge gestartet ({MQTT_HOST}:{MQTT_PORT})")
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("MQTT verbunden")
            # Abonniere alle Topics aus der Liste
            for topic in MQTT_TOPICS:
                client.subscribe(topic)
                logger.info(f"   Abonniert: {topic}")
        else:
            logger.error(f"MQTT Fehler: {rc}")
    
    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            logger.info(f" Empfangen von {msg.topic}")
            validate(instance=payload, schema=SENSOR_SCHEMA)
            self.db.insert_sensor_data(payload)
        except ValidationError as e:
            logger.error(f"Schema Fehler: {e.message}")
        except Exception as e:
            logger.error(f"Fehler: {e}")

# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    bridge = MQTTBridge()
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info(" Bridge gestoppt")