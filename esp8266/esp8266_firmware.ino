// ============================================
// ESP8266 MAX6675 IoT Sensor
// Mit automatischem Provisioning, TLS, MQTT
// Statische IP für schnelle Verbindung
// ============================================
// Version: 1.0.0
// Autor: NouriDeg
// ============================================

#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>  // Für TLS Verbindungen
#include <PubSubClient.h>       // MQTT Client
#include <ArduinoJson.h>        // JSON Verarbeitung
#include <max6675.h>            // MAX6675 Sensor Treiber
#include "provisioning.h"       // Automatisches Device Provisioning

// ============================================
// WLAN KONFIGURATION
// ============================================
const char* WLAN_SSID = "Vodafone-3DDC";
const char* WLAN_PASSWORT = "xske7fyNCgy7abzC";

// ============================================
// STATISCHE IP (vermeidet DHCP Probleme)
// ============================================
IPAddress staticIP(192, 168, 0, 200);     // Feste IP für ESP8266
IPAddress gateway(192, 168, 0, 1);        // Router IP
IPAddress subnet(255, 255, 255, 0);       // Subnetzmaske
IPAddress dns(192, 168, 0, 1);            // DNS Server (Router)

// ============================================
// PROVISIONING SERVICE (für ersten Start)
// ============================================
const char* PROVISIONING_HOST = "192.168.0.105";  // Windows IP
const int PROVISIONING_PORT = 1883;               // MQTT Port ohne TLS

// ============================================
// MAX6675 PINS (SCK an D7 = GPIO13!)
// ============================================
const int PIN_SCK = 13;    // D7 = GPIO13 (Clock)
const int PIN_CS = 15;     // D8 = GPIO15 (Chip Select)
const int PIN_SO = 12;     // D6 = GPIO12 (Data Out)

// ============================================
// TIMING EINSTELLUNGEN
// ============================================
const unsigned long SENSOR_INTERVAL_MS = 5000;   // Alle 5 Sekunden messen

// ============================================
// GLOBALE OBJEKTE
// ============================================
MAX6675 thermocouple(PIN_SCK, PIN_CS, PIN_SO);
ProvisioningClient provisioner(PROVISIONING_HOST, PROVISIONING_PORT);

// MQTT Client (wird nach Provisioning initialisiert)
WiFiClientSecure* espClient = nullptr;
PubSubClient* mqttClient = nullptr;

// Provisionierte Credentials (vom Service erhalten)
String mqttBroker;
uint16_t mqttPort;
String mqttUser;
String mqttPassword;
String caCert;        // CA Zertifikat für TLS
String clientCert;    // Client Zertifikat (für mTLS)
String clientKey;     // Client Private Key

// Globale Zeiger für TLS Objekte (müssen lange leben)
BearSSL::X509List* caCertList = nullptr;
BearSSL::X509List* clientCertList = nullptr;
BearSSL::PrivateKey* clientPrivKey = nullptr;

// ============================================
// SENSOR-FILTER (glättet Ausreißer)
// ============================================
float letzteGueltigeTemp = 25.0;
int filterIndex = 0;
float tempRingBuffer[5];

float getFilteredTemperature() {
  float rohwert = thermocouple.readCelsius();
  
  // Fehler: Kein Thermoelement erkannt
  if (isnan(rohwert)) {
    return letzteGueltigeTemp;
  }
  
  // Ausreißererkennung: Sprung größer 5°C
  if (abs(rohwert - letzteGueltigeTemp) > 5.0) {
    Serial.print(" Ausreißer ignoriert: ");
    Serial.print(rohwert);
    Serial.print(" °C → ");
    Serial.print(letzteGueltigeTemp);
    Serial.println(" °C verwendet");
    return letzteGueltigeTemp;
  }
  
  // Ringbuffer für Mittelwertbildung
  tempRingBuffer[filterIndex] = rohwert;
  filterIndex = (filterIndex + 1) % 5;
  
  float summe = 0.0;
  int anzahl = 0;
  for (int i = 0; i < 5; i++) {
    if (tempRingBuffer[i] != 0.0) {
      summe += tempRingBuffer[i];
      anzahl++;
    }
  }
  
  float gemittelterWert = (anzahl > 0) ? (summe / anzahl) : rohwert;
  
  // Gleitender Filter (70% alt, 30% neu)
  float gefiltert = 0.7 * letzteGueltigeTemp + 0.3 * gemittelterWert;
  letzteGueltigeTemp = gefiltert;
  
  return gefiltert;
}

// ============================================
// WLAN MIT STATISCHER IP VERBINDEN
// ============================================
void connectWLAN() {
  // Statische IP VOR dem Verbinden setzen!
  WiFi.config(staticIP, gateway, subnet, dns);
  
  WiFi.begin(WLAN_SSID, WLAN_PASSWORT);
  Serial.print("Verbinde mit WLAN");
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n WLAN verbunden!");
    Serial.print("   IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("   Gateway: ");
    Serial.println(WiFi.gatewayIP());
    Serial.print("   Signal (RSSI): ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println("\n WLAN Fehler! Neustart...");
    delay(2000);
    ESP.restart();
  }
}

// ============================================
// MQTT VERBINDUNG (mit TLS)
// ============================================
void connectMQTT() {
  if (mqttClient == nullptr) return;
  
  while (!mqttClient->connected()) {
    Serial.print(" Verbinde mit MQTTS (TLS verschlüsselt)... ");
    
    if (mqttClient->connect("ESP8266_MAX6675", mqttUser.c_str(), mqttPassword.c_str())) {
      Serial.println(" verbunden!");
    } else {
      Serial.print(" fehlgeschlagen, rc=");
      Serial.print(mqttClient->state());
      Serial.println(" - Wiederhole in 5 Sekunden");
      delay(5000);
    }
  }
}

// ============================================
// TEMPERATUR ÜBER MQTT SENDEN
// ============================================
void sendTemperature() {
  if (mqttClient == nullptr || !mqttClient->connected()) return;
  
  float temperatur = getFilteredTemperature();
  
  // JSON Payload erstellen
  JsonDocument doc;
  doc["device_id"] = "ESP8266_MAX6675";
  doc["device_type"] = "esp8266";
  doc["sensor"] = "max6675";
  doc["temp"] = temperatur;
  doc["unit"] = "celsius";
  doc["rssi"] = WiFi.RSSI();
  doc["heap"] = ESP.getFreeHeap();
  doc["uptime"] = millis() / 1000;
  
  char buffer[256];
  serializeJson(doc, buffer);
  
  if (mqttClient->publish("sensor/temperatur", buffer)) {
    Serial.print(" ");
    Serial.println(buffer);
  } else {
    Serial.println(" Fehler beim Senden");
  }
}

// ============================================
// SETUP
// ============================================
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n=========================================");
  Serial.println("ESP8266 MAX6675 IoT Sensor");
  Serial.println("Mit automatischem Provisioning & TLS");
  Serial.println("=========================================\n");
  
  // Ringbuffer initialisieren
  for (int i = 0; i < 5; i++) {
    tempRingBuffer[i] = 0.0;
  }
  
  // ==========================================
  // 1. WLAN VERBINDEN
  // ==========================================
  connectWLAN();
  
  // ==========================================
  // 2. PROVISIONING (falls nötig)
  // ==========================================
  if (!provisioner.isProvisioned()) {
    Serial.println("\n Gerät nicht provisioniert. Starte Provisioning...");
    
    if (provisioner.provision()) {
      Serial.println(" Provisioning erfolgreich!");
    } else {
      Serial.println(" Provisioning fehlgeschlagen!");
      delay(5000);
      ESP.restart();
      return;
    }
  }
  
  // ==========================================
  // 3. PROVISIONIERTE CREDENTIALS LADEN
  // ==========================================
  provisioner.getCredentials(mqttBroker, mqttPort, mqttUser, mqttPassword, 
                             caCert, clientCert, clientKey);
  
  Serial.println("\n Provisionierte Credentials:");
  Serial.print("   Broker: ");
  Serial.println(mqttBroker);
  Serial.print("   Port: ");
  Serial.println(mqttPort);
  Serial.print("   User: ");
  Serial.println(mqttUser);
  Serial.print("   CA Cert Länge: ");
  Serial.println(caCert.length());
  
  // ==========================================
  // 4. TLS MIT ZERTIFIKATEN KONFIGURIEREN
  // ==========================================
  espClient = new WiFiClientSecure();
  
  if (caCert.length() > 0) {
    // CA Zertifikat für Server-Validierung
    caCertList = new BearSSL::X509List(caCert.c_str());
    espClient->setTrustAnchors(caCertList);
    Serial.println(" TLS mit CA Zertifikat aktiviert");
  } else {
    // Fallback: Unsicher (nur für Tests!)
    espClient->setInsecure();
    Serial.println(" TLS ohne Zertifikatsprüfung (unsicher!)");
  }
  
  // Client Zertifikat für gegenseitige Authentifizierung (mTLS)
  if (clientCert.length() > 0 && clientKey.length() > 0) {
    clientCertList = new BearSSL::X509List(clientCert.c_str());
    clientPrivKey = new BearSSL::PrivateKey(clientKey.c_str());
    espClient->setClientRSACert(clientCertList, clientPrivKey);
    Serial.println(" Client Zertifikat für mTLS aktiviert");
  }
  
  // ==========================================
  // 5. MQTT CLIENT INITIALISIEREN
  // ==========================================
  mqttClient = new PubSubClient(*espClient);
  mqttClient->setServer(mqttBroker.c_str(), mqttPort);
  
  Serial.println("\n System bereit!");
}

// ============================================
// LOOP
// ============================================
void loop() {
  if (mqttClient == nullptr) {
    delay(1000);
    return;
  }
  
  if (!mqttClient->connected()) {
    connectMQTT();
  }
  mqttClient->loop();
  
  static unsigned long lastSensor = 0;
  if (millis() - lastSensor > SENSOR_INTERVAL_MS) {
    lastSensor = millis();
    sendTemperature();
  }
  
  delay(10);
}