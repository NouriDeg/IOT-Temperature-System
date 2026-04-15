// ============================================
// provisioning.h
// ============================================
// Automatisches Device Provisioning für ESP8266
// 
// Funktionen:
// - Keine statischen MQTT Credentials im Code
// - Automatischer Handshake mit Provisioning Service
// - Persistente Speicherung im EEPROM
// - Unterstützung für TLS Zertifikate (mTLS)
// - Factory Reset Funktion
// ============================================

#ifndef PROVISIONING_H
#define PROVISIONING_H

#include <ESP8266WiFi.h>      // WLAN Funktionen
#include <PubSubClient.h>      // MQTT Client
#include <ArduinoJson.h>       // JSON Parsing
#include <EEPROM.h>            // Persistenten Speicher

// ============================================
// PROVISIONING CLIENT KLASSE
// ============================================
// Verwaltet den automatischen Handshake mit dem Provisioning Service
// Holt dynamisch MQTT Credentials und TLS Zertifikate
// ============================================
class ProvisioningClient {
private:
  // ============================================
  // CREDENTIALS STRUKTUR (wird im EEPROM gespeichert)
  // ============================================
  struct Credentials {
    bool isProvisioned = false;           // Flag: true = bereits provisioniert
    char device_id[32] = {0};             // Eindeutige Geräte-ID (aus MAC)
    char mqtt_broker[64] = {0};           // MQTT Broker IP (z.B. 192.168.0.105)
    uint16_t mqtt_port = 8883;            // MQTT Port (8883 = TLS)
    char mqtt_user[32] = {0};             // MQTT Benutzername (vom Service generiert)
    char mqtt_password[64] = {0};         // MQTT Passwort (vom Service generiert)
    char ca_cert[2048] = {0};             // CA Zertifikat (für Server-Validierung)
    char client_cert[4096] = {0};         // Client Zertifikat (für mTLS, optional)
    char client_key[2048] = {0};          // Client Private Key (für mTLS, optional)
    uint32_t provisioned_at = 0;          // Zeitstempel der Provisionierung
  } creds;
  
  // ============================================
  // PROVISIONING SERVICE KONFIGURATION
  // ============================================
  const char* prov_host;                  // Host des Provisioning Service
  const int prov_port;                    // Port (1883, ohne TLS)
  const char* prov_request_topic = "devices/%s/provisioning/request";
  const char* prov_response_topic = "devices/%s/provisioning/response";
  
  // ============================================
  // MQTT CLIENT (temporär, ohne TLS)
  // ============================================
  WiFiClient wifiClient;
  PubSubClient mqttClient;
  bool provisioningComplete = false;
  String receivedResponse;
  
  // ============================================
  // HILFSFUNKTIONEN
  // ============================================
  
  // Generiert eine eindeutige Device-ID aus der MAC-Adresse
  String getDeviceId() {
    String mac = WiFi.macAddress();
    mac.replace(":", "");
    return "esp8266_" + mac;
  }
  
  // ============================================
  // MQTT CALLBACK FÜR PROVISIONING RESPONSE
  // ============================================
  void callback(char* topic, byte* payload, unsigned int length) {
    String message;
    for (unsigned int i = 0; i < length; i++) {
      message += (char)payload[i];
    }
    receivedResponse = message;
    provisioningComplete = true;
    Serial.println("📥 Provisioning Response empfangen!");
  }
  
  // ============================================
  // CREDENTIALS IM EEPROM SPEICHERN
  // ============================================
  void saveCredentials() {
    Serial.println("💾 Speichere Credentials im EEPROM...");
    Serial.print("   isProvisioned: ");
    Serial.println(creds.isProvisioned);
    EEPROM.put(0, creds);
    EEPROM.commit();
    Serial.println("✅ Credentials gespeichert!");
    
    // Verifiziere
    Credentials test;
    EEPROM.get(0, test);
    Serial.print("   Verifiziert - isProvisioned: ");
    Serial.println(test.isProvisioned);
  }
  
public:
  // ============================================
  // KONSTRUKTOR
  // ============================================
  ProvisioningClient(const char* host, int port) 
    : prov_host(host), prov_port(port) {
    EEPROM.begin(4096);
  }
  
  // ============================================
  // PRÜFT OB GERÄT BEREITS PROVISIONIERT IST
  // ============================================
    bool isProvisioned() {
        EEPROM.get(0, creds);
        Serial.print("🔍 isProvisioned Check - Flag: ");
        Serial.println(creds.isProvisioned);
        Serial.print("   Device ID: ");
        Serial.println(creds.device_id);
        return creds.isProvisioned;
    }
  
  // ============================================
  // FÜHRT PROVISIONING DURCH
  // ============================================
    bool provision() {
        Serial.println("\n🔐 Starte Provisioning Prozess...");

        // 1. GERÄTE-INFORMATIONEN
        String device_id = getDeviceId();
        Serial.print("   Device ID: ");
        Serial.println(device_id);
        Serial.print("   MAC: ");
        Serial.println(WiFi.macAddress());
        
        // 2. TEMPORÄRE MQTT VERBINDUNG
        mqttClient.setClient(wifiClient);
        mqttClient.setServer(prov_host, prov_port);
        mqttClient.setCallback([this](char* t, byte* p, unsigned int l) { this->callback(t, p, l); });
    
    char requestTopic[128];
    snprintf(requestTopic, sizeof(requestTopic), prov_request_topic, device_id.c_str());
    
    char responseTopic[128];
    snprintf(responseTopic, sizeof(responseTopic), prov_response_topic, device_id.c_str());
    
    // Verbindungsversuche
    int attempts = 0;
    while (!mqttClient.connect(device_id.c_str()) && attempts < 5) {
      Serial.print("   MQTT Connect Versuch ");
      Serial.println(attempts + 1);
      delay(2000);
      attempts++;
    }
    
    if (!mqttClient.connected()) {
      Serial.println("❌ Provisioning MQTT Verbindung fehlgeschlagen!");
      return false;
    }
    
    Serial.println("   Temporäre MQTT Verbindung hergestellt");
    
    // ==========================================
    // WICHTIG: ERST ABONNIEREN, DANN SENDEN!
    // ==========================================
    Serial.println("   Abonniere Response Topic...");
    mqttClient.subscribe(responseTopic);
    delay(500);  // Kurze Pause für MQTT Broker
    
    // 3. PROVISIONING REQUEST SENDEN
    StaticJsonDocument<256> req;
    req["mac_address"] = WiFi.macAddress();
    req["device_id"] = device_id;
    req["firmware_version"] = "1.0.0";
    
    char buffer[256];
    serializeJson(req, buffer);
    mqttClient.publish(requestTopic, buffer);
    Serial.println(" Provisioning Request gesendet");
    
    // 4. AUF RESPONSE WARTEN (30 Sekunden)
    unsigned long timeout = millis() + 30000;
    while (millis() < timeout && !provisioningComplete) {
      mqttClient.loop();
      delay(100);
    }
    
    mqttClient.disconnect();
    
    if (!provisioningComplete) {
      Serial.println(" Keine Provisioning Response erhalten!");
      return false;
    }
    
    // 5. RESPONSE PARSEN
    StaticJsonDocument<6144> doc;
    DeserializationError error = deserializeJson(doc, receivedResponse);
    
    if (error) {
      Serial.print(" JSON Parse Fehler: ");
      Serial.println(error.c_str());
      return false;
    }
    
    const char* status = doc["status"];
    if (strcmp(status, "success") != 0) {
      Serial.print(" Provisioning Status: ");
      Serial.println(status);
      return false;
    }
    
    // 6. CREDENTIALS SPEICHERN
    strlcpy(creds.device_id, device_id.c_str(), sizeof(creds.device_id));
    strlcpy(creds.mqtt_broker, doc["mqtt_broker"], sizeof(creds.mqtt_broker));
    creds.mqtt_port = doc["mqtt_port"];
    strlcpy(creds.mqtt_user, doc["mqtt_username"], sizeof(creds.mqtt_user));
    strlcpy(creds.mqtt_password, doc["mqtt_password"], sizeof(creds.mqtt_password));
    
    if (doc.containsKey("certificates")) {
      JsonObject certs = doc["certificates"];
      strlcpy(creds.ca_cert, certs["ca_cert"], sizeof(creds.ca_cert));
      strlcpy(creds.client_cert, certs["client_cert"], sizeof(creds.client_cert));
      strlcpy(creds.client_key, certs["client_key"], sizeof(creds.client_key));
    }
    
    creds.isProvisioned = true;
    creds.provisioned_at = millis();
    saveCredentials();
    
    Serial.println(" Provisioning erfolgreich!");
    return true;
  }
  
  // ============================================
  // PROVISIONIERTE CREDENTIALS ABRUFEN
  // ============================================
  void getCredentials(String &broker, uint16_t &port, 
                      String &user, String &password, 
                      String &caCert, String &clientCert, String &clientKey) {
    if (!creds.isProvisioned) {
      EEPROM.get(0, creds);
    }
    
    broker = String(creds.mqtt_broker);
    port = creds.mqtt_port;
    user = String(creds.mqtt_user);
    password = String(creds.mqtt_password);
    caCert = String(creds.ca_cert);
    clientCert = String(creds.client_cert);
    clientKey = String(creds.client_key);
  }
  
  // ============================================
  // FACTORY RESET
  // ============================================
  void factoryReset() {
    creds.isProvisioned = false;
    memset(&creds, 0, sizeof(creds));
    saveCredentials();
    Serial.println(" Factory Reset durchgeführt. Neustart...");
    delay(1000);
    ESP.restart();
  }
};

#endif