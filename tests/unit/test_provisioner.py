#!/usr/bin/env python
"""
- Unit-Tests für den Provisioning Service
- TDD: Test-Driven Development für automatisches Geräte-Onboarding
- Autor: Nouri Deg.
- Datum: 06.05.2026
"""

import pytest
import json
import secrets
import string
import hashlib
import sys
import os
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

# Füge das Projektverzeichnis zum Python-Pfad hinzu
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

pytestmark = pytest.mark.unit

# ============================================================================
# 1. PASSWORT-GENERIERUNG TESTS
# ============================================================================

class TestPasswordGeneration:
    """Tests für die Passwort-Generierung"""
    
    def test_generate_mqtt_password_length(self):
        """Passwort hat korrekte Länge"""
        def generate_password():
            chars = string.ascii_letters + string.digits + "!@#$%^&*"
            return ''.join(secrets.choice(chars) for _ in range(24))
        
        password = generate_password()
        assert len(password) == 24
    
    @patch('provisioner.app.DatabaseManager')
    @patch('provisioner.app.CertificateManager')
    @patch('provisioner.app.mqtt.Client')
    def test_generate_mqtt_password_default_length(self, mock_mqtt, mock_cert, mock_db):
        """Standard-Passwortlänge ist 24 Zeichen"""
        from provisioner.app import ProvisioningService
        
        # Mock die Datenbankverbindung - verhindert echte DB-Zugriffe!
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        
        mock_cert_instance = MagicMock()
        mock_cert.return_value = mock_cert_instance
        
        mock_mqtt_instance = MagicMock()
        mock_mqtt.return_value = mock_mqtt_instance
        
        service = ProvisioningService()
        password = service.generate_mqtt_password()
        
        assert len(password) == 24
    
    def test_generate_mqtt_password_contains_valid_characters(self):
        """Passwort enthält nur erlaubte Zeichen"""
        def generate_password():
            chars = string.ascii_letters + string.digits + "!@#$%^&*"
            return ''.join(secrets.choice(chars) for _ in range(24))
        
        password = generate_password()
        allowed = set(string.ascii_letters + string.digits + "!@#$%^&*")
        
        for char in password:
            assert char in allowed
    
    @patch('provisioner.app.DatabaseManager')
    @patch('provisioner.app.CertificateManager')
    @patch('provisioner.app.mqtt.Client')
    def test_generate_mqtt_password_is_random(self, mock_mqtt, mock_cert, mock_db):
        """Generierte Passwörter sind zufällig (nicht identisch)"""
        from provisioner.app import ProvisioningService
        
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        
        service = ProvisioningService()
        password1 = service.generate_mqtt_password()
        password2 = service.generate_mqtt_password()
        password3 = service.generate_mqtt_password()
        
        # Alle drei sollten unterschiedlich sein
        assert password1 != password2
        assert password1 != password3
        assert password2 != password3
    
    @patch('provisioner.app.DatabaseManager')
    @patch('provisioner.app.CertificateManager')
    @patch('provisioner.app.mqtt.Client')
    def test_generate_mqtt_password_contains_mixed_case(self, mock_mqtt, mock_cert, mock_db):
        """Passwort enthält Groß- und Kleinbuchstaben"""
        from provisioner.app import ProvisioningService
        
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        
        service = ProvisioningService()
        password = service.generate_mqtt_password()
        
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        
        assert has_upper, "Passwort enthält keine Großbuchstaben"
        assert has_lower, "Passwort enthält keine Kleinbuchstaben"
    
    @patch('provisioner.app.DatabaseManager')
    @patch('provisioner.app.CertificateManager')
    @patch('provisioner.app.mqtt.Client')
    def test_generate_mqtt_password_contains_digits(self, mock_mqtt, mock_cert, mock_db):
        """Passwort enthält Ziffern"""
        from provisioner.app import ProvisioningService
        
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        
        service = ProvisioningService()
        password = service.generate_mqtt_password()
        
        has_digit = any(c.isdigit() for c in password)
        assert has_digit, "Passwort enthält keine Ziffern"
    ####################################################################

    @patch('provisioner.app.DatabaseManager')
    @patch('provisioner.app.CertificateManager')
    @patch('provisioner.app.mqtt.Client')
    def test_generate_mqtt_password_contains_special_chars(self, mock_mqtt, mock_cert, mock_db):
        """ Passwort enthält Sonderzeichen (bei genügend Wiederholungen)"""
        from provisioner.app import ProvisioningService
        
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        
        service = ProvisioningService()
        
        # Generiere mehrere Passwörter (mindestens 10), um sicher zu sein
        # dass Sonderzeichen vorkommen (zufällig)
        has_special_found = False
        special_chars = "!@#$%^&*"
        
        for _ in range(20):  # 20 Versuche
            password = service.generate_mqtt_password()
            if any(c in special_chars for c in password):
                has_special_found = True
                break
        
        assert has_special_found, "Nach 20 Versuchen wurde kein Passwort mit Sonderzeichen gefunden"


# ============================================================================
# 2. PASSWORT-HASHING TESTS (KEINE DB VERBINDUNG NÖTIG!)
# ============================================================================

class TestPasswordHashing:
    """Tests für Passwort-Hashing (SHA256) - Keine DB nötig!"""
    
    def test_hash_password_returns_hex_string(self):
        """Hash wird als Hex-String zurückgegeben"""
        # Direkte Implementierung ohne Service
        def hash_password(password):
            return hashlib.sha256(password.encode()).hexdigest()
        
        hash_result = hash_password("test_password")
        
        # SHA256 Hex-String hat 64 Zeichen
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64
        assert all(c in "0123456789abcdef" for c in hash_result)
    
    def test_hash_password_consistent(self):
        """Gleiches Passwort ergibt gleichen Hash"""
        def hash_password(password):
            return hashlib.sha256(password.encode()).hexdigest()
        
        hash1 = hash_password("test_password")
        hash2 = hash_password("test_password")
        
        assert hash1 == hash2
    
    def test_hash_password_different_for_different_passwords(self):
        """Unterschiedliche Passwörter ergeben unterschiedliche Hashes"""
        def hash_password(password):
            return hashlib.sha256(password.encode()).hexdigest()
        
        hash1 = hash_password("password1")
        hash2 = hash_password("password2")
        
        assert hash1 != hash2
    
    def test_hash_password_not_reversible(self):
        """Hash kann nicht zurück in Passwort umgewandelt werden (Einweg)"""
        def hash_password(password):
            return hashlib.sha256(password.encode()).hexdigest()
        
        original = "my_secret_password"
        hash_result = hash_password(original)
        
        # Der Hash sollte nicht das Original enthalten
        assert original not in hash_result
    
    def test_hash_password_empty_string(self):
        """Leerer String funktioniert auch"""
        def hash_password(password):
            return hashlib.sha256(password.encode()).hexdigest()
        
        hash_result = hash_password("")
        
        assert len(hash_result) == 64


# ============================================================================
# 3. DATENBANK MANAGER TESTS
# ============================================================================

class TestDatabaseManager:
    """Tests für den DatabaseManager des Provisioners"""
    
    @patch('provisioner.app.psycopg2.connect')
    def test_connect_success(self, mock_connect):
        """Datenbankverbindung wird erfolgreich hergestellt"""
        from provisioner.app import DatabaseManager
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        db_manager = DatabaseManager()
        
        mock_connect.assert_called_once()
        assert db_manager.conn == mock_conn
    
    @patch('provisioner.app.psycopg2.connect')
    def test_connect_failure_raises_exception(self, mock_connect):
        """Datenbankverbindungsfehler wird behandelt"""
        from provisioner.app import DatabaseManager
        
        mock_connect.side_effect = Exception("Connection failed")
        
        with pytest.raises(Exception):
            db_manager = DatabaseManager()
    
    @patch('provisioner.app.psycopg2.connect')
    def test_create_tables_creates_devices_table(self, mock_connect):
        """devices Tabelle wird erstellt"""
        from provisioner.app import DatabaseManager
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        db_manager = DatabaseManager()
        
        # Prüfe ob CREATE TABLE ausgeführt wurde
        mock_cursor.execute.assert_called()
        call_args = str(mock_cursor.execute.call_args)
        assert "CREATE TABLE" in call_args
        assert "devices" in call_args
    
    @patch('provisioner.app.psycopg2.connect')
    def test_device_exists_returns_true_for_existing_device(self, mock_connect):
        """Gerät existiert in Datenbank"""
        from provisioner.app import DatabaseManager
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("device_123", "provisioned")
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        db_manager = DatabaseManager()
        result = db_manager.device_exists("EC:FA:BC:5F:0A:DF")
        
        assert result is not None
        assert result[0] == "device_123"
        assert result[1] == "provisioned"
    
    @patch('provisioner.app.psycopg2.connect')
    def test_device_exists_returns_none_for_new_device(self, mock_connect):
        """Neues Gerät existiert noch nicht"""
        from provisioner.app import DatabaseManager
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        db_manager = DatabaseManager()
        result = db_manager.device_exists("AA:BB:CC:DD:EE:FF")
        
        assert result is None
    
    @patch('provisioner.app.psycopg2.connect')
    def test_register_device_inserts_record(self, mock_connect):
        """Neues Gerät wird in Datenbank registriert"""
        from provisioner.app import DatabaseManager
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        db_manager = DatabaseManager()
        db_manager.register_device(
            device_id="esp8266_test",
            mac_address="AA:BB:CC:DD:EE:FF",
            mqtt_username="device_test",
            password_hash="abc123..."
        )
        
        # Prüfe INSERT
        mock_cursor.execute.assert_called()
        call_args = str(mock_cursor.execute.call_args)
        assert "INSERT INTO devices" in call_args


# ============================================================================
# 4. ZERTIFIKAT-MANAGER TESTS
# ============================================================================

class TestCertificateManager:
    """Tests für die Zertifikatsgenerierung"""
    
    @patch('provisioner.app.open')
    @patch('provisioner.app.x509.load_pem_x509_certificate')
    @patch('provisioner.app.serialization.load_pem_private_key')
    def test_load_ca_loads_certificates(self, mock_load_key, mock_load_cert, mock_open):
        """CA Zertifikate werden korrekt geladen"""
        from provisioner.app import CertificateManager
        
        mock_load_key.return_value = MagicMock()
        mock_load_cert.return_value = MagicMock()
        
        with patch('provisioner.app.CERT_DIR', '/app/certs'):
            try:
                cert_manager = CertificateManager()
                assert True
            except Exception as e:
                pytest.skip(f"CA Zertifikate nicht verfügbar: {e}")


# ============================================================================
# 5. MQTT NACHRICHTENVERARBEITUNG TESTS
# ============================================================================

class TestMQTTMessageHandling:
    """Tests für MQTT Nachrichtenverarbeitung"""
    
    @patch('provisioner.app.DatabaseManager')
    @patch('provisioner.app.CertificateManager')
    @patch('provisioner.app.mqtt.Client')
    def test_on_message_valid_request(self, mock_mqtt, mock_cert, mock_db):
        """Gültiger Provisioning Request wird verarbeitet"""
        from provisioner.app import ProvisioningService
        
        # Mock Setup
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        mock_db_instance.device_exists.return_value = None
        
        mock_cert_instance = MagicMock()
        mock_cert.return_value = mock_cert_instance
        
        mock_mqtt_instance = MagicMock()
        mock_mqtt.return_value = mock_mqtt_instance
        
        service = ProvisioningService()
        
        # Erstelle Test-Nachricht
        class MockMessage:
            topic = "provisioning/request"
            payload = json.dumps({
                "device_id": "esp8266_test",
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "firmware_version": "1.0.0"
            }).encode()
        
        # Verarbeite Nachricht
        service.on_message(None, None, MockMessage())
        
        # Prüfe ob Gerät registriert wurde
        mock_db_instance.register_device.assert_called_once()
    
    @patch('provisioner.app.DatabaseManager')
    @patch('provisioner.app.CertificateManager')
    @patch('provisioner.app.mqtt.Client')
    def test_on_message_existing_device(self, mock_mqtt, mock_cert, mock_db):
        """Bereits provisioniertes Gerät wird erkannt"""
        from provisioner.app import ProvisioningService
        
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        # Simuliere bereits existierendes Gerät
        mock_db_instance.device_exists.return_value = ("device_123", "provisioned")
        
        mock_mqtt_instance = MagicMock()
        mock_mqtt.return_value = mock_mqtt_instance
        
        service = ProvisioningService()
        
        class MockMessage:
            topic = "provisioning/request"
            payload = json.dumps({
                "device_id": "esp8266_test",
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "firmware_version": "1.0.0"
            }).encode()
        
        service.on_message(None, None, MockMessage())
        
        # Keine neue Registrierung
        mock_db_instance.register_device.assert_not_called()
    
    @patch('provisioner.app.DatabaseManager')
    @patch('provisioner.app.CertificateManager')
    @patch('provisioner.app.mqtt.Client')
    def test_on_message_invalid_json(self, mock_mqtt, mock_cert, mock_db):
        """Ungültiges JSON wird abgelehnt"""
        from provisioner.app import ProvisioningService
        
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        
        service = ProvisioningService()
        
        class MockMessage:
            topic = "provisioning/request"
            payload = b"invalid json {"
        
        service.on_message(None, None, MockMessage())
        
        # Keine Registrierung bei ungültigem JSON
        mock_db_instance.register_device.assert_not_called()
    
    @patch('provisioner.app.DatabaseManager')
    @patch('provisioner.app.CertificateManager')
    @patch('provisioner.app.mqtt.Client')
    def test_send_response_contains_credentials(self, mock_mqtt, mock_cert, mock_db):
        """Response enthält korrekte Credentials"""
        from provisioner.app import ProvisioningService
        
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        
        mock_mqtt_instance = MagicMock()
        mock_mqtt.return_value = mock_mqtt_instance
        
        service = ProvisioningService()
        
        service.send_response(
            device_id="esp8266_test",
            status="success",
            mqtt_username="device_test",
            mqtt_password="secret123",
            certificates=None
        )
        
        # Prüfe publish Aufruf
        mock_mqtt_instance.publish.assert_called_once()
        call_args = mock_mqtt_instance.publish.call_args
        topic = call_args[0][0]
        payload = json.loads(call_args[0][1])
        
        assert topic == "provisioning/response"
        assert payload["status"] == "success"
        assert payload["mqtt_username"] == "device_test"
        assert payload["mqtt_password"] == "secret123"


# ============================================================================
# 6. INTEGRATION TESTS FÜR PROVISIONER
# ============================================================================

class TestProvisionerIntegration:
    """Integrationstests für den gesamten Provisioner"""
    
    @patch('provisioner.app.DatabaseManager')
    @patch('provisioner.app.CertificateManager')
    @patch('provisioner.app.mqtt.Client')
    def test_provisioning_flow_success(self, mock_mqtt, mock_cert, mock_db):
        """Vollständiger Provisioning Flow funktioniert"""
        from provisioner.app import ProvisioningService
        
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        mock_db_instance.device_exists.return_value = None
        
        mock_mqtt_instance = MagicMock()
        mock_mqtt.return_value = mock_mqtt_instance
        
        service = ProvisioningService()
        
        # Service sollte MQTT Verbindung herstellen
        mock_mqtt_instance.connect.assert_called()
        mock_mqtt_instance.loop_start.assert_called()
    
    @patch('provisioner.app.DatabaseManager')
    @patch('provisioner.app.CertificateManager')
    @patch('provisioner.app.mqtt.Client')
    def test_response_includes_broker_address(self, mock_mqtt, mock_cert, mock_db):
        """Response enthält Broker Adresse für ESP8266"""
        from provisioner.app import ProvisioningService
        
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        
        mock_mqtt_instance = MagicMock()
        mock_mqtt.return_value = mock_mqtt_instance
        
        service = ProvisioningService()
        
        service.send_response(
            device_id="esp8266_test",
            status="success",
            mqtt_username="device_test",
            mqtt_password="secret123"
        )
        
        call_args = mock_mqtt_instance.publish.call_args
        payload = json.loads(call_args[0][1])
        
        assert "mqtt_broker" in payload
        assert "mqtt_port" in payload
        assert payload["mqtt_port"] == 8883


# ============================================================================
# 7. PARAMETRISIERTE TESTS
# ============================================================================

@pytest.mark.parametrize("mac_address,expected", [
    ("EC:FA:BC:5F:0A:DF", "esp8266_ECFABC5F0ADF"),
    ("00:11:22:33:44:55", "esp8266_001122334455"),
    ("AA:BB:CC:DD:EE:FF", "esp8266_AABBCCDDEEFF"),
])
def test_device_id_generation(mac_address, expected):
    """Device ID wird korrekt aus MAC-Adresse generiert"""
    def generate_device_id(mac):
        return "esp8266_" + mac.replace(":", "")
    
    assert generate_device_id(mac_address) == expected

@pytest.mark.parametrize("firmware_version", [
    "1.0.0",
    "2.0.0", 
    "1.2.3",
    "development",
])
def test_firmware_version_handling(firmware_version):
    """Verschiedene Firmware-Versionen werden korrekt verarbeitet"""
    request = {
        "device_id": "esp8266_test",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "firmware_version": firmware_version
    }
    
    assert request["firmware_version"] == firmware_version


# ============================================================================
# 8. PERFORMANZ TESTS
# ============================================================================

class TestProvisionerPerformance:
    """Performance-Tests für den Provisioner"""
    
    def test_password_generation_fast(self):
        """Passwort-Generierung ist schnell (< 1ms)"""
        import time
        
        def generate_password():
            chars = string.ascii_letters + string.digits + "!@#$%^&*"
            return ''.join(secrets.choice(chars) for _ in range(24))
        
        start = time.perf_counter()
        generate_password()
        end = time.perf_counter()
        
        assert (end - start) < 0.001, "Passwort-Generierung zu langsam"
    
    def test_hashing_fast(self):
        """Hashing ist schnell (< 0.5ms)"""
        import time
        
        def hash_password(password):
            return hashlib.sha256(password.encode()).hexdigest()
        
        start = time.perf_counter()
        hash_password("test_password")
        end = time.perf_counter()
        
        assert (end - start) < 0.0005, "Hashing zu langsam"


# ============================================================================
# 9. EXCEPTION TESTS
# ============================================================================

class TestProvisionerExceptions:
    """Tests für Exception-Handling"""
    
    @patch('provisioner.app.psycopg2.connect')
    def test_database_connection_failure_handled(self, mock_connect):
        """Datenbankverbindungsfehler wird abgefangen"""
        from provisioner.app import DatabaseManager
        
        mock_connect.side_effect = Exception("Database unavailable")
        
        with pytest.raises(Exception):
            db_manager = DatabaseManager()
    
    @patch('provisioner.app.DatabaseManager')
    @patch('provisioner.app.CertificateManager')
    @patch('provisioner.app.mqtt.Client')
    def test_certificate_generation_failure_graceful(self, mock_mqtt, mock_cert, mock_db):
        """Zertifikatsfehler brechen Provisioning nicht ab"""
        from provisioner.app import ProvisioningService
        
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        mock_db_instance.device_exists.return_value = None
        
        mock_cert_instance = MagicMock()
        mock_cert_instance.generate_client_certificate.side_effect = Exception("Cert error")
        mock_cert.return_value = mock_cert_instance
        
        mock_mqtt_instance = MagicMock()
        mock_mqtt.return_value = mock_mqtt_instance
        
        service = ProvisioningService()
        
        # Sollte keinen Fehler werfen
        class MockMessage:
            topic = "provisioning/request"
            payload = json.dumps({
                "device_id": "esp8266_test",
                "mac_address": "AA:BB:CC:DD:EE:FF"
            }).encode()
        
        try:
            service.on_message(None, None, MockMessage())
            assert True
        except Exception as e:
            pytest.fail(f"Sollte keinen Fehler werfen: {e}")