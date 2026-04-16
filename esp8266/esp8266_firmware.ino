// ============================================
// ESP8266 MAX6675 IoT Sensor
// MIT AUTOMATISCHEM PROVISIONING & TLS
// ============================================
//================================================
// Version: 2.0 - Final 
// Autor: Nouri (15.04.2026)
//==================================================
// Dieser Code:
// - Holt automatisch MQTT Credentials vom Provisioning Service
// - Speichert Credentials persistent im EEPROM
// - Verbindet sich mit TLS (Port 8883) zum MQTT Broker
// - Sendet Temperaturdaten vom MAX6675 Sensor
// - Verwendet vereinfachte Topics (provisioning/request, provisioning/response)
// ============================================

#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <max6675.h>
#include <EEPROM.h>

// ============================================
// 1. WLAN KONFIGURATION
// ============================================
const char* WLAN_SSID = "Vodafone-3DDC";
const char* WLAN_PASSWORT = "xske7fyNCgy7abzC";

// ============================================
// 2. STATISCHE IP (vermeidet DHCP Probleme)
// ============================================
IPAddress staticIP(192, 168, 0, 200);     // Feste IP für ESP8266
IPAddress gateway(192, 168, 0, 1);        // Router IP (Gateway)
IPAddress subnet(255, 255, 255, 0);       // Subnetzmaske
IPAddress dns(192, 168, 0, 1);            // DNS Server (Router)

// ============================================
// 3. PROVISIONING SERVICE KONFIGURATION
// ============================================
const char* PROVISIONING_HOST = "192.168.0.105";   // IP deines Windows Rechners
const int PROVISIONING_PORT = 1883;                // MQTT Port (ohne TLS)

// Vereinfachte Topics (wie dein Provisioner sie erwartet)
const char* PROV_REQUEST_TOPIC = "provisioning/request";
const char* PROV_RESPONSE_TOPIC = "provisioning/response";

// ============================================
// 4. MAX6675 PINS (SCK an D7 = GPIO13!)
// ============================================
const int PIN_SCK = 13;    // D7 = GPIO13
const int PIN_CS = 15;     // D8 = GPIO15
const int PIN_SO = 12;     // D6 = GPIO12

// ============================================
// 5. EEPROM KONFIGURATION
// ============================================
#define EEPROM_SIZE 4096
#define PROVISIONED_FLAG_ADDR 0
#define MQTT_BROKER_ADDR 50
#define MQTT_PORT_ADDR 120
#define MQTT_USER_ADDR 124
#define MQTT_PASS_ADDR 160

// ============================================
// 6. GLOBALE OBJEKTE
// ============================================
MAX6675 thermocouple(PIN_SCK, PIN_CS, PIN_SO);
WiFiClientSecure espClient;                   // TLS-fähiger WiFi Client
PubSubClient mqttClient(espClient);           // MQTT Client mit TLS

// Globale Variablen für Geräteinformationen
String device_id = "";
String mac_address = "";

// Globale Variablen für provisionierte Credentials
String mqttBroker;
uint16_t mqttPort;
String mqttUser;
String mqttPassword;

// Provisioning Status
bool provisioned = false;
bool provisioningComplete = false;
String receivedResponse = "";
unsigned long provisioningStartTime = 0;

// Temporärer MQTT Client für Provisioning (ohne TLS)
WiFiClient tempWifiClient;
PubSubClient provClient(tempWifiClient);

// ============================================
// 7. SENSOR-FILTER (glättet Ausreißer)
// ============================================
float letzteGueltigeTemp = 25.0;
int filterIndex = 0;
float tempRingBuffer[5];

float getFilteredTemperature() {
    float rohwert = thermocouple.readCelsius();
    
    if (isnan(rohwert)) {
        return letzteGueltigeTemp;
    }
    
    if (abs(rohwert - letzteGueltigeTemp) > 5.0) {
        Serial.print(" Ausreißer ignoriert: ");
        Serial.print(rohwert);
        Serial.print(" °C → ");
        Serial.print(letzteGueltigeTemp);
        Serial.println(" °C verwendet");
        return letzteGueltigeTemp;
    }
    
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
    float gefiltert = 0.7 * letzteGueltigeTemp + 0.3 * gemittelterWert;
    letzteGueltigeTemp = gefiltert;
    
    return gefiltert;
}

// ============================================
// 8. PROVISIONING CALLBACK (globale Funktion!)
// ============================================
void provCallback(char* topic, byte* payload, unsigned int length) {
    Serial.println(" Provisioning Response empfangen!");
    Serial.print("   Topic: ");
    Serial.println(topic);
    
    // Payload in String umwandeln
    String message;
    for (unsigned int i = 0; i < length; i++) {
        message += (char)payload[i];
    }
    
    Serial.print("   Payload: ");
    Serial.println(message);
    
    receivedResponse = message;
    provisioningComplete = true;
}

// ============================================
// 9. GERÄTE INFO
// ============================================
void setupDeviceInfo() {
    byte mac[6];
    WiFi.macAddress(mac);
    
    char macStr[18];
    snprintf(macStr, sizeof(macStr), "%02X:%02X:%02X:%02X:%02X:%02X",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    mac_address = String(macStr);
    
    char deviceIdStr[18];
    snprintf(deviceIdStr, sizeof(deviceIdStr), "esp8266_%02X%02X%02X%02X%02X%02X",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    device_id = String(deviceIdStr);
    
    Serial.println("=== GERÄTE INFO ===");
    Serial.println("Device ID: " + device_id);
    Serial.println("MAC: " + mac_address);
}

// ============================================
// 10. EEPROM FUNKTIONEN
// ============================================
void saveCredentials(String broker, uint16_t port, String user, String password) {
    EEPROM.begin(EEPROM_SIZE);
    
    EEPROM.write(PROVISIONED_FLAG_ADDR, 1);
    
    for (int i = 0; i < broker.length(); i++) {
        EEPROM.write(MQTT_BROKER_ADDR + i, broker[i]);
    }
    EEPROM.write(MQTT_BROKER_ADDR + broker.length(), '\0');
    
    EEPROM.put(MQTT_PORT_ADDR, port);
    
    for (int i = 0; i < user.length(); i++) {
        EEPROM.write(MQTT_USER_ADDR + i, user[i]);
    }
    EEPROM.write(MQTT_USER_ADDR + user.length(), '\0');
    
    for (int i = 0; i < password.length(); i++) {
        EEPROM.write(MQTT_PASS_ADDR + i, password[i]);
    }
    EEPROM.write(MQTT_PASS_ADDR + password.length(), '\0');
    
    EEPROM.commit();
    EEPROM.end();
    Serial.println(" Credentials im EEPROM gespeichert!");
}

bool loadCredentials() {
    EEPROM.begin(EEPROM_SIZE);
    
    bool isProvisioned = (EEPROM.read(PROVISIONED_FLAG_ADDR) == 1);
    
    if (isProvisioned) {
        char buf[128];
        int i = 0;
        
        while (i < 127) {
            buf[i] = EEPROM.read(MQTT_BROKER_ADDR + i);
            if (buf[i] == '\0') break;
            i++;
        }
        buf[i] = '\0';
        mqttBroker = String(buf);
        
        EEPROM.get(MQTT_PORT_ADDR, mqttPort);
        
        i = 0;
        while (i < 127) {
            buf[i] = EEPROM.read(MQTT_USER_ADDR + i);
            if (buf[i] == '\0') break;
            i++;
        }
        buf[i] = '\0';
        mqttUser = String(buf);
        
        i = 0;
        while (i < 127) {
            buf[i] = EEPROM.read(MQTT_PASS_ADDR + i);
            if (buf[i] == '\0') break;
            i++;
        }
        buf[i] = '\0';
        mqttPassword = String(buf);
        
        EEPROM.end();
        return true;
    }
    EEPROM.end();
    return false;
}

void clearProvisioning() {
    EEPROM.begin(EEPROM_SIZE);
    for (int i = 0; i < EEPROM_SIZE; i++) {
        EEPROM.write(i, 0);
    }
    EEPROM.commit();
    EEPROM.end();
    Serial.println(" Provisionierung gelöscht! ");
}

// ============================================
// 11. WLAN VERBINDEN
// ============================================
void connectWLAN() {
    WiFi.config(staticIP, gateway, subnet, dns);
    WiFi.begin(WLAN_SSID, WLAN_PASSWORT);
    Serial.print("Verbinde mit WLAN");
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 40) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n WLAN verbunden!");
        Serial.print("   IP: ");
        Serial.println(WiFi.localIP());
        Serial.print("   MAC: ");
        Serial.println(WiFi.macAddress());
    } else {
        Serial.println("\n WLAN Fehler! Neustart...");
        delay(2000);
        ESP.restart();
    }
}

// ============================================
// 12. PROVISIONING DURCHFÜHREN
// ============================================
bool performProvisioning() {
    Serial.println("\n Starte Provisioning Prozess...");
    
    provisioningComplete = false;
    receivedResponse = "";
    
    // Provisioning Client einrichten
    provClient.setClient(tempWifiClient);
    provClient.setServer(PROVISIONING_HOST, PROVISIONING_PORT);
    provClient.setCallback(provCallback);
    
    // Verbindung zum Provisioning Service herstellen
    Serial.print("   Verbinde mit MQTT Broker ");
    Serial.print(PROVISIONING_HOST);
    Serial.print(":");
    Serial.print(PROVISIONING_PORT);
    Serial.println(" (ohne TLS)");
    
    int attempts = 0;
    while (!provClient.connected() && attempts < 10) {
        Serial.print("   Connect Versuch ");
        Serial.print(attempts + 1);
        
        if (provClient.connect(device_id.c_str())) {
            Serial.println(" ");
        } else {
            Serial.print("  (rc=");
            Serial.print(provClient.state());
            Serial.println(")");
            delay(2000);
            attempts++;
        }
    }
    
    if (!provClient.connected()) {
        Serial.println(" Provisioning MQTT Verbindung fehlgeschlagen!");
        return false;
    }
    
    Serial.println(" Temporäre MQTT Verbindung hergestellt ");
    
    // Response Topic abonnieren (WICHTIG: vor dem Senden!)
    provClient.subscribe(PROV_RESPONSE_TOPIC);
    delay(500);
    Serial.print("   Abonniert: ");
    Serial.println(PROV_RESPONSE_TOPIC);
    
    // Provisioning Request erstellen
    StaticJsonDocument<256> req;
    req["mac_address"] = mac_address;
    req["device_id"] = device_id;
    req["firmware_version"] = "1.0.0";
    
    char buffer[256];
    serializeJson(req, buffer);
    
    // Request senden
    provClient.publish(PROV_REQUEST_TOPIC, buffer);
    Serial.print(" Provisioning Request gesendet: ");
    Serial.println(buffer);
    
    // Auf Response warten (30 Sekunden Timeout)
    unsigned long timeout = millis() + 30000;
    while (millis() < timeout && !provisioningComplete) {
        provClient.loop();  // Wichtig: MQTT Nachrichten verarbeiten!
        delay(50);
    }
    
    provClient.disconnect();
    
    if (!provisioningComplete) {
        Serial.println(" Keine Provisioning Response erhalten!");
        Serial.println("   Timeout nach 30 Sekunden");
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
    Serial.print("   Status: ");
    Serial.println(status);
    
    if (strcmp(status, "success") != 0) {
        Serial.print(" Provisioning Status: ");
        Serial.println(status);
        const char* message = doc["message"];
        if (message) {
            Serial.print("   Nachricht: ");
            Serial.println(message);
        }
        return false;
    }
    
    // Credentials aus Response extrahieren
    String broker = doc["mqtt_broker"].as<String>();
    uint16_t port = doc["mqtt_port"] | 8883;
    String user = doc["mqtt_username"].as<String>();
    String password = doc["mqtt_password"].as<String>();
    
    // Im EEPROM speichern
    saveCredentials(broker, port, user, password);
    
    // Globale Variablen aktualisieren
    mqttBroker = broker;
    mqttPort = port;
    mqttUser = user;
    mqttPassword = password;
    
    Serial.println(" Provisioning erfolgreich!");
    Serial.print("   Broker: ");
    Serial.println(mqttBroker);
    Serial.print("   Port: ");
    Serial.println(mqttPort);
    Serial.print("   User: ");
    Serial.println(mqttUser);
    
    return true;
}

// ============================================
// 13. MQTT VERBINDEN (mit TLS)
// ============================================
void connectMQTT() {
    // Für selbstsignierte Zertifikate (Entwicklung)
    espClient.setInsecure();
    
    while (!mqttClient.connected()) {
        Serial.print("🔌 Verbinde mit MQTTS (TLS verschlüsselt) Port ");
        Serial.print(mqttPort);
        Serial.print("... ");
        
        if (mqttClient.connect(device_id.c_str(), mqttUser.c_str(), mqttPassword.c_str())) {
            Serial.println(" verbunden!");
            
            // Status online publishen
            mqttClient.publish(("status/" + device_id + "/online").c_str(), "true", true);
        } else {
            Serial.print(" fehlgeschlagen, rc=");
            Serial.print(mqttClient.state());
            Serial.println(" - Wiederhole in 5 Sekunden");
            delay(5000);
        }
    }
}

// ============================================
// 14. TEMPERATUR SENDEN
// ============================================
void sendTemperature() {
    if (!mqttClient.connected()) return;
    
    float temperatur = getFilteredTemperature();
    
    // Flexibles JSON Payload
    JsonDocument doc;
    doc["device_id"] = device_id;
    doc["device_type"] = "esp8266";
    doc["sensor"] = "max6675";
    doc["temp"] = temperatur;
    doc["unit"] = "celsius";
    doc["rssi"] = WiFi.RSSI();
    doc["heap"] = ESP.getFreeHeap();
    doc["uptime"] = millis() / 1000;
    
    char buffer[256];
    serializeJson(doc, buffer);
    
    if (mqttClient.publish("sensor/temperatur", buffer)) {
        Serial.print(" ");
        Serial.println(buffer);
    } else {
        Serial.println(" Fehler beim Senden");
    }
}

// ============================================
// 15. SERIELLE KOMMANDOS (für Debug)
// ============================================
void handleSerialCommands() {
    if (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();
        cmd.toUpperCase();
        
        if (cmd == "RESET") {
            Serial.println("\n Factory Reset wird durchgeführt...");
            clearProvisioning();
            Serial.println("   Neustart in 2 Sekunden...");
            delay(2000);
            ESP.restart();
        }
        else if (cmd == "STATUS") {
            Serial.println("\n=== SYSTEM STATUS ===");
            Serial.print("Device ID: ");
            Serial.println(device_id);
            Serial.print("Provisioned: ");
            Serial.println(provisioned ? "Ja" : "Nein");
            Serial.print("MQTT Connected: ");
            Serial.println(mqttClient.connected() ? "Ja" : "Nein");
            Serial.print("Heap: ");
            Serial.println(ESP.getFreeHeap());
            Serial.print("RSSI: ");
            Serial.println(WiFi.RSSI());
        }
        else if (cmd == "INFO") {
            Serial.println("\n=== PROVISIONING INFO ===");
            Serial.print("Broker: ");
            Serial.println(mqttBroker);
            Serial.print("Port: ");
            Serial.println(mqttPort);
            Serial.print("User: ");
            Serial.println(mqttUser);
        }
    }
}

// ============================================
// 16. SETUP
// ============================================
void setup() {
    Serial.begin(115200);
    delay(1000);
    
    Serial.println("\n=========================================");
    Serial.println("ESP8266 MAX6675 IoT Sensor");
    Serial.println("MIT AUTOMATISCHEM PROVISIONING & TLS");
    Serial.println("=========================================\n");
    
    // Ringbuffer für Sensor-Filter initialisieren
    for (int i = 0; i < 5; i++) {
        tempRingBuffer[i] = 0.0;
    }
    
    // MAX6675 initialisieren
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    delay(500);
    
    // WLAN verbinden
    connectWLAN();
    
    // Geräteinformationen ausgeben
    setupDeviceInfo();
    
    // Gespeicherte Credentials laden
    if (loadCredentials()) {
        Serial.println(" Gespeicherte Credentials gefunden!");
        provisioned = true;
    } else {
        Serial.println(" Keine gespeicherten Credentials gefunden!");
        provisioned = false;
    }
    
    // Provisioning durchführen (falls nötig)
    if (!provisioned) {
        Serial.println(" Starte automatisches Provisioning...");
        if (performProvisioning()) {
            provisioned = true;
        } else {
            Serial.println("❌ Provisioning fehlgeschlagen!");
            Serial.println("   Tipp: 'RESET' senden für Factory Reset");
            Serial.println("   Neustart in 10 Sekunden...");
            delay(10000);
            ESP.restart();
            return;
        }
    }
    
    // MQTT Client mit den provisionierten Credentials einrichten
    mqttClient.setServer(mqttBroker.c_str(), mqttPort);
    
    Serial.println("\n Provisionierte Credentials:");
    Serial.print("   Broker: ");
    Serial.println(mqttBroker);
    Serial.print("   Port: ");
    Serial.println(mqttPort);
    Serial.print("   User: ");
    Serial.println(mqttUser);
    
    Serial.println("\n System bereit!");
    Serial.println("📌 Befehle über Serial Monitor: RESET, STATUS, INFO");
}

// ============================================
// 17. LOOP
// ============================================
void loop() {
    // Serielle Kommandos verarbeiten
    handleSerialCommands();
    
    // MQTT Verbindung aufrechterhalten
    if (!mqttClient.connected()) {
        connectMQTT();
    }
    mqttClient.loop();
    
    // Temperatur alle 5 Sekunden messen und senden
    static unsigned long lastSensor = 0;
    if (millis() - lastSensor > 5000) {
        lastSensor = millis();
        sendTemperature();
    }
    
    delay(10);
}