// ============================================================================
// ESP8266 MAX6675 IoT Sensor - FIRMWARE V6.1 (TLS PORT 8883)
// ============================================================================
// 
// Projekt: IoT Temperature Monitoring System
// Autor:   Nouri Deg.
// Datum:   16.08.2026
// Version: 6.1
//
// BESCHREIBUNG:
// Diese Firmware betreibt einen ESP8266 mit MAX6675 Thermoelement-Sensor.
// Die MQTT-Kommunikation erfolgt VERSCHLÜSSELT über Port 8883 (TLS).
// Alle sensiblen Daten werden aus der separaten Datei "secrets.h" geladen.
//
// HARDWARE:
// - ESP8266 (NodeMCU / Wemos D1 Mini)
// - MAX6675 Thermoelement-Modul mit K-Type Thermoelement
//
// PINBELEGUNG:
// - SCK (Clock)  -> D7 (GPIO13)
// - CS  (Select) -> D8 (GPIO15)
// - SO  (Data)   -> D6 (GPIO12)
//
// FUNKTIONEN:
// - TLS-verschlüsselte MQTT Kommunikation (Port 8883)
// - Automatisches Provisioning (Credentials aus EEPROM oder secrets.h)
// - Adafruit SleepyDog Watchdog (verhindert System-Freezes)
// - OTA Updates (Over-the-Air) via Arduino IDE
// - Sensor-Filter gegen Messausreißer (0.00°C, Sprünge >5°C)
// - Heartbeat & LWT (Last Will Testament) für Online-Status
// - Factory Reset über serielles Kommando "RESET"
// - MQTT Reconnect bei Verbindungsverlust
// ============================================================================

// ============================================================================
// 1. BIBLIOTHEKEN
// ============================================================================

#include <ESP8266WiFi.h>         // WLAN-Funktionen
#include <WiFiClientSecure.h>    // TLS/SSL für sichere MQTT Verbindung (Port 8883)
#include <PubSubClient.h>        // MQTT Client
#include <ArduinoJson.h>         // JSON-Erstellung für MQTT-Payloads
#include <max6675.h>             // MAX6675 Sensor-Bibliothek
#include <EEPROM.h>              // Persistentes Speichern von Credentials
#include <ArduinoOTA.h>          // Over-the-Air Updates
#include <Adafruit_SleepyDog.h>  // Watchdog-Timer
#include <ESP8266Ping.h>         // Ping für Netzwerk-Diagnose

// ============================================================================
// 2. SICHERE KONFIGURATION (aus separater Datei - NICHT AUF GITHUB!)
// ============================================================================

#ifdef __has_include
  #if __has_include("secrets.h")
    #include "secrets.h"
    #define SECRETS_AVAILABLE 1
  #else
    #define SECRETS_AVAILABLE 0
    #error "secrets.h nicht gefunden! Bitte erstelle diese Datei."
  #endif
#endif

// ============================================================================
// 3. OTA KONFIGURATION (optional)
// ============================================================================

#ifdef __has_include
  #if __has_include("ota_config.h")
    #include "ota_config.h"
    #define OTA_AVAILABLE 1
  #else
    #define OTA_AVAILABLE 0
  #endif
#endif

#ifndef OTA_AVAILABLE
  #define OTA_AVAILABLE 0
#endif

// ============================================================================
// 4. PINBELEGUNG & HARDWARE-KONFIGURATION
// ============================================================================

// MAX6675 Pins (SPI-Kommunikation)
const int PIN_SCK = 13;   // D7 = GPIO13 (Clock)
const int PIN_CS  = 15;   // D8 = GPIO15 (Chip Select)
const int PIN_SO  = 12;   // D6 = GPIO12 (Data Out)

// Statische IP-Konfiguration (Gerät 2)
IPAddress local_IP(192, 168, 0, 201);
IPAddress gateway(192, 168, 0, 1);
IPAddress subnet(255, 255, 255, 0);
IPAddress dns(8, 8, 8, 8);

// ============================================================================
// 5. TIMING & SCHWELLWERTE
// ============================================================================

#define LWT_HEARTBEAT_INTERVAL  30000   // Heartbeat alle 30 Sekunden
#define LWT_TIMEOUT             90000   // Nach 90 Sekunden = offline
#define WATCHDOG_TIMEOUT_MS     8000    // Watchdog nach 8 Sekunden
#define SENSOR_INTERVAL_MS      5000    // Temperatur alle 5 Sekunden
#define MQTT_RECONNECT_DELAY    5000    // Wartezeit bei MQTT-Fehlern

// ============================================================================
// 6. EEPROM ADRESSEN (für persistente Credentials)
// ============================================================================

#define EEPROM_SIZE             4096
#define PROVISIONED_FLAG_ADDR   0
#define MQTT_BROKER_ADDR        50
#define MQTT_PORT_ADDR          120
#define MQTT_USER_ADDR          124
#define MQTT_PASS_ADDR          160

// ============================================================================
// 7. GLOBALE OBJEKTE
// ============================================================================

MAX6675 thermocouple(PIN_SCK, PIN_CS, PIN_SO);   // Sensor-Objekt
WiFiClientSecure espClient;                       // TLS-fähiger WiFi-Client (Port 8883)
PubSubClient mqttClient(espClient);               // MQTT-Client

// ============================================================================
// 8. GLOBALE VARIABLEN
// ============================================================================

String device_id = "";
String mac_address = "";
String mqttBroker = "";
uint16_t mqttPort = 8883;      // ← Standard: TLS Port
String mqttUser = "";
String mqttPassword = "";

bool isOnline = false;
unsigned long lastHeartbeat = 0;

// Sensor-Filter (Ringbuffer für gleitenden Mittelwert)
float letzteGueltigeTemp = 25.0;
int filterIndex = 0;
float tempRingBuffer[5];

// ============================================================================
// 9. SENSOR-FILTER (glättet Ausreißer und Rauschen)
// ============================================================================

/**
 * Liest und filtert die Temperatur vom MAX6675 Sensor.
 * 
 * Filterstufen:
 * 1. Rohwert lesen
 * 2. Prüfung auf Messfehler (isnan)
 * 3. Ausreißererkennung (Sprung > 5°C)
 * 4. Mittelwertbildung über die letzten 5 Werte
 * 5. Gleitender Filter (70% alt, 30% neu)
 * 
 * @return float Gefilterte Temperatur in °C
 */
float getFilteredTemperature() {
  float rohwert = thermocouple.readCelsius();

  // Fehlererkennung: Kein Thermoelement?
  if (isnan(rohwert)) {
    Serial.println("⚠️ Sensor-Lesefehler! Verwende letzten gültigen Wert");
    return letzteGueltigeTemp;
  }

  // Ausreißererkennung: Sprung > 5°C?
  if (abs(rohwert - letzteGueltigeTemp) > 5.0) {
    Serial.print(" Ausreißer ignoriert: ");
    Serial.print(rohwert);
    Serial.print(" °C → ");
    Serial.print(letzteGueltigeTemp);
    Serial.println(" °C verwendet");
    return letzteGueltigeTemp;
  }

  // Ringbuffer für Mittelwertbildung (letzte 5 Werte)
  tempRingBuffer[filterIndex] = rohwert;
  filterIndex = (filterIndex + 1) % 5;

  // Durchschnitt der letzten 5 Werte berechnen
  float summe = 0.0;
  int anzahl = 0;
  for (int i = 0; i < 5; i++) {
    if (tempRingBuffer[i] != 0.0) {
      summe += tempRingBuffer[i];
      anzahl++;
    }
  }
  float gemittelterWert = (anzahl > 0) ? (summe / anzahl) : rohwert;

  // Gleitender Filter: 70% alt, 30% neu
  float gefiltert = 0.7 * letzteGueltigeTemp + 0.3 * gemittelterWert;
  letzteGueltigeTemp = gefiltert;

  return gefiltert;
}

// ============================================================================
// 10. GERÄTE-INFORMATIONEN (aus MAC-Adresse generiert)
// ============================================================================

String getDeviceIdFromMac() {
  byte mac[6];
  WiFi.macAddress(mac);
  char deviceIdStr[18];
  snprintf(deviceIdStr, sizeof(deviceIdStr), "esp8266_%02X%02X%02X%02X%02X%02X",
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  return String(deviceIdStr);
}

void setupDeviceInfo() {
  byte mac[6];
  WiFi.macAddress(mac);
  char macStr[18];
  snprintf(macStr, sizeof(macStr), "%02X:%02X:%02X:%02X:%02X:%02X",
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  mac_address = String(macStr);
  device_id = getDeviceIdFromMac();

  Serial.println("#==================================#");
  Serial.println("#        GERÄTE INFORMATIONEN      #");
  Serial.println("#==================================#");
  Serial.print ("# Device ID: ");
  Serial.println(device_id);
  Serial.print ("# MAC:       ");
  Serial.println(mac_address);
  Serial.println("#=====================================#");
}

// ============================================================================
// 11. WATCHDOG (Adafruit SleepyDog)
// ============================================================================

void setupWatchdog() {
  int actualTimeout = Watchdog.enable(WATCHDOG_TIMEOUT_MS);
  if (actualTimeout > 0) {
    Serial.print(" Watchdog aktiviert mit ");
    Serial.print(actualTimeout);
    Serial.println(" ms Timeout");
  } else {
    Serial.println(" Watchdog konnte nicht aktiviert werden!");
  }
}

void feedWatchdog() {
  Watchdog.reset();
}

// ============================================================================
// 12. WLAN VERBINDEN (mit statischer IP)
// ============================================================================

void connectWLAN() {
  #if !SECRETS_AVAILABLE
    Serial.println("❌ FEHLER: secrets.h nicht gefunden!");
    return;
  #endif

  Serial.print(" Verbinde mit WLAN");
  WiFi.config(local_IP, gateway, subnet, dns);
  WiFi.begin(WLAN_SSID, WLAN_PASSWORT);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
    feedWatchdog();
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ WLAN verbunden!");
    Serial.print("    IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n❌ WLAN Fehler! Neustart...");
    delay(2000);
    ESP.restart();
  }
}

// ============================================================================
// 13. OTA SETUP (Over-the-Air Updates)
// ============================================================================

void setupOTA() {
  #if OTA_AVAILABLE
    ArduinoOTA.setHostname(OTA_HOSTNAME);
    ArduinoOTA.setPassword(OTA_PASSWORD);
    ArduinoOTA.begin();
    Serial.println("✅ ArduinoOTA bereit");
    Serial.print("   Hostname: ");
    Serial.println(OTA_HOSTNAME);
  #else
    Serial.println(" OTA deaktiviert - ota_config.h nicht gefunden");
  #endif
}

// ============================================================================
// 14. MQTT VERBINDEN (TLS Port 8883)
// ============================================================================

void connectMQTT() {
  // TLS aktivieren (für Port 8883)
  espClient.setInsecure();   // Akzeptiert selbstsignierte Zertifikate (für Entwicklung)
  // Für Produktion: espClient.setCertificate(...) und espClient.setPrivateKey(...)

  while (!mqttClient.connected()) {
    Serial.print(" Verbinde mit MQTT Broker (TLS): ");
    Serial.print(mqttBroker);
    Serial.print(":");
    Serial.print(mqttPort);
    Serial.print("... ");

    if (mqttClient.connect(device_id.c_str(), mqttUser.c_str(), mqttPassword.c_str())) {
      Serial.println("✅ verbunden (TLS)!");
      isOnline = true;
      lastHeartbeat = millis();

      // Online-Status publishen (retained)
      String onlineTopic = "status/" + device_id + "/online";
      mqttClient.publish(onlineTopic.c_str(), "true", true);

      // OTA Command Topic abonnieren
      String otaTopic = "commands/" + device_id + "/ota";
      mqttClient.subscribe(otaTopic.c_str());
      Serial.print("    Abonniert: ");
      Serial.println(otaTopic);

    } else {
      int state = mqttClient.state();
      Serial.print("❌ fehlgeschlagen, rc=");
      Serial.println(state);
      
      // Fehlercodes ausgeben
      switch(state) {
        case -4: Serial.println("   MQTT_CONNECTION_TIMEOUT"); break;
        case -3: Serial.println("   MQTT_CONNECTION_LOST"); break;
        case -2: Serial.println("   MQTT_CONNECT_FAILED"); break;
        case -1: Serial.println("   MQTT_DISCONNECTED"); break;
        case 1: Serial.println("   MQTT_CONNECT_BAD_PROTOCOL"); break;
        case 2: Serial.println("   MQTT_CONNECT_BAD_CLIENT_ID"); break;
        case 3: Serial.println("   MQTT_CONNECT_UNAVAILABLE"); break;
        case 4: Serial.println("   MQTT_CONNECT_BAD_CREDENTIALS"); break;
        case 5: Serial.println("   MQTT_CONNECT_UNAUTHORIZED"); break;
      }
      
      delay(MQTT_RECONNECT_DELAY);
      feedWatchdog();
    }
  }
}

// ============================================================================
// 15. MQTT CALLBACK (für eingehende Nachrichten)
// ============================================================================

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String message;
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.print(" MQTT: ");
  Serial.print(topic);
  Serial.print(" -> ");
  Serial.println(message);
}

// ============================================================================
// 16. TEMPERATUR SENDEN (als JSON über MQTT)
// ============================================================================

void sendTemperature() {
  if (!mqttClient.connected()) return;

  float temperatur = getFilteredTemperature();

  JsonDocument doc;
  doc["device_id"]   = device_id;
  doc["device_type"] = "esp8266";
  doc["sensor"]      = "max6675";
  doc["temp"]        = temperatur;
  doc["unit"]        = "celsius";
  doc["rssi"]        = WiFi.RSSI();
  doc["heap"]        = ESP.getFreeHeap();
  doc["uptime"]      = millis() / 1000;

  char buffer[256];
  serializeJson(doc, buffer);

  if (mqttClient.publish("sensor/temperatur", buffer)) {
    Serial.print("🌡️ ");
    Serial.println(buffer);
    lastHeartbeat = millis();
  } else {
    Serial.println("❌ Fehler beim Senden!");
  }
}

// ============================================================================
// 17. LWT (LAST WILL TESTAMENT) - Heartbeat & Online-Status
// ============================================================================

void publishOnlineStatus() {
  if (!mqttClient.connected()) return;

  static unsigned long lastPublish = 0;
  if (millis() - lastPublish > LWT_HEARTBEAT_INTERVAL) {
    String onlineTopic = "status/" + device_id + "/online";
    mqttClient.publish(onlineTopic.c_str(), "true", true);
    lastPublish = millis();
    Serial.println(" Heartbeat gesendet");
  }
}

void checkLWTTimeout() {
  if (isOnline && (millis() - lastHeartbeat > LWT_TIMEOUT)) {
    isOnline = false;
    Serial.println(" LWT TIMEOUT! Gerät gilt als OFFLINE");
    String onlineTopic = "status/" + device_id + "/online";
    mqttClient.publish(onlineTopic.c_str(), "false", true);
  }
}

// ============================================================================
// 18. EEPROM FUNKTIONEN (Credentials speichern/laden)
// ============================================================================

void saveCredentials(String broker, uint16_t port, String user, String password) {
  Serial.println("\n Speichere Credentials...");
  EEPROM.begin(EEPROM_SIZE);

  // Bereich löschen
  for (int i = PROVISIONED_FLAG_ADDR; i < MQTT_PASS_ADDR + 64; i++) {
    EEPROM.write(i, 0);
  }

  EEPROM.write(PROVISIONED_FLAG_ADDR, 1);

  for (int i = 0; i < broker.length() && i < 50; i++) {
    EEPROM.write(MQTT_BROKER_ADDR + i, broker[i]);
  }
  EEPROM.write(MQTT_BROKER_ADDR + broker.length(), '\0');

  EEPROM.put(MQTT_PORT_ADDR, port);

  for (int i = 0; i < user.length() && i < 32; i++) {
    EEPROM.write(MQTT_USER_ADDR + i, user[i]);
  }
  EEPROM.write(MQTT_USER_ADDR + user.length(), '\0');

  for (int i = 0; i < password.length() && i < 64; i++) {
    EEPROM.write(MQTT_PASS_ADDR + i, password[i]);
  }
  EEPROM.write(MQTT_PASS_ADDR + password.length(), '\0');

  EEPROM.commit();
  EEPROM.end();

  Serial.println("   Broker: " + broker);
  Serial.println("   Port: " + String(port));
  Serial.println("   User: " + user);
  Serial.println(" Credentials in EEPROM gespeichert!");
}

bool loadCredentials() {
  EEPROM.begin(EEPROM_SIZE);
  bool isProvisioned = (EEPROM.read(PROVISIONED_FLAG_ADDR) == 1);

  if (!isProvisioned) {
    EEPROM.end();
    return false;
  }

  char buffer[128];
  int i = 0;

  while (i < 127) {
    buffer[i] = EEPROM.read(MQTT_BROKER_ADDR + i);
    if (buffer[i] == '\0') break;
    i++;
  }
  buffer[i] = '\0';
  mqttBroker = String(buffer);

  EEPROM.get(MQTT_PORT_ADDR, mqttPort);

  i = 0;
  while (i < 127) {
    buffer[i] = EEPROM.read(MQTT_USER_ADDR + i);
    if (buffer[i] == '\0') break;
    i++;
  }
  buffer[i] = '\0';
  mqttUser = String(buffer);

  i = 0;
  while (i < 127) {
    buffer[i] = EEPROM.read(MQTT_PASS_ADDR + i);
    if (buffer[i] == '\0') break;
    i++;
  }
  buffer[i] = '\0';
  mqttPassword = String(buffer);

  EEPROM.end();

  Serial.println("\n Geladene Credentials:");
  Serial.print("   Broker: '");
  Serial.print(mqttBroker);
  Serial.println("'");
  Serial.print("   Port: ");
  Serial.println(mqttPort);
  Serial.print("   User: '");
  Serial.print(mqttUser);
  Serial.println("'");

  return true;
}

// ============================================================================
// 19. SERIELLE KOMMANDOS (RESET, STATUS, INFO, OFFLINE, WATCHDOG)
// ============================================================================

void handleSerialCommands() {
  if (!Serial.available()) return;

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  cmd.toUpperCase();

  if (cmd == "RESET") {
    Serial.println("\n Factory Reset wird durchgeführt...");
    EEPROM.begin(EEPROM_SIZE);
    EEPROM.write(PROVISIONED_FLAG_ADDR, 0);
    EEPROM.commit();
    EEPROM.end();
    delay(1000);
    ESP.restart();
  }
  else if (cmd == "STATUS") {
    Serial.println("\n####################################");
    Serial.println("#        SYSTEM STATUS               #");
    Serial.println("####################################");
    Serial.print ("# Device ID: ");
    Serial.println(device_id);
    Serial.print ("# IP: ");
    Serial.println(WiFi.localIP());
    Serial.print ("# MQTT Status: ");
    Serial.println(mqttClient.connected() ? "Verbunden (TLS)" : "Getrennt");
    Serial.print ("# Online: ");
    Serial.println(isOnline ? "Ja" : "Nein");
    Serial.print ("# Heap: ");
    Serial.print(ESP.getFreeHeap());
    Serial.println(" Bytes");
    Serial.println("####################################");
  }
  else if (cmd == "INFO") {
    Serial.println("\n####################################");
    Serial.println("#      PROVISIONING INFO           #");
    Serial.println("####################################");
    Serial.print ("# Broker: ");
    Serial.println(mqttBroker);
    Serial.print ("# Port:   ");
    Serial.println(mqttPort);
    Serial.print ("# User:   ");
    Serial.println(mqttUser);
    Serial.println("####################################");
  }
  else if (cmd == "OFFLINE") {
    Serial.println("🔌 Simuliere Offline...");
    isOnline = false;
    String onlineTopic = "status/" + device_id + "/online";
    mqttClient.publish(onlineTopic.c_str(), "false", true);
  }
  else if (cmd == "WATCHDOG") {
    Serial.println(" Watchdog Test - 15 Sekunden Blockierung...");
    delay(15000);
    Serial.println("Wenn du das siehst, funktioniert der Watchdog nicht!");
  }
}

// ============================================================================
// 20. NETZWERK-DIAGNOSE (Ping + MQTT-Port-Test)
// ============================================================================

void runNetworkDiagnostics() {
  Serial.println("\n--- NETZWERK DIAGNOSE ---");
  Serial.print("ESP IP: ");
  Serial.println(WiFi.localIP());
  Serial.print("Gateway: ");
  Serial.println(WiFi.gatewayIP());

  Serial.print("Pinge 192.168.0.106... ");
  if (Ping.ping("192.168.0.106", 1)) {
    Serial.println("✅ Erreichbar!");
  } else {
    Serial.println("❌ NICHT erreichbar!");
  }

  Serial.println("\n--- DIREKTER MQTT PORT TEST (8883 TLS) ---");
  WiFiClientSecure testClient;
  testClient.setInsecure();   // Akzeptiert selbstsignierte Zertifikate
  Serial.print("Verbinde zu 192.168.0.106:8883 (TLS)... ");
  if (testClient.connect("192.168.0.106", 8883)) {
    Serial.println("✅ TLS-Port erreichbar!");
    testClient.stop();
  } else {
    Serial.println("❌ TLS-Port NICHT erreichbar!");
  }
  Serial.println("--- DIREKTER MQTT TEST ENDE ---\n");
  Serial.println("--- NETZWERK DIAGNOSE ENDE ---\n");
}

// ============================================================================
// 21. SETUP
// ============================================================================

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n###########################################################");
  Serial.println("#     ESP8266 MAX6675 IoT Sensor - GERÄT 2 (TLS)           #");
  Serial.println("#              VERSCHLÜSSELT (PORT 8883)                   #");
  Serial.println("#############################################################\n");

  setupWatchdog();

  // Sensor-Filter initialisieren
  for (int i = 0; i < 5; i++) {
    tempRingBuffer[i] = 0.0;
  }

  // MAX6675 initialisieren
  pinMode(PIN_CS, OUTPUT);
  digitalWrite(PIN_CS, HIGH);
  delay(500);

  // WLAN verbinden
  connectWLAN();

  // Netzwerk-Diagnose
  runNetworkDiagnostics();

  // Geräteinformationen
  setupDeviceInfo();

  // OTA initialisieren
  setupOTA();

  // Credentials laden (EEPROM oder secrets.h)
  if (loadCredentials()) {
    Serial.println("✅ Gespeicherte Credentials gefunden!");
  } else {
    Serial.println(" Keine gespeicherten Credentials gefunden!");
    #if SECRETS_AVAILABLE
      Serial.println(" Verwende Standard-Credentials aus secrets.h...");
      mqttBroker   = MQTT_BROKER;
      mqttPort     = MQTT_PORT;
      mqttUser     = MQTT_USER;
      mqttPassword = MQTT_PASSWORD;
      saveCredentials(mqttBroker, mqttPort, mqttUser, mqttPassword);
      Serial.println(" Credentials gespeichert! Neustart...");
      delay(3000);
      ESP.restart();
      return;
    #else
      Serial.println("❌ FEHLER: secrets.h nicht gefunden!");
      delay(10000);
      ESP.restart();
      return;
    #endif
  }

  // MQTT Client konfigurieren (TLS Port 8883)
  mqttClient.setServer(mqttBroker.c_str(), mqttPort);
  mqttClient.setCallback(mqttCallback);

  Serial.println("\n✅ System bereit (TLS Modus)!");
  Serial.println(" Befehle: RESET, STATUS, INFO, OFFLINE, WATCHDOG");
}

// ============================================================================
// 22. LOOP
// ============================================================================

void loop() {
  feedWatchdog();

  #if OTA_AVAILABLE
    ArduinoOTA.handle();
  #endif

  handleSerialCommands();

  if (!mqttClient.connected()) {
    connectMQTT();
  }
  mqttClient.loop();

  publishOnlineStatus();
  checkLWTTimeout();

  static unsigned long lastSensor = 0;
  if (millis() - lastSensor > SENSOR_INTERVAL_MS) {
    lastSensor = millis();
    sendTemperature();
  }

  delay(10);
}

// ============================================================================
// ENDE DER FIRMWARE
// ============================================================================