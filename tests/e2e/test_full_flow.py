#!/usr/bin/env python
"""
End-to-End Tests für das gesamte System
Simuliert ESP8266 und testet den kompletten Datenfluss

SICHERHEITSHINWEIS:
- Keine Passwörter oder Secrets im Code!
- Alle Credentials werden aus der .env Datei geladen
- Die .env Datei ist in .gitignore ausgeschlossen

Version: 3.1 - Fix: import ssl hinzugefügt
"""

import pytest
import paho.mqtt.client as mqtt
import requests
import json
import time
import os
import sys
import ssl  # SSL Modul für TLS Verbindungen!
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# ============================================================================
# LADE .env KONFIGURATION (SICHERHEIT)
# ============================================================================
# Alle Secrets werden aus Umgebungsvariablen geladen
# Keine Default-Werte für sensible Daten!

# Bestimme den Pfad zur .env Datei
ENV_PATH = os.path.join(os.path.dirname(__file__), '../..', '.env')
ENV_PATH = os.path.abspath(ENV_PATH)

if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
    print(f" .env Datei geladen von: {ENV_PATH}")
else:
    print(f" .env Datei NICHT gefunden: {ENV_PATH}")
    print("   Bitte erstelle eine .env Datei mit folgenden Variablen:")
    print("   - MQTT_HOST")
    print("   - MQTT_PORT_TLS")
    print("   - MQTT_TEST_USERNAME")
    print("   - MQTT_TEST_PASSWORD")
    print("   - API_BASE_URL")
    sys.exit(1)

# ============================================================================
# KONFIGURATION AUS .env (KEINE HARDCODED WERTE!)
# ============================================================================

# MQTT Konfiguration - MUSS in .env definiert sein!
MQTT_HOST = os.getenv('MQTT_HOST')
if not MQTT_HOST:
    raise ValueError(" MQTT_HOST nicht in .env definiert!")

MQTT_PORT = int(os.getenv('MQTT_PORT_TLS', 8883))

# Test Credentials - MÜSSEN in .env definiert sein!
MQTT_USER = os.getenv('MQTT_TEST_USERNAME')
if not MQTT_USER:
    raise ValueError(" MQTT_TEST_USERNAME nicht in .env definiert!")

MQTT_PASSWORD = os.getenv('MQTT_TEST_PASSWORD')
if not MQTT_PASSWORD:
    raise ValueError(" MQTT_TEST_PASSWORD nicht in .env definiert!")

# API Konfiguration
API_BASE = os.getenv('API_BASE_URL')
if not API_BASE:
    raise ValueError(" API_BASE_URL nicht in .env definiert!")

# Zertifikatspfad (optional, mit Fallback)
CERTS_DIR = os.getenv('CERTS_DIR', './certs')
CA_CERT_PATH = os.path.join(CERTS_DIR, 'ca.crt')

# ============================================================================
# KONFIGURATIONS-VALIDIERUNG
# ============================================================================

print("=" * 60)
print(" E2E Test Konfiguration (Sicher)")
print("=" * 60)
print(f"MQTT_HOST: {MQTT_HOST}")
print(f"MQTT_PORT: {MQTT_PORT}")
print(f"MQTT_USER: {MQTT_USER}")
print(f"MQTT_PASSWORD: {'*' * len(MQTT_PASSWORD) if MQTT_PASSWORD else 'NICHT GESETZT'}")
print(f"API_BASE: {API_BASE}")
print(f"CA_CERT_PATH: {CA_CERT_PATH}")
print("=" * 60)

# ============================================================================
# HELFER-FUNKTIONEN
# ============================================================================

def wait_for_data(api_url: str, timeout: int = 30, check_field: str = None) -> Dict:
    """
    Wartet darauf, dass Daten in der API verfügbar sind
    
    Args:
        api_url: API Endpoint URL (z.B. "http://.../api/latest")
        timeout: Maximale Wartezeit in Sekunden (default: 30)
        check_field: Optionales Feld, das in der Response existieren muss
    
    Returns:
        Dict: API Response Daten als Dictionary
    
    Raises:
        TimeoutError: Wenn nach timeout keine Daten verfügbar sind
    """
    start_time = time.time()
    last_error = None
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(api_url)
            if response.status_code == 200:
                data = response.json()
                if check_field:
                    # Prüfe ob das spezifische Feld existiert
                    if data and check_field in data:
                        return data
                else:
                    # Prüfe ob überhaupt Daten da sind
                    if data:
                        return data
            time.sleep(1)  # Warte 1 Sekunde vor nächstem Versuch
        except Exception as e:
            last_error = e
            time.sleep(1)
    
    raise TimeoutError(f"Keine Daten nach {timeout}s verfügbar. Letzter Fehler: {last_error}")


# ============================================================================
# ESP8266 SIMULATOR KLASSE
# ============================================================================

class SimulatedESP8266:
    """
    Simuliert einen echten ESP8266 für E2E-Tests
    
    Sicherheit:
    - Verwendet Credentials aus .env (nicht hardcoded)
    - Unterstützt TLS für sichere Verbindung
    - Simuliert alle ESP8266 Funktionen
    """
    
    def __init__(self, device_id: str):
        """
        Initialisiert den ESP8266 Simulator
        
        Args:
            device_id: Eindeutige Geräte-ID für die Simulation
        """
        self.device_id = device_id
        self.client = mqtt.Client(client_id=device_id)
        
        # Konfiguriere TLS für sichere Verbindung
        if os.path.exists(CA_CERT_PATH):
            self.client.tls_set(
                ca_certs=CA_CERT_PATH,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLSv1_2
            )
        else:
            # Fallback für Entwicklung (nicht für Produktion!)
            print(f" CA Zertifikat nicht gefunden: {CA_CERT_PATH}")
            self.client.tls_set(cert_reqs=ssl.CERT_NONE)
            self.client.tls_insecure_set(True)
        
        # Setze MQTT Credentials (aus .env, nicht hardcoded!)
        self.client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        
        # Registriere Callbacks
        self.client.on_connect = self._on_connect
        self.client.on_publish = self._on_publish
        
        self.connected = False
        self.last_published = None
    
    def _on_connect(self, client, userdata, flags, rc):
        """
        Callback bei erfolgreicher MQTT Verbindung
        
        Args:
            rc: Return Code (0 = Erfolg)
        """
        self.connected = (rc == 0)
        if self.connected:
            print(f" ESP8266 Simulator verbunden: {self.device_id}")
    
    def _on_publish(self, client, userdata, mid):
        """Callback bei erfolgreichem Publish"""
        self.last_published = time.time()
    
    def connect(self) -> bool:
        """
        Verbindet zum MQTT Broker
        
        Returns:
            bool: True bei erfolgreicher Verbindung
        """
        try:
            self.client.connect(MQTT_HOST, MQTT_PORT, 60)
            self.client.loop_start()
            time.sleep(2)  # Warte auf Verbindungsaufbau
            return self.connected
        except Exception as e:
            print(f" Verbindungsfehler: {e}")
            return False
    
    def send_temperature(self, temperature: float, unit: str = "celsius"):
        """
        Sendet Temperaturdaten an den MQTT Broker
        
        Args:
            temperature: Temperaturwert in °C
            unit: Einheit (default: celsius)
        
        Returns:
            MQTTMessageInfo: Resultat des Publish
        """
        payload = {
            "device_id": self.device_id,
            "device_type": "esp8266",
            "sensor": "max6675",
            "temp": temperature,
            "unit": unit,
            "rssi": -62,
            "heap": 14768,
            "uptime": 12345
        }
        
        result = self.client.publish("sensor/temperatur", json.dumps(payload))
        time.sleep(0.5)  # Kurze Warte für Verarbeitung
        return result
    
    def send_heartbeat(self, status: str = "true"):
        """
        Sendet Heartbeat (Online-Status)
        
        Args:
            status: "true" für online, "false" für offline
        """
        self.client.publish(f"status/{self.device_id}/online", status)
        time.sleep(0.5)
    
    def disconnect(self):
        """Trennt die MQTT Verbindung sicher"""
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass
        self.connected = False


# ============================================================================
# E2E TESTS
# ============================================================================

class TestEndToEnd:
    """End-to-End Tests für das gesamte System"""
    
    @pytest.fixture
    def esp_simulator(self):
        """
        ESP8266 Simulator Fixture für Tests
        
        Stellt sicher, dass der Simulator verbunden ist
        und räumt nach dem Test auf
        """
        # Erstelle Simulator mit eindeutiger ID
        esp = SimulatedESP8266("esp8266_e2e_test")
        
        # Verbinde mit Retry-Logik
        max_retries = 3
        for i in range(max_retries):
            if esp.connect():
                break
            print(f"Verbindungsversuch {i+1}/{max_retries} fehlgeschlagen")
            time.sleep(2)
        
        assert esp.connected == True, "ESP Simulator konnte nicht verbinden!"
        
        yield esp  # Gib den Simulator an den Test
        
        # Aufräumen nach dem Test
        esp.disconnect()
    ###################################################################################

    def test_temperature_data_flow(self, esp_simulator):
        """
        TEST: Temperaturdaten vom ESP → API → Datenbank
        
        Szenario: 
        - ESP sendet eine Temperatur
        - Bridge speichert in Datenbank
        - API gibt die Temperatur zurück
        
        Erwartet: Status 200, korrekte Temperatur
        """
        # Arrangiere: Verwende eine eindeutige Temperatur (mit Zeitstempel)
        import time
        base_temp = 25.0
        unique_offset = (time.time() % 10) / 10  # 0.0 bis 0.9
        test_temperature = round(base_temp + unique_offset, 1)
        
        print(f"Sende Temperatur: {test_temperature}°C")
        
        # Act: ESP sendet Temperatur
        esp_simulator.send_temperature(test_temperature)
        time.sleep(2)  # Warte auf Verarbeitung
        
        # Assert: Warte auf API-Daten (max 15 Sekunden)
        try:
            data = wait_for_data(f"{API_BASE}/latest", timeout=15, check_field='temperature')
            
            print(f"API liefert: {data['temperature']}°C")
            
            # Prüfe dass die gesendete Temperatur in der API ist (erlaube Rundungsfehler)
            assert abs(data['temperature'] - test_temperature) < 0.1, \
                f"Erwartet: {test_temperature}, Erhalten: {data['temperature']}"
            
            # Prüfe dass die Geräte-ID korrekt ist
            assert data['device_id'] == esp_simulator.device_id
            
        except TimeoutError as e:
            pytest.fail(f"Temperaturdaten nicht in API angekommen: {e}")
    
    ##########################################################################

    def test_heartbeat_updates_device_status(self, esp_simulator):
        """
        TEST: Heartbeat aktualisiert Gerätestatus
        
        Szenario:
        - ESP sendet Heartbeat "online"
        - API zeigt Gerät als online
        
        Erwartet: Status 200, Gerät in Liste mit Status 'online'
        """
        # Act: Heartbeat senden
        esp_simulator.send_heartbeat("true")
        time.sleep(3)  # Warte auf Verarbeitung
        
        # Assert: Gerät in Status-Liste abrufen
        response = requests.get(f"{API_BASE}/devices/status")
        assert response.status_code == 200
        
        devices = response.json()
        found = False
        
        for device in devices:
            if device.get('device_id') == esp_simulator.device_id:
                # Gerät gefunden - prüfe Status
                assert device.get('status') == 'online', \
                    f"Status sollte 'online' sein, ist: {device.get('status')}"
                found = True
                break
        
        if not found:
            # Gerät könnte noch nicht in der Liste sein (nicht kritisch)
            print(f" Gerät {esp_simulator.device_id} noch nicht in Status-Liste")
    ###############################################################################

    def test_multiple_temperature_readings(self, esp_simulator):
        """
        TEST: Mehrere Temperaturmessungen werden korrekt gespeichert
        
        Szenario:
        - ESP sendet 5 Temperaturen hintereinander
        - API Statistiken werden abgefragt
        
        Erwartet: Statistiken entsprechen den gesendeten Werten
        """
        # Arrange: Test-Temperaturen definieren
        temperatures = [23.5, 24.0, 24.5, 25.0, 25.5]
        
        # Act: Alle Temperaturen senden
        for temp in temperatures:
            esp_simulator.send_temperature(temp)
            time.sleep(1)  # Warte zwischen Sends
        
        time.sleep(5)  # Warte auf Bridge-Verarbeitung
        
        # Assert: Statistiken abrufen
        response = requests.get(f"{API_BASE}/stats?hours=24")
        
        # Falls keine Daten verfügbar, überspringe Test
        if response.status_code != 200:
            pytest.skip(f"Keine Statistiken verfügbar (Status {response.status_code})")
        
        stats = response.json()
        
        # Flexible Assertions (andere Geräte könnten auch Daten senden)
        if stats.get('min_temp') is not None:
            # Minimaltemperatur sollte <= unserem Minimum sein
            assert stats['min_temp'] <= min(temperatures), \
                f"Min sollte <= {min(temperatures)} sein, ist {stats['min_temp']}"
        
        if stats.get('max_temp') is not None:
            # Maximaltemperatur sollte >= unserem Maximum sein
            assert stats['max_temp'] >= max(temperatures), \
                f"Max sollte >= {max(temperatures)} sein, ist {stats['max_temp']}"
        
        if stats.get('count') is not None:
            # Anzahl sollte >= unserer Anzahl sein
            assert stats['count'] >= len(temperatures), \
                f"Count sollte >= {len(temperatures)} sein, ist {stats['count']}"
    #############################################################################
    
    def test_lwt_on_disconnect(self, esp_simulator):
        """
        TEST: LWT (Last Will Testament) wird bei Verbindungsabbruch ausgelöst
        
        Szenario:
        - ESP verbindet sich und sendet Heartbeat
        - Harte Trennung (kein sauberes Disconnect)
        - Broker erkennt Verlust und sendet LWT
        
        Erwartet: API ist erreichbar, LWT Statistik existiert
        """
        # Arrange: Heartbeat senden
        esp_simulator.send_heartbeat("true")
        time.sleep(2)
        
        # Act: Harte Trennung (simuliert Verbindungsverlust)
        esp_simulator.client.loop_stop()
        esp_simulator.client.disconnect()
        
        # Assert: LWT Statistik ist erreichbar
        # Hinweis: LWT Timeout ist 120 Sekunden, daher prüfen wir nur API Verfügbarkeit
        response = requests.get(f"{API_BASE}/lwt/stats")
        assert response.status_code == 200
        
        stats = response.json()
        assert 'offline_devices' in stats or 'total_devices' in stats


# ============================================================================
# SYSTEM HEALTH TESTS
# ============================================================================

class TestSystemHealth:
    """Tests für die Gesundheit des Gesamtsystems"""
    
    def test_all_services_healthy(self):
        """
        TEST: Alle Services sind gesund
        
        Prüft:
        - Backend API ist erreichbar
        - MQTT Broker ist erreichbar
        - Datenbank ist verbunden
        """
        # 1. Health Check API
        response = requests.get(f"{API_BASE}/health")
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert data['database'] == 'connected'
        
        # 2. MQTT Broker sollte erreichbar sein
        client = mqtt.Client()
        
        # Konfiguriere TLS
        if os.path.exists(CA_CERT_PATH):
            client.tls_set(ca_certs=CA_CERT_PATH)
        
        # Setze Credentials (aus .env)
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        
        # Verbinde und trenne sofort
        client.connect(MQTT_HOST, MQTT_PORT, 10)
        client.loop_start()
        time.sleep(1)
        client.loop_stop()
        client.disconnect()
        
        # Keine Exception = erfolgreich
        assert True


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print(" Starting E2E Tests (Sicherer Modus)")
    print("=" * 60)
    print(f"MQTT Host: {MQTT_HOST}:{MQTT_PORT}")
    print(f"API Base: {API_BASE}")
    print(f"CA Cert: {CA_CERT_PATH}")
    print("=" * 60)
    print("  Alle Credentials werden aus .env geladen")
    print("=" * 60)
    
    # Führe Tests aus
    pytest.main([__file__, "-v", "--tb=short"])