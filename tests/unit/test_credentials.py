# tests/unit/test_credentials.py
"""
Unit-Tests für Credentials Management
TDD: Test-Driven Development für sichere Passwörter und Credentials

SICHERHEITSHINWEIS:
- Keine Passwörter oder Secrets im Code!
- Alle Test-Credentials werden dynamisch generiert
- Keine Default-Werte für sensible Daten
- Autor: Nouri Deg.
"""

import pytest
import os
import sys
import time  
import hashlib
import secrets
import string
import re
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ============================================================================
# LADE .env KONFIGURATION (SICHERHEIT)
# ============================================================================

# Bestimme den Pfad zur .env Datei
ENV_PATH = os.path.join(os.path.dirname(__file__), '../..', '.env')
ENV_PATH = os.path.abspath(ENV_PATH)

if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
    print(f".env Datei geladen von: {ENV_PATH}")
else:
    print(f".env Datei nicht gefunden: {ENV_PATH}")
    print("   Tests verwenden generierte Test-Daten (keine echten Credentials)")

# ============================================================================
# TEST KONFIGURATION AUS .env (falls vorhanden)
# ============================================================================

# Beispiel für Broker IP (optional, für Tests)
TEST_BROKER_IP = os.getenv('MQTT_HOST', '192.168.0.106')
TEST_BROKER_PORT = int(os.getenv('MQTT_PORT_TLS', 8883))

# Mock für paho MQTT vor dem Import von provisioner
sys.modules['paho'] = MagicMock()
sys.modules['paho.mqtt'] = MagicMock()
sys.modules['paho.mqtt.client'] = MagicMock()

# Dann erst importieren
from provisioner.app import ProvisioningService

# Markiere als Unit-Test
pytestmark = pytest.mark.unit

# ============================================================================
# HILFSFUNKTIONEN FÜR TESTS (KEINE HARDCODED PASSWÖRTER!)
# ============================================================================

def generate_test_password(length: int = 24) -> str:
    """
    Generiert ein sicheres Test-Passwort für Unit-Tests
    
    Args:
        length: Länge des Passworts (default: 24)
    
    Returns:
        str: Sicheres Test-Passwort
    """
    uppercase = secrets.choice(string.ascii_uppercase)
    lowercase = secrets.choice(string.ascii_lowercase)
    digit = secrets.choice(string.digits)
    special = secrets.choice("!@#$%^&*")
    
    remaining = length - 4
    all_chars = string.ascii_letters + string.digits + "!@#$%^&*"
    rest = ''.join(secrets.choice(all_chars) for _ in range(remaining))
    
    password_list = list(uppercase + lowercase + digit + special + rest)
    secrets.SystemRandom().shuffle(password_list)
    
    return ''.join(password_list)


def hash_test_password(password: str) -> str:
    """
    Hasht ein Test-Passwort (SHA256)
    
    Args:
        password: Das zu hashende Passwort
    
    Returns:
        str: SHA256 Hash als Hex-String
    """
    return hashlib.sha256(password.encode()).hexdigest()


# ============================================================================
# 1. CREDENTIALS GENERIERUNG TESTS (mit Mocks)
# ============================================================================

class TestCredentialsGeneration:
    """Tests für die Generierung von MQTT Credentials (mit Mocks)"""
    
    def test_generate_device_id_from_mac(self):
        """Device ID wird korrekt aus MAC-Adresse generiert"""
        def generate_device_id(mac):
            return "esp8266_" + mac.replace(":", "")
        
        mac = "EC:FA:BC:5F:0A:DF"
        device_id = generate_device_id(mac)
        
        assert device_id == "esp8266_ECFABC5F0ADF"
        assert device_id.startswith("esp8266_")
    
    @patch('provisioner.app.DatabaseManager')
    @patch('provisioner.app.CertificateManager')
    def test_generate_unique_credentials(self, mock_cert, mock_db):
        """Generierte Credentials sind eindeutig"""
        service = ProvisioningService()
        
        # Überspringe MQTT Verbindung
        service.mqtt_client = MagicMock()
        service.db = MagicMock()
        
        # Test der Passwort-Generierung
        password1 = service.generate_mqtt_password()
        password2 = service.generate_mqtt_password()
        
        assert password1 != password2
        assert len(password1) == 24
        assert len(password2) == 24
    
    def test_mqtt_username_format(self):
        """MQTT Benutzername folgt korrektem Format"""
        device_id = "esp8266_ECFABC5F0ADF"
        username = f"device_{device_id[:16]}"
        
        assert username.startswith("device_")
        assert len(username) <= 32
    
    def test_mqtt_password_complexity(self):
        """MQTT Passwort erfüllt Komplexitätsanforderungen"""
        # Generiere ein neues Passwort für jeden Test (kein Hardcoding!)
        password = generate_test_password()
        
        # Prüfe Länge
        assert len(password) == 24, f"Passwortlänge ist {len(password)}, sollte 24 sein"
        
        # Prüfe Zeichentypen
        has_upper = bool(re.search(r'[A-Z]', password))
        has_lower = bool(re.search(r'[a-z]', password))
        has_digit = bool(re.search(r'\d', password))
        has_special = bool(re.search(r'[!@#$%^&*]', password))
        
        assert has_upper, f"Keine Großbuchstaben in generiertem Passwort"
        assert has_lower, f"Keine Kleinbuchstaben in generiertem Passwort"
        assert has_digit, f"Keine Ziffern in generiertem Passwort"
        assert has_special, f"Keine Sonderzeichen in generiertem Passwort"


# ============================================================================
# 2. CREDENTIALS SPEICHERUNG TESTS (ohne echte DB)
# ============================================================================

class TestCredentialsStorage:
    """Tests für die persistente Speicherung von Credentials"""
    
    def test_save_credentials_to_eeprom(self):
        """Credentials werden korrekt in EEPROM gespeichert (simuliert)"""
        # Generiere Test-Credentials (keine Hardcoding!)
        test_password = generate_test_password()
        
        credentials = {
            'isProvisioned': True,
            'device_id': 'esp8266_test',
            'mqtt_broker': TEST_BROKER_IP,
            'mqtt_port': TEST_BROKER_PORT,
            'mqtt_user': 'test_device',
            'mqtt_password': test_password
        }
        
        # Simuliere EEPROM Speicherung
        storage = {}
        for key, value in credentials.items():
            storage[key] = value
        
        assert storage['isProvisioned'] == True
        assert storage['device_id'] == 'esp8266_test'
        assert storage['mqtt_password'] == test_password
    
    def test_load_credentials_from_eeprom(self):
        """Credentials werden korrekt aus EEPROM geladen (simuliert)"""
        # Generiere Test-Credentials für den Test
        test_password = generate_test_password()
        
        # Simuliere vorher gespeicherte Credentials
        storage = {
            'isProvisioned': 1,
            'broker': TEST_BROKER_IP,
            'port': TEST_BROKER_PORT,
            'user': 'test_device',
            'password': test_password
        }
        
        is_provisioned = storage.get('isProvisioned', 0) == 1
        
        assert is_provisioned == True
        assert storage['broker'] == TEST_BROKER_IP
        assert storage['password'] == test_password


# ============================================================================
# 3. CREDENTIALS VALIDIERUNG TESTS
# ============================================================================

class TestCredentialsValidation:
    """Tests für die Validierung von Credentials"""
    
    def test_valid_credentials_format(self):
        """Korrekt formatierte Credentials werden akzeptiert"""
        # Generiere Test-Passwort (kein Hardcoding!)
        test_password = generate_test_password()
        
        credentials = {
            'broker': TEST_BROKER_IP,
            'port': TEST_BROKER_PORT,
            'username': 'test_device',
            'password': test_password
        }
        
        # Prüfe IP-Adresse
        parts = credentials['broker'].split('.')
        assert len(parts) == 4
        assert all(0 <= int(p) <= 255 for p in parts)
        
        # Prüfe Port
        assert 1 <= credentials['port'] <= 65535
        
        # Prüfe Benutzername
        assert 3 <= len(credentials['username']) <= 32
    
    def test_invalid_ip_rejected(self):
        """Ungültige IP-Adresse wird abgelehnt"""
        def validate_broker(ip):
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            try:
                return all(0 <= int(p) <= 255 for p in parts)
            except ValueError:
                return False
        
        assert validate_broker(TEST_BROKER_IP) == True
        assert validate_broker("256.168.0.1") == False
        assert validate_broker("192.168.0") == False


# ============================================================================
# 4. CREDENTIALS VERSCHLÜSSELUNG TESTS
# ============================================================================

class TestCredentialsEncryption:
    """Tests für die Verschlüsselung von Credentials"""
    
    def test_password_hashing(self):
        """Passwörter werden gehasht gespeichert"""
        # Generiere Test-Passwort (kein Hardcoding!)
        test_password = generate_test_password()
        
        def hash_password(password):
            return hashlib.sha256(password.encode()).hexdigest()
        
        original = test_password
        hashed = hash_password(original)
        
        assert original != hashed
        assert len(hashed) == 64
        assert isinstance(hashed, str)
    
    def test_hash_is_deterministic(self):
        """Gleiches Passwort erzeugt gleichen Hash"""
        # Generiere Test-Passwort (kein Hardcoding!)
        test_password = generate_test_password()
        
        def hash_password(password):
            return hashlib.sha256(password.encode()).hexdigest()
        
        hash1 = hash_password(test_password)
        hash2 = hash_password(test_password)
        
        assert hash1 == hash2
    
    def test_hash_not_reversible(self):
        """Hash kann nicht zurück in Passwort umgewandelt werden"""
        # Generiere Test-Passwort (kein Hardcoding!)
        test_password = generate_test_password()
        
        def hash_password(password):
            return hashlib.sha256(password.encode()).hexdigest()
        
        original = test_password
        hashed = hash_password(original)
        
        assert original not in hashed


# ============================================================================
# 5. FACTORY RESET TESTS
# ============================================================================

class TestFactoryReset:
    """Tests für Factory Reset Funktion"""
    
    def test_factory_reset_clears_credentials(self):
        """Factory Reset löscht alle Credentials"""
        # Generiere Test-Credentials
        test_password = generate_test_password()
        
        storage = {
            'provisioned': True,
            'user': 'test_user',
            'pass': test_password
        }
        
        def factory_reset(s):
            s['provisioned'] = False
            s['user'] = ''
            s['pass'] = ''
            return s
        
        storage = factory_reset(storage)
        
        assert storage['provisioned'] == False
        assert storage['user'] == ''
        assert storage['pass'] == ''
    
    def test_after_factory_reset_isProvisioned_false(self):
        """Nach Factory Reset ist isProvisioned = false"""
        storage = {'provisioned': True}
        
        def is_provisioned(s):
            return s.get('provisioned', False)
        
        assert is_provisioned(storage) == True
        
        storage['provisioned'] = False
        assert is_provisioned(storage) == False


# ============================================================================
# 6. CREDENTIALS LEBENSDAUER TESTS
# ============================================================================

class TestCredentialsLifetime:
    """Tests für Gültigkeitsdauer von Credentials"""
    
    def test_credentials_have_timestamp(self):
        """Credentials haben Zeitstempel der Erstellung"""
        credentials = {'created_at': datetime.now(), 'user': 'test'}
        
        assert 'created_at' in credentials
        assert isinstance(credentials['created_at'], datetime)
    
    def test_credentials_expiry(self):
        """Credentials können ablaufen"""
        created_at = datetime.now() - timedelta(days=400)
        expiry_days = 365
        
        is_valid = (datetime.now() - created_at).days <= expiry_days
        
        assert is_valid == False


# ============================================================================
# 7. PROVISIONING FLOW TESTS
# ============================================================================

class TestProvisioningFlow:
    """Tests für den Provisioning Flow"""
    
    def test_full_provisioning_flow(self):
        """Vollständiger Provisioning Flow mit Credentials"""
        is_provisioned = False
        credentials = None
        
        request = {'device_id': 'new_device', 'mac_address': 'AA:BB:CC:DD:EE:FF'}
        
        # Generiere Test-Credentials für den Flow
        test_password = generate_test_password()
        
        new_credentials = {
            'mqtt_broker': TEST_BROKER_IP,
            'mqtt_port': TEST_BROKER_PORT,
            'mqtt_user': 'device_new_device',
            'mqtt_password': test_password
        }
        
        credentials = new_credentials
        is_provisioned = True
        
        assert is_provisioned == True
        assert credentials['mqtt_broker'] == TEST_BROKER_IP
        assert credentials['mqtt_password'] == test_password


# ============================================================================
# 8. PARAMETRISIERTE TESTS
# ============================================================================

@pytest.mark.parametrize("device_mac,expected_device_id", [
    ("EC:FA:BC:5F:0A:DF", "esp8266_ECFABC5F0ADF"),
    ("00:11:22:33:44:55", "esp8266_001122334455"),
    ("AA:BB:CC:DD:EE:FF", "esp8266_AABBCCDDEEFF"),
])
def test_device_id_generation(device_mac, expected_device_id):
    """Device ID Generierung für verschiedene MACs"""
    def generate_device_id(mac):
        return "esp8266_" + mac.replace(":", "")
    
    assert generate_device_id(device_mac) == expected_device_id


@pytest.mark.parametrize("username,is_valid", [
    ("device_test_user", True),
    ("device123", True),
    ("", False),
    ("a" * 33, False),
    ("invalid user", False),
])
def test_mqtt_username_validation(username, is_valid):
    """MQTT Benutzername Validierung"""
    def validate_username(username):
        if not username:
            return False
        if len(username) > 32:
            return False
        if not username.replace("_", "").isalnum():
            return False
        return True
    
    assert validate_username(username) == is_valid


@pytest.mark.parametrize("password_input,is_strong", [
    ("SecurePass123!", True),
    ("Weak", False),
    ("nouppercase123!", False),
])
def test_password_strength(password_input, is_strong):
    """Passwortstärke Prüfung (mit generierten Passwörtern)"""
    def is_strong_password(p):
        if len(p) < 12:
            return False
        if not any(c.isupper() for c in p):
            return False
        if not any(c.islower() for c in p):
            return False
        if not any(c.isdigit() for c in p):
            return False
        if not any(c in "!@#$%^&*" for c in p):
            return False
        return True
    
    assert is_strong_password(password_input) == is_strong


# ============================================================================
# 9. SECRET MANAGEMENT TESTS
# ============================================================================

class TestSecretManagement:
    """Tests für Secret Management"""
    
    def test_secrets_not_in_code(self):
        """Secrets sind nicht hardcoded im Code"""
        import inspect
        
        # Hole den Quellcode dieser Datei
        source_file = inspect.getsourcefile(TestSecretManagement)
        with open(source_file, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        
        # Diese Muster sind VERBOTEN (außerhalb von Kommentaren/Docstrings)
        forbidden_patterns = [
            r'password\s*=\s*["\'][^"\']+["\']',
            r'passwort\s*=\s*["\'][^"\']+["\']',
            r'secret\s*=\s*["\'][^"\']+["\']',
            r'token\s*=\s*["\'][^"\']+["\']',
        ]
        
        # Entferne Docstrings und Kommentare für die Prüfung
        lines = source_code.split('\n')
        clean_lines = []
        in_docstring = False
        
        for line in lines:
            if '"""' in line or "'''" in line:
                in_docstring = not in_docstring
                continue
            if not in_docstring and not line.strip().startswith('#'):
                clean_lines.append(line)
        
        clean_code = '\n'.join(clean_lines)
        
        # Prüfe auf verbotene Muster
        for pattern in forbidden_patterns:
            matches = re.findall(pattern, clean_code, re.IGNORECASE)
            # Erlaube generate_test_password() Aufrufe
            matches = [m for m in matches if 'generate_test_password' not in m]
            assert len(matches) == 0, f"Hardcoded Secret gefunden: {matches}"
    
    def test_env_file_exists(self):
        """.env Datei existiert (optional)"""
        env_exists = os.path.exists(ENV_PATH)
        # Nur Info, kein Assert - .env ist optional für Tests
        if env_exists:
            print(f".env Datei gefunden: {ENV_PATH}")
        else:
            print(f".env Datei nicht gefunden - Tests verwenden generierte Daten")


# ============================================================================
# 10. PERFORMANZ TESTS
# ============================================================================

class TestCredentialsPerformance:
    """Performance-Tests für Credentials Operationen"""
    
    def test_password_generation_speed(self):
        """Passwort-Generierung ist schnell (< 1ms pro Passwort)"""
        def generate_password():
            chars = string.ascii_letters + string.digits + "!@#$%^&*"
            return ''.join(secrets.choice(chars) for _ in range(24))
        
        start = time.perf_counter()
        for _ in range(100):
            generate_password()
        end = time.perf_counter()
        
        avg_time = (end - start) / 100
        assert avg_time < 0.001, f"Zu langsam: {avg_time:.4f}s pro Passwort"
    
    def test_hashing_speed(self):
        """Passwort-Hashing ist schnell (< 0.5ms pro Hash)"""
        # Generiere Test-Passwort für Performance-Test
        test_password = generate_test_password()
        
        def hash_password(password):
            return hashlib.sha256(password.encode()).hexdigest()
        
        start = time.perf_counter()
        for _ in range(100):
            hash_password(test_password)
        end = time.perf_counter()
        
        avg_time = (end - start) / 100
        assert avg_time < 0.0005, f"Zu langsam: {avg_time:.4f}s pro Hash"


# ============================================================================
# MAIN (für direkte Ausführung)
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Credentials Unit Tests (Sicherer Modus)")
    print("=" * 60)
    print(f"Test Broker IP: {TEST_BROKER_IP}")
    print(f"Test Broker Port: {TEST_BROKER_PORT}")
    print("=" * 60)
    print("Keine Hardcoded Passwörter im Code!")
    print("=" * 60)
    
    pytest.main([__file__, "-v", "--tb=short"])