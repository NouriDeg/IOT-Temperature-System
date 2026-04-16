import paho.mqtt.client as mqtt
import json
import time

# ===== KONFIGURATION =====
MQTT_BROKER = "192.168.0.105"  # IHRE BROKER IP
MQTT_PORT = 1883
REQUEST_TOPIC = "provisioning/request"
RESPONSE_TOPIC = "provisioning/response"

# ===== WLAN KONFIGURATION DIE GESENDET WERDEN SOLL =====
TARGET_WIFI_SSID = "Vodafone-3DDC"     # ← ÄNDERN
TARGET_WIFI_PASSWORD = "xske7fyNCgy7abzC"   # ← ÄNDERN

def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    print(f"\n Empfangen auf {msg.topic}: {payload}")
    
    if msg.topic == REQUEST_TOPIC:
        # Extrahiere Device ID aus der Nachricht
        parts = payload.split('|')
        device_id = parts[0] if len(parts) > 0 else "unknown"
        
        print(f" Provisioning Anfrage von Device: {device_id}")
        
        # Erstelle Antwort mit WLAN-Konfiguration
        response = {
            "status": "success",
            "ssid": TARGET_WIFI_SSID,
            "password": TARGET_WIFI_PASSWORD,
            "interval": 30,
            "timestamp": int(time.time())
        }
        
        response_json = json.dumps(response)
        print(f" Sende Antwort: {response_json}")
        
        # Sende Antwort
        client.publish(RESPONSE_TOPIC, response_json)
        print(f" Antwort gesendet an {RESPONSE_TOPIC}")

# Verbinden
client = mqtt.Client()
client.on_message = on_message

print(f" Verbinde zu MQTT Broker {MQTT_BROKER}:{MQTT_PORT}...")
client.connect(MQTT_BROKER, MQTT_PORT, 60)

client.subscribe(REQUEST_TOPIC)
print(f" Abonniert: {REQUEST_TOPIC}")
print(f" Antwort wird gesendet an: {RESPONSE_TOPIC}")
print(f" Ziel-WLAN: {TARGET_WIFI_SSID}")
print("\n Warte auf Provisioning Anfragen... (Strg+C zum Beenden)\n")

try:
    client.loop_forever()
except KeyboardInterrupt:
    print("\n Server gestoppt")
    client.disconnect()