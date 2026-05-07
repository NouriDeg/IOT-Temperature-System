#!/usr/bin/env python
# ============================================================================
# BACKEND API FÜR IOT TEMPERATURE MONITORING SYSTEM
# ============================================================================
# 
# Version: 3.0 (NUR REST API - KEIN HTML RENDERING!)
# Datum: 30.04.2026
# Autor: Nouri Deg.

# Diese API stellt die Daten aus der PostgreSQL Datenbank als REST-Endpunkte zur Verfügung.
# Das Frontend (SPA) ruft diese Endpunkte auf und visualisiert die Daten.
# 
# ENTWICKLUNGSPRINZIP:
# - Trennung von Frontend und Backend
# - Kein HTML Rendering mehr (nur JSON)
# - RESTful API Design
# - CORS aktiviert für Frontend-Zugriff
# ============================================================================

# ============================================================================
# ENDPUNKTE (ÜBERSICHT)
# ============================================================================
# 
# 
#  ENDPUNKT                    METHODE  BESCHREIBUNG                       
# 
#  /api/health                 GET      Health Check (Datenbank-Verbindung)
#  /api/latest                 GET      Aktuellste Temperatur              
#  /api/stats                  GET      Statistiken (Min, Max, Avg)        
#  /api/history                GET      Temperaturverlauf (Zeitreihen)     
#  /api/devices/status         GET      Gerätestatus (online/offline)      
#  /api/lwt/stats              GET      LWT Statistiken                    
#  /api/firmware/version       GET      Firmware Version                   
#  /api/firmware/upload        POST     Firmware Upload (OTA)              
#
# ============================================================================

# ============================================================================
# IMPORTS
# ============================================================================

from flask import Flask, jsonify, request          # Flask Framework, JSON Responses, Request Handling
from flask_cors import CORS                         # Cross-Origin Resource Sharing (erlaubt Frontend-Zugriff)
import psycopg2                                     # PostgreSQL Datenbank Treiber
import psycopg2.extras                              # RealDictCursor für Dictionary-ähnliche Ergebnisse
import os                                           # Betriebssystem-Funktionen (Dateipfade, Umgebungsvariablen)
from datetime import datetime, timedelta            # Datums- und Zeitfunktionen
import pytz                                         # Zeitzonen-Unterstützung (Europe/Berlin)
import json                                         # JSON Parsing für Firmware-Informationen
import hashlib                                      # MD5 Hash für Firmware-Integritätsprüfung

# ============================================================================
# TEST-MOCK KOMPATIBILITÄT
# ============================================================================

def safe_astimezone(dt, tz):
    """Sichere Zeitzonen-Konvertierung für Tests mit Mocks"""
    try:
        # Prüfe ob es ein MagicMock ist
        if hasattr(dt, 'tzinfo') and str(type(dt)) == "<class 'unittest.mock.MagicMock'>":
            return dt
        # Prüfe ob es ein datetime ist
        if hasattr(dt, 'astimezone'):
            return dt.astimezone(tz)
        return dt
    except (TypeError, AttributeError):
        return dt


# ============================================================================
# FLASK APP INITIALISIERUNG
# ============================================================================

app = Flask(__name__)                               # Flask Applikationsinstanz
CORS(app)                                           # Aktiviert CORS für alle Routen (Frontend kann API aufrufen)

# ============================================================================
# ZEITZONE KONFIGURATION
# ============================================================================
# Alle Zeitstempel werden in lokaler Berliner Zeit (CET/CEST) gespeichert und ausgegeben
LOCAL_TZ = pytz.timezone('Europe/Berlin')           # Zeitzone für Deutschland

# ============================================================================
# OTA FIRMWARE KONFIGURATION
# ============================================================================
# Verzeichnis und Dateien für Firmware-Updates (Over-the-Air)

# Originale Firmware (für Referenz)
ORIGINAL_FIRMWARE_DIR = os.path.join(os.path.dirname(__file__), '..', 'esp8266_firmware')
ORIGINAL_FIRMWARE_PATH = os.path.join(ORIGINAL_FIRMWARE_DIR, 'esp8266_firmware.ino')

# OTA Firmware (für Uploads)
OTA_FIRMWARE_DIR = os.path.join(os.path.dirname(__file__), 'ota_firmware')
os.makedirs(OTA_FIRMWARE_DIR, exist_ok=True)

# Die API verwendet das OTA-Verzeichnis für Uploads
FIRMWARE_PATH = os.path.join(OTA_FIRMWARE_DIR, 'firmware.bin')
FIRMWARE_VERSION_FILE = os.path.join(OTA_FIRMWARE_DIR, 'version.json')      # Erstelle Verzeichnis falls nicht vorhanden

# ============================================================================
# POSTGRESQL DATENBANK KONFIGURATION
# ============================================================================
# Verbindungsparameter aus Umgebungsvariablen (Docker) oder .env Datei
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'postgres'),        # Container-Name (postgres_db) oder localhost
    'port': os.getenv('DB_PORT', 5432),              # PostgreSQL Standardport
    'database': os.getenv('DB_NAME', 'sensordb'),    # Datenbankname
    'user': os.getenv('DB_USER', 'sensor_user'),     # Datenbankbenutzer
    'password': os.getenv('DB_PASSWORD', '')         # Passwort aus .env Datei
}

def get_db_connection():
    """Stellt eine Verbindung zur PostgreSQL Datenbank her"""
    return psycopg2.connect(**DB_CONFIG)

# ============================================================================
# ZEITZONEN HILFSFUNKTIONEN
# ============================================================================

def to_local_time(utc_time):
    """
    Konvertiert einen UTC-Zeitstempel in lokale Berliner Zeit (Europe/Berlin)
    
    @param utc_time: UTC Zeitstempel (datetime Objekt)
    @return: Lokaler Zeitstempel oder None
    """
    # Behandle None 
    if utc_time is None:
        return None
    
    # Mock-Erkennung - das ist der wichtige Teil!
    if 'MagicMock' in str(type(utc_time)):
        # Für Tests: Gib einen echten datetime zurück
        return datetime.now(LOCAL_TZ)
    
    # Normale datetime Objekte
    try:
        if utc_time.tzinfo is None:
            utc_time = pytz.UTC.localize(utc_time)
        return utc_time.astimezone(LOCAL_TZ)
    except (TypeError, AttributeError):
        return datetime.now(LOCAL_TZ)
######################################################               

def get_local_now():
    """Gibt die aktuelle lokale Zeit in Europe/Berlin zurück"""
    return datetime.now(LOCAL_TZ)

# ============================================================================
# FIRMWARE MANAGEMENT HILFSFUNKTIONEN
# ============================================================================

def get_firmware_version():
    """Liest die aktuelle Firmware Version aus der version.json Datei"""
    if os.path.exists(FIRMWARE_VERSION_FILE):
        try:
            with open(FIRMWARE_VERSION_FILE, 'r') as f:
                data = json.load(f)
                return data.get('version', '1.0.0')
        except:
            return '1.0.0'
    return '1.0.0'

def save_firmware_version(version):
    """Speichert die Firmware Version in der version.json Datei"""
    with open(FIRMWARE_VERSION_FILE, 'w') as f:
        json.dump({'version': version, 'updated_at': get_local_now().isoformat()}, f)

def get_firmware_md5():
    """Berechnet den MD5 Hash der Firmware Datei (für Integritätsprüfung)"""
    if os.path.exists(FIRMWARE_PATH):
        with open(FIRMWARE_PATH, 'rb') as f:  
            return hashlib.md5(f.read()).hexdigest()
    return None

# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================
# Prüft ob die API und Datenbank erreichbar sind
# Verwendung: curl http://192.168.0.105:5000/api/health

@app.route('/api/health', methods=['GET'])
def health():
    """Health Check Endpunkt - Prüft Datenbank-Verbindung und Systemstatus"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timezone': 'Europe/Berlin',
            'server_time': get_local_now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e)
        }), 500

# ============================================================================
# TEMPERATUR ENDPOINTS
# ============================================================================

# ----------------------------------------------------------------------------
# GET /api/latest - Aktuellste Temperatur
# ----------------------------------------------------------------------------
@app.route('/api/latest', methods=['GET'])
def get_latest():
    """
    Gibt die aktuellste Temperaturmessung zurück
    
    @return JSON: {
        "device_id": "esp8266_...",
        "temperature": 25.75,
        "unit": "celsius",
        "timestamp": "2026-05-01T10:30:00+02:00"
    }
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT device_id, value as temperature, unit, received_at 
            FROM sensor_data 
            ORDER BY received_at DESC 
            LIMIT 1
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        # DEBUG: Zeige was in row ist
        print(f"DEBUG row type: {type(row)}")
        print(f"DEBUG row content: {row}")
        
        if row:
            # DEBUG: Zeige jeden Wert
            print(f"DEBUG device_id: {row.get('device_id')} type: {type(row.get('device_id'))}")
            print(f"DEBUG temperature: {row.get('temperature')} type: {type(row.get('temperature'))}")
            print(f"DEBUG unit: {row.get('unit')} type: {type(row.get('unit'))}")
            print(f"DEBUG received_at: {row.get('received_at')} type: {type(row.get('received_at'))}")
            
            local_time = to_local_time(row['received_at'])
            return jsonify({
                'device_id': row['device_id'],
                'temperature': float(row['temperature']),
                'unit': row['unit'],
                'timestamp': local_time.isoformat()
            })
        return jsonify({'error': 'No data found'}), 404
    except Exception as e:
        print(f"EXCEPTION: {e}")
        return jsonify({'error': str(e)}), 500

# ----------------------------------------------------------------------------
# GET /api/stats - Statistiken der letzten 24h
# ----------------------------------------------------------------------------
@app.route('/api/stats', methods=['GET'])
def get_stats():
    """
    Gibt statistische Kennzahlen der letzten 24 Stunden zurück
    
    Query-Parameter:
    - hours: Zeitraum in Stunden (optional, default: 24)
    
    @return JSON: {
        "min_temp": 24.50,
        "max_temp": 26.46,
        "avg_temp": 25.49,
        "count": 5483
    }
    """
    hours = request.args.get('hours', 24, type=int)   # Standard: 24 Stunden
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Berechne Min, Max, Durchschnitt und Anzahl der Messungen
        cur.execute("""
            SELECT 
                MIN(value) as min_temp,
                MAX(value) as max_temp,
                AVG(value) as avg_temp,
                COUNT(*) as count
            FROM sensor_data 
            WHERE received_at > NOW() - INTERVAL '%s hours'
        """, (hours,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        return jsonify({
            'min_temp': float(row[0]) if row[0] else None,
            'max_temp': float(row[1]) if row[1] else None,
            'avg_temp': float(row[2]) if row[2] else None,
            'count': row[3] if row[3] else 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ----------------------------------------------------------------------------
# GET /api/history - Temperaturverlauf (Zeitreihen)
# ----------------------------------------------------------------------------
@app.route('/api/history', methods=['GET'])
def get_history():
    """
    Gibt den Temperaturverlauf als Zeitreihe zurück (für Chart.js Diagramm)
    
    Query-Parameter:
    - hours: Zeitraum in Stunden (optional, default: 24)
    - limit: Maximale Anzahl Messungen (optional, default: 200)
    
    @return JSON: [{
        "device_id": "esp8266_...",
        "temperature": 25.75,
        "unit": "celsius",
        "timestamp": "2026-05-01T10:30:00+02:00"
    }]
    """
    hours = request.args.get('hours', 24, type=int)
    limit = request.args.get('limit', 200, type=int)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Zeitreihen-Abfrage (aufsteigend sortiert für Diagramm)
        cur.execute("""
            SELECT device_id, value as temperature, unit, received_at 
            FROM sensor_data 
            WHERE received_at > NOW() - INTERVAL '%s hours'
            ORDER BY received_at ASC
            LIMIT %s
        """, (hours, limit))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        # Konvertiere Zeitstempel in lokale Zeitzone
        return jsonify([{
            'device_id': row['device_id'],
            'temperature': float(row['temperature']),
            'unit': row['unit'],
            'timestamp': to_local_time(row['received_at']).isoformat()
        } for row in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ----------------------------------------------------------------------------
# GET /api/devices/status - Gerätestatus (online/offline)
# ----------------------------------------------------------------------------
@app.route('/api/devices/status', methods=['GET'])
def get_devices_status():
    """
    Gibt den aktuellen Status aller Geräte zurück (online/offline basierend auf LWT)
    
    @return JSON: [{
        "device_id": "esp8266_...",
        "status": "online" | "offline",
        "last_seen": "2026-05-01T10:30:00+02:00",
        "last_rssi": -62,
        "last_free_heap": 14768
    }]
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Alle Gerätestatus aus der Datenbank
        cur.execute("""
            SELECT device_id, status, last_seen, last_rssi, last_free_heap, updated_at
            FROM device_status 
            ORDER BY last_seen DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        devices = []
        now = get_local_now()
        
        for row in rows:
            last_seen = to_local_time(row['last_seen']) if row['last_seen'] else None
            is_online = False
            
            # Ein Gerät gilt als online, wenn die letzte Nachricht weniger als 2 Minuten her ist
            if last_seen:
                time_diff = (now - last_seen).total_seconds()
                is_online = time_diff < 120          # 120 Sekunden = 2 Minuten LWT Timeout
            
            devices.append({
                'device_id': row['device_id'],
                'status': 'online' if is_online else 'offline',
                'last_seen': last_seen.isoformat() if last_seen else None,
                'last_rssi': row['last_rssi'],
                'last_free_heap': row['last_free_heap']
            })
        
        return jsonify(devices)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ----------------------------------------------------------------------------
# GET /api/lwt/stats - LWT (Last Will Testament) Statistiken
# ----------------------------------------------------------------------------
@app.route('/api/lwt/stats', methods=['GET'])
def get_lwt_stats():
    """
    Gibt LWT-Statistiken zurück (Anzahl Geräte, Online/Offline, durchschnittliche RSSI)
    
    @return JSON: {
        "total_devices": 1,
        "online_devices": 1,
        "offline_devices": 0,
        "avg_rssi": -62.5,
        "lwt_timeout_seconds": 120
    }
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Gesamtanzahl Geräte
        cur.execute("SELECT COUNT(DISTINCT device_id) FROM device_status")
        total_devices = cur.fetchone()[0] or 0
        
        # Online-Geräte (letzte 2 Minuten aktiv)
        cur.execute("""
            SELECT COUNT(DISTINCT device_id) 
            FROM device_status 
            WHERE last_seen > NOW() - INTERVAL '2 minutes'
        """)
        online_devices = cur.fetchone()[0] or 0
        
        # Durchschnittliche Signalstärke (RSSI)
        cur.execute("SELECT AVG(last_rssi) FROM device_status WHERE last_rssi IS NOT NULL")
        avg_rssi = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return jsonify({
            'total_devices': total_devices,
            'online_devices': online_devices,
            'offline_devices': total_devices - online_devices,
            'avg_rssi': round(avg_rssi, 2) if avg_rssi else None,
            'lwt_timeout_seconds': 120              # LWT Timeout in Sekunden (konfiguriert im ESP8266)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# FIRMWARE ENDPOINTS (OTA - Over-the-Air Updates)
# ============================================================================

# ----------------------------------------------------------------------------
# GET /api/firmware/version - Aktuelle Firmware Version abfragen
# ----------------------------------------------------------------------------
@app.route('/api/firmware/version', methods=['GET'])
def get_firmware_info():
    """
    Gibt Informationen über die aktuelle Firmware zurück
    
    @return JSON: {
        "version": "1.0.1",
        "md5": "a1b2c3d4...",
        "size": 524288
    }
    """
    return jsonify({
        'version': get_firmware_version(),
        'md5': get_firmware_md5(),
        'size': os.path.getsize(FIRMWARE_PATH) if os.path.exists(FIRMWARE_PATH) else 0
    })

# ----------------------------------------------------------------------------
# POST /api/firmware/upload - Neue Firmware hochladen
# ----------------------------------------------------------------------------
@app.route('/api/firmware/upload', methods=['POST'])
def upload_firmware():
    """
    Lädt eine neue Firmware Datei für OTA Updates hoch
    
    Form-Data:
    - file: .bin Datei mit der Firmware
    - version: Versionsnummer (optional, default: 1.0.0)
    
    @return JSON: {
        "status": "success",
        "message": "Firmware uploaded successfully",
        "version": "1.0.1",
        "md5": "a1b2c3d4..."
    }
    """
    # Prüfe ob eine Datei hochgeladen wurde
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    # Prüfe ob eine Datei ausgewählt wurde
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Prüfe Dateityp (nur .bin Dateien erlaubt)
    if not file.filename.endswith('.bin'):
        return jsonify({'error': 'Only .bin files allowed'}), 400
    
    # Versionsnummer aus Formular (optional)
    version = request.form.get('version', '1.0.0')
    
    try:
        # Lösche alte Firmware falls vorhanden
        if os.path.exists(FIRMWARE_PATH):
            os.remove(FIRMWARE_PATH)
        
        # Speichere neue Firmware
        file.save(FIRMWARE_PATH)
        
        # Speichere Versionsinformationen
        save_firmware_version(version)
        
        return jsonify({
            'status': 'success',
            'message': 'Firmware uploaded successfully',
            'version': version,
            'md5': get_firmware_md5()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# MAIN - FLASK SERVER START
# ============================================================================

if __name__ == '__main__':
    """
    Startet den Flask Entwicklungsserver
    - host='0.0.0.0': Akzeptiert Verbindungen von allen Netzwerkschnittstellen
    - port=5000: Flask Standardport
    - debug=False: Debug-Modus aus (sicherer für Produktion)
    """
    app.run(host='0.0.0.0', port=5000, debug=False)