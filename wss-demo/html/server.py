#!/usr/bin/env python
"""
================================================================================
Einfacher HTTPS Server für WSS Test
================================================================================
Dieser Server stellt eine lokale HTTPS-Umgebung bereit, um HTML Dateien
mit WSS (WebSocket Secure) Verbindungen zu testen.

Warum wird das benötigt?
- Browser erlauben WSS nur von gesicherten Seiten (HTTPS)
- file:// URLs können keine WSS Verbindungen herstellen
- Dieser Server löst das Problem durch lokales HTTPS

Verwendung:
1. Server starten: python server.py
2. Browser öffnen: https://192.168.0.105:4443/wss-all-browser.html
3. WSS Verbindung testen
 
IoT Temperature Monitoring System
Author: Nouri Deg
Datum: 24.04.2026
================================================================================
"""

# =============================================================================
# IMPORTE
# =============================================================================

import http.server          # Stellt einfachen HTTP Server bereit
import ssl                  # TLS/SSL für HTTPS Verschlüsselung
import os                   # Betriebssystem-Funktionen (Dateipfade)

# =============================================================================
# SERVER KONFIGURATION
# =============================================================================

PORT = 4443                 # Port für den HTTPS Server
                            # 4443 ist alternativer HTTPS Port
                            # (Standard HTTPS wäre 443, aber benötigt Admin-Rechte)

# WEB_DIR: Verzeichnis, in dem diese server.py Datei liegt
# os.path.dirname(__file__) gibt den Ordner der aktuellen Datei zurück
WEB_DIR = os.path.dirname(os.path.abspath(__file__))

# CERT_DIR: Pfad zum Zertifikatsverzeichnis
# "../.." geht zwei Ordner hoch zum Hauptverzeichnis, dann in "certs"
CERT_DIR = os.path.join(WEB_DIR, "../../certs")

# CERT_FILE: Pfad zum Server-Zertifikat (öffentlicher Schlüssel)
CERT_FILE = os.path.join(CERT_DIR, "server.crt")

# KEY_FILE: Pfad zum privaten Schlüssel (geheimer Schlüssel)
KEY_FILE = os.path.join(CERT_DIR, "server.key")

# =============================================================================
# HTTP REQUEST HANDLER
# =============================================================================

class Handler(http.server.SimpleHTTPRequestHandler):
    """
    Benutzerdefinierter Handler für HTTP-Anfragen.
    Erbt von SimpleHTTPRequestHandler und konfiguriert das Arbeitsverzeichnis.
    
    Der Handler:
    - Bearbeitet GET-Anfragen für HTML, CSS, JS Dateien
    - Sendet die Dateien aus dem WEB_DIR Verzeichnis
    - Loggt Anfragen automatisch auf der Konsole
    """
    
    def __init__(self, *args, **kwargs):
        """
        Konstruktor des Handlers.
        Ruft den Konstruktor der Elternklasse auf und setzt das Arbeitsverzeichnis.
        
        Parameter:
            *args: Positionsargumente (werden an Elternklasse weitergegeben)
            **kwargs: Keyword-Argumente (werden an Elternklasse weitergegeben)
        """
        # Rufe Elternklasse mit directory=WEB_DIR auf
        # Dadurch werden nur Dateien aus diesem Verzeichnis ausgeliefert
        super().__init__(*args, directory=WEB_DIR, **kwargs)

# =============================================================================
# HAUPTFUNKTION
# =============================================================================

def main():
    """
    Hauptfunktion - startet den HTTPS Server.
    
    Ablauf:
    1. Wechselt ins HTML-Verzeichnis (damit relative Pfade stimmen)
    2. Erstellt einen HTTP Server auf Port 4443
    3. Konfiguriert TLS mit Zertifikat und privatem Schlüssel
    4. Wandelt HTTP Server in HTTPS Server um
    5. Startet die Server-Schleife (läuft bis Ctrl+C)
    """
    
    # =========================================================================
    # 1. ARBEITSVERZEICHNIS WECHSELN
    # =========================================================================
    # Wechselt ins WEB_DIR (dorthin, wo die HTML Dateien liegen)
    # Dadurch werden relative Pfade in der HTML Datei korrekt aufgelöst
    os.chdir(WEB_DIR)
    
    # =========================================================================
    # 2. HTTP SERVER ERSTELLEN
    # =========================================================================
    # Erstellt einen einfachen HTTP Server
    # Parameter:
    #   ('0.0.0.0', PORT) - Hört auf allen Netzwerkschnittstellen auf Port 4443
    #   Handler - Benutzerdefinierter Request Handler für HTML Dateien
    server = http.server.HTTPServer(('0.0.0.0', PORT), Handler)
    
    # =========================================================================
    # 3. TLS/SSL KONFIGURATION (Verschlüsselung)
    # =========================================================================
    # Erstelle einen TLS Kontext für sichere Verbindungen
    # PROTOCOL_TLS_SERVER = Verwende modernes TLS Protokoll
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    
    # Lade Zertifikat und privaten Schlüssel
    # Diese Dateien wurden vorher mit OpenSSL generiert
    # server.crt = Öffentliches Zertifikat
    # server.key = Privater Schlüssel (geheim!)
    ssl_context.load_cert_chain(CERT_FILE, KEY_FILE)
    
    # Verbinde den HTTP Server Socket mit TLS
    # server_side=True bedeutet: Dies ist der Server (nicht Client)
    server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
    
    # =========================================================================
    # 4. SERVER INFO AUSGEBEN
    # =========================================================================
    print(f"✅ HTTPS Server läuft auf https://192.168.0.105:{PORT}")
    print(f"📁 Serving: {WEB_DIR}")
    print("Press Ctrl+C to stop")
    
    # =========================================================================
    # 5. SERVER SCHLEIFE STARTEN
    # =========================================================================
    try:
        # Starte die Server-Schleife (blockiert, läuft endlos)
        # Hier werden eingehende HTTPS Anfragen bearbeitet
        server.serve_forever()
        
    except KeyboardInterrupt:
        # Benutzer hat Ctrl+C gedrückt
        print("\n Server gestoppt !")
        # Herunterfahren des Servers (gibt Ressourcen frei)
        server.shutdown()

# =============================================================================
# PROGRAMMSTART
# =============================================================================
# Diese Bedingung ist True, wenn das Skript direkt ausgeführt wird
# (nicht wenn es als Modul importiert wird)

if __name__ == "__main__":
    main()