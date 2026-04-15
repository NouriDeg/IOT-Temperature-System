# IoT Temperature Monitoring System

> Ein modulares System zur Erfassung, Übertragung, Speicherung und Visualisierung von Temperaturdaten mit ESP8266, MQTT, PostgreSQL und Docker.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Containerized-blue)](https://www.docker.com/)
[![ESP8266](https://img.shields.io/badge/ESP8266-Embedded-green)](https://www.espressif.com/)

---

##  Inhaltsverzeichnis

1. [Architektur](#-architektur)
2. [Features](#-features)
3. [Voraussetzungen](#-voraussetzungen)
4. [Installation](#-installation)
5. [MQTT Schnittstellen](#-mqtt-schnittstellen)
6. [REST API](#-rest-api)
7. [PostgreSQL Schema](#-postgresql-schema)
8. [ESP8266 Setup](#-esp8266-setup)
9. [Docker Services](#-docker-services)
10. [Umgebungsvariablen](#-umgebungsvariablen)
11. [Fehlersuche](#-fehlersuche)
12. [Lizenz](#-lizenz)

---


---

##  Features

| Feature | Beschreibung |
|---------|--------------|
| **Hardware** | ESP8266 mit MAX6675 Thermoelement (SCK an D7) |
| **Konnektivität** | WLAN mit statischer IP, automatischer Reconnect |
| **Messaging** | MQTT mit TLS, Authentifizierung, LWT, ACLs |
| **Persistenz** | PostgreSQL mit TimescaleDB (optional) |
| **Validierung** | JSON Schema serverseitig |
| **Containerisierung** | Vollständig in Docker |
| **OTA Updates** | Over-The-Air Firmware Updates |
| **Provisioning** | Automatisches Geräte-Onboarding |
| **Dashboard** | Web-Interface mit Echtzeit-Charts |

---

##  Voraussetzungen

| Software | Version | Link |
|----------|---------|------|
| Docker Desktop | 20.10+ | [Download](https://www.docker.com/products/docker-desktop/) |
| Git | 2.30+ | [Download](https://git-scm.com/) |
| Arduino IDE | 1.8+ | [Download](https://www.arduino.cc/en/software) |
| ESP8266 Boardpaket | 3.1.2+ | Über Boardverwalter |
| OpenSSL | 3.0+ | Für Zertifikatserstellung |

---

##  Installation

### 1. Repository klonen

```bash
git clone https://github.com/NouriDeg/IOT-Temperature-System.git
cd IOT-Temperature-System

##  Architektur

