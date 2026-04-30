#!/usr/bin/env python
"""
Backend API für IoT Temperature Monitoring System
NUR REST API - KEIN HTML RENDERING MEHR!

Endpoints:
- GET /api/latest - Aktuellste Temperatur
- GET /api/stats - Statistiken (Min, Max, Avg)
- GET /api/history - Historische Daten
- GET /api/devices/status - Gerätestatus
- GET /api/lwt/stats - LWT Statistiken
- GET /api/health - Health Check
- GET /api/firmware/version - Firmware Version
- POST /api/firmware/upload - Firmware Upload
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
import psycopg2.extras
import os
from datetime import datetime, timedelta
import pytz
import json
import hashlib

app = Flask(__name__)
CORS(app)  # Erlaubt Cross-Origin Requests vom Frontend

# ==========================================
# ZEITZONE KONFIGURATION
# ==========================================
LOCAL_TZ = pytz.timezone('Europe/Berlin')

# ==========================================
# OTA FIRMWARE KONFIGURATION
# ==========================================
FIRMWARE_DIR = './firmware'
FIRMWARE_PATH = os.path.join(FIRMWARE_DIR, 'esp8266_firmware.bin')
FIRMWARE_VERSION_FILE = os.path.join(FIRMWARE_DIR, 'version.json')
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
    return psycopg2.connect(**DB_CONFIG)

def to_local_time(utc_time):
    if utc_time is None:
        return None
    if utc_time.tzinfo is None:
        utc_time = pytz.UTC.localize(utc_time)
    return utc_time.astimezone(LOCAL_TZ)

def get_local_now():
    return datetime.now(LOCAL_TZ)

# ==========================================
# FIRMWARE MANAGEMENT
# ==========================================
def get_firmware_version():
    if os.path.exists(FIRMWARE_VERSION_FILE):
        try:
            with open(FIRMWARE_VERSION_FILE, 'r') as f:
                data = json.load(f)
                return data.get('version', '1.0.0')
        except:
            return '1.0.0'
    return '1.0.0'

def save_firmware_version(version):
    with open(FIRMWARE_VERSION_FILE, 'w') as f:
        json.dump({'version': version, 'updated_at': get_local_now().isoformat()}, f)

def get_firmware_md5():
    if os.path.exists(FIRMWARE_PATH):
        with open(FIRMWARE_PATH, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    return None

# ==========================================
# HEALTH CHECK
# ==========================================
@app.route('/api/health', methods=['GET'])
def health():
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
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

# ==========================================
# TEMPERATUR ENDPOINTS
# ==========================================
@app.route('/api/latest', methods=['GET'])
def get_latest():
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
                'timestamp': local_time.isoformat()
            })
        return jsonify({'error': 'No data found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
##########################################################
@app.route('/api/stats', methods=['GET'])
def get_stats():
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
    
############################################################
@app.route('/api/history', methods=['GET'])
def get_history():
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
            'timestamp': to_local_time(row['received_at']).isoformat()
        } for row in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
########################################################
@app.route('/api/devices/status', methods=['GET'])
def get_devices_status():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
            if last_seen:
                time_diff = (now - last_seen).total_seconds()
                is_online = time_diff < 120
            
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
    
###################################################
@app.route('/api/lwt/stats', methods=['GET'])
def get_lwt_stats():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT device_id) FROM device_status")
        total_devices = cur.fetchone()[0] or 0
        
        cur.execute("""
            SELECT COUNT(DISTINCT device_id) 
            FROM device_status 
            WHERE last_seen > NOW() - INTERVAL '2 minutes'
        """)
        online_devices = cur.fetchone()[0] or 0
        
        cur.execute("SELECT AVG(last_rssi) FROM device_status WHERE last_rssi IS NOT NULL")
        avg_rssi = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return jsonify({
            'total_devices': total_devices,
            'online_devices': online_devices,
            'offline_devices': total_devices - online_devices,
            'avg_rssi': round(avg_rssi, 2) if avg_rssi else None,
            'lwt_timeout_seconds': 120
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================================
# FIRMWARE ENDPOINTS
# ==========================================
@app.route('/api/firmware/version', methods=['GET'])
def get_firmware_info():
    return jsonify({
        'version': get_firmware_version(),
        'md5': get_firmware_md5(),
        'size': os.path.getsize(FIRMWARE_PATH) if os.path.exists(FIRMWARE_PATH) else 0
    })

##################################################
@app.route('/api/firmware/upload', methods=['POST'])
def upload_firmware():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.bin'):
        return jsonify({'error': 'Only .bin files allowed'}), 400
    
    version = request.form.get('version', '1.0.0')
    
    try:
        if os.path.exists(FIRMWARE_PATH):
            os.remove(FIRMWARE_PATH)
        file.save(FIRMWARE_PATH)
        save_firmware_version(version)
        
        return jsonify({
            'status': 'success',
            'message': 'Firmware uploaded successfully',
            'version': version,
            'md5': get_firmware_md5()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================================
# MAIN
# ==========================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)