# 🌡️ IoT Temperature Monitoring System

Ein vollständiges IoT-System zur Überwachung von Temperaturen mit ESP8266, MAX6675 Thermoelement-Sensor und einer Docker-basierten Microservices-Architektur.

## 📋 Inhaltsverzeichnis

- [Überblick](#überblick)
- [Architektur](#architektur)
- [Technologie-Stack](#technologie-stack)
- [Schnittstellen](#schnittstellen)
- [Voraussetzungen](#voraussetzungen)
- [Installation](#installation)
- [Konfiguration](#konfiguration)
- [Betrieb](#betrieb)
- [API Dokumentation](#api-dokumentation)
- [Fehlersuche](#fehlersuche)
- [Erweiterungsmöglichkeiten](#erweiterungsmöglichkeiten)

## 🎯 Überblick

Das System ermöglicht die automatische Erfassung, Übertragung und Visualisierung von Temperaturdaten. Ein ESP8266 mit MAX6675 Sensor sendet die Daten verschlüsselt via MQTTS an einen Mosquitto Broker. Eine Bridge speichert die Daten in PostgreSQL, während ein Flask-Backend und Nginx-Frontend die Visualisierung übernehmen.

### Hauptmerkmale

- ✅ **Automatisches Provisioning** - Neue Geräte werden automatisch registriert
- 🔒 **Verschlüsselte Kommunikation** - TLS für MQTT (Port 8883)
- 📊 **Echtzeit-Dashboard** - Live-Temperaturanzeige mit Chart.js
- 🗄️ **Persistente Speicherung** - PostgreSQL mit TimescaleDB-Option
- 🐳 **Containerisiert** - Vollständige Docker-Compose Umgebung
- ⏰ **Lokale Zeitzone** - Alle Zeitstempel in Europe/Berlin (CET/CEST)

## 🏗️ Architektur

### Komponentendiagramm

```plantuml
@startuml
!theme plain
skinparam componentStyle rectangle
skinparam backgroundColor #1a1a2e
skinparam componentBackground #16213e
skinparam componentBorderColor #e94560
skinparam fontColor white
skinparam arrowColor #e94560

title IoT Temperature Monitoring System - Komponenten & Schnittstellen

' === EDGE LAYER ===
package "Edge Layer" {
    component "ESP8266 Firmware" as ESP
    component "MAX6675 Treiber" as MAX
    component "MQTTs Client" as MQTT_CLIENT
    note right of ESP : C++/Arduino\nWiFiClientSecure\nPubSubClient
}

' === MESSAGING LAYER ===
package "Messaging Layer" {
    component "MQTT Broker\n(Mosquitto)" as BROKER
    database "Passwd File" as PASSWD
    file "ACL" as ACL
    note right of BROKER : Port 1883 (anonym)\nPort 8883 (TLS)
}

' === SERVICE LAYER ===
package "Service Layer" {
    component "Provisioning Service\n(Python)" as PROV
    component "MQTT Bridge\n(Python)" as BRIDGE
    component "Backend API\n(Flask)" as BACKEND
    component "JSON Schema\nValidator" as VALIDATOR
    note right of BRIDGE : MQTT → PostgreSQL\nJSON Validierung
}

' === PRESENTATION LAYER ===
package "Presentation Layer" {
    component "Web Frontend\n(Nginx)" as FRONTEND
    component "Chart.js\nVisualisierung" as CHART
    component "REST API\nEndpoints" as REST
}

' === DATA LAYER ===
package "Data Layer" {
    database "PostgreSQL 15" as DB
    component "TimescaleDB\n(optional)" as TIMESCALE
    note right of DB : Tabellen:\n- sensor_data\n- device_status\n- devices
}

' === VERBINDUNGEN ===
ESP -down-> MAX : SPI\n(D5, D6, D8)
ESP -down-> MQTT_CLIENT : MQTTs\n(JSON Payload)
MQTT_CLIENT -right-> BROKER : TLS/8883

BROKER -down-> PROV : MQTT/1883\ndevices/+/provisioning/request
BROKER -down-> BRIDGE : MQTT/1883\nsensor/temperatur

PROV -down-> DB : SQL/5432\nINSERT devices
BRIDGE -down-> DB : SQL/5432\nINSERT sensor_data

BACKEND -down-> DB : SQL/5432\nSELECT sensor_data
BACKEND -right-> REST : HTTP/5000\nJSON Responses
REST -up-> CHART : Chart.js\nData Binding

FRONTEND -up-> BACKEND : HTTP/8080 → 5000\nAPI Calls

BROKER -right-> PASSWD : Auth
BROKER -right-> ACL : ACLs
DB -right-> TIMESCALE : Extension

@enduml



@startuml
!theme plain
skinparam nodeBackground #16213e
skinparam componentBackground #1a1a2e
skinparam databaseBackground #0f3460
skinparam nodeBorderColor #e94560
skinparam fontColor white

title Docker Container Deployment

node "Windows Rechner\n192.168.0.105" {
    
    rectangle "Docker Network: iot_network (bridge)" {
        
        node "mqtt_broker\n(Mosquitto)" {
            component "Port 1883 (MQTT)"
            component "Port 8883 (MQTTs)"
            file "mosquitto.conf"
            file "passwd_file"
            file "acls"
        }
        
        node "provisioner_service\n(Python)" {
            component "app.py"
            component "MQTT Client"
            component "Zertifikats-Generator"
        }
        
        node "mqtt_bridge\n(Python)" {
            component "bridge.py"
            component "MQTT Subscriber"
            component "JSON Validator"
        }
        
        node "api_backend\n(Flask)" {
            component "Port 5000"
            component "REST Endpoints"
            component "Templates"
        }
        
        node "web_frontend\n(Nginx)" {
            component "Port 8080"
            component "index.html"
            component "nginx.conf"
        }
        
        database "postgres_db\n(PostgreSQL 15)" {
            component "Port 5432"
            component "sensor_data"
            component "device_status"
            component "devices"
            file "init.sql"
        }
    }
}

node "ESP8266\n192.168.0.200" {
    component "MAX6675 Sensor"
    component "MQTTs Client"
    component "Provisioning"
}

' Verbindungen
ESP -down-> mqtt_broker : MQTTs (TLS) Port 8883
ESP -down-> provisioner_service : Provisioning (temporär) Port 1883

web_frontend -right-> api_backend : HTTP Port 5000
api_backend -down-> postgres_db : SQL Port 5432
provisioner_service -down-> postgres_db : SQL Port 5432
mqtt_bridge -down-> postgres_db : SQL Port 5432

mqtt_bridge -up-> mqtt_broker : MQTT Port 1883
provisioner_service -up-> mqtt_broker : MQTT Port 1883

@enduml


Technologie-Stack
Komponente	Technologie	Version	Port
Edge Device	ESP8266 + MAX6675	-	-
Firmware	Arduino C++	-	-
MQTT Broker	Eclipse Mosquitto	2.0	1883, 8883
Provisioning	Python + Paho MQTT	3.11	-
Bridge	Python + Paho MQTT	3.11	-
Backend API	Flask + CORS	2.3.3	5000
Frontend	Nginx + HTML/JS	latest	8080
Database	PostgreSQL	15	5432
Visualisierung	Chart.js	4.x	-
Container	Docker + Compose	24.x	-
🔌 Schnittstellen
1. MQTT Schnittstellen
Provisioning Topics
Topic	Richtung	Beschreibung	Payload
provisioning/request	ESP → Provisioner	Anfrage für neue Credentials	{"mac_address":"...", "device_id":"...", "firmware_version":"..."}
provisioning/response	Provisioner → ESP	Antwort mit Credentials	{"status":"success", "mqtt_username":"...", "mqtt_password":"...", "mqtt_broker":"...", "mqtt_port":8883}
Sensor Topics
Topic	Richtung	Beschreibung	Payload
sensor/temperatur	ESP → Bridge	Temperaturdaten	{"device_id":"...", "device_type":"esp8266", "sensor":"max6675", "temp":25.5, "unit":"celsius", "rssi":-59, "heap":18840, "uptime":6}
Status Topics
Topic	Richtung	Beschreibung
status/{device_id}/online	ESP → Broker	Gerät ist online
status/{device_id}/will	ESP → Broker	Last Will Nachricht
2. REST API Endpoints (Port 5000)
Methode	Endpoint	Beschreibung	Response
GET	/api/latest	Aktuellste Temperatur	{"device_id":"...", "temperature":25.5, "unit":"celsius", "timestamp":"2026-04-17 10:30:00"}
GET	/api/history?hours=24&limit=200	Historische Daten	[{"device_id":"...", "temperature":25.5, "timestamp":"..."}]
GET	/api/devices	Alle registrierten Geräte	[{"device_id":"...", "status":"online", "last_seen":"..."}]
GET	/api/stats?hours=24	Statistiken	{"min_temp":23.5, "max_temp":25.8, "avg_temp":24.6, "count":288}
GET	/api/health	Health Check	{"status":"healthy", "database":"connected", "timezone":"Europe/Berlin"}
GET	/	Dashboard HTML	HTML Seite
3. Datenbank Schema
sensor_data Tabelle
sql

CREATE TABLE sensor_data (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    device_type VARCHAR(32),
    sensor_type VARCHAR(32),
    value DECIMAL(10,2),
    unit VARCHAR(16),
    raw_payload JSONB,
    received_at TIMESTAMPTZ DEFAULT NOW()
);

device_status Tabelle
sql

CREATE TABLE device_status (
    device_id VARCHAR(64) PRIMARY KEY,
    status VARCHAR(20) DEFAULT 'offline',
    last_seen TIMESTAMPTZ,
    last_rssi INTEGER,
    last_free_heap INTEGER,
    updated_at TIMESTAMPTZ
);

devices Tabelle (Provisioning)
sql

CREATE TABLE devices (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(64) UNIQUE NOT NULL,
    mac_address VARCHAR(17) UNIQUE NOT NULL,
    mqtt_username VARCHAR(64) UNIQUE,
    mqtt_password_hash VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending',
    provisioned_at TIMESTAMPTZ DEFAULT NOW()
);

4. Docker Volumes & Bind Mounts
Volume/Mount	Container	Beschreibung
postgres_data	postgres_db	Persistente Datenbankdateien
./mosquitto/config:/mosquitto/config	mqtt_broker	Mosquitto Konfiguration
./mosquitto/passwd:/mosquitto/passwd	mqtt_broker	Passwortdatei
./certs:/mosquitto/certs:ro	mqtt_broker	TLS Zertifikate
./certs:/app/certs:ro	provisioner	CA Zertifikate
💻 Voraussetzungen

    Docker Desktop (Version 24.0+)

    Docker Compose (Version 2.20+)

    Git (für Repository)

    ESP8266 mit MAX6675 Modul

    Windows/Linux/Mac als Host-System

    Python 3.11+ (für lokale Entwicklung)

🚀 Installation
1. Repository klonen
bash

git clone https://github.com/dein-benutzername/IOT-Temperature-System.git
cd IOT-Temperature-System

2. Umgebungsvariablen konfigurieren

Erstelle eine .env Datei:
env

# Datenbank
DB_PASSWORD=dein_sicheres_passwort

# MQTT Benutzer
MQTT_BRIDGE_USER=bridge_user
MQTT_BRIDGE_PASSWORD=bridge_passwort
MQTT_PROVISION_USER=provisioner
MQTT_PROVISION_PASSWORD=provisioner_passwort

# Broker Adresse (IP des Hosts)
MQTT_BROKER_ADDRESS=192.168.0.105

3. TLS Zertifikate generieren
bash

cd certs
openssl genrsa -out ca.key 2048
openssl req -new -x509 -days 365 -key ca.key -out ca.crt -subj "/CN=MQTT-CA"
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr -subj "/CN=192.168.0.105"
openssl x509 -req -days 365 -in server.csr -CA ca.crt -CAkey ca.key -set_serial 01 -out server.crt
cd ..

4. Docker Container starten
bash

docker-compose up -d

5. ESP8266 Firmware flashen

    Öffne main.ino in Arduino IDE

    Installiere benötigte Bibliotheken:

        PubSubClient

        ArduinoJson

        MAX6675

    Kompiliere und flashe auf ESP8266

⚙️ Konfiguration
Mosquitto Konfiguration (mosquitto/config/mosquitto.conf)
conf

listener 1883 0.0.0.0
allow_anonymous true

listener 8883 0.0.0.0
allow_anonymous false
certfile /mosquitto/certs/server.crt
keyfile /mosquitto/certs/server.key
cafile /mosquitto/certs/ca.crt
require_certificate false

password_file /mosquitto/passwd/passwd_file

ESP8266 Konfiguration (main.ino)
cpp

// WLAN
const char* WLAN_SSID = "Dein_WLAN";
const char* WLAN_PASSWORT = "Dein_Passwort";

// Statische IP
IPAddress staticIP(192, 168, 0, 200);
IPAddress gateway(192, 168, 0, 1);
IPAddress subnet(255, 255, 255, 0);

// Provisioning Service
const char* PROVISIONING_HOST = "192.168.0.105";
const int PROVISIONING_PORT = 1883;

🔧 Betrieb
Container Management
bash

# Alle Container starten
docker-compose up -d

# Container stoppen
docker-compose down

# Logs anzeigen
docker-compose logs -f

# Einzelnen Service neu starten
docker-compose restart bridge

# Container neu bauen
docker-compose build --no-cache bridge

Dashboard Zugriff
Service	URL	Beschreibung
Backend Dashboard	http://192.168.0.105:5000	Vollständiges Dashboard mit Diagramm
Frontend Dashboard	http://192.168.0.105:8080	Einfaches Dashboard
API Health Check	http://192.168.0.105:5000/api/health	Statusabfrage
Datenbank Abfragen
bash

# Letzte 10 Messungen
docker exec postgres_db psql -U sensor_user -d sensordb -c "SELECT device_id, value, received_at FROM sensor_data ORDER BY id DESC LIMIT 10;"

# Durchschnittstemperatur letzte Stunde
docker exec postgres_db psql -U sensor_user -d sensordb -c "SELECT AVG(value) FROM sensor_data WHERE received_at > NOW() - INTERVAL '1 hour';"

# Gerätestatus
docker exec postgres_db psql -U sensor_user -d sensordb -c "SELECT * FROM device_status;"

📖 API Dokumentation
GET /api/latest

Response:
json

{
    "device_id": "esp8266_ECFABC5F0",
    "temperature": 23.5,
    "unit": "celsius",
    "timestamp": "2026-04-17 10:30:00",
    "timezone": "Europe/Berlin"
}

GET /api/history

Parameter:

    hours (optional, default: 24) - Zeitraum in Stunden

    limit (optional, default: 200) - Maximale Anzahl

Response:
json

[
    {
        "device_id": "esp8266_ECFABC5F0",
        "temperature": 23.5,
        "unit": "celsius",
        "timestamp": "2026-04-17 10:25:00"
    }
]

GET /api/stats

Parameter:

    hours (optional, default: 24)

Response:
json

{
    "min_temp": 23.2,
    "max_temp": 24.8,
    "avg_temp": 23.9,
    "count": 288
}

🐛 Fehlersuche
Bridge startet nicht (pytz fehlt)
bash

docker-compose build --no-cache bridge
docker-compose up -d bridge

MQTT Verbindungsfehler (rc=-2)
bash

# Prüfe ob Mosquitto läuft
docker ps | findstr mqtt

# Prüfe Logs
docker logs mqtt_broker --tail 30

# Teste TLS Verbindung
docker exec mqtt_broker mosquitto_sub -t "test" -u test_device -P test_password_123 --cafile /mosquitto/certs/ca.crt -p 8883

Keine Daten in der Datenbank
bash

# Prüfe Bridge Logs
docker logs mqtt_bridge --tail 50

# Prüfe ESP8266 Verbindung
docker logs mqtt_broker --tail 20 | findstr "esp8266"

# Sende manuelle Test-Nachricht
docker exec mqtt_broker mosquitto_pub -t "sensor/temperatur" -m '{"device_id":"test","temp":25.5}' -u test_device -P test_password_123 -p 1883

Factory Reset für ESP8266

Sende RESET über den Seriellen Monitor (115200 Baud).
🔮 Erweiterungsmöglichkeiten
1. Mehrere Sensoren

    Einfach weitere ESP8266 hinzufügen

    Automatisches Provisioning pro Gerät

2. Alarme & Benachrichtigungen
python

# Beispiel für E-Mail Alarm bei Temperaturschwelle
if temperature > 30.0:
    send_email_alert("Hohe Temperatur!", temperature)

3. Grafana Integration
yaml

grafana:
  image: grafana/grafana:latest
  ports:
    - "3000:3000"
  volumes:
    - grafana_data:/var/lib/grafana

4. InfluxDB + TimescaleDB
yaml

timescaledb:
  image: timescale/timescaledb:latest-pg15
  environment:
    POSTGRES_DB: sensordb

5. OTA Updates

    MQTT Topic: commands/{device_id}/ota

    Firmware Update über MQTT

📄 Lizenz

MIT License - Siehe LICENSE Datei
👥 Autoren

    Dein Name - Initiales Projekt

🙏 Danksagung

    ESP8266 Community

    Eclipse Mosquitto Team

    Flask & PostgreSQL Entwickler





