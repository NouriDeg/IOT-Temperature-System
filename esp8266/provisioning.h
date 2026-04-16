#ifndef PROVISIONING_H
#define PROVISIONING_H

#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <EEPROM.h>

class ProvisioningClient {
private:
  struct Credentials {
    bool isProvisioned = false;
    char device_id[32] = {0};
    char mqtt_broker[64] = {0};
    uint16_t mqtt_port = 8883;
    char mqtt_user[32] = {0};
    char mqtt_password[64] = {0};
    char ca_cert[2048] = {0};
    uint32_t provisioned_at = 0;
  } creds;
  
  const char* prov_host;
  const int prov_port;
  
  // Vereinfachte Topics (wie dein Provisioner)
  const char* prov_request_topic = "provisioning/request";
  const char* prov_response_topic = "provisioning/response";
  
  WiFiClient wifiClient;
  PubSubClient mqttClient;
  bool provisioningComplete = false;
  String receivedResponse;
  
  String getDeviceId() {
    String mac = WiFi.macAddress();
    mac.replace(":", "");
    return "esp8266_" + mac;
  }
  
  // Wichtig: Der Callback MUSS als static Funktion oder Lambda registriert werden
  static void staticCallback(char* topic, byte* payload, unsigned int length) {
    // Die Instanz muss irgendwo gespeichert werden - einfacher: direkte Verarbeitung
    ProvisioningClient* instance = nullptr;
    // Das ist ein bekanntes Problem mit PubSubClient und Klassenmethoden
    // Alternative: Verarbeite im Loop
  }
  
  void saveCredentials() {
    EEPROM.begin(4096);
    EEPROM.put(0, creds);
    EEPROM.commit();
    EEPROM.end();
    Serial.println(" Credentials gespeichert!");
  }
  
public:
  ProvisioningClient(const char* host, int port) 
    : prov_host(host), prov_port(port) {
    EEPROM.begin(4096);
  }
  
  bool isProvisioned() {
    EEPROM.get(0, creds);
    return creds.isProvisioned;
  }
  
  bool provision() {
    Serial.println("\n Starte Provisioning Prozess...");
    
    String device_id = getDeviceId();
    Serial.print("   Device ID: ");
    Serial.println(device_id);
    
    // MQTT Client für Provisioning
    mqttClient.setClient(wifiClient);
    mqttClient.setServer(prov_host, prov_port);
    
    // Verbinden
    int attempts = 0;
    while (!mqttClient.connect(device_id.c_str()) && attempts < 5) {
      Serial.print("   MQTT Connect Versuch ");
      Serial.println(attempts + 1);
      delay(2000);
      attempts++;
    }
    
    if (!mqttClient.connected()) {
      Serial.println(" Provisioning MQTT Verbindung fehlgeschlagen!");
      return false;
    }
    
    Serial.println("    Temporäre MQTT Verbindung hergestellt");
    
    // Response Topic abonnieren
    mqttClient.subscribe(prov_response_topic);
    delay(500);
    
    // Provisioning Request senden
    StaticJsonDocument<256> req;
    req["mac_address"] = WiFi.macAddress();
    req["device_id"] = device_id;
    req["firmware_version"] = "1.0.0";
    
    char buffer[256];
    serializeJson(req, buffer);
    mqttClient.publish(prov_request_topic, buffer);
    Serial.print(" Request gesendet: ");
    Serial.println(buffer);
    
    // Auf Response warten - HIER MÜSSEN WIR LOOPEN UND NACH NACHRICHTEN SCHAUEN!
    unsigned long timeout = millis() + 30000;
    while (millis() < timeout && !provisioningComplete) {
      mqttClient.loop();  // Wichtig: Verarbeitet eingehende Nachrichten!
      
      // Prüfe manuell auf Nachrichten (Fallback)
      if (mqttClient.available()) {
        // PubSubClient hat keine available() Methode - wir sind auf loop() angewiesen
      }
      delay(50);
    }
    
    mqttClient.disconnect();
    
    if (!provisioningComplete) {
      Serial.println(" Keine Provisioning Response erhalten!");
      return false;
    }
    
    // Response parsen
    StaticJsonDocument<1024> doc;
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
    
    // Credentials speichern
    strlcpy(creds.device_id, device_id.c_str(), sizeof(creds.device_id));
    strlcpy(creds.mqtt_broker, doc["mqtt_broker"] | "192.168.0.105", sizeof(creds.mqtt_broker));
    creds.mqtt_port = doc["mqtt_port"] | 8883;
    strlcpy(creds.mqtt_user, doc["mqtt_username"] | "", sizeof(creds.mqtt_user));
    strlcpy(creds.mqtt_password, doc["mqtt_password"] | "", sizeof(creds.mqtt_password));
    
    creds.isProvisioned = true;
    creds.provisioned_at = millis();
    saveCredentials();
    
    Serial.println(" Provisioning erfolgreich!");
    return true;
  }
  
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
    clientCert = "";
    clientKey = "";
  }
  
  void factoryReset() {
    Serial.println(" Factory Reset...");
    creds.isProvisioned = false;
    memset(&creds, 0, sizeof(creds));
    saveCredentials();
    delay(1000);
    ESP.restart();
  }
  
  // Hilfsfunktion um die Response manuell zu setzen (für Tests)
  void setResponseForTesting(String response) {
    receivedResponse = response;
    provisioningComplete = true;
  }
};

#endif 