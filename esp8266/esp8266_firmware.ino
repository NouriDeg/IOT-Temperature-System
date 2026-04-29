// ============================================
// ESP8266 MAX6675 IoT Sensor
// MIT ADAFRUIT SLEEPYDOG WATCHDOG, LWT & OTA
// ============================================
//
// Projekt: IoT Temperature Monitoring System
// Autor: Nouri Deg.
// Datum: 2026-04-20
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
// ============================================

// ============================================
// BIBLIOTHEKEN
// ============================================

#include <ESP8266WiFi.h>         // WLAN Verbindung für ESP8266
#include <WiFiClientSecure.h>    // TLS/SSL für sichere MQTT Verbindung
#include <PubSubClient.h>        // MQTT Client für Nachrichtenaustausch
#include <ArduinoJson.h>         // JSON Parsing für MQTT Nachrichten
#include <max6675.h>             // MAX6675 Thermoelement Sensor
#include <EEPROM.h>              // Persistente Speicherung (Credentials)
#include <ArduinoOTA.h>          // Over-the-Air Updates
#include <Adafruit_SleepyDog.h>  // Watchdog Timer (verhindert Freezes)
#include "provisioning.h"        // Automatisches Provisioning

// ============================================
// OTA KONFIGURATION (aus separater Sicherheitsdatei)
// ============================================
// Diese Datei ist NICHT auf GitHub!
// Enthält Passwörter und Hostnamen für OTA Updates.
// ============================================

#ifdef __has_include               // Prüft ob Datei existiert
#if __has_include("ota_config.h")  // Wenn ota_config.h vorhanden
#include "ota_config.h"            // Lade OTA Konfiguration
#define OTA_AVAILABLE 1            // OTA ist verfügbar
#else
#define OTA_AVAILABLE 0  // OTA nicht verfügbar
#warning "ota_config.h nicht gefunden - OTA deaktiviert"
#endif
#endif

#ifndef OTA_AVAILABLE
#define OTA_AVAILABLE 0  // Fallback: OTA deaktiviert
#endif

// ============================================
// 1. WLAN KONFIGURATION
// ============================================
// Deine WLAN Zugangsdaten - hier anpassen!
// ============================================

const char* WLAN_SSID = "Vodafone-3DDC";         // Name deines WLANs
const char* WLAN_PASSWORT = "xske7fyNCgy7abzC";  // Dein WLAN Passwort

// ============================================
// 2. STATISCHE IP KONFIGURATION
// ============================================
// Vermeidet DHCP Probleme und sorgt für feste IP
// Passe diese Werte an dein Netzwerk an!
// ============================================

IPAddress staticIP(192, 168, 0, 200);  // Feste IP für ESP8266
IPAddress gateway(192, 168, 0, 1);     // Router IP (Gateway)
IPAddress subnet(255, 255, 255, 0);    // Subnetzmaske (Standard Heimnetz)
IPAddress dns(192, 168, 0, 1);         // DNS Server (meist Router)

// ============================================
// 3. PROVISIONING SERVICE KONFIGURATION
// ============================================
// Der Provisioning Service vergibt automatisch MQTT Credentials
// ============================================

const char* PROVISIONING_HOST = "192.168.0.105";  // IP deines Windows Rechners (Docker Host)
const int PROVISIONING_PORT = 1883;               // MQTT Port (ohne TLS, nur für Provisioning)

// ============================================
// 4. MAX6675 PINS
// ============================================
// Pinbelegung für das MAX6675 Thermoelement Modul
// ============================================

const int PIN_SCK = 13;  // SCK (Clock) an D7 = GPIO13
const int PIN_CS = 15;   // CS (Chip Select) an D8 = GPIO15
const int PIN_SO = 12;   // SO (Data Out) an D6 = GPIO12

// ============================================
// 5. LWT (LAST WILL TESTAMENT) KONFIGURATION
// ============================================
// LWT benachrichtigt den Broker wenn das Gerät unerwartet offline geht
// ============================================

#define LWT_HEARTBEAT_INTERVAL 30000  // Heartbeat alle 30 Sekunden (ms)
#define LWT_TIMEOUT 90000             // Nach 90 Sekunden ohne Heartbeat = offline (ms)

// ============================================
// 6. WATCHDOG KONFIGURATION (Adafruit SleepyDog)
// ============================================
// Der Watchdog startet den ESP8266 neu, wenn er sich aufhängt
// ESP8266 unterstützt max. ~8 Sekunden Timeout
// ============================================

#define WATCHDOG_TIMEOUT_MS 8000  // 8 Sekunden Timeout (ms)

// ============================================
// 7. EEPROM KONFIGURATION
// ============================================
// Adressen für persistente Speicherung der Credentials
// ============================================

#define EEPROM_SIZE 4096         // EEPROM Größe in Bytes
#define PROVISIONED_FLAG_ADDR 0  // Adresse für Provisionierungs-Flag (1 Byte)
#define MQTT_BROKER_ADDR 50      // Adresse für Broker IP (max. 50 Bytes)
#define MQTT_PORT_ADDR 120       // Adresse für Broker Port (2 Bytes)
#define MQTT_USER_ADDR 124       // Adresse für Benutzername (max. 36 Bytes)
#define MQTT_PASS_ADDR 160       // Adresse für Passwort (max. 64 Bytes)

// ============================================
// 8. GLOBALE OBJEKTE
// ============================================

MAX6675 thermocouple(PIN_SCK, PIN_CS, PIN_SO);                         // Thermoelement Objekt
WiFiClientSecure espClient;                                            // TLS-fähiger WiFi Client
PubSubClient mqttClient(espClient);                                    // MQTT Client (mit TLS)
ProvisioningClient provisioner(PROVISIONING_HOST, PROVISIONING_PORT);  // Provisioning

// Globale Variablen für Geräteinformationen
String device_id = "";    // Eindeutige Geräte-ID (aus MAC generiert)
String mac_address = "";  // MAC-Adresse des ESP8266

// Globale Variablen für MQTT Credentials
String mqttBroker;      // MQTT Broker IP Adresse
uint16_t mqttPort;      // MQTT Port (1883 oder 8883)
String mqttUser;        // MQTT Benutzername
String mqttPassword;    // MQTT Passwort
String mqttCaCert;      // CA Zertifikat (für TLS)
String mqttClientCert;  // Client Zertifikat (für mTLS, optional)
String mqttClientKey;   // Client Private Key (für mTLS, optional)

// Status Flags
bool onlineStatusPublished = false;  // Wurde Online-Status gesendet?
unsigned long lastHeartbeat = 0;     // Letzter Heartbeat Zeitstempel
bool isOnline = false;               // Ist Gerät online?
bool otaInProgress = false;          // Läuft gerade ein OTA Update?
int watchdogMS = 0;                  // Watchdog Timeout in ms (0 = nicht aktiv)

// ============================================
// 9. SENSOR-FILTER (glättet Ausreißer)
// ============================================
// Der MAX6675 liefert gelegentlich fehlerhafte Werte (0.00°C oder Sprünge).
// Dieser Filter erkennt und ignoriert solche Ausreißer.
// ============================================

float letzteGueltigeTemp = 25.0;  // Letzte gültige Temperatur
int filterIndex = 0;              // Index für Ringbuffer
float tempRingBuffer[5];          // Speichert die letzten 5 Werte

/**
 * Liest und filtert die Temperatur vom MAX6675 Sensor
 * @return Gefilterte Temperatur in Celsius
 */
float getFilteredTemperature() {
  // 1. Rohwert vom Sensor lesen
  float rohwert = thermocouple.readCelsius();

  // 2. Fehlererkennung: Kein Thermoelement erkannt (isnan = Not a Number)
  if (isnan(rohwert)) {
    Serial.println("⚠️ Sensor-Lesefehler! Verwende letzten gültigen Wert");
    return letzteGueltigeTemp;  // Letzten gültigen Wert zurückgeben
  }

  // 3. Ausreißererkennung: Sprung größer 5°C in 5 Sekunden
  if (abs(rohwert - letzteGueltigeTemp) > 5.0) {
    Serial.print(" Ausreißer ignoriert: ");
    Serial.print(rohwert);
    Serial.print(" °C → ");
    Serial.print(letzteGueltigeTemp);
    Serial.println(" °C verwendet");
    return letzteGueltigeTemp;  // Ausreißer ignorieren
  }

  // 4. Ringbuffer für Mittelwertbildung (letzte 5 Werte)
  tempRingBuffer[filterIndex] = rohwert;
  filterIndex = (filterIndex + 1) % 5;  // Zirkulärer Index

  // 5. Durchschnitt der letzten 5 Werte berechnen
  float summe = 0.0;
  int anzahl = 0;
  for (int i = 0; i < 5; i++) {
    if (tempRingBuffer[i] != 0.0) {
      summe += tempRingBuffer[i];
      anzahl++;
    }
  }

  float gemittelterWert = (anzahl > 0) ? (summe / anzahl) : rohwert;

  // 6. Gleitender Filter (70% alter Wert, 30% neuer Wert) - glättet Kurven
  float gefiltert = 0.7 * letzteGueltigeTemp + 0.3 * gemittelterWert;
  letzteGueltigeTemp = gefiltert;

  return gefiltert;
}

// ============================================
// 10. GERÄTE INFO
// ============================================
// Liest MAC-Adresse und generiert eindeutige Device ID
// ============================================

/**
 * Generiert eine eindeutige Device ID aus der MAC-Adresse
 * @return Device ID z.B. "esp8266_ECFABC5F0ADF"
 */
String getDeviceIdFromMac() {
  byte mac[6];
  WiFi.macAddress(mac);
  char deviceIdStr[18];
  snprintf(deviceIdStr, sizeof(deviceIdStr), "esp8266_%02X%02X%02X%02X%02X%02X",
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  return String(deviceIdStr);
}

/**
 * Gibt Geräteinformationen auf der seriellen Konsole aus
 */
void setupDeviceInfo() {
  byte mac[6];
  WiFi.macAddress(mac);

  // MAC-Adresse als String formatieren (mit Doppelpunkten)
  char macStr[18];
  snprintf(macStr, sizeof(macStr), "%02X:%02X:%02X:%02X:%02X:%02X",
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  mac_address = String(macStr);
  device_id = getDeviceIdFromMac();

  Serial.println("=== GERÄTE INFO ===");
  Serial.println("Device ID: " + device_id);
  Serial.println("MAC: " + mac_address);
}

// ============================================
// 11. WATCHDOG SETUP (Adafruit SleepyDog)
// ============================================
// Der Watchdog startet den ESP8266 neu, wenn er sich aufhängt
// Muss regelmäßig mit feedWatchdog() zurückgesetzt werden
// ============================================

/**
 * Aktiviert den Watchdog Timer mit konfiguriertem Timeout
 * Bei Timeout startet der ESP8266 automatisch neu
 */
void setupWatchdog() {
  // Watchdog mit 8 Sekunden Timeout aktivieren
  // Die enable() Funktion gibt den tatsächlichen Timeout zurück
  int actualTimeout = Watchdog.enable(WATCHDOG_TIMEOUT_MS);

  if (actualTimeout > 0) {
    Serial.print("✅ Watchdog aktiviert mit ");
    Serial.print(actualTimeout);
    Serial.println(" ms Timeout");

    // Optional: Zeige Warnung wenn Timeout abweicht
    if (actualTimeout != WATCHDOG_TIMEOUT_MS) {
      Serial.print("   (Angefragt waren ");
      Serial.print(WATCHDOG_TIMEOUT_MS);
      Serial.println(" ms)");
    }
  } else {
    Serial.println(" Watchdog konnte nicht aktiviert werden!");
    Serial.println("   Prüfe ob Adafruit SleepyDog Bibliothek korrekt installiert ist");
  }
}

/**
 * Setzt den Watchdog Timer zurück 
 * Muss regelmäßig im Loop aufgerufen werden
 * Verhindert dass der Watchdog auslöst und den ESP8266 neustartet
 */
void feedWatchdog() {
  // Einfach den Watchdog zurücksetzen
  // Keine Variable nötig - die Bibliothek stellt die Funktion bereit
  Watchdog.reset();
}

// ============================================
// 12. WLAN VERBINDEN
// ============================================
// Verbindet mit WLAN und konfiguriert statische IP
// ============================================

/**
 * Stellt WLAN Verbindung her mit automatischem Reconnect
 * Verwendet statische IP Konfiguration
 */
void connectWLAN() {
  // Statische IP vor dem Verbinden setzen
  WiFi.config(staticIP, gateway, subnet, dns);

  // WLAN Verbindung starten
  WiFi.begin(WLAN_SSID, WLAN_PASSWORT);
  Serial.print("Verbinde mit WLAN");

  // Bis zu 40 Versuche (20 Sekunden) warten
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
    feedWatchdog();  // Watchdog zurücksetzen während WLAN Verbindung
  }

  // Verbindungsstatus prüfen
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ WLAN verbunden!");
    Serial.print("   IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n❌ WLAN Fehler! Neustart...");
    delay(2000);
    ESP.restart();  // Bei Fehler neu starten
  }
}

// ============================================
// 13. MQTT OTA UPDATE HANDLER
// ============================================
// Behandelt OTA Update Befehle über MQTT
// ============================================

/**
 * Verarbeitet OTA Update Befehle von MQTT
 * @param command Der Befehl (z.B. "update" oder "update:http://url")
 */
void handleOTACommand(String command) {
  Serial.println("\n OTA Update via MQTT ausgelöst!");
  Serial.println("   Bitte ArduinoOTA verwenden für Firmware Update");
  Serial.println("   Arduino IDE -> Werkzeuge -> Port -> Netzwerkport");
}

// ============================================
// 14. OTA SETUP (ArduinoOTA)
// ============================================
// Over-the-Air Updates via Arduino IDE
// ============================================

/**
 * Initialisiert Over-the-Air (OTA) Updates
 * Ermöglicht Firmware Updates über WLAN
 */
void setupOTA() {
#if OTA_AVAILABLE
  // Prüfe ob Passwort konfiguriert ist
  if (OTA_PASSWORD == nullptr || strlen(OTA_PASSWORD) == 0) {
    Serial.println(" OTA deaktiviert: Kein Passwort konfiguriert");
  } else {
    // OTA Konfiguration
    ArduinoOTA.setHostname(OTA_HOSTNAME);  // Gerätename im Netzwerk
    ArduinoOTA.setPassword(OTA_PASSWORD);  // Passwort für Sicherheit

    // Callback: OTA Update gestartet
    ArduinoOTA.onStart([]() {
      String type;
      if (ArduinoOTA.getCommand() == U_FLASH) {
        type = "sketch";
      } else {
        type = "filesystem";
      }
      Serial.println("\n OTA Update gestartet: " + type);
    });

    // Callback: OTA Update abgeschlossen
    ArduinoOTA.onEnd([]() {
      Serial.println("\n✅ OTA Update abgeschlossen!");
    });

    // Callback: Fortschrittsanzeige
    ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
      Serial.printf("   Fortschritt: %u%%\r", (progress / (total / 100)));
    });

    // Callback: Fehlerbehandlung
    ArduinoOTA.onError([](ota_error_t error) {
      Serial.printf("❌ OTA Fehler [%u]: ", error);
      if (error == OTA_AUTH_ERROR) Serial.println("Authentifizierungsfehler");
      else if (error == OTA_BEGIN_ERROR) Serial.println("Begin Fehler");
      else if (error == OTA_CONNECT_ERROR) Serial.println("Verbindungsfehler");
      else if (error == OTA_RECEIVE_ERROR) Serial.println("Empfangsfehler");
      else if (error == OTA_END_ERROR) Serial.println("End Fehler");
    });

    // OTA Service starten
    ArduinoOTA.begin();
    Serial.println("✅ ArduinoOTA bereit");
    Serial.print("   Hostname: ");
    Serial.println(OTA_HOSTNAME);
    Serial.println("   OTA mit Passwortschutz aktiviert");
  }
#else
  Serial.println(" OTA deaktiviert - ota_config.h nicht gefunden");
  Serial.println("   Erstelle ota_config.h für OTA Funktion");
#endif
}

// ============================================
// 15. MQTT VERBINDEN
// ============================================
// Stellt TLS-geschützte MQTT Verbindung her
// ============================================

/**
 * Stellt MQTT Verbindung mit TLS Verschlüsselung her
 * Bei Verbindungsverlust automatischer Reconnect
 */
void connectMQTT() {
  // Akzeptiere selbstsignierte Zertifikate (Entwicklung)
  espClient.setInsecure();

  while (!mqttClient.connected()) {
    Serial.print("✅ Verbinde mit MQTTS (TLS) Port: ");
    Serial.print(mqttPort);
    Serial.print("... ");

    // Verbinde mit Device ID, Benutzername und Passwort
    if (mqttClient.connect(device_id.c_str(), mqttUser.c_str(), mqttPassword.c_str())) {
      Serial.println(" verbunden!!!");
      isOnline = true;
      lastHeartbeat = millis();

      // Online Status publishen (retained = true)
      String onlineTopic = "status/" + device_id + "/online";
      mqttClient.publish(onlineTopic.c_str(), "true", true);

      // OTA Command Topic abonnieren
      String otaTopic = "commands/" + device_id + "/ota";
      mqttClient.subscribe(otaTopic.c_str());
      Serial.print("  Abonniert: ");
      Serial.println(otaTopic);

    } else {
      // Fehlercode analysieren
      int state = mqttClient.state();
      Serial.print("❌ fehlgeschlagen, rc=");
      Serial.print(state);

      switch (state) {
        case -2:
          Serial.print(" (Netzwerkfehler)");
          break;
        case -3:
          Serial.print(" (Verbindung verloren)");
          break;
        case -4:
          Serial.print(" (Timeout)");
          break;
        case 4:
          Serial.print(" (Falscher Benutzername/Passwort)");
          break;
        case 5:
          Serial.print(" (Nicht autorisiert)");
          break;
      }
      Serial.println(" - Wiederhole in 5 Sekunden");
      delay(5000);
      feedWatchdog();  // Watchdog zurücksetzen während Wartezeit
    }
  }
}

// ============================================
// 16. MQTT CALLBACK
// ============================================
// Verarbeitet eingehende MQTT Nachrichten
// ============================================

/**
 * Callback Funktion für eingehende MQTT Nachrichten
 * @param topic MQTT Topic der Nachricht
 * @param payload Daten der Nachricht
 * @param length Länge des Payloads
 */
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  // Payload in String umwandeln
  String message;
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  Serial.print(" MQTT Nachricht: ");
  Serial.print(topic);
  Serial.print(" -> ");
  Serial.println(message);

  String otaTopic = "commands/" + device_id + "/ota";

  // Prüfe auf OTA Befehl
  if (String(topic) == otaTopic) {
    handleOTACommand(message);
  }
  // Prüfe auf LWT Nachrichten von anderen Geräten
  else if (String(topic).startsWith("lwt/")) {
    Serial.println("!!!  LWT Nachricht von einem anderen Gerät empfangen !!! ");
  }
}

// ============================================
// 17. TEMPERATUR SENDEN
// ============================================
// Sendet Temperaturdaten als JSON via MQTT
// ============================================

/**
 * Sendet die gefilterte Temperatur als JSON über MQTT
 * Topic: sensor/temperatur
 */
void sendTemperature() {
  if (!mqttClient.connected()) return;  // Nur senden wenn verbunden

  float temperatur = getFilteredTemperature();

  // JSON Dokument erstellen
  JsonDocument doc;
  doc["device_id"] = device_id;     // Geräte-ID
  doc["device_type"] = "esp8266";   // Gerätetyp
  doc["sensor"] = "max6675";        // Sensortyp
  doc["temp"] = temperatur;         // Temperaturwert
  doc["unit"] = "celsius";          // Einheit
  doc["rssi"] = WiFi.RSSI();        // Signalstärke
  doc["heap"] = ESP.getFreeHeap();  // Freier RAM
  doc["uptime"] = millis() / 1000;  // Betriebszeit in Sekunden

  // JSON in String konvertieren
  char buffer[256];
  serializeJson(doc, buffer);

  // Über MQTT senden
  if (mqttClient.publish("sensor/temperatur", buffer)) {
    Serial.print(" ");
    Serial.println(buffer);
    lastHeartbeat = millis();  // Temperatur senden aktualisiert Heartbeat
  } else {
    Serial.println("!!! Fehler beim Senden !!!");
  }
}

// ============================================
// 18. LWT (LAST WILL TESTAMENT) FUNKTIONEN
// ============================================
// Überwacht Online-Status durch regelmäßige Heartbeats
// ============================================

/**
 * Sendet periodisch Heartbeat um Online-Status zu bestätigen
 * Wird alle LWT_HEARTBEAT_INTERVAL Millisekunden aufgerufen
 */
void publishOnlineStatus() {
  if (!mqttClient.connected()) return;

  static unsigned long lastPublish = 0;
  if (millis() - lastPublish > LWT_HEARTBEAT_INTERVAL) {
    String onlineTopic = "status/" + device_id + "/online";
    mqttClient.publish(onlineTopic.c_str(), "true", true);
    lastPublish = millis();
    Serial.println(" Heartbeat gesendet ");
  }
}

/**
 * Prüft ob Heartbeat-Timeout überschritten wurde
 * Wenn kein Heartbeat für LWT_TIMEOUT ms, wird Offline-Status gesendet
 */
void checkLWTTimeout() {
  if (isOnline && (millis() - lastHeartbeat > LWT_TIMEOUT)) {
    isOnline = false;
    Serial.println(" LWT TIMEOUT! Gerät gilt als OFFLINE ");

    String onlineTopic = "status/" + device_id + "/online";
    mqttClient.publish(onlineTopic.c_str(), "false", true);
  }
}

// ============================================
// 19. EEPROM FUNKTIONEN
// ============================================
// Persistente Speicherung von MQTT Credentials
// ============================================

/**
 * Speichert MQTT Credentials persistent im EEPROM
 * @param broker MQTT Broker IP
 * @param port MQTT Port
 * @param user MQTT Benutzername
 * @param password MQTT Passwort
 */
void saveCredentials(String broker, uint16_t port, String user, String password) {
  EEPROM.begin(EEPROM_SIZE);

  // Provisionierungs-Flag setzen
  EEPROM.write(PROVISIONED_FLAG_ADDR, 1);

  // Broker IP speichern
  for (int i = 0; i < broker.length(); i++) {
    EEPROM.write(MQTT_BROKER_ADDR + i, broker[i]);
  }
  EEPROM.write(MQTT_BROKER_ADDR + broker.length(), '\0');  // Null-Terminator

  // Port speichern (2 Bytes)
  EEPROM.put(MQTT_PORT_ADDR, port);

  // Benutzername speichern
  for (int i = 0; i < user.length(); i++) {
    EEPROM.write(MQTT_USER_ADDR + i, user[i]);
  }
  EEPROM.write(MQTT_USER_ADDR + user.length(), '\0');

  // Passwort speichern
  for (int i = 0; i < password.length(); i++) {
    EEPROM.write(MQTT_PASS_ADDR + i, password[i]);
  }
  EEPROM.write(MQTT_PASS_ADDR + password.length(), '\0');

  // Änderungen schreiben
  EEPROM.commit();
  EEPROM.end();
  Serial.println(" Credentials im EEPROM gespeichert!!!");
}

/**
 * Lädt gespeicherte MQTT Credentials aus dem EEPROM
 * @return true wenn Credentials vorhanden, false wenn nicht
 */
bool loadCredentials() {
  EEPROM.begin(EEPROM_SIZE);
  bool isProvisioned = (EEPROM.read(PROVISIONED_FLAG_ADDR) == 1);

  if (isProvisioned) {
    char buf[128];
    int i = 0;

    // Broker laden
    while (i < 127) {
      buf[i] = EEPROM.read(MQTT_BROKER_ADDR + i);
      if (buf[i] == '\0') break;
      i++;
    }
    buf[i] = '\0';
    mqttBroker = String(buf);

    // Port laden
    EEPROM.get(MQTT_PORT_ADDR, mqttPort);

    // Benutzername laden
    i = 0;
    while (i < 127) {
      buf[i] = EEPROM.read(MQTT_USER_ADDR + i);
      if (buf[i] == '\0') break;
      i++;
    }
    buf[i] = '\0';
    mqttUser = String(buf);

    // Passwort laden
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

// ============================================
// 20. SERIELLE KOMMANDOS
// ============================================
// Verarbeitet Befehle vom Seriellen Monitor
// ============================================

/**
 * Verarbeitet Befehle vom Seriellen Monitor
 * Verfügbare Befehle:
 * - RESET: Factory Reset (löscht alle Credentials)
 * - STATUS: Zeigt Systemstatus an
 * - INFO: Zeigt aktuelle Credentials
 * - OFFLINE: Simuliert Offline (für LWT Test)
 * - WATCHDOG: Testet Watchdog (blockiert für 15s)
 */
void handleSerialCommands() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    cmd.toUpperCase();

    // Factory Reset - löscht alle Credentials
    if (cmd == "RESET") {
      Serial.println("\n Factory Reset wird durchgeführt... ");
      provisioner.factoryReset();  // Löscht Credentials und startet neu
    }
    // Systemstatus anzeigen
    else if (cmd == "STATUS") {
      Serial.println("\n=== SYSTEM STATUS ===");
      Serial.print("Device ID: ");
      Serial.println(device_id);
      Serial.print("MQTT Connected: ");
      Serial.println(mqttClient.connected() ? "Ja" : "Nein");
      Serial.print("Online Status: ");
      Serial.println(isOnline ? "Online" : "Offline");
      Serial.print("Heartbeat vor: ");
      Serial.print((millis() - lastHeartbeat) / 1000);
      Serial.println(" Sekunden");
      Serial.print("Watchdog aktiv: ");
      Serial.println(watchdogMS > 0 ? "Ja" : "Nein");
      Serial.print("Heap: ");
      Serial.println(ESP.getFreeHeap());
      Serial.print("RSSI: ");
      Serial.println(WiFi.RSSI());
      Serial.print("Uptime: ");
      Serial.println(millis() / 1000);
    }
    // Provisionierungs Info anzeigen
    else if (cmd == "INFO") {
      Serial.println("\n=== PROVISIONING INFO ===");
      Serial.print("Broker: ");
      Serial.println(mqttBroker);
      Serial.print("Port: ");
      Serial.println(mqttPort);
      Serial.print("User: ");
      Serial.println(mqttUser);
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
      delay(15000);  // Blockiert den Loop - Watchdog sollte auslösen!
      Serial.println("Wenn du das siehst, funktioniert der Watchdog nicht!");
    }
  }
}

// ============================================
// 21. SETUP
// ============================================
// Initialisierung aller Komponenten
// ============================================

void setup() {
  // Serielle Konsole für Debug-Ausgaben
  Serial.begin(115200);
  delay(1000);

  // Willkommensmeldung
  Serial.println("\n=========================================");
  Serial.println("ESP8266 MAX6675 IoT Sensor");
  Serial.println("MIT ADAFRUIT SLEEPYDOG WATCHDOG & OTA");
  Serial.println("=========================================\n");

  // Watchdog initialisieren (verhindert Freezes)
  setupWatchdog();

  // Sensor-Filter Ringbuffer initialisieren
  for (int i = 0; i < 5; i++) {
    tempRingBuffer[i] = 0.0;
  }

  // MAX6675 Sensor initialisieren
  pinMode(PIN_CS, OUTPUT);
  digitalWrite(PIN_CS, HIGH);  // Chip Select hoch (inaktiv)
  delay(500);                  // Kurze Wartezeit für Sensor Stabilisierung

  // WLAN verbinden
  connectWLAN();

  // Geräteinformationen ausgeben
  setupDeviceInfo();

  // OTA Updates initialisieren
  setupOTA();

  // Gespeicherte Credentials laden oder neues Provisioning starten
  if (loadCredentials()) {
    Serial.println("📀 Gespeicherte Credentials gefunden!");
  } else {
    Serial.println(" Keine gespeicherten Credentials gefunden! ");
    Serial.println(" Starte automatisches Provisioning... ");

    if (provisioner.provision()) {
      // Nach erfolgreichem Provisioning Credentials holen
      provisioner.getCredentials(mqttBroker, mqttPort, mqttUser, mqttPassword,
                                 mqttCaCert, mqttClientCert, mqttClientKey);
      // Im EEPROM speichern für nächsten Start
      saveCredentials(mqttBroker, mqttPort, mqttUser, mqttPassword);
    } else {
      Serial.println("❌ Provisioning fehlgeschlagen!");
      Serial.println("   Neustart in 10 Sekunden...");
      delay(10000);
      ESP.restart();
      return;
    }
  }

  // Provisionierte Credentials ausgeben
  Serial.println("\n Provisionierte Credentials: ");
  Serial.print("   Broker: ");
  Serial.println(mqttBroker);
  Serial.print("   Port: ");
  Serial.println(mqttPort);
  Serial.print("   User: ");
  Serial.println(mqttUser);

  // LWT Konfiguration ausgeben
  Serial.println("\n LWT Konfiguration: ");
  Serial.print("   Heartbeat Intervall: ");
  Serial.print(LWT_HEARTBEAT_INTERVAL / 1000);
  Serial.println(" Sekunden");
  Serial.print("   Timeout: ");
  Serial.print(LWT_TIMEOUT / 1000);
  Serial.println(" Sekunden");

  // MQTT Client konfigurieren
  mqttClient.setServer(mqttBroker.c_str(), mqttPort);
  mqttClient.setCallback(mqttCallback);  // Für OTA Commands

  // Fertig! System läuft.
  Serial.println("\n✅ System bereit!");
  Serial.println(" Befehle: RESET, STATUS, INFO, OFFLINE, WATCHDOG");
  Serial.println(" OTA: Arduino IDE -> Werkzeuge -> Port -> Netzwerkport");
}

// ============================================
// 22. LOOP
// ============================================
// Hauptprogramm - läuft endlos
// ============================================
void loop() {
  // ============================================
  // WATCHDOG ZURÜCKSETZEN (FÜTTERN)
  // ============================================
  // Der Watchdog muss regelmäßig zurückgesetzt werden.
  // Wenn der Loop länger als WATCHDOG_TIMEOUT_MS (8 Sekunden) braucht
  // oder sich aufhängt, startet der Watchdog den ESP8266 neu.
  // Das ist eine Sicherheitsmaßnahme gegen Software-Freezes.
  // ============================================
  feedWatchdog();  // Watchdog füttern

// ================================================================
// ARDUINO OTA HANDLE
// ================================================================
// Muss regelmäßig aufgerufen werden damit OTA Updates funktionieren
// ================================================================
#if OTA_AVAILABLE
  if (!otaInProgress) {
    ArduinoOTA.handle();
  }
#endif

  // ============================================================
  // SERIELLE KOMMANDOS
  // =============================================================
  // Verarbeitet Befehle wie RESET, STATUS, INFO, OFFLINE, WATCHDOG
  // ============================================
  handleSerialCommands();

  // ============================================
  // MQTT VERBINDUNG
  // ============================================
  // Stellt sicher dass MQTT immer verbunden ist
  // ============================================
  if (!mqttClient.connected()) {
    connectMQTT();
  }
  mqttClient.loop();  // Verarbeitet eingehende MQTT Nachrichten

  // ============================================
  // LWT (LAST WILL TESTAMENT)
  // ============================================
  // Sendet periodisch Heartbeat und prüft auf Timeout
  // ============================================
  publishOnlineStatus();  // Heartbeat alle 30 Sekunden
  checkLWTTimeout(); // Prüft ob Heartbeat-Timeout (90 Sekunden)

  // ============================================
  // TEMPERATUR SENDEN
  // ============================================
  // Temperatur alle 5 Sekunden messen und via MQTT senden
  // ============================================
  static unsigned long lastSensor = 0;
  if (millis() - lastSensor > 5000) {
    lastSensor = millis();
    sendTemperature();
  }

  // Kleine Verzögerung um CPU-Last zu reduzieren
  // Achtung: delay() füttert den Hardware-Watchdog automatisch!
  delay(10);
}