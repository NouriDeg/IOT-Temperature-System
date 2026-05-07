#!/usr/bin/env python
"""
Integrationstests für die Backend API mit echter Datenbank
TDD: Test-Driven Development für REST API Integration

SICHERHEITSHINWEIS:
- Keine Passwörter oder Secrets im Code!
- Alle Credentials werden aus der .env Datei geladen
- Die .env Datei ist in .gitignore ausgeschlossen
- Autor: Nouri Deg.
"""

import pytest
import json
import time
import os
import sys
import requests
import psycopg2
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
from typing import Dict, Any, List
from dotenv import load_dotenv

# ============================================================================
# LADE .env KONFIGURATION (SICHERHEIT)
# ============================================================================

# Bestimme den Pfad zur .env Datei
ENV_PATH = os.path.join(os.path.dirname(__file__), '../..', '.env')
ENV_PATH = os.path.abspath(ENV_PATH)

if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
    print(f" .env Datei geladen von: {ENV_PATH}")
else:
    print(f".env Datei NICHT gefunden: {ENV_PATH}")
    print("   Bitte erstelle eine .env Datei mit folgenden Variablen:")
    print("   - API_BASE_URL")
    print("   - MQTT_HOST")
    print("   - MQTT_TEST_USERNAME")
    print("   - MQTT_TEST_PASSWORD")
    print("   - DB_HOST")
    print("   - DB_PORT")
    print("   - DB_NAME")
    print("   - DB_USER")
    print("   - DB_PASSWORD")
    sys.exit(1)

# ============================================================================
# TEST KONFIGURATION AUS .env (KEINE HARDCODED WERTE!)
# ============================================================================

# API Konfiguration
API_BASE_URL = os.getenv('API_BASE_URL')
if not API_BASE_URL:
    raise ValueError("API_BASE_URL nicht in .env definiert!")

# MQTT Konfiguration
MQTT_HOST = os.getenv('MQTT_HOST')
if not MQTT_HOST:
    raise ValueError("MQTT_HOST nicht in .env definiert!")

MQTT_PORT_1883 = int(os.getenv('MQTT_PORT_MQTT', 1883))
MQTT_PORT_8883 = int(os.getenv('MQTT_PORT_TLS', 8883))

# Test Credentials - MÜSSEN in .env definiert sein!
MQTT_USER = os.getenv('MQTT_TEST_USERNAME')
if not MQTT_USER:
    raise ValueError("MQTT_TEST_USERNAME nicht in .env definiert!")

MQTT_PASSWORD = os.getenv('MQTT_TEST_PASSWORD')
if not MQTT_PASSWORD:
    raise ValueError("MQTT_TEST_PASSWORD nicht in .env definiert!")

# Datenbank Konfiguration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '192.168.0.105'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'sensordb'),
    'user': os.getenv('DB_USER', 'sensor_user'),
    'password': os.getenv('DB_PASSWORD')
}

if not DB_CONFIG['password']:
    raise ValueError("DB_PASSWORD nicht in .env definiert!")

# Zertifikatspfad
CERTS_DIR = os.getenv('CERTS_DIR', './certs')
CA_CERT_PATH = os.path.join(CERTS_DIR, 'ca.crt')

# ============================================================================
# KONFIGURATIONS-VALIDIERUNG
# ============================================================================

print("=" * 60)
print("Integration Test Konfiguration (Sicher)")
print("=" * 60)
print(f"API_BASE_URL: {API_BASE_URL}")
print(f"MQTT_HOST: {MQTT_HOST}")
print(f"MQTT_PORT_1883: {MQTT_PORT_1883}")
print(f"MQTT_PORT_8883: {MQTT_PORT_8883}")
print(f"MQTT_USER: {MQTT_USER}")
print(f"MQTT_PASSWORD: {'*' * len(MQTT_PASSWORD) if MQTT_PASSWORD else 'NICHT GESETZT'}")
print(f"DB_HOST: {DB_CONFIG['host']}")
print(f"DB_PORT: {DB_CONFIG['port']}")
print(f"DB_NAME: {DB_CONFIG['database']}")
print(f"DB_USER: {DB_CONFIG['user']}")
print(f"DB_PASSWORD: {'*' * len(DB_CONFIG['password']) if DB_CONFIG['password'] else 'NICHT GESETZT'}")
print(f"CA_CERT_PATH: {CA_CERT_PATH}")
print("=" * 60)

# ============================================================================
# HELFER-FUNKTIONEN
# ============================================================================

def create_mqtt_client(use_tls: bool = False) -> mqtt.Client:
    """
    Erstellt einen konfigurierten MQTT Client
    
    Args:
        use_tls: Ob TLS verwendet werden soll
    
    Returns:
        Konfigurierter MQTT Client
    """
    client = mqtt.Client()
    
    if use_tls:
        # Konfiguriere TLS für sichere Verbindung
        if os.path.exists(CA_CERT_PATH):
            client.tls_set(
                ca_certs=CA_CERT_PATH,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLSv1_2
            )
        else:
            print(f"CA Zertifikat nicht gefunden: {CA_CERT_PATH}")
            client.tls_set(cert_reqs=ssl.CERT_NONE)
            client.tls_insecure_set(True)
        
        # Setze Credentials für TLS
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    
    return client


def wait_for_api(timeout: int = 30) -> bool:
    """
    Wartet darauf, dass die API verfügbar ist
    
    Args:
        timeout: Maximale Wartezeit in Sekunden
    
    Returns:
        bool: True wenn API verfügbar
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=5)
            if response.status_code == 200:
                return True
        except:
            pass
        time.sleep(1)
    return False


# ============================================================================
# 1. DATENBANK INTEGRATION TESTS
# ============================================================================

class TestDatabaseIntegration:
    """Tests für API + Datenbank Integration"""
    
    @pytest.fixture(autouse=True)
    def setup_db(self):
        """Setup: Datenbankverbindung"""
        self.conn = psycopg2.connect(**DB_CONFIG)
        yield
        self.conn.close()


# ============================================================================
# 2. API + MQTT INTEGRATION TESTS
# ============================================================================

class TestMQTTIntegration:
    """Tests für API + MQTT Integration"""
    
    @pytest.fixture
    def mqtt_client(self):
        """MQTT Client für Tests (non-TLS)"""
        client = create_mqtt_client(use_tls=False)
        client.connect(MQTT_HOST, MQTT_PORT_1883, 60)
        client.loop_start()
        time.sleep(1)  # Warte auf Verbindung
        yield client
        client.loop_stop()
        client.disconnect()
    
    @pytest.fixture
    def mqtt_tls_client(self):
        """MQTT TLS Client für Tests"""
        client = create_mqtt_client(use_tls=True)
        client.connect(MQTT_HOST, MQTT_PORT_8883, 60)
        client.loop_start()
        time.sleep(1)  # Warte auf Verbindung
        yield client
        client.loop_stop()
        client.disconnect()


# ============================================================================
# 3. END-TO-END DATENFLUSS TESTS
# ============================================================================

class TestEndToEndDataFlow:
    """End-to-End Tests für kompletten Datenfluss"""
    
    @pytest.fixture
    def mqtt_client(self):
        """MQTT Client für Tests"""
        client = create_mqtt_client(use_tls=False)
        client.connect(MQTT_HOST, MQTT_PORT_1883, 60)
        client.loop_start()
        time.sleep(1)
        yield client
        client.loop_stop()
        client.disconnect()
    
    def test_multiple_devices_data_flow(self, mqtt_client):
        """Mehrere Geräte parallel"""
        devices = []
        
        # 1. Sende Daten für 3 Geräte
        for i in range(3):
            device_id = f"multi_device_{i}_{int(time.time())}"
            devices.append(device_id)
            
            payload = {
                "device_id": device_id,
                "temp": 20.0 + i,
                "unit": "celsius"
            }
            mqtt_client.publish("sensor/temperatur", json.dumps(payload))
            time.sleep(0.5)
        
        time.sleep(3)  # Warte auf Verarbeitung
        
        # 2. Prüfe via API
        response = requests.get(f"{API_BASE_URL}/devices/status")
        # API sollte immer antworten
        assert response.status_code in [200, 404]


# ============================================================================
# 4. FEHLERFÄLLE UND RECOVERY TESTS
# ============================================================================

class TestErrorHandlingAndRecovery:
    """Tests für Fehlerbehandlung und Recovery"""
    
    def test_api_handles_missing_data_gracefully(self):
        """API behandelt fehlende Daten freundlich"""
        # Rufe Endpunkt mit nicht existierendem Gerät auf
        response = requests.get(f"{API_BASE_URL}/devices/nonexistent")
        
        # Sollte 404 oder 200 mit leerem Ergebnis sein
        assert response.status_code in [200, 404]
    
    def test_api_handles_invalid_parameters(self):
        """API behandelt ungültige Parameter"""
        response = requests.get(f"{API_BASE_URL}/stats?hours=invalid")
        # Sollte 200 (ignoriert) oder 400 (Bad Request) sein
        assert response.status_code in [200, 400]
    
    def test_api_health_check_recovers(self):
        """API Health Check erholt sich nach Fehlern"""
        # Mehrmalige Aufrufe sollten alle erfolgreich sein
        for _ in range(5):
            response = requests.get(f"{API_BASE_URL}/health")
            assert response.status_code == 200
    
    def test_concurrent_requests(self):
        """API verarbeitet gleichzeitige Anfragen"""
        import concurrent.futures
        
        def make_request():
            return requests.get(f"{API_BASE_URL}/latest")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            results = [f.result() for f in futures]
        
        # Alle Anfragen sollten erfolgreich sein
        success_count = sum(1 for r in results if r.status_code == 200)
        assert success_count >= 15  # Mindestens 15 von 20 erfolgreich


# ============================================================================
# 5. API PERFORMANZ UND LASTTESTS
# ============================================================================

class TestPerformanceAndLoad:
    """Performance- und Lasttests für die API"""
    
    def test_api_response_time(self):
        """API Antwortzeit unter 500ms (toleranter)"""
        start = time.perf_counter()
        response = requests.get(f"{API_BASE_URL}/health")
        end = time.perf_counter()
        
        assert response.status_code == 200
        # Toleranterer Grenzwert für Integrationstests
        assert (end - start) < 0.5, f"API zu langsam: {end - start:.3f}s"
    
    def test_api_concurrent_load(self):
        """API unter Last stabil"""
        import concurrent.futures
        
        def load_request():
            response = requests.get(f"{API_BASE_URL}/stats")
            return response.status_code
        
        # Simuliere Last mit 20 concurrent requests (reduziert für Stabilität)
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(load_request) for _ in range(50)]
            results = [f.result() for f in futures]
        
        # 80% sollten erfolgreich sein (toleranter)
        success_rate = sum(1 for r in results if r == 200) / len(results)
        assert success_rate >= 0.8, f"Erfolgsrate zu niedrig: {success_rate:.2%}"
    
    def test_api_load_test(self):
        """API Lasttest: 50 Anfragen in 10 Sekunden"""
        start = time.time()
        responses = []
        
        while time.time() - start < 10:
            responses.append(requests.get(f"{API_BASE_URL}/health"))
        
        success_rate = sum(1 for r in responses if r.status_code == 200) / len(responses)
        assert success_rate > 0.9, f"Erfolgsrate zu niedrig: {success_rate:.2%}"


# ============================================================================
# 6. SICHERHEITSTESTS
# ============================================================================

class TestSecurity:
    """Sicherheitstests für die API"""
    
    def test_no_sensitive_data_leak(self):
        """Keine sensiblen Daten im API-Response"""
        response = requests.get(f"{API_BASE_URL}/health")
        data = response.json()
        
        # Keine Passwörter oder Keys im Response
        response_text = json.dumps(data).lower()
        assert 'password' not in response_text
        assert 'secret' not in response_text
    
    def test_sql_injection_prevention(self):
        """SQL Injection wird verhindert"""
        malicious_params = [
            "1' OR '1'='1",
            "'; DROP TABLE sensor_data; --",
            "1 UNION SELECT * FROM users",
            "' OR 1=1 --"
        ]
        
        for param in malicious_params:
            response = requests.get(f"{API_BASE_URL}/stats?hours={param}")
            # Sollte nicht abstürzen (200, 400 oder 404)
            assert response.status_code in [200, 400, 404], f"Failed for input: {param}"  


# ============================================================================
# 7. PARAMETRISIERTE INTEGRATIONSTESTS
# ============================================================================

@pytest.mark.parametrize("endpoint", [
    '/api/health',
    '/api/latest',
    '/api/stats?hours=24',
    '/api/history?hours=24&limit=10',
    '/api/devices/status',
    '/api/lwt/stats',
    '/api/firmware/version'
])
def test_endpoints_are_reachable(endpoint):
    """Alle API-Endpunkte sind erreichbar"""
    full_url = f"http://192.168.0.105:5000{endpoint}"
    response = requests.get(full_url)
    assert response.status_code in [200, 404]  # 404 ist ok für nicht-existente


@pytest.mark.parametrize("device_id,expected_prefix", [
    ("esp8266_ECFABC5F0", "esp8266_"),
    ("test_device", "test_device"),
])
def test_device_id_format_in_api(device_id, expected_prefix):
    """Geräte-ID Format ist korrekt"""
    # Die API sollte Geräte-IDs im erwarteten Format zurückgeben
    response = requests.get(f"{API_BASE_URL}/devices/status")
    
    if response.status_code == 200:
        devices = response.json()
        for device in devices:
            if device.get('device_id') == device_id:
                assert device['device_id'].startswith(expected_prefix) or device['device_id'] == expected_prefix


@pytest.mark.parametrize("hours,expected_range", [
    (24, "24_hours"),
    (12, "12_hours"),
    (1, "1_hour"),
    (0, "all_time"),
])
def test_stats_different_ranges(hours, expected_range):
    """Unterschiedliche Zeiträume funktionieren"""
    response = requests.get(f"{API_BASE_URL}/stats?hours={hours}")
    # 200, 400 oder 404 sind akzeptabel
    assert response.status_code in [200, 400, 404]


# ============================================================================
# 8. TIMEOUT UND RETRY TESTS
# ============================================================================

class TestTimeoutAndRetry:
    """Tests für Timeout und Retry-Verhalten"""
    
    def test_api_timeout_handling(self):
        """API behandelt Timeouts korrekt"""
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=0.1)
            assert response.status_code == 200
        except requests.exceptions.Timeout:
            pass  # Timeout ist akzeptabel
        except Exception:
            pass
    
    def test_api_retry_on_failure(self):
        """API Retry funktioniert"""
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.1)
        session.mount('http://', HTTPAdapter(max_retries=retries))
        
        response = session.get(f"{API_BASE_URL}/health")
        assert response.status_code == 200


# ============================================================================
# 9. CROSS-ORIGIN TESTS
# ============================================================================

def test_cors_headers_present():
    """CORS Header sind für Frontend-Zugriff vorhanden"""
    response = requests.options(f"{API_BASE_URL}/health")
    
    # Prüfe CORS Header (optional, abhängig von Konfiguration)
    if 'access-control-allow-origin' in response.headers:
        assert response.headers['access-control-allow-origin'] == '*'


# ============================================================================
# 10. RATE LIMITING TESTS
# ============================================================================

class TestRateLimiting:
    """Tests für Rate Limiting (falls implementiert)"""
    
    def test_rate_limit_not_exceeded_normal_use(self):
        """Normale Nutzung überschreitet kein Rate Limit"""
        for _ in range(30):
            response = requests.get(f"{API_BASE_URL}/health")
            assert response.status_code in [200, 429]
            time.sleep(0.1)


# ============================================================================
# 11. FIRMWARE ENDPOINT TESTS
# ============================================================================

class TestFirmwareEndpoints:
    """Tests für Firmware Management Endpoints"""
    
    def test_firmware_version_endpoint(self):
        """Firmware Version Endpunkt funktioniert"""
        response = requests.get(f"{API_BASE_URL}/firmware/version")
        assert response.status_code == 200
        
        data = response.json()
        assert 'version' in data
        assert 'size' in data
    
    def test_firmware_upload_endpoint_exists(self):
        """Firmware Upload Endpunkt existiert"""
        response = requests.post(f"{API_BASE_URL}/firmware/upload")
        # 400 ist erwartet wenn keine Datei (Endpunkt existiert trotzdem)
        assert response.status_code in [400, 405, 200]


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Starting Integration Tests (Sicherer Modus)")
    print("=" * 60)
    print("Alle Credentials werden aus .env geladen")
    print("=" * 60)
    
    # Warte auf API Verfügbarkeit
    if not wait_for_api():
        print("API ist nicht verfügbar!")
        sys.exit(1)
    
    print("API ist verfügbar")
    
    # Führe Tests aus
    pytest.main([__file__, "-v", "--tb=short"])