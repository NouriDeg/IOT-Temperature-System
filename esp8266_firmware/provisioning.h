// =============================================================================
// provisioning.h - Automatisches Device Provisioning für ESP8266
// =============================================================================
// Diese Bibliothek ermöglicht das automatische Onboarding von ESP8266 Geräten.
// 
// Funktionen:
// - Keine statischen MQTT Credentials im Code
// - Automatischer Handshake mit Provisioning Service
// - Persistente Speicherung im EEPROM
// - Unterstützung für Factory Reset
// 
// Ablauf:
// 1. ESP8266 startet und prüft ob Credentials im EEPROM vorhanden sind
// 2. Wenn ja -> Verwende gespeicherte Credentials
// 3. Wenn nein -> Fordere neue Credentials vom Provisioning Service an
// 4. Credentials werden im EEPROM gespeichert
// 
// Sicherheit:
// - Keine hardcoded Secrets im Code
// - Credentials werden persistent und sicher gespeichert
// - Factory Reset löscht alle gespeicherten Daten
//
// Autor: Nouri Deg.  
// IoT Temperature Monitoring System
// Datum:   24.04.2026 
// Version: 1.0
// =============================================================================

#ifndef PROVISIONING_H                     // Include-Guard: Verhindert mehrfaches Einbinden
#define PROVISIONING_H

// =============================================================================
// INCLUDES (Benötigte Bibliotheken)
// =============================================================================
#include <ESP8266WiFi.h>      // WLAN Funktionen für ESP8266
#include <PubSubClient.h>     // MQTT Client für Kommunikation
#include <ArduinoJson.h>      // JSON Parsing für Nachrichten
#include <EEPROM.h>           // Persistenten Speicher für Credentials

// =============================================================================
// PROVISIONING CLIENT KLASSE
// =============================================================================
/**
 * Hauptklasse für das automatische Provisioning
 * 
 * Verwaltet den gesamten Provisioning Prozess:
 * - Prüft ob Credentials vorhanden sind
 * - Fordert neue Credentials an
 * - Speichert Credentials persistent
 * - Bietet Factory Reset Funktion
 */
class ProvisioningClient {
private:
    // =========================================================================
    // CREDENTIALS STRUKTUR (wird im EEPROM gespeichert)
    // =========================================================================
    /**
     * Diese Struktur enthält alle MQTT Zugangsdaten.
     * Sie wird persistent im EEPROM abgelegt und bleibt über Neustarts erhalten.
     */
    struct Credentials {
        bool isProvisioned = false;          // Flag: true = bereits provisioniert
        char device_id[32] = {0};            // Eindeutige Geräte-ID (aus MAC generiert)
        char mqtt_broker[64] = {0};          // MQTT Broker IP (z.B. "192.168.0.105")
        uint16_t mqtt_port = 8883;           // MQTT Port (8883 = TLS, 1883 = ohne TLS)
        char mqtt_user[32] = {0};            // MQTT Benutzername (vom Service generiert)
        char mqtt_password[64] = {0};        // MQTT Passwort (vom Service generiert)
        char ca_cert[2048] = {0};            // CA Zertifikat für Server-Validierung
        uint32_t provisioned_at = 0;         // Zeitstempel der Provisionierung
    } creds;                                 // Instanz der Credentials-Struktur
    
    // =========================================================================
    // PROVISIONING SERVICE KONFIGURATION
    // =========================================================================
    const char* prov_host;                   // Host/IP des Provisioning Service
    const int prov_port;                     // Port des Provisioning Service (1883)
    
    // MQTT Topics für Provisioning (vereinfacht)
    const char* prov_request_topic = "provisioning/request";   // ESP -> Service
    const char* prov_response_topic = "provisioning/response"; // Service -> ESP
    
    // =========================================================================
    // MQTT CLIENT (temporär, ohne TLS)
    // =========================================================================
    WiFiClient wifiClient;                   // Normaler WiFiClient (kein TLS)
    PubSubClient mqttClient;                 // MQTT Client für Provisioning
    bool provisioningComplete = false;       // Flag für Response Empfang
    String receivedResponse;                 // Empfangene Response als String
    
    // =========================================================================
    // HILFSFUNKTIONEN
    // =========================================================================
    
    /**
     * Generiert eine eindeutige Device-ID aus der MAC-Adresse
     * 
     * @return String Device-ID im Format "esp8266_<MAC>"
     *         Beispiel: "esp8266_AC67B2D3E4F5"
     */
    String getDeviceId() {
        String mac = WiFi.macAddress();      // MAC holen (z.B. "AC:67:B2:D3:E4:F5")
        mac.replace(":", "");                // Doppelpunkte entfernen
        return "esp8266_" + mac;             // Prefix + MAC ohne Doppelpunkte
    }
    
    /**
     * Callback-Funktion für eingehende MQTT Nachrichten
     * Wird aufgerufen wenn eine Nachricht auf dem responseTopic ankommt
     * 
     * @param topic   MQTT Topic der Nachricht
     * @param payload Daten der Nachricht
     * @param length  Länge des Payloads
     */
    void callback(char* topic, byte* payload, unsigned int length) {
        // Payload in String umwandeln
        String message;
        for (unsigned int i = 0; i < length; i++) {
            message += (char)payload[i];
        }
        
        // Response speichern und Flag setzen
        receivedResponse = message;
        provisioningComplete = true;
        
        // Debug-Ausgabe
        Serial.println(" Provisioning Response erhalten!");
    }
    
    /**
     * Speichert die Credentials persistent im EEPROM
     * Die Daten bleiben auch nach einem Neustart erhalten
     */
    void saveCredentials() {
        EEPROM.begin(4096);                  // EEPROM mit 4KB initialisieren
        EEPROM.put(0, creds);                // Ab Adresse 0 speichern
        EEPROM.commit();                     // Änderungen tatsächlich schreiben
        EEPROM.end();                        // EEPROM freigeben
        Serial.println(" Credentials gespeichert!");
    }
    
public:
    // =========================================================================
    // KONSTRUKTOR
    // =========================================================================
    /**
     * Initialisiert den Provisioning Client
     * 
     * @param host IP/Hostname des Provisioning Service (z.B. "192.168.0.105")
     * @param port Port des Provisioning Service (meist 1883)
     */
    ProvisioningClient(const char* host, int port) 
        : prov_host(host), prov_port(port) {
        EEPROM.begin(4096);                  // EEPROM für Credentials initialisieren
    }
    
    // =========================================================================
    // ÖFFENTLICHE METHODEN
    // =========================================================================
    
    /**
     * Prüft ob das Gerät bereits provisioniert ist
     * 
     * @return true  = Credentials vorhanden (Gerät ist provisioniert)
     * @return false = Keine Credentials (Provisioning nötig)
     */
    bool isProvisioned() {
        EEPROM.get(0, creds);                // Credentials aus EEPROM laden
        return creds.isProvisioned;          // Flag zurückgeben
    }
    
    /**
     * Führt den Provisioning Prozess durch
     * 
     * Ablauf:
     * 1. Temporäre MQTT Verbindung (ohne TLS, anonymer Zugriff)
     * 2. Sendet Provisioning Request mit MAC-Adresse
     * 3. Empfängt generierte Credentials
     * 4. Speichert alles im EEPROM
     * 
     * @return true  = Provisioning erfolgreich
     * @return false = Provisioning fehlgeschlagen
     */
    bool provision() {
        Serial.println("\n Starte Provisioning Prozess...");
        
        // =====================================================================
        // 1. GERÄTE-INFORMATIONEN AUSGEBEN
        // =====================================================================
        String device_id = getDeviceId();           // Device ID generieren
        Serial.print("   Device ID: ");
        Serial.println(device_id);
        
        // Zurücksetzen der Status-Flags
        provisioningComplete = false;
        receivedResponse = "";
        
        // =====================================================================
        // 2. TEMPORÄRE MQTT VERBINDUNG (ANONYM, KEIN TLS!)
        // =====================================================================
        mqttClient.setClient(wifiClient);           // Normaler WiFiClient (kein TLS)
        mqttClient.setServer(prov_host, prov_port); // Server setzen
        
        // Lambda-Callback für eingehende Nachrichten
        mqttClient.setCallback([this](char* t, byte* p, unsigned int l) {
            this->callback(t, p, l);
        });
        
        // Verbindungsversuche (max. 5)
        int attempts = 0;
        while (!mqttClient.connect(device_id.c_str()) && attempts < 5) {
            Serial.print("   MQTT Connect Versuch ");
            Serial.println(attempts + 1);
            delay(2000);
            attempts++;
        }
        
        if (!mqttClient.connected()) {
            Serial.println("Provisioning MQTT Verbindung fehlgeschlagen!");
            return false;
        }
        
        Serial.println("   Temporäre MQTT Verbindung hergestellt");
        
        // =====================================================================
        // 3. PROVISIONING REQUEST SENDEN
        // =====================================================================
        // Response Topic abonnieren (WICHTIG: VOR dem Senden!)
        mqttClient.subscribe(prov_response_topic);
        delay(500);
        
        // JSON Request erstellen
        StaticJsonDocument<256> req;
        req["mac_address"] = WiFi.macAddress();     // MAC-Adresse senden
        req["device_id"] = device_id;               // Device ID senden
        req["firmware_version"] = "1.0.0";          // Firmware Version
        
        // JSON in String konvertieren und senden
        char buffer[256];
        serializeJson(req, buffer);
        mqttClient.publish(prov_request_topic, buffer);
        Serial.print(" Provisioning Request gesendet: ");
        Serial.println(buffer);
        
        // =====================================================================
        // 4. AUF RESPONSE WARTEN (30 Sekunden Timeout)
        // =====================================================================
        unsigned long timeout = millis() + 30000;   // 30 Sekunden Timeout
        while (millis() < timeout && !provisioningComplete) {
            mqttClient.loop();                      // MQTT Nachrichten verarbeiten
            delay(50);
        }
        
        mqttClient.disconnect();                    // Temporäre Verbindung trennen
        
        if (!provisioningComplete) {
            Serial.println(" Keine Provisioning Response erhalten!");
            return false;
        }
        
        // =====================================================================
        // 5. RESPONSE PARSEN (JSON auswerten)
        // =====================================================================
        StaticJsonDocument<1024> doc;               // Großes JSON Dokument
        DeserializationError error = deserializeJson(doc, receivedResponse);
        
        if (error) {
            Serial.print("❌ JSON Parse Fehler: ");
            Serial.println(error.c_str());
            return false;
        }
        
        // Status prüfen
        const char* status = doc["status"];
        if (strcmp(status, "success") != 0) {
            Serial.print(" Provisioning Status: ");
            Serial.println(status);
            return false;
        }
        
        // =====================================================================
        // 6. CREDENTIALS IN STRUKTUR SPEICHERN
        // =====================================================================
        strlcpy(creds.device_id, device_id.c_str(), sizeof(creds.device_id));
        strlcpy(creds.mqtt_broker, doc["mqtt_broker"] | "192.168.0.105", sizeof(creds.mqtt_broker));
        creds.mqtt_port = doc["mqtt_port"] | 8883;
        strlcpy(creds.mqtt_user, doc["mqtt_username"] | "", sizeof(creds.mqtt_user));
        strlcpy(creds.mqtt_password, doc["mqtt_password"] | "", sizeof(creds.mqtt_password));
        
        // Zertifikate speichern (falls vom Service gesendet)
        if (doc.containsKey("certificates")) {
            JsonObject certs = doc["certificates"];
            strlcpy(creds.ca_cert, certs["ca_cert"], sizeof(creds.ca_cert));
        }
        
        creds.isProvisioned = true;                 // Flag setzen
        creds.provisioned_at = millis();            // Zeitstempel setzen
        saveCredentials();                          // Im EEPROM speichern
        
        Serial.println("✅ Provisioning erfolgreich!");
        return true;
    }
    
    /**
     * Holt die provisionierten Credentials aus dem EEPROM
     * 
     * @param broker     MQTT Broker IP (wird gefüllt)
     * @param port       MQTT Port (wird gefüllt)
     * @param user       MQTT Benutzername (wird gefüllt)
     * @param password   MQTT Passwort (wird gefüllt)
     * @param caCert     CA Zertifikat (wird gefüllt)
     * @param clientCert Client Zertifikat (wird gefüllt, optional)
     * @param clientKey  Client Private Key (wird gefüllt, optional)
     */
    void getCredentials(String &broker, uint16_t &port, 
                        String &user, String &password, 
                        String &caCert, String &clientCert, String &clientKey) {
        // Falls Credentials noch nicht geladen, aus EEPROM holen
        if (!creds.isProvisioned) {
            EEPROM.get(0, creds);
        }
        
        // Werte in die Referenz-Variablen kopieren
        broker = String(creds.mqtt_broker);
        port = creds.mqtt_port;
        user = String(creds.mqtt_user);
        password = String(creds.mqtt_password);
        caCert = String(creds.ca_cert);
        clientCert = "";                        // mTLS wird nicht verwendet
        clientKey = "";                         // mTLS wird nicht verwendet
    }
    
    /**
     * Führt einen Factory Reset durch
     * 
     * Löscht alle gespeicherten Credentials und startet das Gerät neu.
     * Nach dem Reset muss das Gerät neu provisioniert werden.
     */
    void factoryReset() {
        Serial.println(" Factory Reset wird durchgeführt...");
        creds.isProvisioned = false;            // Flag löschen
        memset(&creds, 0, sizeof(creds));       // gesamte Struktur mit Nullen füllen
        saveCredentials();                      // Geleerte Struktur speichern
        Serial.println(" Factory Reset abgeschlossen. Neustart...");
        delay(1000);
        ESP.restart();                          // ESP8266 neu starten
    }
};

#endif  // PROVISIONING_H