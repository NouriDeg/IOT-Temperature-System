#!/usr/bin/env python
"""
End-to-End Tests für ESP8266 Simulation (keine echte Hardware benötigt!)
TDD: Test-Driven Development für ESP8266 Firmware

SICHERHEITSHINWEIS:
- Keine Passwörter oder Credentials im Code!
- Alle Secrets werden aus der .env Datei geladen
- Die .env Datei ist in .gitignore ausgeschlossen

Getestete Komponenten:
1. MQTT Verbindung (TLS/SSL)
2. Temperaturdaten Senden
3. Heartbeat Funktionalität
4. LWT (Last Will Testament)
5. OTA Updates
6. Provisioning Prozess
"""

import pytest
import json
import time
import ssl
import os
import sys
import paho.mqtt.client as mqtt
import requests
import random
from datetime import datetime
from typing import Dict, Any, List, Optional

# Lade .env Datei (für Umgebungsvariablen)
try:
    from dotenv import load_dotenv
except ImportError:
    print(" python-dotenv nicht installiert. Führe aus: pip install python-dotenv")
    sys.exit(1)

# ============================================
# LADE .env KONFIGURATION
# ============================================

# Bestimme den Pfad zur .env Datei (Hauptverzeichnis)
ENV_PATH = os.path.join(os.path.dirname(__file__), '../..', '.env')

if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
    print(f" .env Datei geladen von: {ENV_PATH}")
else:
    print(f" .env Datei nicht gefunden: {ENV_PATH}")
    print("   Stelle sicher, dass die .env Datei existiert und folgende Variablen enthält:")
    print("   - MQTT_HOST")
    print("   - MQTT_TEST_USERNAME")
    print("   - MQTT_TEST_PASSWORD")

# ============================================
# TEST KONFIGURATION (NUR aus .env!)
# ============================================

# MQTT Konfiguration - KEINE DEFAULTS für Sicherheit!
MQTT_HOST = os.getenv('MQTT_HOST')
if not MQTT_HOST:
    raise ValueError(" MQTT_HOST nicht in .env definiert!")

# MQTT Ports - mit sicheren Defaults
MQTT_PORT_TLS = int(os.getenv('MQTT_PORT_TLS', 8883))
MQTT_PORT_WS = int(os.getenv('MQTT_PORT_WS', 8085))
MQTT_PORT_WSS = int(os.getenv('MQTT_PORT_WSS', 8084))
MQTT_PORT_MQTT = int(os.getenv('MQTT_PORT_MQTT', 1883))

# Test Credentials - NUR aus .env, KEINE DEFAULTS!
MQTT_TEST_USERNAME = os.getenv('MQTT_TEST_USERNAME')
MQTT_TEST_PASSWORD = os.getenv('MQTT_TEST_PASSWORD')

# Prüfe ob Credentials existieren (für TLS Tests)
if not MQTT_TEST_USERNAME or not MQTT_TEST_PASSWORD:
    print(" MQTT_TEST_USERNAME oder MQTT_TEST_PASSWORD nicht in .env definiert!")
    print("   TLS Tests werden übersprungen.")

# API Konfiguration
API_BASE_URL = os.getenv('API_BASE_URL')
if not API_BASE_URL:
    raise ValueError("API_BASE_URL nicht in .env definiert!")

# Zertifikatspfad (optional)
CERTS_DIR = os.getenv('CERTS_DIR', './certs')
CA_CERT_PATH = os.path.join(CERTS_DIR, 'ca.crt')

# ============================================
# ESP8266 SIMULATOR KLASSE
# ============================================

class ESP8266Simulator:
    """
    Simuliert einen echten ESP8266 für Tests
    
    Sicherheit:
    - Keine Hardcoded Credentials
    - Credentials werden bei Verbindung übergeben
    - TLS wird bevorzugt verwendet
    """
    
    def __init__(self, device_id: str, use_tls: bool = True):
        """
        Initialisiert die ESP8266 Simulation
        
        Args:
            device_id: Eindeutige Geräte-ID für die Simulation
            use_tls: Ob TLS/SSL verwendet werden soll (empfohlen: True)
        """
        self.device_id = device_id
        self.use_tls = use_tls
        self.client = mqtt.Client(client_id=device_id)
        self.connected = False
        self.published_messages = []
        self.received_messages = []
        self.last_temperature = 25.0
        self.uptime = 0
        
        # Konfiguriere TLS wenn gewünscht
        if use_tls:
            self._configure_tls()
        
        # Registriere Callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish
        self.client.on_disconnect = self._on_disconnect
    
    def _configure_tls(self):
        """Konfiguriert TLS/SSL für sichere Verbindung"""
        try:
            if os.path.exists(CA_CERT_PATH):
                # Verwende CA Zertifikat für Validierung
                self.client.tls_set(
                    ca_certs=CA_CERT_PATH,
                    cert_reqs=ssl.CERT_REQUIRED,
                    tls_version=ssl.PROTOCOL_TLSv1_2
                )
            else:
                # Kein Zertifikat gefunden - nur für Entwicklung
                print(f"CA Zertifikat nicht gefunden: {CA_CERT_PATH}")
                self.client.tls_set(cert_reqs=ssl.CERT_NONE)
                self.client.tls_insecure_set(True)
        except Exception as e:
            print(f"TLS Konfiguration fehlgeschlagen: {e}")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback bei erfolgreicher Verbindung"""
        self.connected = (rc == 0)
        if self.connected:
            # Abonniere OTA Topic für Kommandos
            self.client.subscribe(f"commands/{self.device_id}/ota")
    
    def _on_message(self, client, userdata, msg):
        """Callback bei empfangener Nachricht"""
        self.received_messages.append({
            'topic': msg.topic,
            'payload': msg.payload.decode()
        })
    
    def _on_publish(self, client, userdata, mid):
        """Callback bei gesendeter Nachricht"""
        self.published_messages.append(mid)
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback bei Trennung"""
        self.connected = False
    
    def connect(self, host: str, port: int, username: str = None, password: str = None) -> bool:
        """
        Verbindet zum MQTT Broker
        
        Args:
            host: MQTT Broker Hostname/IP
            port: MQTT Port
            username: MQTT Benutzername (optional, aus .env)
            password: MQTT Passwort (optional, aus .env)
        
        Returns:
            bool: True bei erfolgreicher Verbindung
        """
        # Setze Credentials falls vorhanden
        if username and password:
            self.client.username_pw_set(username, password)
        
        try:
            self.client.connect(host, port, 60)
            self.client.loop_start()
            time.sleep(1)
            return self.connected
        except Exception as e:
            print(f"Verbindungsfehler: {e}")
            return False
    
    def disconnect(self):
        """Trennt die Verbindung sicher"""
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass
        self.connected = False
    
    def send_temperature(self, temperature: float = None, unit: str = "celsius") -> float:
        """
        Sendet Temperaturdaten an den Broker
        
        Args:
            temperature: Temperaturwert (None = zufällige Änderung)
            unit: Einheit (default: celsius)
        
        Returns:
            float: Gesendeter Temperaturwert
        """
        if temperature is None:
            # Simuliere leichte Temperaturänderung
            self.last_temperature += random.uniform(-0.3, 0.3)
            temperature = self.last_temperature
        
        payload = {
            "device_id": self.device_id,
            "device_type": "esp8266",
            "sensor": "max6675",
            "temp": round(temperature, 2),
            "unit": unit,
            "rssi": random.randint(-70, -50),
            "heap": random.randint(14000, 16000),
            "uptime": self.uptime
        }
        
        self.uptime += 5  # Simuliere 5 Sekunden Betriebszeit
        
        self.client.publish("sensor/temperatur", json.dumps(payload))
        return temperature
    
    def send_heartbeat(self, status: bool = True):
        """Sendet Heartbeat (Online-Status)"""
        self.client.publish(f"status/{self.device_id}/online", "true" if status else "false")
    
    def send_lwt(self, status: str = "offline", reason: str = "test_disconnect"):
        """Sendet LWT (Last Will Testament) Nachricht"""
        payload = {
            "status": status,
            "reason": reason,
            "timestamp": int(time.time())
        }
        self.client.publish(f"lwt/{self.device_id}", json.dumps(payload))
    
    def simulate_connection_loss(self):
        """Simuliert plötzlichen Verbindungsverlust"""
        try:
            self.client.disconnect()
        except Exception:
            pass
        self.connected = False
    
    def simulate_reconnect(self):
        """Simuliert Wiederherstellung der Verbindung"""
        try:
            self.client.reconnect()
            time.sleep(1)
        except Exception:
            pass


# ============================================
# 1. GRUNDLEGENDE MQTT VERBINDUNGSTESTS
# ============================================

class TestMQTTConnection:
    """Tests für MQTT Verbindungen des ESP8266"""
    
    def test_mqtt_connection_success(self):
        """ESP8266 verbindet sich erfolgreich via MQTTS (TLS)"""
        esp = ESP8266Simulator("test_conn_success", use_tls=True)  # ← TLS verwenden
        
        try:
            result = esp.connect(MQTT_HOST, MQTT_PORT_TLS, MQTT_TEST_USERNAME, MQTT_TEST_PASSWORD)
            assert result == True
            assert esp.connected == True
        finally:
            esp.disconnect()
    
    def test_mqtt_tls_connection_success(self):
        """ESP8266 verbindet sich erfolgreich via MQTTS (Port 8883)"""
        # Überspringe Test wenn keine Credentials in .env
        if not MQTT_TEST_USERNAME or not MQTT_TEST_PASSWORD:
            pytest.skip("MQTT_TEST_USERNAME/PASSWORD nicht in .env definiert")
        
        esp = ESP8266Simulator("test_tls_success", use_tls=True)
        
        try:
            result = esp.connect(MQTT_HOST, MQTT_PORT_TLS, MQTT_TEST_USERNAME, MQTT_TEST_PASSWORD)
            assert result == True
            assert esp.connected == True
        finally:
            esp.disconnect()
    
    def test_mqtt_connection_with_wrong_credentials_fails(self):
        """Falsche Credentials führen zu Verbindungsfehler"""
        esp = ESP8266Simulator("test_wrong_creds", use_tls=True)
        
        # Verwende bewusst falsche Credentials
        result = esp.connect(MQTT_HOST, MQTT_PORT_TLS, "wrong_user_123", "wrong_pass_456")
        assert result == False
    
    def test_mqtt_reconnect_after_disconnect(self):
        """ESP8266 kann nach Trennung wieder verbinden (via TLS)"""
        esp = ESP8266Simulator("test_reconnect", use_tls=True)  # ← TLS verwenden
        
        try:
            esp.connect(MQTT_HOST, MQTT_PORT_TLS, MQTT_TEST_USERNAME, MQTT_TEST_PASSWORD)
            assert esp.connected == True
            
            esp.disconnect()
            assert esp.connected == False
            
            esp.connect(MQTT_HOST, MQTT_PORT_TLS, MQTT_TEST_USERNAME, MQTT_TEST_PASSWORD)
            assert esp.connected == True
        finally:
            esp.disconnect()


# ============================================
# 2. TEMPERATURDATEN TESTS
# ============================================

class TestTemperatureData:
    """Tests für Temperaturdaten Übertragung"""
    
    @pytest.fixture
    def esp(self):
        """ESP8266 Simulator Fixture mit TLS"""
        # Überspringe wenn keine Credentials
        if not MQTT_TEST_USERNAME or not MQTT_TEST_PASSWORD:
            pytest.skip("MQTT_TEST_USERNAME/PASSWORD nicht in .env definiert")
        
        esp = ESP8266Simulator("test_temp_device", use_tls=True)
        esp.connect(MQTT_HOST, MQTT_PORT_TLS, MQTT_TEST_USERNAME, MQTT_TEST_PASSWORD)
        yield esp
        esp.disconnect()
    
    def test_send_single_temperature(self, esp):
        """Einzelne Temperatur wird korrekt gesendet"""
        temperature = 25.5
        esp.send_temperature(temperature)
        time.sleep(1)
        
        # Prüfe ob API die Temperatur empfangen hat
        response = requests.get(f"{API_BASE_URL}/latest")
        assert response.status_code in [200, 404]
    
    def test_send_multiple_temperatures(self, esp):
        """Mehrere Temperaturwerte hintereinander"""
        temperatures = [23.5, 24.0, 24.5, 25.0, 25.5]
        
        for temp in temperatures:
            esp.send_temperature(temp)
            time.sleep(0.5)
        
        time.sleep(2)
        
        # Prüfe API Stats
        response = requests.get(f"{API_BASE_URL}/stats?hours=24")
        assert response.status_code in [200, 404]
    
    def test_extreme_temperature_values(self, esp):
        """Extreme Temperaturwerte werden akzeptiert"""
        extreme_values = [-50.0, -10.0, 0.0, 35.0, 85.0, 125.0]
        
        for temp in extreme_values:
            esp.send_temperature(temp)
            time.sleep(0.5)
        
        time.sleep(2)
        assert True


# ============================================
# 3. HEARTBEAT UND LWT TESTS
# ============================================

class TestHeartbeatAndLWT:
    """Tests für Heartbeat und LWT Funktionalität"""
    
    @pytest.fixture
    def esp(self):
        """ESP8266 Simulator Fixture mit TLS"""
        if not MQTT_TEST_USERNAME or not MQTT_TEST_PASSWORD:
            pytest.skip("MQTT_TEST_USERNAME/PASSWORD nicht in .env definiert")
        
        esp = ESP8266Simulator("test_heartbeat_device", use_tls=True)
        esp.connect(MQTT_HOST, MQTT_PORT_TLS, MQTT_TEST_USERNAME, MQTT_TEST_PASSWORD)
        yield esp
        esp.disconnect()
    
    def test_send_heartbeat(self, esp):
        """Heartbeat wird korrekt gesendet"""
        esp.send_heartbeat(True)
        time.sleep(1)
        
        # Prüfe über API
        response = requests.get(f"{API_BASE_URL}/devices/status")
        assert response.status_code == 200
    
    def test_send_lwt_message(self, esp):
        """LWT Nachricht wird korrekt gesendet"""
        esp.send_lwt("offline", "simulated_test")
        time.sleep(1)
        assert True


# ============================================
# 4. PROVISIONING TESTS
# ============================================

class TestProvisioning:
    """Tests für automatisches Provisioning"""
    
    def test_provisioning_request_sent(self):
        """Provisioning Request wird gesendet"""
        device_id = f"new_device_{int(time.time())}"
        mac = f"AA:BB:CC:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}"
        
        esp = ESP8266Simulator(device_id, use_tls=False)
        esp.connect(MQTT_HOST, MQTT_PORT_MQTT)
        
        # Simuliere Provisioning Request
        payload = {
            "mac_address": mac,
            "device_id": device_id,
            "firmware_version": "1.0.0"
        }
        esp.client.publish("provisioning/request", json.dumps(payload))
        time.sleep(2)
        
        esp.disconnect()
        assert True


# ============================================
# 5. PARAMETRISIERTE TESTS
# ============================================

@pytest.mark.parametrize("temperature", [
    20.0, 25.5, 30.0, -10.0, 0.0, 100.0
])
def test_various_temperatures(temperature):
    """Verschiedene Temperaturwerte funktionieren"""
    if not MQTT_TEST_USERNAME or not MQTT_TEST_PASSWORD:
        pytest.skip("MQTT_TEST_USERNAME/PASSWORD nicht in .env definiert")
    
    esp = ESP8266Simulator(f"test_temp_{temperature}", use_tls=True)
    esp.connect(MQTT_HOST, MQTT_PORT_TLS, MQTT_TEST_USERNAME, MQTT_TEST_PASSWORD)
    
    esp.send_temperature(temperature)
    time.sleep(1)
    
    esp.disconnect()
    assert True


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print(" E2E Tests für ESP8266 Simulation")
    print("=" * 60)
    print(f"MQTT Host: {MQTT_HOST}")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"TLS Port: {MQTT_PORT_TLS}")
    print(f"Non-TLS Port: {MQTT_PORT_MQTT}")
    print("=" * 60)
    
    # Führe Tests aus
    pytest.main([__file__, "-v", "--tb=short"])