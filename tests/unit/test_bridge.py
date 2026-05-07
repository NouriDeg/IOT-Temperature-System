#!/usr/bin/env python
"""
Unit-Tests für die MQTT Bridge Komponente
TDD: Test-Driven Development
- Autor: Nouri Deg.
"""

import pytest
import json
import sys
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Füge das Bridge-Verzeichnis zum Python-Pfad hinzu
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

# Markiere als Unit-Test
pytestmark = pytest.mark.unit

# ============================================
# 1. JSON SCHEMA TESTS
# ============================================

class TestJSONSchema:
    """Tests für JSON Schema Validierung (ohne echte DB)"""
    
    def test_valid_sensor_data_passes_validation(self):
        """Gültige Sensordaten bestehen Validierung"""
        from jsonschema import validate
        
        # Lokales Schema für Test
        SENSOR_SCHEMA = {
            "type": "object",
            "required": ["device_id", "temp", "unit"],
            "properties": {
                "device_id": {"type": "string"},
                "temp": {"type": "number"},
                "unit": {"type": "string"}
            }
        }
        
        valid_payload = {
            "device_id": "esp8266_test",
            "temp": 25.75,
            "unit": "celsius"
        }
        
        # Sollte keine Exception werfen
        validate(instance=valid_payload, schema=SENSOR_SCHEMA)
        assert True
    
    def test_missing_required_field_fails_validation(self):
        """Fehlende Pflichtfelder führen zu Validierungsfehler"""
        from jsonschema import validate, ValidationError
        
        # Lokales Schema für Test - KEIN Import von bridge!
        SENSOR_SCHEMA = {
            "type": "object",
            "required": ["device_id", "temp", "unit"],
            "properties": {
                "device_id": {"type": "string"},
                "temp": {"type": "number"},
                "unit": {"type": "string"}
            }
        }
        
        invalid_payload = {
            "device_id": "esp8266_ECFABC5F0",
            # "temp" fehlt! (Pflichtfeld)
            "unit": "celsius"
        }
        
        with pytest.raises(ValidationError):
            validate(instance=invalid_payload, schema=SENSOR_SCHEMA)
    
    def test_invalid_temperature_type_fails_validation(self):
        """Falscher Datentyp für Temperatur führt zu Fehler"""
        from jsonschema import validate, ValidationError
        
        # Lokales Schema für Test
        SENSOR_SCHEMA = {
            "type": "object",
            "required": ["device_id", "temp", "unit"],
            "properties": {
                "device_id": {"type": "string"},
                "temp": {"type": "number"},
                "unit": {"type": "string"}
            }
        }
        
        invalid_payload = {
            "device_id": "esp8266_ECFABC5F0",
            "temp": "not a number",  # String statt Number
            "unit": "celsius"
        }
        
        with pytest.raises(ValidationError):
            validate(instance=invalid_payload, schema=SENSOR_SCHEMA)


# ============================================
# 2. DATABASE MANAGER TESTS
# ============================================

class TestDatabaseManager:
    """Tests für den DatabaseManager"""
    
    @patch('bridge.bridge.psycopg2.connect')
    def test_insert_sensor_data_success(self, mock_connect):
        """Sensordaten erfolgreich in DB speichern"""
        from bridge.bridge import DatabaseManager
        
        # Mock Setup
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        db_manager = DatabaseManager()
        payload = {
            "device_id": "esp8266_test",
            "device_type": "esp8266",
            "sensor": "max6675",
            "temp": 25.75,
            "unit": "celsius",
            "rssi": -62,
            "heap": 14768
        }
        
        # Test mit Exception-Handling
        try:
            db_manager.insert_sensor_data(payload)
            assert True
        except Exception as e:
            pytest.fail(f"Insert sollte nicht fehlschlagen: {e}")
    
    @patch('bridge.bridge.psycopg2.connect')
    def test_update_heartbeat_updates_device_status(self, mock_connect):
        """Heartbeat aktualisiert Gerätestatus"""
        from bridge.bridge import DatabaseManager
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        db_manager = DatabaseManager()
        
        try:
            db_manager.update_heartbeat("esp8266_test", "true")
            assert True
        except Exception as e:
            pytest.fail(f"Update heartbeat sollte nicht fehlschlagen: {e}")


# ============================================
# 3. MQTT BRIDGE TESTS
# ============================================

class TestMQTTBridge:
    """Tests für die MQTT Bridge"""
    
    @patch('bridge.bridge.mqtt.Client')
    @patch('bridge.bridge.DatabaseManager')
    def test_on_message_heartbeat_handling(self, mock_db_class, mock_mqtt_class):
        """Heartbeat Nachrichten werden korrekt verarbeitet"""
        from bridge.bridge import MQTTBridge
        
        # Mock Setup
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance
        
        mock_mqtt_instance = MagicMock()
        mock_mqtt_class.return_value = mock_mqtt_instance
        
        bridge = MQTTBridge()
        
        # Erstelle Test-Nachricht
        class MockMessage:
            topic = "status/esp8266_test/online"
            payload = b"true"
        
        # Verarbeite Nachricht
        bridge.on_message(None, None, MockMessage())
        
        # Assertion - update_heartbeat sollte aufgerufen werden
        mock_db_instance.update_heartbeat.assert_called()
    
    @patch('bridge.bridge.mqtt.Client')
    @patch('bridge.bridge.DatabaseManager')
    def test_on_message_temperature_handling(self, mock_db_class, mock_mqtt_class):
        """Temperaturdaten werden korrekt verarbeitet"""
        from bridge.bridge import MQTTBridge
        
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance
        
        mock_mqtt_instance = MagicMock()
        mock_mqtt_class.return_value = mock_mqtt_instance
        
        bridge = MQTTBridge()
        
        # Erstelle Test-Nachricht
        class MockMessage:
            topic = "sensor/temperatur"
            payload = json.dumps({
                "device_id": "esp8266_test",
                "temp": 25.75,
                "unit": "celsius"
            }).encode()
        
        # Verarbeite Nachricht
        bridge.on_message(None, None, MockMessage())
        
        # Assertion - insert_sensor_data sollte aufgerufen werden
        mock_db_instance.insert_sensor_data.assert_called()
    
    @patch('bridge.bridge.mqtt.Client')
    @patch('bridge.bridge.DatabaseManager')
    def test_on_message_lwt_handling(self, mock_db_class, mock_mqtt_class):
        """LWT Nachrichten werden korrekt verarbeitet"""
        from bridge.bridge import MQTTBridge
        
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance
        
        mock_mqtt_instance = MagicMock()
        mock_mqtt_class.return_value = mock_mqtt_instance
        
        bridge = MQTTBridge()
        
        # Erstelle Test-Nachricht
        class MockMessage:
            topic = "lwt/esp8266_test"
            payload = json.dumps({"status": "offline", "reason": "timeout"}).encode()
        
        # Verarbeite Nachricht
        bridge.on_message(None, None, MockMessage())
        
        # Assertion - update_lwt sollte aufgerufen werden
        mock_db_instance.update_lwt.assert_called()


# ============================================
# 4. ZEITZONEN TESTS
# ============================================

class TestTimezone:
    """Tests für Zeitzonen-Funktionalität"""
    
    def test_get_local_now_returns_berlin_timezone(self):
        """get_local_now gibt Berliner Zeitzone zurück"""
        from bridge.bridge import get_local_now
        
        now = get_local_now()
        
        # Prüfe dass die Zeitzone Europe/Berlin ist (String-Vergleich statt Objekt-Vergleich)
        assert str(now.tzinfo) == 'Europe/Berlin'
    
    def test_local_tz_is_europe_berlin(self):
        """LOCAL_TZ ist Europe/Berlin"""
        from bridge.bridge import LOCAL_TZ
        
        assert str(LOCAL_TZ) == 'Europe/Berlin'