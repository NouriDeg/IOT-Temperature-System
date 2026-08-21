#!/usr/bin/env python
# ============================================================================
# PROVISIONING SERVICE - AUTOMATISCHES GERÄTE-ONBOARDING
# ============================================================================
# 
# Version: 2.0
# Datum: 30.04.2026
# Autor: Nouri Deg.
# 
# Dieser Service ermöglicht das automatische Onboarding neuer ESP8266 Geräte.
# Neue Geräte müssen keine festen MQTT Credentials im Code haben - sie werden
# automatisch vom Provisioning Service mit eindeutigen Zugangsdaten versorgt.
# 
# ABLAUF:
# 1. ESP8266 startet ohne Credentials
# 2. ESP8266 sendet Provisioning Request (MAC-Adresse, Device ID)
# 3. Provisioning Service generiert eindeutige MQTT Credentials
# 4. Service erstellt TLS Zertifikate für das Gerät
# 5. Service speichert Geräteinformationen in PostgreSQL
# 6. Service sendet Credentials zurück an das ESP8266
# 7. ESP8266 speichert Credentials und verbindet sich dauerhaft
# 
# TOPICS:
# - Request:  provisioning/request  (ESP8266 → Service)
# - Response: provisioning/response (Service → ESP8266)
# ============================================================================

# ============================================================================
# IMPORTS
# ============================================================================

import paho.mqtt.client as mqtt          # MQTT Client für Kommunikation
import psycopg2                          # PostgreSQL Datenbank Treiber
import json                              # JSON Parsing für Nachrichten
import os                                # Betriebssystem-Funktionen
import logging                           # Logging für Konsolenausgaben
import secrets                           # Kryptografisch sichere Zufallszahlen
import string                            # Zeichenketten für Passwort-Generierung
import hashlib                           # SHA256 Hashing für Passwörter
from datetime import datetime, timedelta # Datums- und Zeitfunktionen
import time                              # Zeitfunktionen für Main Loop
from cryptography.hazmat.primitives import serialization  # Zertifikats-Serialisierung
from cryptography.hazmat.primitives.asymmetric import rsa # RSA Schlüssel-Generierung
from cryptography import x509            # X.509 Zertifikate
from cryptography.x509.oid import NameOID # X.509 Name OIDs
from cryptography.hazmat.primitives import hashes  # Hash-Funktionen für Zertifikate
from dotenv import load_dotenv           # Lädt Umgebungsvariablen aus .env

# ============================================================================
# UMWELTVARIABLEN LADEN
# ============================================================================
# Läd die Konfiguration aus der .env Datei (nicht auf GitHub!)
load_dotenv()

# ============================================================================
# 1. KONFIGURATION (aus Umgebungsvariablen)
# ============================================================================

# ----------------------------------------------------------------------------
# MQTT KONFIGURATION
# ----------------------------------------------------------------------------
MQTT_HOST = os.getenv('MQTT_HOST', 'mosquitto')                    # Broker Hostname (Docker DNS)
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))                       # MQTT Port (1883 = unverschlüsselt)
MQTT_PROVISION_USER = os.getenv('MQTT_PROVISION_USER', 'provisioner')     # MQTT Benutzername
MQTT_PROVISION_PASSWORD = os.getenv('MQTT_PROVISION_PASSWORD', '')        # MQTT Passwort

# ----------------------------------------------------------------------------
# POSTGRESQL KONFIGURATION
# ----------------------------------------------------------------------------
DB_HOST = os.getenv('DB_HOST', 'postgres')                         # Datenbank Hostname
DB_PORT = int(os.getenv('DB_PORT', 5432))                           # PostgreSQL Standardport
DB_NAME = os.getenv('DB_NAME', 'sensordb')                          # Datenbankname
DB_USER = os.getenv('DB_USER', 'sensor_user')                       # Datenbankbenutzer
DB_PASSWORD = os.getenv('DB_PASSWORD', '')                          # Datenbank Passwort

# ----------------------------------------------------------------------------
# PROVISIONING KONFIGURATION
# ----------------------------------------------------------------------------
MQTT_BROKER_ADDRESS = os.getenv('MQTT_BROKER_ADDRESS', '192.168.0.106')  # Externe Broker Adresse
CERT_DIR = '/app/certs'                                             # Verzeichnis für CA Zertifikate

# ===========================================================================
# 2. LOGGING KONFIGURATION
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# 3. DATENBANK MANAGER
# ============================================================================

class DatabaseManager:
    """
    Verwaltet die PostgreSQL Datenbankverbindung und Tabellen für provisionierte Geräte
    """
    
    def __init__(self):
        """Initialisiert die Datenbankverbindung und erstellt Tabellen"""
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
            logger.info("✅ Datenbank verbunden")
        except Exception as e:
            logger.error(f"❌ DB Fehler: {e}")
            raise

    def create_tables(self):
        """
        Erstellt die benötigten Tabellen, falls sie nicht existieren
        Tabelle: devices - speichert alle provisionierten Geräte
        """
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
            logger.info("✅ Tabellen bereit")

    def device_exists(self, mac_address):
        """
        Prüft ob ein Gerät mit der gegebenen MAC-Adresse bereits existiert
        
        @param mac_address: MAC-Adresse des Geräts (z.B. "EC:FA:BC:5F:0A:DF")
        @return: (device_id, status) oder None
        """
        with self.conn.cursor() as cur:
            cur.execute("SELECT device_id, status FROM devices WHERE mac_address = %s", (mac_address,))
            return cur.fetchone()

    def register_device(self, device_id, mac_address, mqtt_username, password_hash):
        """
        Registriert ein neues Gerät in der Datenbank
        
        @param device_id: Eindeutige Geräte-ID (z.B. "esp8266_ECFABC5F0")
        @param mac_address: MAC-Adresse des Geräts
        @param mqtt_username: Generierter MQTT Benutzername
        @param password_hash: SHA256 Hash des MQTT Passworts
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO devices (device_id, mac_address, mqtt_username, mqtt_password_hash, status)
                VALUES (%s, %s, %s, %s, 'provisioned')
                ON CONFLICT (device_id) DO UPDATE SET
                    status = 'provisioned', last_seen = NOW()
            """, (device_id, mac_address, mqtt_username, password_hash))
            self.conn.commit()
            logger.info(f"✅ Gerät registriert: {device_id}")

# ============================================================================
# 4. ZERTIFIKAT MANAGER
# ============================================================================

class CertificateManager:
    """
    Verwaltet TLS Zertifikate für die Geräte (mTLS)
    Erstellt Client-Zertifikate für sichere MQTT Kommunikation
    """
    
    def __init__(self):
        """Lädt die CA Zertifikate beim Start"""
        self.load_ca()

    def load_ca(self):
        """Lädt das CA Zertifikat und den privaten Schlüssel aus dem Docker Volume"""
        with open(f'{CERT_DIR}/ca.key', 'rb') as f:
            self.ca_key = serialization.load_pem_private_key(f.read(), password=None)
        with open(f'{CERT_DIR}/ca.crt', 'rb') as f:
            self.ca_cert = x509.load_pem_x509_certificate(f.read())

    def generate_client_certificate(self, device_id, mac_address):
        """
        Generiert ein Client Zertifikat für ein neues Gerät
        Gültig für 365 Tage (1 Jahr)
        
        @param device_id: Eindeutige Geräte-ID
        @param mac_address: MAC-Adresse des Geräts
        @return: (private_key, certificate) Tupel
        """
        # 1. Privaten Schlüssel für das Gerät generieren (RSA 2048 Bit)
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        # 2. Certificate Signing Request (CSR) erstellen
        # Enthält Geräte-Identifikation
        csr = x509.CertificateSigningRequestBuilder().subject_name(
            x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, device_id),
                x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "IoT Devices"),
            ])
        ).sign(private_key, hashes.SHA256())

        # 3. Zertifikat mit CA signieren
        # Gültigkeit: 365 Tage ab jetzt
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
        """
        Formatiert die Zertifikate für die Übertragung als JSON
        
        @param private_key: Privater Schlüssel des Clients
        @param cert: Client Zertifikat
        @return: Dictionary mit PEM-formatierten Zertifikaten
        """
        return {
            'ca_cert': open(f'{CERT_DIR}/ca.crt', 'r').read(),
            'client_cert': cert.public_bytes(serialization.Encoding.PEM).decode('utf-8'),
            'client_key': private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')
        }

# ============================================================================
# 5. PROVISIONING SERVICE
# ============================================================================

class ProvisioningService:
    """
    Hauptservice für das Device Provisioning
    Empfängt Requests, generiert Credentials, sendet Responses
    """
    
    def __init__(self):
        """Initialisiert Datenbank, Zertifikatsmanager und MQTT Verbindung"""
        self.db = DatabaseManager()
        self.cert_manager = CertificateManager()
        self.setup_mqtt()

    def generate_mqtt_password(self, length=24):
        """
        Generiert ein sicheres, zufälliges Passwort für MQTT
        
        @param length: Länge des Passworts (Standard: 24 Zeichen)
        @return: Zufälliges Passwort mit Buchstaben, Zahlen und Sonderzeichen
        """
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(chars) for _ in range(length))

    def hash_password(self, password):
        """
        Hasht das Passwort für die Datenbank (SHA256)
        Passwörter werden nie im Klartext gespeichert!
        
        @param password: Klartext-Passwort
        @return: SHA256 Hash als Hex-String
        """
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
        """
        Callback wenn MQTT Verbindung hergestellt wurde
        Abonniert das Provisioning Request Topic
        """
        if rc == 0:
            logger.info("✅ MQTT verbunden")
            # Abonniere das vereinfachte Provisioning Topic
            client.subscribe("provisioning/request")
            logger.info("  Abonniert: provisioning/request ")
        else:
            logger.error(f"❌ MQTT Fehler: {rc}")

    def on_message(self, client, userdata, msg):
        """
        Callback wenn eine MQTT Nachricht empfangen wird
        Verarbeitet Provisioning Requests von ESP8266 Geräten
        
        Erwartetes JSON Format:
        {
            "device_id": "esp8266_ECFABC5F0",
            "mac_address": "EC:FA:BC:5F:0A:DF",
            "firmware_version": "1.0.0"
        }
        """
        device_id = None
        
        try:
            # JSON Payload parsen
            payload = json.loads(msg.payload.decode())
            device_id = payload.get('device_id')
            mac_address = payload.get('mac_address')
            firmware_version = payload.get('firmware_version', 'unknown')

            logger.info(f" Provisioning Request von {device_id} (MAC: {mac_address})")

            # Stelle sicher dass die Datenbankverbindung sauber ist
            # Bei jedem Request eine neue Verbindung?
            if self.db.conn.closed:
                self.db.connect()
            
            # Oder: Rollback einer fehlerhaften Transaktion
            try:
                self.db.conn.rollback()
            except:
                pass

            # ==========================================
            # 1. PRÜFE OB GERÄT BEREITS EXISTIERT
            # ==========================================
            existing = self.db.device_exists(mac_address)
            if existing:
                logger.info(f" Bekanntes Gerät!: {existing[0]}")
                self.send_response(device_id, status="already_provisioned")
                return

            # ==========================================
            # 2. GENERIERE NEUE CREDENTIALS
            # ==========================================
            mqtt_password = self.generate_mqtt_password()          # Zufälliges Passwort
            mqtt_username = f"device_{device_id[:16]}" if device_id else f"device_{mac_address[:16]}"
            password_hash = self.hash_password(mqtt_password)      # Hash für DB

            # ==========================================
            # 3. GENERIERE TLS ZERTIFIKATE (optional für mTLS)
            # ==========================================
            certs = None
            try:
                private_key, cert = self.cert_manager.generate_client_certificate(device_id, mac_address)
                certs = self.cert_manager.format_certificates(private_key, cert)
            except Exception as e:
                # Fehler bei Zertifikatsgenerierung ist nicht kritisch
                # Gerät kann sich auch mit Benutzername/Passwort authentifizieren
                logger.warning(f" Zertifikatsgenerierung fehlgeschlagen: {e}")

            # ==========================================
            # 4. IN DATENBANK SPEICHERN
            # ==========================================
            self.db.register_device(device_id, mac_address, mqtt_username, password_hash)

            # ==========================================
            # 5. RESPONSE MIT CREDENTIALS SENDEN
            # ==========================================
            self.send_response(device_id, status="success", mqtt_username=mqtt_username,
                               mqtt_password=mqtt_password, certificates=certs)
            logger.info(f"✅ Gerät {device_id} erfolgreich provisioniert")

        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON Parse Fehler: {e}")
            if device_id:
                self.send_response(device_id, status="error", message=f"Invalid JSON: {e}")
                
        except Exception as e:
            logger.error(f"❌ Provisioning Fehler: {e}")
            if device_id:
                self.send_response(device_id, status="error", message=str(e))

    def send_response(self, device_id, status, mqtt_username=None, mqtt_password=None,
                      certificates=None, message=None):
        """
        Sendet die Provisioning Response an das Gerät
        
        @param device_id: Eindeutige Geräte-ID
        @param status: "success", "error", oder "already_provisioned"
        @param mqtt_username: Generierter MQTT Benutzername (nur bei success)
        @param mqtt_password: Generiertes MQTT Passwort (nur bei success)
        @param certificates: TLS Zertifikate (optional, für mTLS)
        @param message: Fehlermeldung (nur bei error)
        """
        response = {"status": status}
        
        # Bei Erfolg: Füge MQTT Credentials hinzu
        if mqtt_username:
            response["mqtt_username"] = mqtt_username
            response["mqtt_password"] = mqtt_password
            response["mqtt_broker"] = MQTT_BROKER_ADDRESS
            response["mqtt_port"] = 8883                 # TLS Port für ESP8266
            
        # Füge Zertifikate hinzu (falls vorhanden)
        if certificates:
            response["certificates"] = certificates
            
        # Füge Fehlermeldung hinzu (falls vorhanden)
        if message:
            response["message"] = message

        # Vereinfachtes Response Topic (ohne device_id im Topic)
        topic = "provisioning/response"
        self.mqtt_client.publish(topic, json.dumps(response))
        logger.info(f" Response gesendet an {topic}")

# ============================================================================
# 6. MAIN
# ============================================================================

if __name__ == "__main__":
    """
    Hauptprogramm - Startet den Provisioning Service
    Läuft endlos bis Ctrl+C gedrückt wird
    """
    service = ProvisioningService()
    try:
        # Endlosschleife - Service läuft im Hintergrund (MQTT Loop)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info(" Provisioning Service gestoppt")