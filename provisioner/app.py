#!/usr/bin/env python
"""
Device Provisioning Service - Automatisches Onboarding neuer ESP8266 Geräte

Dieser Service:
1. Empfängt Provisioning Requests von neuen ESP8266 Geräten
2. Generiert eindeutige MQTT Credentials für jedes Gerät
3. Erstellt TLS Zertifikate für sichere Kommunikation
4. Speichert Geräteinformationen in PostgreSQL
5. Sendet die Credentials zurück an das Gerät

Topics (vereinfacht):
- Request: provisioning/request
- Response: provisioning/response
"""

# ============================================
# IMPORTS
# ============================================
import paho.mqtt.client as mqtt
import psycopg2
import json
import os
import logging
import secrets
import string
import hashlib
from datetime import datetime, timedelta
import time
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from dotenv import load_dotenv

# Umgebungsvariablen aus .env laden
load_dotenv()

# ============================================
# KONFIGURATION (aus Umgebungsvariablen)
# ============================================

# MQTT Konfiguration
MQTT_HOST = os.getenv('MQTT_HOST', 'mosquitto')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_PROVISION_USER = os.getenv('MQTT_PROVISION_USER', 'provisioner')
MQTT_PROVISION_PASSWORD = os.getenv('MQTT_PROVISION_PASSWORD', '')

# PostgreSQL Konfiguration
DB_HOST = os.getenv('DB_HOST', 'postgres')
DB_PORT = int(os.getenv('DB_PORT', 5432))
DB_NAME = os.getenv('DB_NAME', 'sensordb')
DB_USER = os.getenv('DB_USER', 'sensor_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')

# MQTT Broker Adresse (für die Geräte)
MQTT_BROKER_ADDRESS = os.getenv('MQTT_BROKER_ADDRESS', '192.168.0.105')
CERT_DIR = '/app/certs'

# ============================================
# LOGGING KONFIGURATION
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================
# DATENBANK MANAGER
# ============================================
class DatabaseManager:
    """Verwaltet die PostgreSQL Datenbankverbindung und Tabellen"""
    
    def __init__(self):
        self.conn = None
        self.connect()
        self.create_tables()

    def connect(self):
        """Stellt Verbindung zur PostgreSQL Datenbank her"""
        try:
            self.conn = psycopg2.connect(
                host=DB_HOST, port=DB_PORT, database=DB_NAME,
                user=DB_USER, password=DB_PASSWORD,
                connect_timeout=10
            )
            logger.info(" Datenbank verbunden")
        except Exception as e:
            logger.error(f" DB Fehler: {e}")
            raise

    def create_tables(self):
        """Erstellt die benötigten Tabellen, falls sie nicht existieren"""
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id SERIAL PRIMARY KEY,
                    device_id VARCHAR(64) UNIQUE NOT NULL,
                    mac_address VARCHAR(17) UNIQUE NOT NULL,
                    mqtt_username VARCHAR(64) UNIQUE,
                    mqtt_password_hash VARCHAR(255),
                    client_cert_serial VARCHAR(255),
                    status VARCHAR(20) DEFAULT 'pending',
                    firmware_version VARCHAR(20),
                    last_seen TIMESTAMPTZ,
                    provisioned_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            self.conn.commit()
            logger.info(" Tabellen bereit")

    def device_exists(self, mac_address):
        """Prüft ob ein Gerät mit der gegebenen MAC-Adresse bereits existiert"""
        with self.conn.cursor() as cur:
            cur.execute("SELECT device_id, status FROM devices WHERE mac_address = %s", (mac_address,))
            return cur.fetchone()

    def register_device(self, device_id, mac_address, mqtt_username, password_hash):
        """Registriert ein neues Gerät in der Datenbank"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO devices (device_id, mac_address, mqtt_username, mqtt_password_hash, status)
                VALUES (%s, %s, %s, %s, 'provisioned')
                ON CONFLICT (device_id) DO UPDATE SET
                    status = 'provisioned', last_seen = NOW()
            """, (device_id, mac_address, mqtt_username, password_hash))
            self.conn.commit()
            logger.info(f" Gerät registriert: {device_id}")


# ============================================
# ZERTIFIKAT MANAGER
# ============================================
class CertificateManager:
    """Verwaltet TLS Zertifikate für die Geräte"""
    
    def __init__(self):
        self.load_ca()

    def load_ca(self):
        """Lädt das CA Zertifikat und den privaten Schlüssel"""
        with open(f'{CERT_DIR}/ca.key', 'rb') as f:
            self.ca_key = serialization.load_pem_private_key(f.read(), password=None)
        with open(f'{CERT_DIR}/ca.crt', 'rb') as f:
            self.ca_cert = x509.load_pem_x509_certificate(f.read())

    def generate_client_certificate(self, device_id, mac_address):
        """
        Generiert ein Client Zertifikat für ein neues Gerät
        Gültig für 365 Tage
        """
        # 1. Privaten Schlüssel für das Gerät generieren
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        # 2. Certificate Signing Request (CSR) erstellen
        csr = x509.CertificateSigningRequestBuilder().subject_name(
            x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, device_id),
                x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "IoT Devices"),
            ])
        ).sign(private_key, hashes.SHA256())

        # 3. Zertifikat mit CA signieren (gültig für 365 Tage)
        cert = (
            x509.CertificateBuilder()
            .subject_name(csr.subject)
            .issuer_name(self.ca_cert.subject)
            .public_key(csr.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(self.ca_key, hashes.SHA256())
        )

        return private_key, cert

    def format_certificates(self, private_key, cert):
        """Formatiert die Zertifikate für die Übertragung als JSON"""
        return {
            'ca_cert': open(f'{CERT_DIR}/ca.crt', 'r').read(),
            'client_cert': cert.public_bytes(serialization.Encoding.PEM).decode('utf-8'),
            'client_key': private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')
        }


# ============================================
# PROVISIONING SERVICE
# ============================================
class ProvisioningService:
    """Hauptservice für das Device Provisioning"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.cert_manager = CertificateManager()
        self.setup_mqtt()

    def generate_mqtt_password(self, length=24):
        """Generiert ein sicheres, zufälliges Passwort für MQTT"""
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(chars) for _ in range(length))

    def hash_password(self, password):
        """Hasht das Passwort für die Datenbank (SHA256)"""
        return hashlib.sha256(password.encode()).hexdigest()

    def setup_mqtt(self):
        """Initialisiert die MQTT Verbindung für den Provisioning Service"""
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(MQTT_PROVISION_USER, MQTT_PROVISION_PASSWORD)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        self.mqtt_client.loop_start()
        logger.info("🔌 Provisioning Service gestartet")

    def on_connect(self, client, userdata, flags, rc):
        """Callback wenn MQTT Verbindung hergestellt wurde"""
        if rc == 0:
            logger.info(" MQTT verbunden")
            # Abonniere das vereinfachte Provisioning Topic
            client.subscribe("provisioning/request")
            logger.info("   Abonniert: provisioning/request")
        else:
            logger.error(f" MQTT Fehler: {rc}")

    def on_message(self, client, userdata, msg):
        """
        Callback wenn eine MQTT Nachricht empfangen wird
        Verarbeitet Provisioning Requests von ESP8266 Geräten
        """
        device_id = None
        
        try:
            # JSON Payload parsen
            payload = json.loads(msg.payload.decode())
            device_id = payload.get('device_id')
            mac_address = payload.get('mac_address')
            firmware_version = payload.get('firmware_version', 'unknown')

            logger.info(f" Provisioning Request von {device_id} (MAC: {mac_address})")

            # ==========================================
            # 1. PRÜFE OB GERÄT BEREITS EXISTIERT
            # ==========================================
            existing = self.db.device_exists(mac_address)
            if existing:
                logger.info(f" Bekanntes Gerät: {existing[0]}")
                self.send_response(device_id, status="already_provisioned")
                return

            # ==========================================
            # 2. GENERIERE NEUE CREDENTIALS
            # ==========================================
            mqtt_password = self.generate_mqtt_password()
            mqtt_username = f"device_{device_id[:16]}" if device_id else f"device_{mac_address[:16]}"
            password_hash = self.hash_password(mqtt_password)

            # ==========================================
            # 3. GENERIERE TLS ZERTIFIKATE (optional)
            # ==========================================
            certs = None
            try:
                private_key, cert = self.cert_manager.generate_client_certificate(device_id, mac_address)
                certs = self.cert_manager.format_certificates(private_key, cert)
            except Exception as e:
                logger.warning(f"Zertifikatsgenerierung fehlgeschlagen: {e}")

            # ==========================================
            # 4. IN DATENBANK SPEICHERN
            # ==========================================
            self.db.register_device(device_id, mac_address, mqtt_username, password_hash)

            # ==========================================
            # 5. RESPONSE MIT CREDENTIALS SENDEN
            # ==========================================
            self.send_response(device_id, status="success", mqtt_username=mqtt_username,
                               mqtt_password=mqtt_password, certificates=certs)
            logger.info(f" Gerät {device_id} erfolgreich provisioniert")

        except json.JSONDecodeError as e:
            logger.error(f" JSON Parse Fehler: {e}")
            if device_id:
                self.send_response(device_id, status="error", message=f"Invalid JSON: {e}")
                
        except Exception as e:
            logger.error(f" Provisioning Fehler: {e}")
            if device_id:
                self.send_response(device_id, status="error", message=str(e))

    def send_response(self, device_id, status, mqtt_username=None, mqtt_password=None,
                      certificates=None, message=None):
        """
        Sendet die Provisioning Response an das Gerät
        
        Args:
            device_id: Eindeutige Geräte-ID
            status: "success", "error", oder "already_provisioned"
            mqtt_username: Generierter MQTT Benutzername (nur bei success)
            mqtt_password: Generiertes MQTT Passwort (nur bei success)
            certificates: TLS Zertifikate (optional)
            message: Fehlermeldung (nur bei error)
        """
        response = {"status": status}
        
        if mqtt_username:
            response["mqtt_username"] = mqtt_username
            response["mqtt_password"] = mqtt_password
            response["mqtt_broker"] = MQTT_BROKER_ADDRESS
            response["mqtt_port"] = 8883
            
        if certificates:
            response["certificates"] = certificates
            
        if message:
            response["message"] = message

        # Vereinfachtes Response Topic (ohne device_id)
        topic = "provisioning/response"
        self.mqtt_client.publish(topic, json.dumps(response))
        logger.info(f" Response gesendet an {topic}")


# ============================================
# MAIN
# ============================================
if __name__ == "__main__":
    service = ProvisioningService()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info(" Provisioning Service gestoppt")




