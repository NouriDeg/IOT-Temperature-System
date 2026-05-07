# Test Fixtures für Bridge
import pytest
import json
from unittest.mock import Mock, patch

@pytest.fixture
def sample_mqtt_message():
    """Erzeugt eine Beispiel-MQTT Nachricht"""
    class MockMessage:
        def __init__(self, topic, payload):
            self.topic = topic
            self.payload = payload.encode()
    
    return MockMessage

@pytest.fixture
def sample_temperature_payload():
    """Beispiel-Temperaturdaten"""
    return {
        "device_id": "esp8266_test",
        "device_type": "esp8266",
        "sensor": "max6675",
        "temp": 25.75,
        "unit": "celsius",
        "rssi": -62,
        "heap": 14768,
        "uptime": 12345
    }

@pytest.fixture
def sample_heartbeat_payload():
    """Beispiel-Heartbeat Nachricht"""
    return "true"

@pytest.fixture
def sample_lwt_payload():
    """Beispiel-LWT Nachricht"""
    return {
        "status": "offline",
        "reason": "timeout"
    }

@pytest.fixture
def mock_db_connection():
    """Mock für Datenbankverbindung"""
    with patch('bridge.psycopg2.connect') as mock_connect:
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        yield mock_conn