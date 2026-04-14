#!/usr/bin/env python
"""
Device Provisioning Service
Automatisches Onboarding neuer ESP8266 Geräte
"""

import paho.mqtt.client as mqtt
import psycopg2
import json
import os
import logging
import secrets
import string
import hashlib
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# KONFIGURATION
# ==========================================
MQTT_HOST = os.getenv('MQTT_HOST', 'mosquitto')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USER = os.getenv('MQTT_PROVISION_USER', 'provisioner')
MQTT_PASSWORD = os.getenv('MQTT_PROVISION_PASSWORD', '')

DB_HOST = os.getenv('DB_HOST', 'postgres')
DB_PORT = int(os.getenv('DB_PORT', 5432))
DB_NAME = os.getenv('DB_NAME', 'sensordb')
DB_USER = os.getenv('DB_USER', 'sensor_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

MQTT_BROKER_ADDRESS = os.getenv('MQTT_BROKER_ADDRESS', '192.168.1.100')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
            logger.info("Datenbank verbunden")
        except Exception as e:
            logger.error(f"DB Fehler: {e}")
            raise
    
    def create_tables(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id SERIAL PRIMARY KEY,
                    device_id VARCHAR(64) UNIQUE NOT NULL,
                    mac_address VARCHAR(17) UNIQUE NOT NULL,
                    mqtt_username VARCHAR(64) UNIQUE,
                    mqtt_password_hash VARCHAR(255),
                    status VARCHAR(20) DEFAULT 'pending',
                    provisioned_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            self.conn.commit()
            logger.info("Tabellen bereit")
    
    def device_exists(self, mac_address):
        with self.conn.cursor() as cur:
            cur.execute("SELECT device_id, status FROM devices WHERE mac_address = %s", (mac_address,))
            return cur.fetchone()
    
    def register_device(self, device_id, mac_address, mqtt_username, password_hash):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO devices (device_id, mac_address, mqtt_username, mqtt_password_hash, status)
                VALUES (%s, %s, %s, %s, 'provisioned')
                ON CONFLICT (device_id) DO UPDATE SET
                    status = 'provisioned'
            """, (device_id, mac_address, mqtt_username, password_hash))
            self.conn.commit()
            logger.info(f"Gerät registriert: {device_id}")

# ==========================================
# PROVISIONING SERVICE
# ==========================================
class ProvisioningService:
    def __init__(self):
        self.db = DatabaseManager()
        self.setup_mqtt()
    
    def generate_password(self, length=24):
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(chars) for _ in range(length))
    
    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    def setup_mqtt(self):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        self.mqtt_client.loop_start()
        logger.info("Provisioning Service gestartet")
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("MQTT verbunden")
            client.subscribe("devices/+/provisioning/request")
        else:
            logger.error(f"MQTT Fehler: {rc}")
    
    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            device_id = msg.topic.split('/')[1]
            mac_address = payload.get('mac_address')
            
            logger.info(f"Provisioning Request von {device_id}")
            
            existing = self.db.device_exists(mac_address)
            if existing:
                logger.info(f"Bekanntes Gerät: {existing[0]}")
                return
            
            mqtt_password = self.generate_password()
            mqtt_username = f"device_{device_id[:16]}"
            password_hash = self.hash_password(mqtt_password)
            
            self.db.register_device(device_id, mac_address, mqtt_username, password_hash)
            
            response = {
                "status": "success",
                "mqtt_broker": MQTT_BROKER_ADDRESS,
                "mqtt_port": 8883,
                "mqtt_username": mqtt_username,
                "mqtt_password": mqtt_password
            }
            
            topic = f"devices/{device_id}/provisioning/response"
            self.mqtt_client.publish(topic, json.dumps(response))
            logger.info(f" Gerät {device_id} provisioniert")
            
        except Exception as e:
            logger.error(f" Provisioning Fehler: {e}")

# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    service = ProvisioningService()
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info(" Provisioning Service gestoppt")
