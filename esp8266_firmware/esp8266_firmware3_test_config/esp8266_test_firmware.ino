
//============================================
// ESP8266 MAX6675 IoT Sensor - GERÄT 2 (SICHER)
// MIT ADAFRUIT SLEEPYDOG WATCHDOG, LWT & OTA
// ============================================
//
// Projekt: IoT Temperature Monitoring System
// Autor: Nouri Deg.
// Datum: 20.04.2026
// Version: 5.0
//
// Funktionen:
// - Automatisches Provisioning (MQTT Credentials werden vom Server geholt)
// - Adafruit SleepyDog Watchdog-Timer (verhindert System-Freezes)
// - OTA (Over-the-Air) Updates via Arduino IDE
// - MQTT OTA Commands (Update über MQTT auslösbar)
// - TLS verschlüsselte MQTT Kommunikation (Port 8883)
// - MAX6675 Thermoelement Sensor (Temperaturmessung)
// - Heartbeat & LWT (Last Will Testament) für Online-Status
// - Sensor-Filter gegen Ausreißer
// - Factory Reset Funktion
//
// Hardware:
// - ESP8266 (NodeMCU / Wemos D1 Mini)
// - MAX6675 Thermoelement Modul
// - K-Type Thermoelement
//
// Pinbelegung:
// - SCK (Clock)  -> D7 (GPIO13)
// - CS (Chip Select) -> D8 (GPIO15)
// - SO (Data Out) -> D6 (GPIO12)
// 
// ============================================================================
// 
// ############################################################################
// #  SICHERHEITSHINWEIS:                                                     #
// #  Dieses Projekt enthält KEINE festen Passwörter im Code!                 #
// #  Alle sensiblen Daten werden aus secrets.h geladen.                      #
// #  Die secrets.h Datei ist in .gitignore ausgeschlossen!                   #
// ############################################################################
// ============================================================================

// ============================================================================
// BIBLIOTHEKEN
// ============================================================================

#include <ESP8266WiFi.h>         // WLAN-Funktionen für ESP8266
//#include <WiFiClientSecure.h>    // TLS/SSL für sichere MQTT Verbindung
#include <WiFiClient.h>

#include <PubSubClient.h>        // MQTT Client für Nachrichtenaustausch
#include <ArduinoJson.h>         // JSON Parsing für MQTT Nachrichten
#include <max6675.h>             // MAX6675 Thermoelement Sensor Bibliothek
#include <EEPROM.h>              // Persistente Speicherung (Credentials bleiben erhalten)
#include <ArduinoOTA.h>          // Over-the-Air Updates via WLAN
#include <Adafruit_SleepyDog.h>  // Watchdog Timer (verhindert System-Freezes)
#include <ESP8266Ping.h>

// ============================================================================
// SICHERE KONFIGURATION (aus separater Datei - NICHT auf GitHub!)
// ============================================================================
// Die secrets.h Datei muss manuell erstellt werden und wird NIE gecommitted!
// Sie enthält: WLAN-Zugangsdaten, MQTT-Credentials und OTA-Passwort
// ============================================================================

#ifdef __has_include                     // Prüft ob eine Datei existiert
  #if __has_include("secrets.h")         // Wenn secrets.h im Sketch-Ordner existiert
    #include "secrets.h"                 // Lade die sichere Konfigurationsdatei
    #define SECRETS_AVAILABLE 1          // Setze Flag auf 1 (verfügbar)
  #else
    #define SECRETS_AVAILABLE 0          // Setze Flag auf 0 (nicht verfügbar)
    #error "secrets.h nicht gefunden! Bitte erstelle diese Datei."  // Compiler-Fehler
  #endif
#endif

// ============================================================================
// OTA KONFIGURATION (Over-the-Air Updates)
// ============================================================================
// OTA ermöglicht Firmware-Updates über WLAN ohne USB-Kabel
// Die Konfiguration kann entweder in ota_config.h oder in secrets.h sein
// ============================================================================

#ifdef __has_include                      // Prüft ob ota_config.h existiert
  #if __has_include("ota_config.h")      
    #include "ota_config.h"              // Lade OTA-Konfiguration (falls vorhanden)
    #define OTA_AVAILABLE 1              // OTA ist verfügbar
  #else
    #define OTA_AVAILABLE 0              // OTA ist nicht verfügbar
  #endif
#endif

#ifndef OTA_AVAILABLE                     // Fallback falls nicht definiert
  #define OTA_AVAILABLE 0                // OTA standardmäßig deaktiviert
#endif

// ============================================================================
// 1. STATISCHE IP KONFIGURATION - GERÄT 2 (201)
// ============================================================================
// Jeder ESP8266 bekommt eine eigene feste IP-Adresse
// Gerät 1: 192.168.0.200 | Gerät 2: 192.168.0.201
// ============================================================================

IPAddress local_IP(192, 168, 0, 201);    // Feste IP-Adresse für dieses Gerät
IPAddress gateway(192, 168, 0, 1);       // Router-IP (Gateway)
IPAddress subnet(255, 255, 255, 0);      // Subnetzmaske (Standard Heimnetz)
IPAddress dns(8, 8, 8, 8);               // Google DNS-Server (alternativ Router)

// ============================================================================
// 2. PROVISIONING SERVICE KONFIGURATION
// ============================================================================
// Der Provisioning Service vergibt automatisch MQTT-Credentials
// Läuft als Docker-Container auf dem Server
// ============================================================================

const char* PROVISIONING_HOST = "192.168.0.106";   // IP des Docker-Hosts
const int   PROVISIONING_PORT = 1883;              // MQTT-Port (ohne TLS)

// ============================================================================
// 3. MAX6675 PINS (SPI-Kommunikation)
// ============================================================================

const int PIN_SCK = 13;   // SCK (Clock)     an D7 = GPIO13 - Clock-Signal
const int PIN_CS  = 15;   // CS (Chip Select) an D8 = GPIO15 - Chip-Auswahl
const int PIN_SO  = 12;   // SO (Data Out)    an D6 = GPIO12 - Datenleitung

// ============================================================================
// 4. LWT (LAST WILL TESTAMENT) KONFIGURATION
// ============================================================================
// LWT benachrichtigt den Broker bei unerwartetem Verbindungsverlust
// ============================================================================

#define LWT_HEARTBEAT_INTERVAL 30000   // Heartbeat alle 30 Sekunden (30000 ms)
#define LWT_TIMEOUT            90000   // Nach 90 Sekunden ohne Heartbeat = offline
#define WATCHDOG_TIMEOUT_MS    8000    // Watchdog-Timeout: 8 Sekunden

// ============================================================================
// 5. EEPROM KONFIGURATION
// ============================================================================
// EEPROM (Electrically Erasable Programmable Read-Only Memory)
// Speichert Credentials persistent über Neustarts hinweg
// ============================================================================

#define EEPROM_SIZE         4096        // EEPROM-Größe: 4 KB
#define PROVISIONED_FLAG_ADDR 0         // Adresse für Provisionierungs-Flag (1 Byte)
#define MQTT_BROKER_ADDR    50          // Startadresse für Broker-IP (max. 50 Bytes)
#define MQTT_PORT_ADDR      120         // Adresse für Broker-Port (2 Bytes)
#define MQTT_USER_ADDR      124         // Startadresse für Benutzername (max. 32 Bytes)
#define MQTT_PASS_ADDR      160         // Startadresse für Passwort (max. 64 Bytes)

// ============================================================================
// 6. GLOBALE OBJEKTE
// ============================================================================

MAX6675 thermocouple(PIN_SCK, PIN_CS, PIN_SO);   // Thermoelement-Objekt
//WiFiClientSecure espClient;    
WiFiClient espClient;                  // TLS-fähiger WiFi-Client
PubSubClient mqttClient(espClient);              // MQTT-Client (mit TLS)

// ============================================================================
// 7. GLOBALE VARIABLEN
// ============================================================================

String device_id = "";          // Eindeutige Geräte-ID (aus MAC generiert)
String mac_address = "";        // MAC-Adresse des ESP8266
String mqttBroker;              // MQTT-Broker IP (z.B. "192.168.0.106")
uint16_t mqttPort;              // MQTT-Port (8883 für TLS, 1883 für ohne TLS)
String mqttUser;                // MQTT-Benutzername (vom Service generiert)
String mqttPassword;            // MQTT-Passwort (vom Service generiert)

bool isOnline = false;          // Flag: Ist das Gerät online?
unsigned long lastHeartbeat = 0; // Zeitstempel des letzten Heartbeats

// ============================================================================
// 8. SENSOR-FILTER (glättet Ausreißer und Rauschen)
// ============================================================================
// Der MAX6675 liefert gelegentlich fehlerhafte Werte (0.00°C oder Sprünge)
// Dieser 3-stufige Filter erkennt und korrigiert solche Ausreißer
// ============================================================================

float letzteGueltigeTemp = 25.0;   // Letzte gültige Temperatur als Referenz
int filterIndex = 0;               // Index für den Ringbuffer (0-4)
float tempRingBuffer[5];           // Ringbuffer für die letzten 5 Messwerte

/**
 * Liest und filtert die Temperatur vom MAX6675 Sensor
 * 
 * Schritt 1: Rohwert vom Sensor lesen
 * Schritt 2: Prüfung auf Messfehler (isnan = Not a Number)
 * Schritt 3: Ausreißererkennung (Sprung > 5°C in 5 Sekunden)
 * Schritt 4: Mittelwertbildung über die letzten 5 Werte
 * Schritt 5: Gleitender Filter (70% alter Wert, 30% neuer Wert)
 * 
 * @return float Gefilterte Temperatur in Celsius
 */
float getFilteredTemperature() {
  // Schritt 1: Rohwert vom Sensor lesen
  float rohwert = thermocouple.readCelsius();

  // Schritt 2: Fehlererkennung - Kein Thermoelement angeschlossen?
  if (isnan(rohwert)) {
    Serial.println("⚠️ Sensor-Lesefehler! Verwende letzten gültigen Wert");
    return letzteGueltigeTemp;                    // Fallback auf letzten gültigen Wert
  }

  // Schritt 3: Ausreißererkennung - Sprung größer 5°C?
  if (abs(rohwert - letzteGueltigeTemp) > 5.0) {
    Serial.print(" Ausreißer ignoriert: ");
    Serial.print(rohwert);
    Serial.print(" °C → ");
    Serial.print(letzteGueltigeTemp);
    Serial.println(" °C verwendet");
    return letzteGueltigeTemp;                    // Ausreißer ignorieren
  }

  // Schritt 4: Ringbuffer für Mittelwertbildung (speichert letzte 5 Werte)
  tempRingBuffer[filterIndex] = rohwert;          // Neuen Wert im Ringbuffer speichern
  filterIndex = (filterIndex + 1) % 5;            // Index zirkulär erhöhen (0,1,2,3,4,0,...)

  // Schritt 4b: Durchschnitt der letzten 5 Werte berechnen
  float summe = 0.0;
  int anzahl = 0;
  for (int i = 0; i < 5; i++) {
    if (tempRingBuffer[i] != 0.0) {              // Nur vorhandene Werte berücksichtigen
      summe += tempRingBuffer[i];
      anzahl++;
    }
  }
  float gemittelterWert = (anzahl > 0) ? (summe / anzahl) : rohwert;

  // Schritt 5: Gleitender Filter (glättet Kurven)
  // 70% alter Wert + 30% neuer Wert = sanfte Übergänge
  float gefiltert = 0.7 * letzteGueltigeTemp + 0.3 * gemittelterWert;
  letzteGueltigeTemp = gefiltert;                 // Referenz für nächste Messung aktualisieren

  return gefiltert;
}

// ============================================================================
// 9. GERÄTE INFO (aus MAC generiert - keine feste ID!)
// ============================================================================
// Die MAC-Adresse ist einmalig und wird vom Hersteller vergeben
// Daraus wird eine eindeutige Device ID generiert
// ============================================================================

/**
 * Generiert eine eindeutige Device ID aus der MAC-Adresse
 * 
 * @return String Device ID im Format "esp8266_<MAC>"
 *         Beispiel: "esp8266_AC67B2D3E4F5"
 */
String getDeviceIdFromMac() {
  byte mac[6];                                    // Array für 6 MAC-Bytes
  WiFi.macAddress(mac);                          // MAC-Adresse auslesen
  char deviceIdStr[18];                          // Puffer für Device ID (17 Zeichen + Null)
  snprintf(deviceIdStr, sizeof(deviceIdStr), "esp8266_%02X%02X%02X%02X%02X%02X",
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);  // Formatieren
  return String(deviceIdStr);                    // Als String zurückgeben
}

/**
 * Gibt Geräteinformationen auf der seriellen Konsole aus
 * Wird einmalig beim Start ausgeführt
 */
void setupDeviceInfo() {
  byte mac[6];
  WiFi.macAddress(mac);
  
  // MAC-Adresse im lesbaren Format (mit Doppelpunkten)
  char macStr[18];
  snprintf(macStr, sizeof(macStr), "%02X:%02X:%02X:%02X:%02X:%02X",
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  mac_address = String(macStr);
  device_id = getDeviceIdFromMac();

  // Ausgabe mit dekorativem Rahmen für bessere Lesbarkeit
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
// 10. WATCHDOG (Adafruit SleepyDog)
// ============================================================================
// Der Watchdog ist ein Hardware-Timer, der den ESP8266 automatisch neu startet,
// wenn er sich aufhängt. Das erhöht die Zuverlässigkeit erheblich.
// ============================================================================

/**
 * Aktiviert den Watchdog Timer mit konfiguriertem Timeout
 * Bei Timeout (8 Sekunden ohne Reset) startet der ESP8266 neu
 */
void setupWatchdog() {
  int actualTimeout = Watchdog.enable(WATCHDOG_TIMEOUT_MS);
  if (actualTimeout > 0) {
    Serial.print(" Watchdog aktiviert mit ");
    Serial.print(actualTimeout);
    Serial.println(" ms Timeout");
  } else {
    Serial.println("Watchdog konnte nicht aktiviert werden!");
  }
}

/**
 * Setzt den Watchdog Timer zurück (füttert den Hund)
 * Muss regelmäßig im Loop aufgerufen werden, sonst rebootet der ESP8266
 */
void feedWatchdog() {
  Watchdog.reset();      // Watchdog zurücksetzen - verhindert Neustart
}

// ============================================================================
// 11. WLAN VERBINDEN (mit Werten aus secrets.h)
// ============================================================================

void connectWLAN() {
  // Sicherheitsprüfung: secrets.h muss vorhanden sein
  #if !SECRETS_AVAILABLE
    Serial.println("❌ FEHLER: secrets.h nicht gefunden!");
    return;
  #endif

  Serial.print(" Verbinde mit WLAN");

  // Statische IP vor dem Verbinden setzen
  WiFi.config(local_IP, gateway, subnet, dns);
  
  // WLAN-Verbindung starten (Zugangsdaten aus secrets.h)
  WiFi.begin(WLAN_SSID, WLAN_PASSWORT);

  // Bis zu 40 Versuche (20 Sekunden) warten
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
    feedWatchdog();      // Watchdog während des Wartens zurücksetzen
  }

  // Verbindungsstatus prüfen
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ WLAN verbunden!");
    Serial.print("    IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n❌ WLAN Fehler! Neustart...");
    delay(2000);
    ESP.restart();       // Bei Fehler neu starten
  }
}

// ============================================================================
// 12. OTA SETUP (Over-the-Air Updates)
// ============================================================================
// Ermöglicht Firmware-Updates über WLAN (Arduino IDE)
// Aktiviert nur, wenn ota_config.h vorhanden ist
// ============================================================================

void setupOTA() {
#if OTA_AVAILABLE
  ArduinoOTA.setHostname(OTA_HOSTNAME);     // Gerätename im Netzwerk
  ArduinoOTA.setPassword(OTA_PASSWORD);     // Passwort für Sicherheit
  ArduinoOTA.begin();                       // OTA-Service starten
  Serial.println("✅ ArduinoOTA bereit");
  Serial.print("   Hostname: ");
  Serial.println(OTA_HOSTNAME);
#else
  Serial.println("OTA deaktiviert - ota_config.h nicht gefunden");
#endif
}

// ============================================================================
// 13. MQTT VERBINDEN (mit Werten aus secrets.h oder EEPROM)
// ============================================================================
// Stellt die TLS-geschützte MQTT Verbindung zum Broker her
// Bei Verbindungsverlust automatischer Reconnect
// ============================================================================

void connectMQTT() {
  // Kein setInsecure() für WiFiClient!
  
  while (!mqttClient.connected()) {
    Serial.print(" Verbinde mit MQTT Broker: ");
    Serial.print(mqttBroker);
    Serial.print(":");
    Serial.print(mqttPort);
    Serial.print("... ");

    // Client-ID, Benutzername und Passwort
    if (mqttClient.connect(device_id.c_str(), mqttUser.c_str(), mqttPassword.c_str())) {
      Serial.println("✅ verbunden!");
      // ...
    } else {
      int state = mqttClient.state();
      Serial.print("❌ fehlgeschlagen, rc=");
      Serial.println(state);
      
      // Fehlercodes
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
      
      delay(5000);
    }
  }
}


// void connectMQTT() {
//   // Akzeptiere selbstsignierte Zertifikate (für Entwicklung)
//   // In Produktion sollte hier eine echte Zertifikatsprüfung erfolgen!
//   espClient.setInsecure();

//   while (!mqttClient.connected()) {
//     Serial.print(" Verbinde mit MQTT Broker: ");
//     Serial.print(mqttBroker);
//     Serial.print(":");
//     Serial.print(mqttPort);
//     Serial.print("... ");

//     // Verbinde mit Device ID, Benutzername und Passwort
//     if (mqttClient.connect(device_id.c_str(), mqttUser.c_str(), mqttPassword.c_str())) {
//       Serial.println("✅ verbunden!");
//       isOnline = true;
//       lastHeartbeat = millis();

//       // Online Status publishen (retained = true bedeutet, dass der Status erhalten bleibt)
//       String onlineTopic = "status/" + device_id + "/online";
//       mqttClient.publish(onlineTopic.c_str(), "true", true);

//       // OTA Command Topic abonnieren (für ferngesteuerte Updates)
//       String otaTopic = "commands/" + device_id + "/ota";
//       mqttClient.subscribe(otaTopic.c_str());
//       Serial.print("    Abonniert: ");
//       Serial.println(otaTopic);

//     } else {
//       int state = mqttClient.state();
//       Serial.print("❌ fehlgeschlagen, rc=");
//       Serial.println(state);
//       delay(5000);      // 5 Sekunden warten vor nächstem Versuch
//       feedWatchdog();   // Watchdog während Wartezeit zurücksetzen
//     }
//   }
// }

// ============================================================================
// 14. MQTT CALLBACK
// ============================================================================
// Diese Funktion wird aufgerufen, wenn eine MQTT Nachricht auf einem
// abonnierten Topic eingeht (z.B. OTA Commands)
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
// 15. TEMPERATUR SENDEN
// ============================================================================
// Sendet die gefilterte Temperatur als JSON über MQTT
// Das JSON enthält alle relevanten Geräteinformationen
// ============================================================================

void sendTemperature() {
  if (!mqttClient.connected()) return;   // Nur senden wenn verbunden

  float temperatur = getFilteredTemperature();

  // JSON Dokument erstellen (ArduinoJson 7.x Syntax)
  JsonDocument doc;
  doc["device_id"]   = device_id;           // Eindeutige Geräte-ID
  doc["device_type"] = "esp8266";           // Gerätetyp
  doc["sensor"]      = "max6675";           // Sensortyp
  doc["temp"]        = temperatur;          // Temperaturwert in °C
  doc["unit"]        = "celsius";           // Einheit
  doc["rssi"]        = WiFi.RSSI();         // Signalstärke in dBm
  doc["heap"]        = ESP.getFreeHeap();   // Freier RAM in Bytes
  doc["uptime"]      = millis() / 1000;     // Betriebszeit in Sekunden

  // JSON in String konvertieren
  char buffer[256];
  serializeJson(doc, buffer);

  // Über MQTT senden
  if (mqttClient.publish("sensor/temperatur", buffer)) {
    Serial.print("🌡️ ");
    Serial.println(buffer);
    lastHeartbeat = millis();    // Temperatur senden aktualisiert Heartbeat
  } else {
    Serial.println("❌ Fehler beim Senden!");
  }
}

// ============================================================================
// 16. LWT (LAST WILL TESTAMENT) FUNKTIONEN
// ============================================================================
// Heartbeat signalisiert dem Broker, dass das Gerät noch lebt
// Bei Timeout wird das Gerät als offline markiert
// ============================================================================

/**
 * Sendet periodisch einen Heartbeat, um den Online-Status zu bestätigen
 * Wird alle LWT_HEARTBEAT_INTERVAL Millisekunden aufgerufen
 */
void publishOnlineStatus() {
  if (!mqttClient.connected()) return;

  static unsigned long lastPublish = 0;     // Statische Variable für letzten Send Zeitpunkt
  if (millis() - lastPublish > LWT_HEARTBEAT_INTERVAL) {
    String onlineTopic = "status/" + device_id + "/online";
    mqttClient.publish(onlineTopic.c_str(), "true", true);
    lastPublish = millis();
    Serial.println(" Heartbeat gesendet");
  }
}

/**
 * Prüft ob der Heartbeat-Timeout überschritten wurde
 * Wenn kein Heartbeat für LWT_TIMEOUT ms, wird Offline-Status gesendet
 */
void checkLWTTimeout() {
  if (isOnline && (millis() - lastHeartbeat > LWT_TIMEOUT)) {
    isOnline = false;
    Serial.println(" LWT TIMEOUT! Gerät gilt als OFFLINE");
    String onlineTopic = "status/" + device_id + "/online";
    mqttClient.publish(onlineTopic.c_str(), "false", true);
  }
}

// ============================================================================
// 17. EEPROM FUNKTIONEN
// ============================================================================
// Speichert und lädt Credentials persistent im EEPROM
// Die Daten bleiben auch nach einem Stromausfall erhalten
// ============================================================================

/**
 * Speichert MQTT Credentials persistent im EEPROM
 * 
 * @param broker   MQTT Broker IP Adresse
 * @param port     MQTT Port (1883 oder 8883)
 * @param user     MQTT Benutzername
 * @param password MQTT Passwort
 */
void saveCredentials(String broker, uint16_t port, String user, String password) {
  Serial.println("\n Speichere Credentials...");
  
  EEPROM.begin(EEPROM_SIZE);
  
  // Lösche zuerst den gesamten Credentials-Bereich (sicherheitshalber)
  for (int i = PROVISIONED_FLAG_ADDR; i < MQTT_PASS_ADDR + 64; i++) {
    EEPROM.write(i, 0);
  }
  
  // 1. Provisionierungs-Flag setzen (zeigt an dass Credentials gespeichert sind)
  EEPROM.write(PROVISIONED_FLAG_ADDR, 1);
  
  // 2. Broker IP speichern (mit Null-Terminator für String-Ende)
  for (int i = 0; i < broker.length() && i < 50; i++) {
    EEPROM.write(MQTT_BROKER_ADDR + i, broker[i]);
  }
  EEPROM.write(MQTT_BROKER_ADDR + broker.length(), '\0');
  
  // 3. Port speichern (2 Bytes)
  EEPROM.put(MQTT_PORT_ADDR, port);
  
  // 4. Benutzername speichern (mit Null-Terminator)
  for (int i = 0; i < user.length() && i < 32; i++) {
    EEPROM.write(MQTT_USER_ADDR + i, user[i]);
  }
  EEPROM.write(MQTT_USER_ADDR + user.length(), '\0');
  
  // 5. Passwort speichern (mit Null-Terminator)
  for (int i = 0; i < password.length() && i < 64; i++) {
    EEPROM.write(MQTT_PASS_ADDR + i, password[i]);
  }
  EEPROM.write(MQTT_PASS_ADDR + password.length(), '\0');
  
  EEPROM.commit();    // Änderungen tatsächlich in den EEPROM schreiben
  EEPROM.end();       // EEPROM freigeben
  
  // Debug-Ausgabe
  Serial.println("   Broker: " + broker);
  Serial.println("   Port: " + String(port));
  Serial.println("   User: " + user);
  Serial.println(" Credentials in EEPROM gespeichert!");
}

/**
 * Lädt gespeicherte MQTT Credentials aus dem EEPROM
 * 
 * @return true  wenn Credentials vorhanden und geladen
 * @return false wenn keine Credentials vorhanden
 */
bool loadCredentials() {
  EEPROM.begin(EEPROM_SIZE);
  
  bool isProvisioned = (EEPROM.read(PROVISIONED_FLAG_ADDR) == 1);
  
  if (!isProvisioned) {
    EEPROM.end();
    return false;
  }
  
  char buffer[128];
  int i = 0;
  
  // Broker IP laden (bis Null-Terminator)
  while (i < 127) {
    buffer[i] = EEPROM.read(MQTT_BROKER_ADDR + i);
    if (buffer[i] == '\0') break;
    i++;
  }
  buffer[i] = '\0';
  mqttBroker = String(buffer);
  
  // Port laden
  EEPROM.get(MQTT_PORT_ADDR, mqttPort);
  
  // Benutzername laden
  i = 0;
  while (i < 127) {
    buffer[i] = EEPROM.read(MQTT_USER_ADDR + i);
    if (buffer[i] == '\0') break;
    i++;
  }
  buffer[i] = '\0';
  mqttUser = String(buffer);
  
  // Passwort laden (für Verbindung, wird nicht angezeigt)
  i = 0;
  while (i < 127) {
    buffer[i] = EEPROM.read(MQTT_PASS_ADDR + i);
    if (buffer[i] == '\0') break;
    i++;
  }
  buffer[i] = '\0';
  mqttPassword = String(buffer);
  
  EEPROM.end();
  
  // Debug-Ausgabe (Passwort wird aus Sicherheitsgründen nicht angezeigt!)
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
// 18. SERIELLE KOMMANDOS
// ============================================================================
// Verarbeitet Befehle vom Seriellen Monitor
// 
// Verfügbare Befehle:
// - RESET    : Factory Reset (löscht alle Credentials)
// - STATUS   : Zeigt Systemstatus an
// - INFO     : Zeigt aktuelle Credentials (Passwort wird nicht angezeigt!)
// - OFFLINE  : Simuliert Offline (für LWT Test)
// - WATCHDOG : Testet Watchdog (blockiert für 15s)
// ============================================================================

void handleSerialCommands() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    cmd.toUpperCase();

    // Factory Reset - löscht alle Credentials aus dem EEPROM
    if (cmd == "RESET") {
      Serial.println("\n Factory Reset wird durchgeführt...");
      EEPROM.begin(EEPROM_SIZE);
      EEPROM.write(PROVISIONED_FLAG_ADDR, 0);    // Provisionierungs-Flag löschen
      EEPROM.commit();
      EEPROM.end();
      delay(1000);
      ESP.restart();
    }
    // Systemstatus anzeigen
    else if (cmd == "STATUS") {
      Serial.println("\n####################################");
      Serial.println("#        SYSTEM STATUS               #");
      Serial.println("######################################");
      Serial.print ("# Device ID: ");
      Serial.println(device_id);
      Serial.print ("# IP: ");
      Serial.println(WiFi.localIP());
      Serial.print ("# MQTT Status: ");
      Serial.println(mqttClient.connected() ? "Verbunden" : "Getrennt");
      Serial.print ("# Online: ");
      Serial.println(isOnline ? "Ja" : "Nein");
      Serial.print ("# Heap: ");
      Serial.print(ESP.getFreeHeap());
      Serial.println(" Bytes");
      Serial.println("####################################");
    }
    // Provisionierungs Info anzeigen
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
      Serial.println("######################################");
      // Passwort wird aus Sicherheitsgründen NICHT angezeigt!
    }
    // Offline simulieren (für LWT Test)
    else if (cmd == "OFFLINE") {
      Serial.println("🔌 Simuliere Offline...");
      isOnline = false;
      String onlineTopic = "status/" + device_id + "/online";
      mqttClient.publish(onlineTopic.c_str(), "false", true);
    }
    // Watchdog Test (blockiert Loop für 15s)
    else if (cmd == "WATCHDOG") {
      Serial.println(" Watchdog Test - 15 Sekunden Blockierung...");
      delay(15000);    // Blockiert den Loop - Watchdog sollte auslösen und Gerät neustarten!
      Serial.println("Wenn du das siehst, funktioniert der Watchdog nicht!");
    }
  }
}

// ============================================================================
// 19. SETUP
// ============================================================================
// Initialisierung aller Komponenten
// Wird einmalig beim Start des ESP8266 ausgeführt
// ============================================================================

void setup() {
  // Serielle Konsole für Debug-Ausgaben (115200 Baud)
  Serial.begin(115200);
  delay(1000);

  // Willkommensmeldung mit Sicherheitshinweis
  Serial.println("\n###########################################################");
  Serial.println("#     ESP8266 MAX6675 IoT Sensor - GERÄT 2 (201)            #");
  Serial.println("#              VOLLSTÄNDIG SICHER                           #");
  Serial.println("#############################################################\n");

  // Watchdog initialisieren (verhindert Freezes)
  setupWatchdog();

  // Sensor-Filter Ringbuffer initialisieren (alle Werte auf 0)
  for (int i = 0; i < 5; i++) {
    tempRingBuffer[i] = 0.0;
  }

  // MAX6675 Sensor initialisieren
  pinMode(PIN_CS, OUTPUT);
  digitalWrite(PIN_CS, HIGH);   // Chip Select hoch (inaktiv)
  delay(500);                    // Wartezeit für Sensor-Stabilisierung

  // WLAN verbinden
  connectWLAN();

  // Nach connectWLAN(); einfügen:
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

// Teste MQTT-Verbindung direkt (ohne Ping)
Serial.println("\n--- DIREKTER MQTT TEST ---");
WiFiClient testClient;
Serial.print("Verbinde zu 192.168.0.106:1883... ");
if (testClient.connect("192.168.0.106", 1883)) {
    Serial.println("✅ MQTT-Port erreichbar!");
    testClient.stop();
} else {
    Serial.println("❌ MQTT-Port NICHT erreichbar!");
}
Serial.println("--- DIREKTER MQTT TEST ENDE ---\n");

Serial.println("--- NETZWERK DIAGNOSE ENDE ---\n");

  // Geräteinformationen ausgeben
  setupDeviceInfo();

  // OTA Updates initialisieren
  setupOTA();

  // ==========================================================================
  // CREDENTIALS LADEN (aus EEPROM oder secrets.h)
  // ==========================================================================
  
  if (loadCredentials()) {
    // Credentials erfolgreich aus EEPROM geladen
    Serial.println("✅ Gespeicherte Credentials gefunden!");
  } else {
    // Keine Credentials im EEPROM - verwende Fallback aus secrets.h
    Serial.println("Keine gespeicherten Credentials gefunden!");
    
    #if SECRETS_AVAILABLE
      Serial.println("Verwende Standard-Credentials aus secrets.h...");
      mqttBroker   = MQTT_BROKER;
      mqttPort     = MQTT_PORT;
      mqttUser     = MQTT_USER;
      mqttPassword = MQTT_PASSWORD;
      
      // Credentials im EEPROM speichern für nächste Starts
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

  // Geladene Credentials ausgeben (Passwort wird NICHT angezeigt!)
  Serial.println("\n Geladene Credentials:");
  Serial.print("   Broker: ");
  Serial.println(mqttBroker);
  Serial.print("   Port: ");
  Serial.println(mqttPort);
  Serial.print("   User: ");
  Serial.println(mqttUser);
  // Passwort wird aus Sicherheitsgründen NICHT angezeigt!

  // MQTT Client konfigurieren
  mqttClient.setServer(mqttBroker.c_str(), mqttPort);
  mqttClient.setCallback(mqttCallback);

  // Fertig! System läuft.
  Serial.println("\n✅ System bereit!");
  Serial.println(" Befehle: RESET, STATUS, INFO, OFFLINE, WATCHDOG");
}

// ============================================================================
// 20. LOOP
// ============================================================================
// Hauptprogramm - läuft endlos
// Hier werden alle wiederkehrenden Aufgaben erledigt
// ============================================================================

void loop() {
  // 1. Watchdog zurücksetzen (verhindert Neustart durch Timeout)
  feedWatchdog();

  // 2. OTA Updates verarbeiten (falls verfügbar)
  #if OTA_AVAILABLE
    ArduinoOTA.handle();
  #endif

  // 3. Serielle Kommandos verarbeiten (RESET, STATUS, INFO, etc.)
  handleSerialCommands();

  // 4. MQTT Verbindung aufrechterhalten
  if (!mqttClient.connected()) {
    connectMQTT();
  }
  mqttClient.loop();    // Verarbeitet eingehende MQTT Nachrichten

  // 5. LWT (Heartbeat) Funktionen
  publishOnlineStatus();   // Heartbeat alle 30 Sekunden
  checkLWTTimeout();       // Prüft ob Timeout überschritten

  // 6. Temperatur alle 5 Sekunden senden
  static unsigned long lastSensor = 0;
  if (millis() - lastSensor > 5000) {
    lastSensor = millis();
    sendTemperature();
  }

  // Kleine Verzögerung zur Reduzierung der CPU-Last
  // ACHTUNG: delay() füttert den Hardware-Watchdog automatisch!
  delay(10);
}