#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <max6675.h>
#include <ArduinoJson.h>

// ==========================================
// KONFIGURATION
// ==========================================
const char* ssid = "Vodafone-3DDC";
const char* password = "xske7fyNCgy7abzC";
const char* mqtt_server = "192.168.0.126";
const int mqtt_port = 1883;
const char* client_id = "ESP8266_MAX6675";

// MAX6675 Pins
int thermoSCK = 13;   // D7 (GPIO13)
int thermoCS  = 15;   // D8 (GPIO15)
int thermoSO  = 12;   // D6 (GPIO12)

// Statische IP
IPAddress staticIP(192, 168, 0, 200);
IPAddress gateway(192, 168, 0, 1);
IPAddress subnet(255, 255, 255, 0);

MAX6675 thermocouple(thermoSCK, thermoCS, thermoSO);
WiFiClient espClient;
PubSubClient client(espClient);

// ==========================================
// SENSOR FILTER
// ==========================================
float letzteGueltigeTemp = 25.0;

float getFilteredTemperature() {
  float rohwert = thermocouple.readCelsius();
  
  if (isnan(rohwert)) {
    return letzteGueltigeTemp;
  }
  
  if (abs(rohwert - letzteGueltigeTemp) > 5.0) {
    return letzteGueltigeTemp;
  }
  
  letzteGueltigeTemp = rohwert;
  return rohwert;
}

// ==========================================
// FLEXIBLE JSON NACHRICHT (kompakt)
// ==========================================
void sendSensorData(float temperature) {
  // Verwende StaticJsonDocument für bessere Speichereffizienz
  StaticJsonDocument<256> doc;
  
  doc["device_id"] = "ESP8266_MAX6675";
  doc["device_type"] = "esp8266";
  doc["sensor"] = "max6675";
  doc["temp"] = temperature;
  doc["unit"] = "celsius";
  doc["rssi"] = WiFi.RSSI();
  doc["heap"] = ESP.getFreeHeap();
  doc["uptime"] = millis() / 1000;
  
  char buffer[256];
  size_t len = serializeJson(doc, buffer);
  
  // Wichtig: Nur senden wenn verbunden
  if (client.connected()) {
    if (client.publish("sensor/temperatur", buffer)) {
      Serial.print(" ");
      Serial.println(buffer);
    } else {
      Serial.println(" Publish fehlgeschlagen");
    }
  }
}

// ==========================================
// STATUS SENDEN
// ==========================================
void sendStatus(const char* status) {
  StaticJsonDocument<128> doc;
  doc["device_id"] = "ESP8266_MAX6675";
  doc["status"] = status;
  doc["rssi"] = WiFi.RSSI();
  
  char buffer[128];
  serializeJson(doc, buffer);
  client.publish("status/ESP8266_MAX6675", buffer, true);
}

// ==========================================
// WLAN
// ==========================================
void setup_wifi() {
  Serial.print("Verbinde mit WLAN: ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.config(staticIP, gateway, subnet);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n WLAN verbunden!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n WLAN Fehler! Neustart...");
    ESP.restart();
  }
}

// ==========================================
// MQTT mit LWT
// ==========================================
void reconnectMqtt() {
  while (!client.connected()) {
    Serial.print("Verbinde mit MQTT... ");
    
    // LWT (Last Will and Testament)
    if (client.connect(client_id, "status/ESP8266_MAX6675/will", 1, true, "offline")) {
      Serial.println(" verbunden (mit LWT)!");
      sendStatus("online");
    } else {
      Serial.print(" rc=");
      Serial.print(client.state());
      Serial.println(" - Wiederhole in 5 Sekunden");
      delay(5000);
    }
  }
}

// ==========================================
// SETUP
// ==========================================
void setup() {
  Serial.begin(115200);
  Serial.println("\n=================================");
  Serial.println("ESP8266 MAX6675 IoT Sensor");
  Serial.println("=================================");
  
  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  
  Serial.println(" System bereit!");
}

// ==========================================
// LOOP
// ==========================================
void loop() {
  if (!client.connected()) {
    reconnectMqtt();
  }
  client.loop();
  
  static unsigned long lastSensorRead = 0;
  unsigned long now = millis();
  
  if (now - lastSensorRead > 5000) {
    lastSensorRead = now;
    
    float temperature = getFilteredTemperature();
    sendSensorData(temperature);
  }
  
  delay(10);
}