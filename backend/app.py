#!/usr/bin/env python
"""
Backend API für IoT Temperature Monitoring System
Mit Web Dashboard, LWT Status und OTA Firmware Management

Features:
- REST API für Temperaturdaten
- LWT (Last Will Testament) Status Anzeige
- OTA (Over-the-Air) Firmware Management
- Dashboard mit Chart.js
- PostgreSQL Datenbank Anbindung
"""

from flask import Flask, jsonify, request, render_template, send_file
from flask_cors import CORS
import psycopg2
import psycopg2.extras
import os
from datetime import datetime, timedelta
import pytz
import json
import hashlib

app = Flask(__name__)
CORS(app)

# ==========================================
# ZEITZONE KONFIGURATION (Berlin)
# ==========================================
LOCAL_TZ = pytz.timezone('Europe/Berlin')

# ==========================================
# OTA FIRMWARE KONFIGURATION
# ==========================================
FIRMWARE_DIR = './firmware'
FIRMWARE_PATH = os.path.join(FIRMWARE_DIR, 'esp8266_firmware.bin')
FIRMWARE_VERSION_FILE = os.path.join(FIRMWARE_DIR, 'version.json')

# Stelle sicher dass das Firmware Verzeichnis existiert
os.makedirs(FIRMWARE_DIR, exist_ok=True)

# ==========================================
# PostgreSQL KONFIGURATION
# ==========================================
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'postgres'),
    'port': os.getenv('DB_PORT', 5432),
    'database': os.getenv('DB_NAME', 'sensordb'),
    'user': os.getenv('DB_USER', 'sensor_user'),
    'password': os.getenv('DB_PASSWORD', '')
}

def get_db_connection():
    """Stellt Verbindung zur PostgreSQL Datenbank her"""
    return psycopg2.connect(**DB_CONFIG)

def to_local_time(utc_time):
    """Konvertiert UTC Zeit in lokale Berliner Zeit"""
    if utc_time is None:
        return None
    if utc_time.tzinfo is None:
        utc_time = pytz.UTC.localize(utc_time)
    local_time = utc_time.astimezone(LOCAL_TZ)
    return local_time

def get_local_now():
    """Gibt die aktuelle lokale Zeit in Berlin zurück"""
    return datetime.now(LOCAL_TZ)

# ==========================================
# FIRMWARE VERSION MANAGEMENT
# ==========================================

def get_firmware_version():
    """Liest die aktuelle Firmware Version aus"""
    if os.path.exists(FIRMWARE_VERSION_FILE):
        try:
            with open(FIRMWARE_VERSION_FILE, 'r') as f:
                data = json.load(f)
                return data.get('version', '1.0.0')
        except:
            return '1.0.0'
    return '1.0.0'

def save_firmware_version(version):
    """Speichert die Firmware Version"""
    with open(FIRMWARE_VERSION_FILE, 'w') as f:
        json.dump({'version': version, 'updated_at': get_local_now().isoformat()}, f)

def get_firmware_md5():
    """Berechnet MD5 Hash der Firmware Datei"""
    if os.path.exists(FIRMWARE_PATH):
        with open(FIRMWARE_PATH, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    return None

# ==========================================
# WEB DASHBOARD
# ==========================================

@app.route('/')
def dashboard():
    """Zeigt das HTML Dashboard mit LWT und OTA Status"""
    return render_template('index.html')

# ==========================================
# OTA FIRMWARE ENDPOINTS
# ==========================================

@app.route('/api/firmware/version', methods=['GET'])
def get_version():
    """Gibt die aktuelle Firmware Version zurück"""
    return jsonify({
        'version': get_firmware_version(),
        'md5': get_firmware_md5(),
        'size': os.path.getsize(FIRMWARE_PATH) if os.path.exists(FIRMWARE_PATH) else 0,
        'updated_at': get_local_now().isoformat()
    })

@app.route('/api/firmware/update.bin', methods=['GET'])
def get_firmware():
    """OTA Firmware Download Endpoint für ESP8266"""
    if os.path.exists(FIRMWARE_PATH):
        return send_file(
            FIRMWARE_PATH, 
            as_attachment=True,
            download_name='firmware.bin',
            mimetype='application/octet-stream'
        )
    return jsonify({'error': 'Firmware not found'}), 404

@app.route('/api/firmware/upload', methods=['POST'])
def upload_firmware():
    """OTA Firmware Upload Endpoint (für Entwickler)"""
    # Prüfe ob Datei vorhanden ist
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    # Prüfe Dateiname
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Prüfe Dateityp
    if not file.filename.endswith('.bin'):
        return jsonify({'error': 'Invalid file type. Only .bin files allowed'}), 400
    
    # Optional: Version aus Formular
    version = request.form.get('version', '1.0.0')
    
    try:
        # Lösche alte Firmware falls vorhanden
        if os.path.exists(FIRMWARE_PATH):
            os.remove(FIRMWARE_PATH)
        
        # Speichere neue Firmware
        file.save(FIRMWARE_PATH)
        
        # Speichere Version
        save_firmware_version(version)
        
        # Berechne MD5
        md5 = get_firmware_md5()
        
        return jsonify({
            'status': 'success',
            'message': 'Firmware uploaded successfully',
            'version': version,
            'md5': md5,
            'size': os.path.getsize(FIRMWARE_PATH)
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/api/firmware/delete', methods=['DELETE'])
def delete_firmware():
    """Löscht die Firmware Datei"""
    try:
        if os.path.exists(FIRMWARE_PATH):
            os.remove(FIRMWARE_PATH)
        return jsonify({'status': 'success', 'message': 'Firmware deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================================
# LWT & DEVICE STATUS ENDPOINTS
# ==========================================

@app.route('/api/devices/status', methods=['GET'])
def get_all_devices_status():
    """Gibt den Status aller Geräte zurück (online/offline basierend auf LWT)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Hole alle Geräte aus device_status
        cur.execute("""
            SELECT 
                device_id, 
                status, 
                last_seen, 
                last_rssi, 
                last_free_heap,
                updated_at
            FROM device_status 
            ORDER BY last_seen DESC
        """)
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        # Berechne online/offline basierend auf LWT Timeout
        devices = []
        now = get_local_now()
        
        for row in rows:
            last_seen = to_local_time(row['last_seen']) if row['last_seen'] else None
            is_online = False
            
            if last_seen:
                # Gerät ist online wenn letzte Nachricht < 2 Minuten her ist
                time_diff = (now - last_seen).total_seconds()
                is_online = time_diff < 120  # 2 Minuten Timeout
            
            devices.append({
                'device_id': row['device_id'],
                'status': 'online' if is_online else 'offline',
                'last_seen': last_seen.isoformat() if last_seen else None,
                'last_rssi': row['last_rssi'],
                'last_free_heap': row['last_free_heap'],
                'last_update': to_local_time(row['updated_at']).isoformat() if row['updated_at'] else None
            })
        
        return jsonify(devices)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices/<device_id>/status', methods=['GET'])
def get_device_status(device_id):
    """Gibt den Status eines einzelnen Geräts zurück"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute("""
            SELECT 
                device_id, 
                status, 
                last_seen, 
                last_rssi, 
                last_free_heap,
                updated_at
            FROM device_status 
            WHERE device_id = %s
        """, (device_id,))
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            last_seen = to_local_time(row['last_seen']) if row['last_seen'] else None
            now = get_local_now()
            is_online = False
            
            if last_seen:
                time_diff = (now - last_seen).total_seconds()
                is_online = time_diff < 120
            
            return jsonify({
                'device_id': row['device_id'],
                'status': 'online' if is_online else 'offline',
                'last_seen': last_seen.isoformat() if last_seen else None,
                'last_rssi': row['last_rssi'],
                'last_free_heap': row['last_free_heap'],
                'uptime_seconds': int(time_diff) if last_seen and is_online else None
            })
        
        return jsonify({'error': 'Device not found'}), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================================
# LWT STATISTICS ENDPOINTS
# ==========================================

@app.route('/api/lwt/stats', methods=['GET'])
def get_lwt_stats():
    """Gibt LWT Statistiken zurück (Online-Zeit, Offline-Ereignisse)"""
    hours = request.args.get('hours', 24, type=int)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Gesamtanzahl Geräte
        cur.execute("SELECT COUNT(DISTINCT device_id) FROM device_status")
        total_devices = cur.fetchone()[0] or 0
        
        # Online Geräte (letzte 2 Minuten aktiv)
        cur.execute("""
            SELECT COUNT(DISTINCT device_id) 
            FROM device_status 
            WHERE last_seen > NOW() - INTERVAL '2 minutes'
        """)
        online_devices = cur.fetchone()[0] or 0
        
        # Durchschnittliche RSSI (Signalstärke)
        cur.execute("""
            SELECT AVG(last_rssi) 
            FROM device_status 
            WHERE last_rssi IS NOT NULL
        """)
        avg_rssi = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return jsonify({
            'total_devices': total_devices,
            'online_devices': online_devices,
            'offline_devices': total_devices - online_devices,
            'avg_rssi': round(avg_rssi, 2) if avg_rssi else None,
            'lwt_timeout_seconds': 120,
            'timezone': 'Europe/Berlin'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================================
# TEMPERATUR DATA ENDPOINTS
# ==========================================

@app.route('/api/latest')
def get_latest():
    """Aktuellste Temperatur mit lokaler Berliner Zeit"""
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
        
        if row:
            local_time = to_local_time(row['received_at'])
            return jsonify({
                'device_id': row['device_id'],
                'temperature': float(row['temperature']),
                'unit': row['unit'],
                'timestamp': local_time.strftime('%Y-%m-%d %H:%M:%S'),
                'timezone': 'Europe/Berlin'
            })
        return jsonify({'error': 'Keine Daten'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history')
def get_history():
    """Historische Temperaturdaten mit lokaler Berliner Zeit"""
    hours = request.args.get('hours', 24, type=int)
    limit = request.args.get('limit', 200, type=int)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
        
        return jsonify([{
            'device_id': row['device_id'],
            'temperature': float(row['temperature']),
            'unit': row['unit'],
            'timestamp': to_local_time(row['received_at']).strftime('%Y-%m-%d %H:%M:%S')
        } for row in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices')
def get_devices():
    """Alle registrierten Geräte mit lokaler Berliner Zeit"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT device_id, status, last_seen, updated_at as last_update
            FROM device_status 
            ORDER BY last_seen DESC NULLS LAST
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify([{
            'device_id': row['device_id'],
            'status': row['status'],
            'last_seen': to_local_time(row['last_seen']).strftime('%Y-%m-%d %H:%M:%S') if row['last_seen'] else None,
            'last_update': to_local_time(row['last_update']).strftime('%Y-%m-%d %H:%M:%S') if row['last_update'] else None
        } for row in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Statistiken (Min, Max, Avg) für lokale Zeit"""
    hours = request.args.get('hours', 24, type=int)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
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

# ==========================================
# OTA COMMAND ENDPOINTS (für MQTT)
# ==========================================

@app.route('/api/ota/command/<device_id>', methods=['POST'])
def send_ota_command(device_id):
    """
    Sendet OTA Update Befehl an ein bestimmtes Gerät via MQTT
    Dies wird von der Bridge weitergeleitet
    """
    data = request.get_json()
    command = data.get('command', 'update')
    firmware_url = data.get('firmware_url', None)
    
    # Hier könnte eine MQTT Nachricht an das Gerät gesendet werden
    # Für jetzt nur Logik
    
    return jsonify({
        'status': 'command_received',
        'device_id': device_id,
        'command': command,
        'firmware_url': firmware_url or f'http://{request.host}/api/firmware/update.bin'
    })

# ==========================================
# HEALTH CHECK
# ==========================================

@app.route('/api/health')
def health():
    """Health Check Endpoint mit Zeitzonen Info"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        
        # Prüfe ob Firmware existiert
        firmware_exists = os.path.exists(FIRMWARE_PATH)
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timezone': 'Europe/Berlin',
            'server_time': get_local_now().strftime('%Y-%m-%d %H:%M:%S'),
            'firmware_available': firmware_exists,
            'firmware_version': get_firmware_version() if firmware_exists else None
        })
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

# ==========================================
# MAIN
# ==========================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)