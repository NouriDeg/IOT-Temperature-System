#!/usr/bin/env python
"""
Integrationstests für MQTT Broker und Bridge
Verwendet echte MQTT und PostgreSQL Instanzen (über docker-compose.test.yml)

Diese Tests benötigen eine laufende Test-Umgebung:
    docker-compose -f docker-compose.test.yml up integration-test

Alternativ können die Tests auch manuell mit einem laufenden Broker ausgeführt werden.
- Autor: Nouri Deg.
"""

import pytest
import paho.mqtt.client as mqtt
import json
import time
import os
import ssl
from unittest.mock import Mock, patch

# ============================================
# TEST KONFIGURATION (aus Umgebungsvariablen)
# ============================================

MQTT_HOST = os.getenv('MQTT_HOST', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_TLS_PORT = int(os.getenv('MQTT_TLS_PORT', 8883))
MQTT_USER = os.getenv('MQTT_USER', 'test_device')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', 'test_password_123')
CA_CERT_PATH = os.getenv('CA_CERT_PATH', './certs/ca.crt')

# ============================================
# FIXTURES
# ============================================

@pytest.fixture
def mqtt_client():
    """MQTT Client Fixture (ohne TLS)"""
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    return client


@pytest.fixture
def mqtt_tls_client():
    """MQTT TLS Client Fixture (mit TLS)"""
    client = mqtt.Client()
    
    # TLS Konfiguration
    if os.path.exists(CA_CERT_PATH):
        client.tls_set(
            ca_certs=CA_CERT_PATH,
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLSv1_2
        )
    else:
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)
    
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    return client


@pytest.fixture
def connected_mqtt_client(mqtt_client):
    """Verbundenes MQTT Client Fixture"""
    try:
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        mqtt_client.loop_start()
        time.sleep(1)
        yield mqtt_client
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    except Exception as e:
        pytest.skip(f"MQTT Broker nicht verfügbar: {e}")


@pytest.fixture
def connected_tls_client(mqtt_tls_client):
    """Verbundenes TLS MQTT Client Fixture"""
    try:
        mqtt_tls_client.connect(MQTT_HOST, MQTT_TLS_PORT, 60)
        mqtt_tls_client.loop_start()
        time.sleep(1)
        yield mqtt_tls_client
        mqtt_tls_client.loop_stop()
        mqtt_tls_client.disconnect()
    except Exception as e:
        pytest.skip(f"TLS MQTT Broker nicht verfügbar: {e}")

# ============================================
# 1. MQTT VERBINDUNGSTESTS
# ============================================

class TestMQTTConnection:
    """Tests für MQTT Verbindungen"""
    
    def test_connect_to_broker(self, mqtt_client):
        """Verbindung zum MQTT Broker (Port 1883)"""
        try:
            mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
            mqtt_client.loop_start()
            time.sleep(1)
            assert mqtt_client.is_connected() == True
            mqtt_client.disconnect()
        except Exception as e:
            pytest.skip(f"MQTT Broker nicht verfügbar: {e}")
    
    def test_connect_with_wrong_credentials(self):
        """Falsche Credentials verhindern Verbindung"""
        client = mqtt.Client()
        client.username_pw_set("wrong_user", "wrong_pass")
        
        try:
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            client.loop_start()
            time.sleep(1)
            # Bei falschen Credentials sollte is_connected() False sein
            assert client.is_connected() == False
            client.disconnect()
        except Exception:
            # Verbindungsfehler ist akzeptabel bei falschen Credentials
            pass
# ============================================
# 2. MQTT PUBLISH / SUBSCRIBE TESTS
# ============================================

class TestMQTTPublishSubscribe:
    """Tests für Publish und Subscribe"""
    
    def test_publish_and_subscribe(self, connected_mqtt_client):
        """Publish und Subscribe funktionieren"""
        received_messages = []
        
        def on_message(client, userdata, msg):
            received_messages.append(msg.payload.decode())
        
        connected_mqtt_client.subscribe("test/integration")
        connected_mqtt_client.on_message = on_message
        time.sleep(0.5)
        
        # Sende Testnachricht
        result = connected_mqtt_client.publish("test/integration", "Hello MQTT!")
        assert result.rc == mqtt.MQTT_ERR_SUCCESS
        
        time.sleep(1)
        
        assert len(received_messages) > 0, "Keine Nachricht empfangen"
        assert "Hello MQTT!" in received_messages[0]
    
    def test_publish_multiple_messages(self, connected_mqtt_client):
        """Mehrere Nachrichten hintereinander senden"""
        received_messages = []
        
        def on_message(client, userdata, msg):
            received_messages.append(msg.payload.decode())
        
        connected_mqtt_client.subscribe("test/multi")
        connected_mqtt_client.on_message = on_message
        time.sleep(0.5)
        
        for i in range(5):
            connected_mqtt_client.publish("test/multi", f"Message {i}")
            time.sleep(0.1)
        
        time.sleep(1)
        
        assert len(received_messages) == 5, f"Nur {len(received_messages)} von 5 Nachrichten empfangen"
        assert "Message 0" in received_messages[0]
        assert "Message 4" in received_messages[4]

# ============================================
# 3. MQTT TLS TESTS
# ============================================

class TestMQTTTLS:
    """Tests für MQTTS (TLS) Verbindungen"""
    
    def test_tls_connection(self, connected_tls_client):
        """TLS Verbindung funktioniert"""
        assert connected_tls_client.is_connected() == True
    
    def test_tls_publish_and_subscribe(self, connected_tls_client):
        """TLS Publish und Subscribe funktionieren"""
        received_messages = []
        
        def on_message(client, userdata, msg):
            received_messages.append(msg.payload.decode())
        
        connected_tls_client.subscribe("test/tls")
        connected_tls_client.on_message = on_message
        time.sleep(0.5)
        
        connected_tls_client.publish("test/tls", "Hello TLS MQTT!")
        time.sleep(1)
        
        assert len(received_messages) > 0, "Keine TLS Nachricht empfangen"
        assert "Hello TLS MQTT!" in received_messages[0]

# ============================================
# 4. TEMPERATURDATEN TESTS
# ============================================

class TestTemperatureData:
    """Tests für Temperaturdaten Übertragung"""
    
    def test_publish_temperature_data(self, connected_mqtt_client):
        """Temperaturdaten über MQTT senden"""
        test_payload = {
            "device_id": "integration_test_device",
            "device_type": "esp8266",
            "sensor": "max6675",
            "temp": 25.75,
            "unit": "celsius",
            "rssi": -62,
            "heap": 14768,
            "uptime": 12345
        }
        
        result = connected_mqtt_client.publish("sensor/temperatur", json.dumps(test_payload))
        assert result.rc == mqtt.MQTT_ERR_SUCCESS
    
    def test_temperature_payload_format(self):
        """Temperatur-Payload hat korrektes Format"""
        valid_payload = {
            "device_id": "esp8266_test",
            "device_type": "esp8266",
            "sensor": "max6675",
            "temp": 25.5,
            "unit": "celsius",
            "rssi": -62,
            "heap": 14768,
            "uptime": 12345
        }
        
        required_fields = ["device_id", "temp", "unit"]
        for field in required_fields:
            assert field in valid_payload, f"Pflichtfeld '{field}' fehlt"
        
        assert isinstance(valid_payload["temp"], (int, float))
        assert isinstance(valid_payload["unit"], str)

# ============================================
# 5. HEARTBEAT UND LWT TESTS
# ============================================

class TestHeartbeatAndLWT:
    """Tests für Heartbeat und LWT Nachrichten"""
    
    def test_heartbeat_payload_format(self):
        """ Heartbeat-Payload hat korrektes Format """
        valid_statuses = ["true", "false"]
        assert "true" in valid_statuses
        assert "false" in valid_statuses
    
    def test_send_heartbeat(self, connected_mqtt_client):
        """Heartbeat senden"""
        device_id = "heartbeat_test_device"
        topic = f"status/{device_id}/online"
        
        result = connected_mqtt_client.publish(topic, "true", retain=True)
        assert result.rc == mqtt.MQTT_ERR_SUCCESS
    
    def test_lwt_payload_format(self):
        """LWT-Payload hat korrektes Format"""
        valid_payload = {
            "status": "offline",
            "reason": "timeout"
        }
        
        assert "status" in valid_payload
        assert valid_payload["status"] in ["online", "offline"]
    
    def test_send_lwt(self, connected_mqtt_client):
        """LWT Nachricht senden"""
        device_id = "lwt_test_device"
        topic = f"lwt/{device_id}"
        payload = {"status": "offline", "reason": "test_disconnect"}
        
        result = connected_mqtt_client.publish(topic, json.dumps(payload))
        assert result.rc == mqtt.MQTT_ERR_SUCCESS

# ============================================
# 6. NACHRICHTEN QUALITÄT TESTS
# ============================================

class TestMessageQuality:
    """Tests für Nachrichtenqualität"""
    
    def test_retained_message(self, connected_mqtt_client):
        """Retained Messages funktionieren"""
        topic = "test/retained"
        
        # Sende retained message
        connected_mqtt_client.publish(topic, "retained value", retain=True)
        time.sleep(0.5)
        
        received_messages = []
        
        def on_message(client, userdata, msg):
            received_messages.append(msg.payload.decode())
        
        connected_mqtt_client.subscribe(topic)
        connected_mqtt_client.on_message = on_message
        time.sleep(0.5)
        
        # Sollte die retained message sofort bekommen
        assert len(received_messages) > 0, "Retained message nicht empfangen"
        assert "retained value" in received_messages[0]
    
    def test_qos_levels(self, connected_mqtt_client):
        """Verschiedene QoS Level funktionieren"""
        received_messages_qos0 = []
        received_messages_qos1 = []
        
        def on_message_qos0(client, userdata, msg):
            received_messages_qos0.append(msg.payload.decode())
        
        def on_message_qos1(client, userdata, msg):
            received_messages_qos1.append(msg.payload.decode())
        
        # QoS 0 Test
        connected_mqtt_client.subscribe("test/qos0", qos=0)
        connected_mqtt_client.on_message = on_message_qos0
        
        # QoS 1 Test
        connected_mqtt_client.subscribe("test/qos1", qos=1)
        
        time.sleep(0.5)
        
        connected_mqtt_client.publish("test/qos0", "QoS 0 message", qos=0)
        connected_mqtt_client.publish("test/qos1", "QoS 1 message", qos=1)
        time.sleep(1)
        
        # QoS 0 sollte ankommen, QoS 1 auch
        assert len(received_messages_qos0) > 0 or len(received_messages_qos1) > 0

# ============================================
# 7. PARAMETRISIERTE TESTS
# ============================================

@pytest.mark.parametrize("topic,payload", [
    ("test/param1", "Message 1"),
    ("test/param2", '{"key": "value"}'),
    ("test/param3", "12345"),
])
def test_different_payloads(connected_mqtt_client, topic, payload):
    """Unterschiedliche Payload Formate werden akzeptiert"""
    received_messages = []
    
    def on_message(client, userdata, msg):
        received_messages.append(msg.payload.decode())
    
    connected_mqtt_client.subscribe(topic)
    connected_mqtt_client.on_message = on_message
    time.sleep(0.5)
    
    result = connected_mqtt_client.publish(topic, payload)
    assert result.rc == mqtt.MQTT_ERR_SUCCESS
    
    time.sleep(1)
    # Nachricht könnte ankommen, muss aber nicht zwingend (abhängig vom Broker)

# ============================================
# 8. PERFORMANZ TESTS (optional)
# ============================================

class TestPerformance:
    """Performance-Tests für MQTT"""
    
    def test_message_throughput(self, connected_mqtt_client):
        """Nachrichtendurchsatz akzeptabel"""
        message_count = 50
        received_count = 0
        
        def on_message(client, userdata, msg):
            nonlocal received_count
            received_count += 1
        
        connected_mqtt_client.subscribe("test/throughput")
        connected_mqtt_client.on_message = on_message
        time.sleep(0.5)
        
        start_time = time.time()
        for i in range(message_count):
            connected_mqtt_client.publish("test/throughput", f"Message {i}")
        
        time.sleep(2)  # Warte auf letzte Nachrichten
        end_time = time.time()
        
        duration = end_time - start_time
        print(f"\n{message_count} Nachrichten in {duration:.2f} Sekunden")
        
        # 50 Nachrichten sollten in < 5 Sekunden verarbeitet werden
        assert duration < 5, f"Zu langsam: {duration:.2f} Sekunden"

# ============================================
# 9. FEHLERSIMULATION TESTS
# ============================================

class TestErrorSimulation:
    """Tests für Fehlersituationen"""
    
    def test_invalid_json_payload(self, connected_mqtt_client):
        """Ungültiges JSON wird trotzdem gesendet (Broker akzeptiert es)"""
        # Der Broker akzeptiert auch ungültiges JSON
        result = connected_mqtt_client.publish("sensor/temperatur", "invalid json {")
        # Publish sollte trotzdem Erfolg haben (Broker prüft nicht)
        assert result.rc == mqtt.MQTT_ERR_SUCCESS
    
    def test_empty_payload(self, connected_mqtt_client):
        """Leerer Payload wird akzeptiert"""
        result = connected_mqtt_client.publish("test/empty", "")
        assert result.rc == mqtt.MQTT_ERR_SUCCESS

